"""Google reauthentication for deleting the currently authenticated account."""
import re
import secrets
import time
from beta_store import StoreError
from google_signin import GoogleSubject
from signin_store import digest
from reauth_migration import validate_reauth


def invalid():return StoreError(401,'刪除確認已失效，請重新登入並確認身分。','reauth_invalid')

class GoogleAccountDeletion:
    def __init__(self,store,verifier):
        self.store,self.verifier=store,verifier
        with store.db() as db:validate_reauth(db)

    def _account(self,db,session):
        if not isinstance(session,str) or not re.fullmatch('[A-Za-z0-9_-]{43}',session):raise invalid()
        row=db.execute("SELECT u.id,i.subject FROM sessions s JOIN users u ON u.id=s.uid JOIN login_identities i ON i.uid=u.id AND i.provider='google' WHERE s.token=? AND s.expires>? AND u.enabled=1",(digest(session),time.time())).fetchone()
        if not row:raise invalid()
        return row

    def challenge(self,session):
        identity=secrets.token_hex(16);secret=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32)
        expires=time.time()+300
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE');account=self._account(db,session)
            db.execute('DELETE FROM deletion_challenges WHERE expires<=? OR uid=?',(time.time(),account['id']))
            db.execute('INSERT INTO deletion_challenges VALUES(?,?,?,?,?,?)',(identity,account['id'],digest(session),digest(secret),nonce,expires))
        return {'challenge':identity,'secret':secret,'nonce':nonce,'expires_at':expires}

    def _read(self,db,session,identity,secret):
        account=self._account(db,session)
        if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{32}',identity):raise invalid()
        if not isinstance(secret,str) or not re.fullmatch('[A-Za-z0-9_-]{43}',secret):raise invalid()
        row=db.execute('SELECT * FROM deletion_challenges WHERE id=? AND uid=? AND session=?',(identity,account['id'],digest(session))).fetchone()
        if not row or row['expires']<=time.time() or not secrets.compare_digest(row['secret'],digest(secret)):raise invalid()
        return dict(row),dict(account)

    def delete(self,session,identity,secret,token):
        with self.store.db() as db:challenge,account=self._read(db,session,identity,secret)
        try:subject=self.verifier.verify(token,challenge['nonce'])
        except Exception:raise invalid() from None
        if not isinstance(subject,GoogleSubject) or subject.provider!='google' or subject.subject!=account['subject']:raise invalid()
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current,owner=self._read(db,session,identity,secret)
            if current['nonce']!=challenge['nonce'] or owner!=account:raise invalid()
            # Session, Google identity and enabled state were rechecked under this
            # write lock. Cascades revoke every session and remove personal data.
            db.execute('DELETE FROM users WHERE id=?',(owner['id'],))
            db.execute('DELETE FROM audit WHERE uid=?',(owner['id'],))
            db.execute('INSERT INTO deletions(uid,deleted_at) VALUES(?,?)',(owner['id'],time.time()))
        # Account deletion does not cancel a Google Play subscription.
        return {'deleted':True,'subscription_cancelled':False}
