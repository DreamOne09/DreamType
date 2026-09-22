"""Invitation-only beta accounts, sessions and quota ledger (SQLite)."""
import contextlib
import hashlib
import json
import re
import secrets
import sqlite3
import time
import base64
from private_crypto import key_file, encrypt, decrypt
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
        self.payload_key=key_file(path.parent/'payload.key')
        with self.db() as db:
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if version>4:raise RuntimeError('Database is newer than this server; refusing to downgrade.')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL,
              salt TEXT NOT NULL, password TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
              allowance INTEGER NOT NULL DEFAULT 72000, preferences TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, uid TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(uid TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              id TEXT NOT NULL, digest TEXT NOT NULL, month TEXT NOT NULL, seconds INTEGER NOT NULL,
              state TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(uid,id));
            ''')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS results(uid TEXT NOT NULL,id TEXT NOT NULL,payload BLOB NOT NULL,
              expires REAL NOT NULL,PRIMARY KEY(uid,id),FOREIGN KEY(uid,id) REFERENCES jobs(uid,id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,created REAL NOT NULL,action TEXT NOT NULL,uid TEXT);
            CREATE TABLE IF NOT EXISTS reset_codes(uid TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
              digest TEXT NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts(uid TEXT NOT NULL,id TEXT NOT NULL,confirmed INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(uid,id),FOREIGN KEY(uid,id) REFERENCES jobs(uid,id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS pending_audio(uid TEXT NOT NULL,id TEXT NOT NULL,payload BLOB NOT NULL,
              expires REAL NOT NULL,PRIMARY KEY(uid,id),FOREIGN KEY(uid,id) REFERENCES jobs(uid,id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS deletions(uid TEXT PRIMARY KEY,deleted_at REAL NOT NULL);
            PRAGMA user_version=4;
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
            # Password hashing intentionally happens outside the write lock.
            # Recheck under the same transaction that issues the session so a
            # concurrent reset/disable/delete cannot revive an old credential.
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT salt,password,enabled FROM users WHERE id=?',(row['id'],)).fetchone()
            if not current or not current['enabled'] or current['salt']!=row['salt'] or current['password']!=row['password']:
                raise StoreError(401,'帳號或密碼不正確')
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
    def reserve(self,uid,jid,digest,seconds,retry_failed=False):
        month=datetime.now(timezone.utc).strftime('%Y-%m')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM jobs WHERE uid=? AND id=?',(uid,jid)).fetchone()
            if old:
                if old['digest']!=digest:raise StoreError(409,'同一請求代碼不能用於不同录音或設定')
                if retry_failed and old['state']=='failed':db.execute('DELETE FROM jobs WHERE uid=? AND id=?',(uid,jid))
                else:return dict(old),False
            user=db.execute('SELECT * FROM users WHERE id=? AND enabled=1',(uid,)).fetchone()
            if not user:raise StoreError(403,'帳號已停用')
            if db.execute("SELECT 1 FROM jobs WHERE uid=? AND state IN ('queued','running')",(uid,)).fetchone():raise StoreError(429,'上一段還在處理，請稍候')
            if db.execute("SELECT 1 FROM receipts r JOIN jobs j ON j.uid=r.uid AND j.id=r.id WHERE r.uid=? AND r.confirmed=0 AND j.state='done'",(uid,)).fetchone():raise StoreError(409,'請先取回上一筆結果，或等候結果過期後釋放額度')
            used=db.execute("SELECT COALESCE(SUM(seconds),0) FROM jobs WHERE uid=? AND month=? AND state IN ('queued','running','done')",(uid,month)).fetchone()[0]
            if used+seconds>user['allowance']:raise StoreError(402,'本月試用額度已用完')
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(uid,jid,digest,month,seconds,'queued',time.time()))
        return self.job(uid,jid),True
    def job(self,uid,jid):
        with self.db() as db:row=db.execute('SELECT * FROM jobs WHERE uid=? AND id=?',(uid,jid)).fetchone()
        if not row:raise StoreError(404,'找不到這筆請求')
        return dict(row)
    def state(self,uid,jid,state):
        with self.db() as db:
            db.execute('UPDATE jobs SET state=? WHERE uid=? AND id=?',(state,uid,jid))
            if state=='failed':db.execute('DELETE FROM pending_audio WHERE uid=? AND id=?',(uid,jid))
    def save_pending(self,uid,jid,audio,prefs,receipt_required=False):
        expires=time.time()+3600
        payload=encrypt(self.payload_key,json.dumps({'audio':base64.b64encode(audio).decode(),'preferences':prefs}).encode(),f'audio/{uid}/{jid}/{expires}'.encode())
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO pending_audio VALUES(?,?,?,?)',(uid,jid,payload,expires))
            if receipt_required:db.execute('INSERT OR IGNORE INTO receipts(uid,id) VALUES(?,?)',(uid,jid))
    def pending(self):
        with self.db() as db:rows=db.execute("SELECT a.* FROM pending_audio a JOIN jobs j ON j.uid=a.uid AND j.id=a.id WHERE j.state='queued' ORDER BY j.created").fetchall()
        for row in rows:
            uid,jid=row['uid'],row['id']
            try:
                if row['expires']<=time.time():raise ValueError('expired')
                data=json.loads(decrypt(self.payload_key,row['payload'],f"audio/{uid}/{jid}/{row['expires']}".encode()))
                yield uid,jid,base64.b64decode(data['audio']),data['preferences']
            except Exception:self.state(uid,jid,'failed')
    def complete(self,uid,jid,result):
        expires=time.time()+900
        context=f'{uid}/{jid}/{expires}'.encode()
        payload=encrypt(self.payload_key,json.dumps(result,ensure_ascii=False).encode(),context)
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO results VALUES(?,?,?,?)',(uid,jid,payload,expires))
            if not db.execute("UPDATE jobs SET state='done' WHERE uid=? AND id=? AND state='running'",(uid,jid)).rowcount:
                raise ValueError('Job is no longer running')
            db.execute('DELETE FROM pending_audio WHERE uid=? AND id=?',(uid,jid))
    def result(self,uid,jid):
        with self.db() as db:row=db.execute('SELECT payload,expires FROM results WHERE uid=? AND id=?',(uid,jid)).fetchone()
        if not row or row['expires']<=time.time():return None
        try:return json.loads(decrypt(self.payload_key,row['payload'],f"{uid}/{jid}/{row['expires']}".encode()))
        except Exception:
            # An unreadable result cannot be delivered; release the charge and permit explicit retry.
            with self.db() as db:
                db.execute('DELETE FROM results WHERE uid=? AND id=?',(uid,jid))
                db.execute("UPDATE jobs SET state='failed' WHERE uid=? AND id=?",(uid,jid))
            return None
    def cleanup(self):
        with self.db() as db:
            db.execute("UPDATE jobs SET state='failed' WHERE state='done' AND EXISTS (SELECT 1 FROM receipts r JOIN results x ON x.uid=r.uid AND x.id=r.id WHERE r.uid=jobs.uid AND r.id=jobs.id AND r.confirmed=0 AND x.expires<=?)",(time.time(),))
            db.execute('DELETE FROM results WHERE expires<=?',(time.time(),))
            db.execute('DELETE FROM reset_codes WHERE expires<=?',(time.time(),))
            db.execute('DELETE FROM audit WHERE created<?',(time.time()-90*86400,))
    def expect_receipt(self,uid,jid):
        with self.db() as db:db.execute('INSERT OR IGNORE INTO receipts(uid,id) VALUES(?,?)',(uid,jid))
    def receipt(self,uid,jid):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT 1 FROM jobs j JOIN results r ON j.uid=r.uid AND j.id=r.id WHERE j.uid=? AND j.id=? AND j.state='done' AND r.expires>?",(uid,jid,time.time())).fetchone()
            if not row:raise StoreError(409,'結果已過期或尚未完成')
            db.execute('UPDATE receipts SET confirmed=1 WHERE uid=? AND id=?',(uid,jid))
    def audit(self,action,uid=None):
        with self.db() as db:db.execute('INSERT INTO audit(created,action,uid) VALUES(?,?,?)',(time.time(),action,uid))
    def issue_reset(self,uid):
        self.me(uid)
        code=secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO reset_codes VALUES(?,?,?)',(uid,hashlib.sha256(code.encode()).hexdigest(),time.time()+900))
            db.execute('INSERT INTO audit(created,action,uid) VALUES(?,?,?)',(time.time(),'password_reset_issued',uid))
        return code
    def reset_password(self,code,new):
        if not isinstance(code,str) or len(code)>128:raise StoreError(400,'重設代碼無效')
        if not isinstance(new,str) or not 12<=len(new)<=128:raise StoreError(400,'新密碼需為 12–128 個字元')
        salt=secrets.token_hex(16);encoded=password_hash(new,salt)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT uid FROM reset_codes WHERE digest=? AND expires>?',(hashlib.sha256(code.encode()).hexdigest(),time.time())).fetchone()
            if not row:raise StoreError(400,'重設代碼無效或已過期')
            uid=row['uid']
            db.execute('UPDATE users SET salt=?,password=? WHERE id=?',(salt,encoded,uid))
            db.execute('DELETE FROM sessions WHERE uid=?',(uid,))
            db.execute('DELETE FROM reset_codes WHERE uid=?',(uid,))
            db.execute('INSERT INTO audit(created,action,uid) VALUES(?,?,?)',(time.time(),'password_reset_completed',uid))
    def latest(self,uid):
        with self.db() as db:row=db.execute('SELECT id FROM jobs WHERE uid=? ORDER BY created DESC,id DESC LIMIT 1',(uid,)).fetchone()
        return row['id'] if row else None
    def recover(self):
        with self.db() as db:
            db.execute("UPDATE jobs SET state=CASE WHEN EXISTS (SELECT 1 FROM pending_audio a WHERE a.uid=jobs.uid AND a.id=jobs.id AND a.expires>?) THEN 'queued' ELSE 'failed' END WHERE state IN ('queued','running')",(time.time(),))
            db.execute('DELETE FROM pending_audio WHERE expires<=?',(time.time(),))
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
            db.execute('INSERT INTO deletions(uid,deleted_at) VALUES(?,?)',(uid,time.time()))
            db.execute('DELETE FROM users WHERE id=?',(uid,))
    def change_password(self,uid,current,new):
        if not isinstance(new,str) or not 12<=len(new)<=128:raise StoreError(400,'新密碼需為 12–128 個字元')
        with self.db() as db:
            row=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            if not row or not isinstance(current,str) or len(current)>128 or not secrets.compare_digest(password_hash(current,row['salt']),row['password']):raise StoreError(403,'目前密碼不正確')
            salt=secrets.token_hex(16);encoded=password_hash(new,salt)
            db.execute('UPDATE users SET salt=?,password=? WHERE id=?',(salt,encoded,uid))
            db.execute('DELETE FROM sessions WHERE uid=?',(uid,))
