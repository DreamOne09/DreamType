"""One bounded billing pass. Caller schedules it; credentials stay server-side."""
from datetime import datetime,timezone
import time
import math
from billing_crypto import BillingCipher
from billing_service import play_account_id
from billing_store import BillingStore
from beta_store import StoreError
from process_lock import exclusive,LockBusy


def run(store,verifier,*,clock=time.time,limit=10,budget_seconds=120,monotonic=time.monotonic):
    if store.entitlement_policy is None:raise ValueError('Billing worker requires an explicit entitlement policy')
    if type(limit) is not int or not 1<=limit<=20:raise ValueError('Invalid billing batch limit')
    if type(budget_seconds) not in (int,float) or not math.isfinite(budget_seconds) or not 1<=budget_seconds<=300:
        raise ValueError('Invalid billing time budget')
    try:
        with exclusive(store.path.parent/'billing-worker.lock'):
            return _run(store,verifier,clock,limit,monotonic,monotonic()+budget_seconds)
    except LockBusy:return {'skipped':'billing_worker_running'}


def _run(store,verifier,clock,limit,monotonic,deadline):
    now=clock();billing=BillingStore(store)
    with store.db() as db:
        rows=[dict(row) for row in db.execute('''SELECT p.digest,p.uid,p.revision,p.token,
          COALESCE(r.attempts,0) AS attempts FROM play_subscriptions p JOIN users u ON u.id=p.uid
          LEFT JOIN billing_retry r ON r.digest=p.digest AND r.revision=p.revision
          WHERE u.enabled=1 AND (p.ack_pending=1 OR p.needs_refresh=1 OR p.checked_at<=?)
          AND NOT EXISTS (SELECT 1 FROM play_replacements replacement WHERE replacement.old_digest=p.digest)
          AND COALESCE(r.next_attempt,0)<=? ORDER BY p.checked_at LIMIT ?''',
          (now-store.entitlement_policy.max_age/2,now,limit))]
    result={'checked':0,'confirmed':0,'retry':0,'superseded':0}
    for row in rows:
        # Stop admitting new work; an in-flight provider request retains its own
        # timeout. This is not a hard deadline for the whole pass.
        if monotonic()>=deadline:break
        revision=row['revision'];digest=row['digest'];uid=row['uid']
        try:
            cipher=BillingCipher(store.path.parent,existing_records=True)
            token=cipher.open(uid,digest,row['token'])
            value=verifier.verify(token,play_account_id(uid),datetime.fromtimestamp(clock(),timezone.utc))
            billing.refresh_verified(uid,token,value,revision);revision+=1
            result['checked']+=1
            if value.needs_acknowledgement:
                def check_current():billing.require_acknowledgement(uid,digest,revision)
                check_current()
                confirmed=verifier.ensure_acknowledged(token,play_account_id(uid),datetime.fromtimestamp(clock(),timezone.utc),before_post=check_current)
                billing.refresh_verified(uid,token,confirmed,revision);revision+=1
                result['confirmed']+=1
            with store.db() as db:db.execute('DELETE FROM billing_retry WHERE digest=? AND revision<=?',(digest,revision))
        except StoreError as error:
            if error.status in (401,403,409):result['superseded']+=1;continue
            _retry(store,row,revision,clock());result['retry']+=1
        except Exception:
            # Never log provider payloads, request URLs, credentials or tokens.
            _retry(store,row,revision,clock());result['retry']+=1
    return result


def _retry(store,row,revision,now):
    attempts=row['attempts']+1;delay=min(3600,30*2**min(attempts-1,7))
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        current=db.execute('SELECT revision FROM play_subscriptions WHERE digest=?',(row['digest'],)).fetchone()
        if current and current['revision']==revision:
            db.execute('INSERT INTO billing_retry VALUES(?,?,?,?) ON CONFLICT(digest) DO UPDATE SET revision=excluded.revision,attempts=excluded.attempts,next_attempt=excluded.next_attempt',
                       (row['digest'],revision,attempts,now+delay))
