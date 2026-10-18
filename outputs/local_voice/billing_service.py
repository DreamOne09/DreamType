"""Verified purchase ownership orchestration, not paid entitlement activation."""
from dataclasses import dataclass
import hashlib
import re
from beta_store import StoreError
from play_billing import VerifiedSubscription
from billing_store import BillingStore


def play_account_id(uid):
    # IDs are server-generated 128-bit random values, never email/usernames.
    if not isinstance(uid,str) or not re.fullmatch('[0-9a-f]{32}',uid):
        raise ValueError('Invalid internal account ID')
    return hashlib.sha256(('DreamType/google_play/account/v1/'+uid).encode()).hexdigest()


@dataclass(frozen=True)
class VerifiedClaim:
    subscription: VerifiedSubscription
    newly_bound: bool


class PlayPurchaseService:
    def __init__(self,store,verifier):
        self.store=store
        self.verifier=verifier
        self.billing=BillingStore(store)

    def account_identifier(self,session_token):
        user=self.store.authenticate(session_token)
        return play_account_id(user['id'])

    def verify_and_claim(self,session_token,purchase_token,now):
        user=self.store.authenticate(session_token)
        # Network I/O occurs outside the SQLite write transaction.
        revision=self.billing.revision(user['id'],purchase_token)
        verified=self.verifier.verify(purchase_token,play_account_id(user['id']),now)
        # Logout, password reset, disable or deletion during the provider call
        # must invalidate the session before persisting ownership.
        current=self.store.authenticate(session_token)
        if current['id']!=user['id']:raise StoreError(401,'登入已失效，請重新登入')
        bound=self.billing.save_verified(user['id'],session_token,purchase_token,verified,revision)
        return VerifiedClaim(verified,bound)
