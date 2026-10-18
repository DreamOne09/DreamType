from datetime import datetime,timezone
from pathlib import Path
import tempfile
import unittest
import httpx
from billing_test_fixture import prepared_store
from beta_store import Store,StoreError
from billing_service import PlayPurchaseService,play_account_id
from play_billing import PlayVerifier,BillingVerificationError
from entitlements import SubscriptionPolicy


class ServiceTests(unittest.TestCase):
    def test_provider_linked_tokens_reconcile_out_of_order_with_no_duplicate_quota(self):
        with tempfile.TemporaryDirectory() as d:
            store=prepared_store(Path(d)/'accounts.sqlite3',SubscriptionPolicy({('fixture','monthly'):('pro',120)}))
            uid=store.create('alice','fixture-password');session=store.login('alice','fixture-password')['token']
            methods=[];links={'last':'middle','middle':'first'}
            def respond(request):
                methods.append(request.method)
                token=request.url.path.rsplit('/',1)[-1]
                data={'externalAccountIdentifiers':{'obfuscatedExternalAccountId':play_account_id(uid)},
                      'subscriptionState':'SUBSCRIPTION_STATE_ACTIVE',
                      'acknowledgementState':'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED',
                      'lineItems':[{'productId':'fixture','offerDetails':{'basePlanId':'monthly'},'expiryTime':'2027-01-01T00:00:00Z'}]}
                if token in links:data['linkedPurchaseToken']=links[token]
                return httpx.Response(200,json=data)
            service=PlayPurchaseService(store,PlayVerifier(lambda:'fixture-oauth',{('fixture','monthly')},transport=httpx.MockTransport(respond)))
            now=datetime(2026,10,16,tzinfo=timezone.utc)
            for token in ('first','last','middle','middle'):service.verify_and_claim(session,token,now)
            self.assertEqual(store.me(uid)['limit_seconds'],120)
            self.assertEqual(methods,['GET']*4)
            self.assertEqual(service.billing.pending(),[])
            with store.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM play_replacements').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM play_subscriptions').fetchone()[0],2)
            # Authentication still precedes applying an older missing edge.
            store.logout(session)
            with self.assertRaises(StoreError):service.verify_and_claim(session,'middle',now)
            self.assertEqual(methods,['GET']*4)

    def test_authenticated_provider_verification_precedes_idempotent_binding(self):
        with tempfile.TemporaryDirectory() as d:
            store=prepared_store(Path(d)/'accounts.sqlite3');uid=store.create('alice','fixture-password')
            session=store.login('alice','fixture-password')['token']
            expected=play_account_id(uid);mode=['valid']
            def respond(request):
                if mode[0]=='logout':store.logout(session)
                return httpx.Response(200,json={
                    'externalAccountIdentifiers':{'obfuscatedExternalAccountId':expected if mode[0]!='wrong' else 'someone-else'},
                    'subscriptionState':'SUBSCRIPTION_STATE_ACTIVE',
                    'acknowledgementState':'ACKNOWLEDGEMENT_STATE_PENDING',
                    'lineItems':[{'productId':'fixture','offerDetails':{'basePlanId':'monthly'},'expiryTime':'2027-01-01T00:00:00Z'}]})
            service=PlayPurchaseService(store,PlayVerifier(lambda:'fixture-oauth',{('fixture','monthly')},transport=httpx.MockTransport(respond)))
            now=datetime(2026,10,16,tzinfo=timezone.utc)
            self.assertEqual(service.account_identifier(session),expected)
            mode[0]='wrong'
            with self.assertRaises(BillingVerificationError):service.verify_and_claim(session,'bad-purchase',now)
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM purchase_claims').fetchone()[0],0)
            mode[0]='valid'
            self.assertTrue(service.verify_and_claim(session,'good-purchase',now).newly_bound)
            self.assertFalse(service.verify_and_claim(session,'good-purchase',now).newly_bound)
            self.assertEqual(store.me(uid)['plan'],'closed-beta')
            mode[0]='logout'
            with self.assertRaises(StoreError):service.verify_and_claim(session,'later-purchase',now)
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM purchase_claims').fetchone()[0],1)

    def test_revoked_session_is_checked_inside_claim_transaction(self):
        with tempfile.TemporaryDirectory() as d:
            store=prepared_store(Path(d)/'accounts.sqlite3');uid=store.create('alice','fixture-password')
            session=store.login('alice','fixture-password')['token'];store.logout(session)
            from billing_store import BillingStore
            from play_billing import VerifiedSubscription
            value=VerifiedSubscription('fixture','monthly','SUBSCRIPTION_STATE_ACTIVE',datetime(2027,1,1,tzinfo=timezone.utc),True,True,False)
            with self.assertRaises(StoreError):BillingStore(store).save_verified(uid,session,'fixture',value,0)
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM purchase_claims').fetchone()[0],0)


if __name__=='__main__':unittest.main()
