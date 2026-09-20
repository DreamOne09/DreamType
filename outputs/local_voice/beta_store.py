"""Invitation-only beta accounts, sessions and quota ledger (SQLite)."""
import contextlib
import hashlib
import json
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone

class StoreError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)

def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()

class Store:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL,
              salt TEXT NOT NULL, password TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
              allowance INTEGER NOT NULL DEFAULT 72000, preferences TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, uid TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(uid TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              id TEXT NOT NULL, digest TEXT NOT NULL, month TEXT NOT NULL, seconds INTEGER NOT NULL,
              state TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(uid,id));
            ''')
    @contextlib.contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:yield db
        finally:db.close()
    def create(self,name,password,minutes=1200):
        if not isinstance(name,str):raise StoreError(400,'帳號格式錯誤')
        name=name.strip().lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,39}',name):raise StoreError(400,'帳號需為 3–40 個英數字或 . _ -')
        if not isinstance(password,str) or not 12<=len(password)<=128:raise StoreError(400,'密碼需為 12–128 個字元')
        if type(minutes) is not int or not 0<=minutes<=100000:raise StoreError(400,'額度格式錯誤')
        uid=secrets.token_hex(16);salt=secrets.token_hex(16);encoded=password_hash(password,salt)
        try:
            with self.db() as db:db.execute('INSERT INTO users(id,name,salt,password,allowance) VALUES(?,?,?,?,?)',(uid,name,salt,encoded,minutes*60))
        except sqlite3.IntegrityError:raise StoreError(409,'帳號已存在')
        return uid
    def login(self,name,password):
        if not isinstance(name,str) or not isinstance(password,str) or len(name)>40 or len(password)>128:raise StoreError(401,'帳號或密碼不正確')
        with self.db() as db:row=db.execute('SELECT * FROM users WHERE name=?',(name.strip().lower(),)).fetchone()
        salt=row['salt'] if row else '00'*16
        encoded=password_hash(password,salt)
        if not row or not row['enabled'] or not secrets.compare_digest(encoded,row['password']):raise StoreError(401,'帳號或密碼不正確')
        token=secrets.token_urlsafe(32);expires=time.time()+7*86400
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],expires))
        return {'token':token,'expires_at':expires,'user':{'id':row['id'],'name':row['name']}}
    def authenticate(self,token):
        with self.db() as db:
            row=db.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.uid WHERE s.token=? AND s.expires>? AND u.enabled=1',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if not row:raise StoreError(401,'登入已失效，請重新登入')
        return dict(row)
    def logout(self,token):
        with self.db() as db:db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
    def me(self,uid):
        month=datetime.now(timezone.utc).strftime('%Y-%m')
        with self.db() as db:
            row=db.execute('SELECT id,name,enabled,allowance,preferences FROM users WHERE id=?',(uid,)).fetchone()
            if not row:raise StoreError(404,'帳號不存在')
            used=db.execute("SELECT COALESCE(SUM(seconds),0) FROM jobs WHERE uid=? AND month=? AND state='done'",(uid,month)).fetchone()[0]
            reserved=db.execute("SELECT COALESCE(SUM(seconds),0) FROM jobs WHERE uid=? AND month=? AND state IN ('queued','running')",(uid,month)).fetchone()[0]
        return {'id':uid,'name':row['name'],'enabled':bool(row['enabled']),'plan':'closed-beta','month_utc':month,'limit_seconds':row['allowance'],'used_seconds':used,'reserved_seconds':reserved,'remaining_seconds':max(0,row['allowance']-used-reserved),'preferences':json.loads(row['preferences'])}
    def preferences(self,uid,values):
        with self.db() as db:db.execute('UPDATE users SET preferences=? WHERE id=?',(json.dumps(values,ensure_ascii=False),uid))
    def reserve(self,uid,jid,digest,seconds):
        month=datetime.now(timezone.utc).strftime('%Y-%m')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM jobs WHERE uid=? AND id=?',(uid,jid)).fetchone()
            if old:
                if old['digest']!=digest:raise StoreError(409,'同一請求代碼不能用於不同录音或設定')
                return dict(old),False
            user=db.execute('SELECT * FROM users WHERE id=? AND enabled=1',(uid,)).fetchone()
            if not user:raise StoreError(403,'帳號已停用')
            if db.execute("SELECT 1 FROM jobs WHERE uid=? AND state IN ('queued','running')",(uid,)).fetchone():raise StoreError(429,'上一段還在處理，請稍候')
            used=db.execute("SELECT COALESCE(SUM(seconds),0) FROM jobs WHERE uid=? AND month=? AND state IN ('queued','running','done')",(uid,month)).fetchone()[0]
            if used+seconds>user['allowance']:raise StoreError(402,'本月試用額度已用完')
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(uid,jid,digest,month,seconds,'queued',time.time()))
        return self.job(uid,jid),True
    def job(self,uid,jid):
        with self.db() as db:row=db.execute('SELECT * FROM jobs WHERE uid=? AND id=?',(uid,jid)).fetchone()
        if not row:raise StoreError(404,'找不到這筆請求')
        return dict(row)
    def state(self,uid,jid,state):
        with self.db() as db:db.execute('UPDATE jobs SET state=? WHERE uid=? AND id=?',(state,uid,jid))
    def recover(self):
        with self.db() as db:
            db.execute("UPDATE jobs SET state='failed' WHERE state IN ('queued','running')")
            db.execute('DELETE FROM jobs WHERE created<?',(time.time()-93*86400,))
    def users(self):
        with self.db() as db:ids=[r[0] for r in db.execute('SELECT id FROM users ORDER BY name')]
        return [{k:v for k,v in self.me(uid).items() if k!='preferences'} for uid in ids]
    def update(self,uid,enabled,minutes):
        if type(enabled) is not bool or type(minutes) is not int or not 0<=minutes<=100000:raise StoreError(400,'帳號設定格式錯誤')
        with self.db() as db:
            if not db.execute('UPDATE users SET enabled=?,allowance=? WHERE id=?',(enabled,minutes*60,uid)).rowcount:raise StoreError(404,'帳號不存在')
            if not enabled:db.execute('DELETE FROM sessions WHERE uid=?',(uid,))
    def delete(self,uid,password):
        with self.db() as db:
            row=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            if not row or not isinstance(password,str) or len(password)>128 or not secrets.compare_digest(password_hash(password,row['salt']),row['password']):raise StoreError(403,'密碼不正確')
            db.execute('DELETE FROM users WHERE id=?',(uid,))
    def change_password(self,uid,current,new):
        if not isinstance(new,str) or not 12<=len(new)<=128:raise StoreError(400,'新密碼需為 12–128 個字元')
        with self.db() as db:
            row=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            if not row or not isinstance(current,str) or len(current)>128 or not secrets.compare_digest(password_hash(current,row['salt']),row['password']):raise StoreError(403,'目前密碼不正確')
            salt=secrets.token_hex(16);encoded=password_hash(new,salt)
            db.execute('UPDATE users SET salt=?,password=? WHERE id=?',(salt,encoded,uid))
            db.execute('DELETE FROM sessions WHERE uid=?',(uid,))
