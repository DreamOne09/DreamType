"""Atomic verified snapshot and pending acknowledgement; no quota granting."""
from dataclasses import asdict
import hashlib
import json
import time
from beta_store import StoreError
from billing_crypto import BillingCipher


def token_digest(token):
    if not isinstance(token,str) or not 1<=len(token)<=4096 or any(c.isspace() for c in token):
        raise StoreError(400,'購買憑證格式錯誤')
    return hashlib.sha256(token.encode()).hexdigest()


class BillingStore:
    def __init__(self,store):self.store=store

    def revision(self,uid,token):
        digest=token_digest(token)
        with self.store.db() as db:
            row=db.execute('SELECT uid,revision FROM play_subscriptions WHERE digest=?',(digest,)).fetchone()
            if row and row['uid']!=uid:raise StoreError(409,'這筆購買已綁定其他帳號')
            return row['revision'] if row else 0

    def save_verified(self,uid,session,token,verified,expected_revision):
        if not isinstance(session,str) or not session:raise StoreError(401,'登入已失效，請重新登入')
        return self._save(uid,session,token,verified,expected_revision)

    def refresh_verified(self,uid,token,verified,expected_revision):
        """Internal worker only; may refresh an existing owned record, never bind."""
        return self._save(uid,None,token,verified,expected_revision)

    def _save(self,uid,session,token,verified,expected_revision):
        digest=token_digest(token);snapshot=asdict(verified)
        snapshot['expires_at']=verified.expires_at.isoformat()
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            retired=db.execute('SELECT uid FROM play_replacements WHERE old_digest=?',(digest,)).fetchone()
            if session is not None and not db.execute('SELECT 1 FROM sessions s JOIN users u ON s.uid=u.id WHERE s.token=? AND s.uid=? AND s.expires>? AND u.enabled=1',
                              (hashlib.sha256(session.encode()).hexdigest(),uid,time.time())).fetchone():
                raise StoreError(401,'登入已失效，請重新登入')
            claim=db.execute("SELECT uid FROM purchase_claims WHERE provider='google_play' AND digest=?",(digest,)).fetchone()
            if claim and claim['uid']!=uid:raise StoreError(409,'這筆購買已綁定其他帳號')
            if retired and retired['uid']!=uid:raise StoreError(409,'這筆購買已綁定其他帳號')
            old=db.execute('SELECT uid,revision FROM play_subscriptions WHERE digest=?',(digest,)).fetchone()
            if session is None and (not old or not claim or not db.execute('SELECT 1 FROM users WHERE id=? AND enabled=1',(uid,)).fetchone()):
                raise StoreError(403,'訂閱帳號不可用')
            if old and old['uid']!=uid:raise StoreError(409,'這筆購買已綁定其他帳號')
            if (old['revision'] if old else 0)!=expected_revision:
                raise StoreError(409,'訂閱狀態已更新，請重新查驗','purchase_revision_changed')
            linked=verified.linked_digest
            completed=verified.state not in ('SUBSCRIPTION_STATE_PENDING','SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED')
            # A signed-in re-verification may fill in an older missing edge.
            # Background tasks must still stop before acknowledging retired tokens.
            if retired and (session is None or not linked or not completed):
                raise StoreError(409,'購買憑證已被新訂閱取代','purchase_replaced')
            if linked:
                if len(linked)!=64 or any(c not in '0123456789abcdef' for c in linked) or linked==digest:
                    raise StoreError(409,'訂閱關聯無效')
                previous=db.execute("SELECT uid FROM purchase_claims WHERE provider='google_play' AND digest=?",(linked,)).fetchone()
                if previous and previous['uid']!=uid:raise StoreError(409,'原訂閱已綁定其他帳號')
                edge=db.execute('SELECT new_digest,uid FROM play_replacements WHERE old_digest=?',(linked,)).fetchone()
                if edge and (edge['new_digest']!=digest or edge['uid']!=uid):raise StoreError(409,'原訂閱已被其他購買取代')
                incoming=db.execute('SELECT old_digest FROM play_replacements WHERE new_digest=?',(digest,)).fetchone()
                if incoming and incoming['old_digest']!=linked:raise StoreError(409,'訂閱關聯已變更')
                if db.execute('''WITH RECURSIVE successors(digest) AS (
                    SELECT ? UNION SELECT r.new_digest FROM play_replacements r
                    JOIN successors s ON r.old_digest=s.digest
                    ) SELECT 1 FROM successors WHERE digest=?''',(digest,linked)).fetchone():
                    raise StoreError(409,'訂閱關聯形成循環')
                # Pending checkout must not retire a still usable subscription.
                # Completed states also retire it when first observed after expiry.
                if completed:
                    if not previous:db.execute('INSERT INTO purchase_claims VALUES(?,?,?,?)',('google_play',linked,uid,time.time()))
                    db.execute('INSERT OR IGNORE INTO play_replacements VALUES(?,?,?)',(linked,digest,uid))
                    if not edge:db.execute('UPDATE play_subscriptions SET ack_pending=0,revision=revision+1 WHERE digest=?',(linked,))
                    db.execute('DELETE FROM billing_retry WHERE digest=?',(linked,))
            if retired:
                # Preserve the authoritative successor. No token snapshot, quota,
                # acknowledgement or revision of this retired purchase is revived.
                return False
            # Serialize key creation with the same database write lock.
            existing=db.execute('SELECT 1 FROM play_subscriptions LIMIT 1').fetchone() is not None
            cipher=BillingCipher(self.store.path.parent,existing_records=existing)
            _,sealed=cipher.seal(uid,token)
            if not claim:db.execute('INSERT INTO purchase_claims VALUES(?,?,?,?)',('google_play',digest,uid,time.time()))
            db.execute('INSERT INTO play_subscriptions VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(digest) DO UPDATE SET token=excluded.token,snapshot=excluded.snapshot,revision=excluded.revision,ack_pending=excluded.ack_pending,needs_refresh=0,checked_at=excluded.checked_at',
                       (digest,uid,sealed,json.dumps(snapshot),expected_revision+1,int(verified.needs_acknowledgement),0,time.time()))
        return claim is None

    def pending(self):
        """No token plaintext in the task inventory; a worker must reverify."""
        with self.store.db() as db:
            return [dict(row) for row in db.execute('SELECT p.digest,p.uid,p.revision,p.needs_refresh FROM play_subscriptions p JOIN users u ON p.uid=u.id WHERE p.ack_pending=1 AND u.enabled=1 AND NOT EXISTS (SELECT 1 FROM play_replacements r WHERE r.old_digest=p.digest) ORDER BY p.checked_at LIMIT 100')]
