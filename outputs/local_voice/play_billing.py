"""Server-side Play subscription verification; never trust phone purchase state.

This adapter does not grant quota. Its caller must
atomically bind the token to an account before granting/acknowledging, and
refresh verified state on RTDN and periodically. Not yet enabled in the API.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
import hashlib
import json
import time
from urllib.parse import quote
import httpx

PACKAGE='tw.localvoice.keyboard'
API='https://androidpublisher.googleapis.com/androidpublisher/v3/applications/'
ALLOWED_STATES={'SUBSCRIPTION_STATE_ACTIVE','SUBSCRIPTION_STATE_IN_GRACE_PERIOD','SUBSCRIPTION_STATE_CANCELED'}
KNOWN_STATES=ALLOWED_STATES|{'SUBSCRIPTION_STATE_PENDING','SUBSCRIPTION_STATE_PAUSED','SUBSCRIPTION_STATE_ON_HOLD','SUBSCRIPTION_STATE_EXPIRED','SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED'}


class BillingVerificationError(ValueError):
    """Safe reason only: never include purchase tokens or provider payloads."""


@dataclass(frozen=True)
class VerifiedSubscription:
    product_id: str
    base_plan_id: str
    state: str
    expires_at: datetime
    entitled: bool
    needs_acknowledgement: bool
    test_purchase: bool
    linked_digest: str | None = None


def evaluate_purchase(data, expected_account_id, catalog, now, allow_test=False):
    """Only call with a response obtained from the authenticated Google API.

    catalog is a server-owned set of (product_id, base_plan_id) pairs.
    expected_account_id comes from the authenticated DreamType account.
    """
    if not isinstance(now,datetime) or now.tzinfo is None:raise BillingVerificationError('invalid_clock')
    if not isinstance(data,dict):raise BillingVerificationError('invalid_response')
    identity=data.get('externalAccountIdentifiers')
    account=identity.get('obfuscatedExternalAccountId') if isinstance(identity,dict) else None
    if not isinstance(account,str) or not isinstance(expected_account_id,str) or not expected_account_id or not hmac.compare_digest(account.encode(),expected_account_id.encode()):
        raise BillingVerificationError('account_mismatch')
    state=data.get('subscriptionState')
    if not isinstance(state,str) or state not in KNOWN_STATES:raise BillingVerificationError('unknown_subscription_state')
    test='testPurchase' in data
    if test and not isinstance(data['testPurchase'],dict):raise BillingVerificationError('invalid_test_purchase')
    if test and not allow_test:raise BillingVerificationError('test_purchase_not_allowed')
    ack=data.get('acknowledgementState')
    if ack not in ('ACKNOWLEDGEMENT_STATE_PENDING','ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED'):
        raise BillingVerificationError('invalid_acknowledgement')
    items=data.get('lineItems')
    # Multiple items require explicit entitlement aggregation, not guessing a tier.
    if not isinstance(items,list) or len(items)!=1 or not isinstance(items[0],dict):
        raise BillingVerificationError('unsupported_line_items')
    item=items[0];offer=item.get('offerDetails')
    product=item.get('productId');plan=offer.get('basePlanId') if isinstance(offer,dict) else None
    if not isinstance(product,str) or not isinstance(plan,str) or (product,plan) not in catalog:
        raise BillingVerificationError('unknown_product')
    try:
        expiry=datetime.fromisoformat(item['expiryTime'].replace('Z','+00:00'))
        if expiry.tzinfo is None:raise ValueError()
    except (KeyError,AttributeError,TypeError,ValueError):
        raise BillingVerificationError('invalid_expiry') from None
    entitled=state in ALLOWED_STATES and expiry>now
    linked=data.get('linkedPurchaseToken')
    if linked is not None and (not isinstance(linked,str) or not 1<=len(linked)<=4096 or any(c.isspace() for c in linked)):
        raise BillingVerificationError('invalid_linked_token')
    return VerifiedSubscription(product,plan,state,expiry.astimezone(timezone.utc),entitled,
                                entitled and ack=='ACKNOWLEDGEMENT_STATE_PENDING',test,
                                hashlib.sha256(linked.encode()).hexdigest() if linked else None)


class PlayVerifier:
    def __init__(self, access_token, catalog, *, transport=None, allow_test=False):
        if not callable(access_token) or type(allow_test) is not bool:
            raise ValueError('Invalid billing verifier configuration')
        self.access_token=access_token
        self.catalog=frozenset(catalog)
        if not self.catalog or any(not isinstance(pair,tuple) or len(pair)!=2 or
                not all(isinstance(value,str) and value and len(value)<=128 and
                        all(c.isascii() and (c.isalnum() or c in '._-') for c in value)
                        for value in pair) for pair in self.catalog):
            raise ValueError('Invalid server billing catalog')
        self.transport=transport
        self.allow_test=allow_test

    def verify(self, purchase_token, expected_account_id, now):
        if not isinstance(purchase_token,str) or not 1<=len(purchase_token)<=4096 or any(c.isspace() for c in purchase_token):
            raise BillingVerificationError('invalid_purchase_token')
        try:
            bearer=self.access_token()
            if not isinstance(bearer,str) or not bearer:raise ValueError()
        except Exception:
            raise BillingVerificationError('billing_credentials_unavailable') from None
        url=API+PACKAGE+'/purchases/subscriptionsv2/tokens/'+quote(purchase_token,safe='')
        deadline=time.monotonic()+15
        try:
            with httpx.Client(timeout=15,follow_redirects=False,trust_env=False,transport=self.transport) as client:
                with client.stream('GET',url,headers={'Authorization':'Bearer '+bearer,'Accept':'application/json'}) as response:
                    if response.status_code!=200:raise BillingVerificationError('purchase_verification_failed')
                    body=bytearray()
                    for chunk in response.iter_bytes():
                        # A per-read socket timeout alone permits an endless drip.
                        # Check elapsed time between reads as well; each blocked
                        # read remains bounded by the HTTP client's timeout.
                        if time.monotonic()>deadline:raise BillingVerificationError('billing_response_deadline')
                        body.extend(chunk)
                        if len(body)>262144:raise BillingVerificationError('response_too_large')
                    if time.monotonic()>deadline:raise BillingVerificationError('billing_response_deadline')
            data=json.loads(body)
        except BillingVerificationError:raise
        except (httpx.HTTPError,ValueError):
            raise BillingVerificationError('billing_provider_unavailable') from None
        return evaluate_purchase(data,expected_account_id,self.catalog,now,self.allow_test)

    def ensure_acknowledged(self,purchase_token,expected_account_id,now):
        """For a durable acknowledgement job AFTER entitlement is persisted.

        Re-query before every attempt. If a prior POST succeeded but its response
        was lost, the next attempt observes acknowledged and skips the POST.
        No automatic retry occurs inside this method; the durable job owns it.
        """
        verified=self.verify(purchase_token,expected_account_id,now)
        if not verified.entitled:raise BillingVerificationError('purchase_not_entitled')
        if not verified.needs_acknowledgement:return verified
        try:
            bearer=self.access_token()
            if not isinstance(bearer,str) or not bearer:raise ValueError()
        except Exception:
            raise BillingVerificationError('billing_credentials_unavailable') from None
        url=API+PACKAGE+'/purchases/subscriptions/'+quote(verified.product_id,safe='')+'/tokens/'+quote(purchase_token,safe='')+':acknowledge'
        try:
            with httpx.Client(timeout=15,follow_redirects=False,trust_env=False,transport=self.transport) as client:
                with client.stream('POST',url,headers={'Authorization':'Bearer '+bearer},json={}) as response:
                    if response.status_code not in (200,204):
                        raise BillingVerificationError('acknowledgement_unconfirmed')
        except httpx.HTTPError:
            raise BillingVerificationError('acknowledgement_unconfirmed') from None
        # A POST success alone does not replace the authoritative purchase state.
        confirmed=self.verify(purchase_token,expected_account_id,now)
        if not confirmed.entitled or confirmed.needs_acknowledgement:
            raise BillingVerificationError('acknowledgement_unconfirmed')
        return confirmed
