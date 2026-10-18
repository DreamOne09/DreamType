from datetime import datetime,timezone
import unittest
import httpx
from unittest.mock import patch
from play_billing import PlayVerifier,BillingVerificationError

NOW=datetime(2026,10,16,tzinfo=timezone.utc)
CATALOG={('fixture_pro','monthly')}


def purchase():
    return {'subscriptionState':'SUBSCRIPTION_STATE_ACTIVE',
            'externalAccountIdentifiers':{'obfuscatedExternalAccountId':'account-a'},
            'acknowledgementState':'ACKNOWLEDGEMENT_STATE_PENDING',
            'lineItems':[{'productId':'fixture_pro','offerDetails':{'basePlanId':'monthly'},'expiryTime':'2026-11-16T00:00:00Z'}]}


class PlayTests(unittest.TestCase):
    def test_slow_drip_is_rejected_even_below_the_size_limit(self):
        class Drip(httpx.SyncByteStream):
            def __iter__(self):
                yield b'{';yield b' ';yield b'}'
        verifier=PlayVerifier(lambda:'fixture',CATALOG,transport=httpx.MockTransport(lambda request:httpx.Response(200,stream=Drip())))
        with patch('play_billing.time.monotonic',side_effect=[0,1,8,16]),self.assertRaisesRegex(BillingVerificationError,'billing_response_deadline'):
            verifier.verify('fixture','account-a',NOW)

    def test_malformed_test_marker_never_becomes_a_production_purchase(self):
        for marker in (None,False,0,'',[]):
            data=purchase();data['testPurchase']=marker
            with self.subTest(marker=marker),self.assertRaisesRegex(BillingVerificationError,'invalid_test_purchase'):
                self.verifier(data).verify('fixture','account-a',NOW)

    def test_configuration_rejects_truthy_test_mode_and_invalid_catalogs(self):
        for allow in ('false',1,None):
            with self.assertRaises(ValueError):PlayVerifier(lambda:'fixture',CATALOG,allow_test=allow)
        for catalog in (set(),{('fixture','')},{('fixture','has space')},{('fixture','../path')},{'fixture'}):
            with self.assertRaises(ValueError):PlayVerifier(lambda:'fixture',catalog)

    def test_linked_token_is_validated_and_only_digest_leaves_verifier(self):
        import hashlib
        data=purchase();data['linkedPurchaseToken']='old-secret'
        result=self.verifier(data).verify('new-secret','account-a',NOW)
        self.assertEqual(result.linked_digest,hashlib.sha256(b'old-secret').hexdigest())
        self.assertNotIn('old-secret',repr(result))
        for bad in ('',123,'has space','x'*4097):
            data['linkedPurchaseToken']=bad
            with self.assertRaisesRegex(BillingVerificationError,'invalid_linked_token'):
                self.verifier(data).verify('new-secret','account-a',NOW)

    def test_ack_response_lost_recovers_without_duplicate_post(self):
        data=purchase();methods=[]
        def respond(request):
            methods.append(request.method)
            if request.method=='POST':
                self.assertTrue(request.url.path.endswith('/purchases/subscriptions/fixture_pro/tokens/fixture:acknowledge'))
                self.assertEqual(request.content,b'{}')
                data['acknowledgementState']='ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED'
                raise httpx.ReadTimeout('sensitive URL must not escape',request=request)
            return httpx.Response(200,json=data)
        verifier=PlayVerifier(lambda:'fixture-oauth',CATALOG,transport=httpx.MockTransport(respond))
        with self.assertRaisesRegex(BillingVerificationError,'^acknowledgement_unconfirmed$'):
            verifier.ensure_acknowledged('fixture','account-a',NOW)
        result=verifier.ensure_acknowledged('fixture','account-a',NOW)
        self.assertFalse(result.needs_acknowledgement)
        self.assertEqual(methods,['GET','POST','GET'])

    def test_ack_requires_eligible_purchase_and_authoritative_confirmation(self):
        for state in ('SUBSCRIPTION_STATE_PENDING','SUBSCRIPTION_STATE_EXPIRED'):
            data=purchase();data['subscriptionState']=state;methods=[]
            def respond(request):methods.append(request.method);return httpx.Response(200,json=data)
            verifier=PlayVerifier(lambda:'fixture',CATALOG,transport=httpx.MockTransport(respond))
            with self.assertRaisesRegex(BillingVerificationError,'purchase_not_entitled'):
                verifier.ensure_acknowledged('fixture','account-a',NOW)
            self.assertEqual(methods,['GET'])
        data=purchase();methods=[]
        def unchanged(request):
            methods.append(request.method)
            return httpx.Response(204) if request.method=='POST' else httpx.Response(200,json=data)
        verifier=PlayVerifier(lambda:'fixture',CATALOG,transport=httpx.MockTransport(unchanged))
        with self.assertRaisesRegex(BillingVerificationError,'acknowledgement_unconfirmed'):
            verifier.ensure_acknowledged('fixture','account-a',NOW)
        self.assertEqual(methods,['GET','POST','GET'])

    def verifier(self,data,**kwargs):
        return PlayVerifier(lambda:'fixture-oauth',CATALOG,transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data)),**kwargs)

    def test_queries_google_fixed_package_with_server_credentials(self):
        requests=[]
        def respond(request):
            requests.append(request)
            self.assertEqual(request.url.host,'androidpublisher.googleapis.com')
            self.assertIn('/applications/tw.localvoice.keyboard/',request.url.path)
            self.assertTrue(request.url.raw_path.endswith(b'/token%2Fwith%3Freserved'))
            self.assertEqual(request.headers['Authorization'],'Bearer fixture-oauth')
            return httpx.Response(200,json=purchase())
        verified=PlayVerifier(lambda:'fixture-oauth',CATALOG,transport=httpx.MockTransport(respond)).verify('token/with?reserved','account-a',NOW)
        self.assertTrue(verified.entitled);self.assertTrue(verified.needs_acknowledgement)
        self.assertEqual(len(requests),1)

    def test_entitlement_states_and_cancelled_paid_through_period(self):
        for state,entitled in [('ACTIVE',True),('IN_GRACE_PERIOD',True),('CANCELED',True),('EXPIRED',False),('ON_HOLD',False),('PAUSED',False),('PENDING',False),('PENDING_PURCHASE_CANCELED',False)]:
            with self.subTest(state=state):
                data=purchase();data['subscriptionState']='SUBSCRIPTION_STATE_'+state
                result=self.verifier(data).verify('fixture','account-a',NOW)
                self.assertEqual(result.entitled,entitled)
                self.assertEqual(result.needs_acknowledgement,entitled)
        data=purchase();data['lineItems'][0]['expiryTime']='2026-10-16T00:00:00Z'
        self.assertFalse(self.verifier(data).verify('fixture','account-a',NOW).entitled)

    def test_wrong_account_unknown_product_and_malformed_responses_rejected(self):
        variants=[]
        data=purchase();data['externalAccountIdentifiers']={};variants.append(data)
        data=purchase();data['lineItems'][0]['offerDetails']['basePlanId']='unapproved';variants.append(data)
        data=purchase();data['lineItems'][0]['expiryTime']='2026-11-16';variants.append(data)
        data=purchase();data['lineItems']*=2;variants.append(data)
        data=purchase();data['subscriptionState']='NEW_STATE';variants.append(data)
        variants.extend([[],None,{}])
        for data in variants:
            with self.subTest(data=data),self.assertRaises(BillingVerificationError):self.verifier(data).verify('fixture','account-a',NOW)
        with self.assertRaisesRegex(BillingVerificationError,'account_mismatch'):
            self.verifier(purchase()).verify('fixture','account-b',NOW)

    def test_test_purchases_require_explicit_sandbox_configuration(self):
        data=purchase();data['testPurchase']={}
        with self.assertRaisesRegex(BillingVerificationError,'test_purchase_not_allowed'):
            self.verifier(data).verify('fixture','account-a',NOW)
        self.assertTrue(self.verifier(data,allow_test=True).verify('fixture','account-a',NOW).test_purchase)

    def test_provider_failure_redirect_and_oversize_never_grant_or_leak_token(self):
        responses=[httpx.Response(401,text='secret-token'),httpx.Response(302,headers={'Location':'https://evil.example'}),httpx.Response(200,text='invalid-json'),httpx.Response(200,content=b' '*262145)]
        for response in responses:
            requests=[]
            def respond(request):requests.append(request);return response
            with self.subTest(status=response.status_code),self.assertRaises(BillingVerificationError) as caught:
                PlayVerifier(lambda:'fixture',CATALOG,transport=httpx.MockTransport(respond)).verify('secret-token','account-a',NOW)
            self.assertNotIn('secret-token',str(caught.exception))
            self.assertEqual(len(requests),1)


if __name__=='__main__':unittest.main()
