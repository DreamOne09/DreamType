"""Atomic Google account/session creation with expiring, single-use challenges."""
import hashlib
import re
import secrets
import time
from beta_store import StoreError
from google_signin import GoogleSubject
from signin_migration import validate_signin


def digest(value):return hashlib.sha256(value.encode('ascii')).hexdigest()

def invalid():return StoreError(401,'登入請求已失效，請重新開始。','signin_invalid')

class SignInStore:
    def __init__(self,store,verifier):
        self.store,self.verifier=store,verifier
        with store.db() as db:validate_signin(db)

    def challenge(self,purpose):
        if purpose not in ('signin','signup'):raise StoreError(400,'請選擇登入或建立帳號。')
        identity=secrets.token_hex(16);secret=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32)
        expires=time.time()+300
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM login_challenges WHERE expires<=?',(time.time(),))
            if db.execute('SELECT count(*) FROM login_challenges').fetchone()[0]>=1000:
                raise StoreError(429,'目前登入請求較多，請稍後再試。')
            db.execute('INSERT INTO login_challenges VALUES(?,?,?,?,?)',(identity,digest(secret),nonce,purpose,expires))
        return {'challenge':identity,'secret':secret,'nonce':nonce,'expires_at':expires}

    def _read(self,db,identity,secret):
        if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{32}',identity):raise invalid()
        if not isinstance(secret,str) or not re.fullmatch('[A-Za-z0-9_-]{43}',secret):raise invalid()
        row=db.execute('SELECT * FROM login_challenges WHERE id=?',(identity,)).fetchone()
        if not row or row['expires']<=time.time() or not secrets.compare_digest(row['secret'],digest(secret)):raise invalid()
        return row

    def login(self,identity,secret,token):
        with self.store.db() as db:challenge=dict(self._read(db,identity,secret))
        # Network/signature validation stays outside the SQLite write lock.
        try:subject=self.verifier.verify(token,challenge['nonce'])
        except Exception:raise invalid() from None
        if not isinstance(subject,GoogleSubject) or subject.provider!='google':raise invalid()
        session=secrets.token_urlsafe(32);expires=time.time()+7*86400
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current=self._read(db,identity,secret)
            if current['nonce']!=challenge['nonce'] or current['purpose']!=challenge['purpose']:raise invalid()
            row=db.execute('SELECT u.id,u.name,u.enabled FROM login_identities i JOIN users u ON u.id=i.uid WHERE i.provider=? AND i.subject=?',('google',subject.subject)).fetchone()
            if row is None:
                if current['purpose']!='signup':raise invalid()
                uid=secrets.token_hex(16);name='g_'+uid
                # No usable password and no free quota. Existing password login cannot match this sentinel.
                db.execute('INSERT INTO users(id,name,salt,password,allowance) VALUES(?,?,?,?,0)',(uid,name,secrets.token_hex(16),'!google-only'))
                db.execute('INSERT INTO login_identities VALUES(?,?,?)',('google',subject.subject,uid))
                db.execute('INSERT INTO audit(created,action,uid) VALUES(?,?,?)',(time.time(),'google_account_created',uid))
            else:
                if not row['enabled']:raise invalid()
                uid,name=row['id'],row['name']
            db.execute('DELETE FROM login_challenges WHERE id=?',(identity,))
            db.execute('DELETE FROM sessions WHERE expires<=?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(session),uid,expires))
        return {'token':session,'expires_at':expires,'user':{'id':uid,'name':name}}
