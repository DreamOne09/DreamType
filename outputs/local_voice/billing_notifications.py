"""Authenticated Pub/Sub trigger: notifications never grant subscription rights.

Not mounted by the live API. Production requires google-auth, explicit push
identity/audience/subscription configuration and bounded HTTP request bodies.
"""
import base64
import json
import hashlib
import time
from beta_store import StoreError
from billing_store import token_digest
from play_billing import PACKAGE
from billing_identity import google_identity


class PlayNotifications:
    def __init__(self,store,*,audience,email,subscription,verify_identity=google_identity):
        if not audience.startswith('https://') or not email.endswith('.iam.gserviceaccount.com') or not subscription.startswith('projects/'):
            raise ValueError('Explicit Pub/Sub identity configuration required')
        self.store=store;self.audience=audience;self.email=email
        self.subscription=subscription;self.verify_identity=verify_identity

    def receive(self,authorization,body):
        if not isinstance(authorization,str) or not authorization.startswith('Bearer ') or len(authorization)>16384:
            raise StoreError(401,'付款通知驗證失敗')
        try:
            claims=self.verify_identity(authorization[7:],self.audience)
            if claims.get('email')!=self.email or claims.get('email_verified') is not True or claims.get('aud')!=self.audience:
                raise ValueError()
        except Exception:
            raise StoreError(401,'付款通知驗證失敗') from None
        try:
            if not isinstance(body,bytes) or len(body)>32768:raise ValueError()
            envelope=json.loads(body)
            if envelope['subscription']!=self.subscription:raise ValueError()
            message_id=envelope['message']['messageId']
            if not isinstance(message_id,str) or not 1<=len(message_id)<=256:raise ValueError()
            message_hash=hashlib.sha256((self.subscription+'\0'+message_id).encode()).hexdigest()
            event=json.loads(base64.b64decode(envelope['message']['data'],validate=True))
            payload_hash=hashlib.sha256(json.dumps(event,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
            if event['packageName']!=PACKAGE:raise ValueError()
            kinds=[key for key in ('subscriptionNotification','voidedPurchaseNotification','testNotification','oneTimeProductNotification','pendingRefundReviewNotification') if key in event]
            if len(kinds)!=1:raise ValueError()
            kind=kinds[0];notice=event[kind]
            if not isinstance(notice,dict):raise ValueError()
            if kind=='testNotification':return {'status':'test_received'}
            if kind not in ('subscriptionNotification','voidedPurchaseNotification'):
                raise StoreError(503,'此通知類型尚待處理')
            if kind=='voidedPurchaseNotification' and notice.get('productType')!=1:
                raise StoreError(503,'此商品類型尚待處理')
            digest=token_digest(notice['purchaseToken'])
        except StoreError:raise
        except (ValueError,TypeError,KeyError,AttributeError):
            raise StoreError(400,'付款通知格式錯誤') from None
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            from notification_migration import validate_notifications
            validate_notifications(db)
            db.execute('DELETE FROM play_notifications WHERE created<?',(time.time()-90*86400,))
            previous=db.execute('SELECT payload_hash FROM play_notifications WHERE message_hash=?',(message_hash,)).fetchone()
            if previous:
                if previous['payload_hash']!=payload_hash:raise StoreError(409,'通知識別碼內容不一致')
                return {'status':'duplicate'}
            # A late notification for a retired purchase refreshes its successor.
            seen=set()
            while True:
                if digest in seen:raise StoreError(503,'訂閱關聯需修復')
                seen.add(digest)
                edge=db.execute('SELECT new_digest FROM play_replacements WHERE old_digest=?',(digest,)).fetchone()
                if not edge:break
                digest=edge['new_digest']
            row=db.execute('SELECT p.uid,u.enabled FROM play_subscriptions p JOIN users u ON u.id=p.uid WHERE digest=?',(digest,)).fetchone()
            # Never bind an unauthenticated user from notification contents.
            if not row:raise StoreError(503,'訂閱尚未綁定，請稍後重試')
            if not row['enabled']:return {'status':'account_disabled'}
            db.execute('UPDATE play_subscriptions SET needs_refresh=1,revision=revision+1 WHERE digest=?',(digest,))
            db.execute('DELETE FROM billing_retry WHERE digest=?',(digest,))
            db.execute('INSERT INTO play_notifications VALUES(?,?,?,?)',(message_hash,payload_hash,row['uid'],time.time()))
        return {'status':'refresh_queued'}
