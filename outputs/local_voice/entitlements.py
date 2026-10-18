"""Server-owned monthly UTC quota policy for verified Play subscriptions."""
from dataclasses import dataclass
from datetime import datetime
import json
import math
from play_billing import ALLOWED_STATES


@dataclass(frozen=True)
class Entitlement:
    plan: str
    seconds: int
    status: str


class SubscriptionPolicy:
    def __init__(self,catalog,*,max_verified_age=3600,allow_test=False):
        # (product, base-plan) -> (public plan name, monthly UTC seconds).
        self.catalog=dict(catalog)
        if not self.catalog or type(allow_test) is not bool or type(max_verified_age) is not int or not 60<=max_verified_age<=86400:
            raise ValueError('Invalid billing policy')
        for pair,value in self.catalog.items():
            if not isinstance(pair,tuple) or len(pair)!=2 or not all(isinstance(s,str) and s for s in pair):raise ValueError('Invalid billing product')
            if not isinstance(value,tuple) or len(value)!=2 or not isinstance(value[0],str) or not value[0] or type(value[1]) is not int or not 1<=value[1]<=6000000:raise ValueError('Invalid billing quota')
        self.max_age=max_verified_age;self.allow_test=allow_test

    def resolve(self,db,uid,now):
        candidates=[];refresh=False
        for row in db.execute('SELECT snapshot,checked_at,needs_refresh FROM play_subscriptions p WHERE uid=? AND NOT EXISTS (SELECT 1 FROM play_replacements r WHERE r.old_digest=p.digest)',(uid,)):
            checked=row['checked_at']
            if row['needs_refresh'] or not isinstance(checked,(int,float)) or not math.isfinite(checked) or not 0<=now-checked<=self.max_age:
                refresh=True;continue
            try:
                data=json.loads(row['snapshot'])
                expiry=datetime.fromisoformat(data['expires_at'])
                if expiry.tzinfo is None:raise ValueError()
                pair=(data['product_id'],data['base_plan_id'])
                if data['test_purchase'] is not False and not self.allow_test:continue
                if data['entitled'] is True and data['state'] in ALLOWED_STATES and expiry.timestamp()>now and pair in self.catalog:
                    candidates.append(self.catalog[pair])
            except (ValueError,TypeError,KeyError,AttributeError):
                refresh=True
        # Replacement chains must be reconciled before multiple tokens grant.
        if len(candidates)>1:return Entitlement('subscription',0,'entitlement_conflict')
        if refresh:return Entitlement('subscription',0,'verification_required')
        if candidates:return Entitlement(*candidates[0],'active')
        return Entitlement('subscription',0,'subscription_required')
