"""Private opt-in configuration; never infer paid products or cloud credentials."""
import json
import threading
import time
from types import SimpleNamespace
import httpx
from billing_runtime import BillingRuntime
from entitlements import SubscriptionPolicy
from play_billing import PlayVerifier

TOKEN_URI='https://oauth2.googleapis.com/token'
SCOPE='https://www.googleapis.com/auth/androidpublisher'


class PlayCredentials:
    def __init__(self,info,transport=None):
        from google.oauth2.service_account import Credentials
        if info.get('type')!='service_account' or info.get('token_uri')!=TOKEN_URI or info.get('universe_domain','googleapis.com')!='googleapis.com':
            raise ValueError('Unsupported Play service credentials')
        self.credentials=Credentials.from_service_account_info(info,scopes=[SCOPE])
        self.transport=transport;self.lock=threading.Lock()

    def request(self,url,method='POST',body=None,headers=None,**kwargs):
        if url!=TOKEN_URI or method!='POST':raise ValueError('Invalid OAuth endpoint')
        deadline=time.monotonic()+10
        with httpx.Client(timeout=10,trust_env=False,follow_redirects=False,transport=self.transport) as client:
            with client.stream('POST',TOKEN_URI,content=body,headers=headers) as response:
                # Retry belongs to the durable worker, not nested OAuth retries.
                if response.status_code!=200:raise ValueError('OAuth unavailable')
                data=bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic()>deadline:raise ValueError('OAuth response deadline')
                    data.extend(chunk)
                    if len(data)>65536:raise ValueError('OAuth response too large')
                if time.monotonic()>deadline:raise ValueError('OAuth response deadline')
                return SimpleNamespace(status=200,data=bytes(data),headers=dict(response.headers))

    def __call__(self):
        try:
            if not self.lock.acquire(timeout=10):raise ValueError('Credentials busy')
            try:
                if not self.credentials.valid:self.credentials.refresh(self.request)
                token=self.credentials.token
                if not isinstance(token,str) or not token:raise ValueError()
                return token
            finally:self.lock.release()
        except Exception:raise ValueError('Play credentials unavailable') from None


def private_json(path,work,limit):
    resolved=path.resolve()
    if resolved.parent!=work.resolve():raise ValueError('Private file must remain in work directory')
    with resolved.open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('Private configuration too large')
    return json.loads(data)


def load_billing(work):
    path=work/'billing-config.json'
    if not path.exists():return None
    try:
        config=private_json(path,work,32768)
        if not isinstance(config,dict):raise ValueError()
        if set(config)=={'enabled'} and config['enabled'] is False:return None
        if set(config)!={'enabled','products','push','credentials_file'} or config['enabled'] is not True:raise ValueError()
        products=config['products']
        if not isinstance(products,list) or not 1<=len(products)<=20:raise ValueError()
        catalog={}
        for item in products:
            if set(item)!={'product_id','base_plan_id','plan','monthly_seconds'}:raise ValueError()
            pair=(item['product_id'],item['base_plan_id'])
            if pair in catalog:raise ValueError()
            catalog[pair]=(item['plan'],item['monthly_seconds'])
        policy=SubscriptionPolicy(catalog)
        push=config['push']
        if set(push)!={'audience','email','subscription'}:raise ValueError()
        if push['audience']!='https://dreamtype.dreamone.li/billing/google/play/notifications':raise ValueError()
        filename=config['credentials_file']
        # Credentials must be a private file directly inside the work directory.
        if not isinstance(filename,str) or not filename or '/' in filename or '\\' in filename or ':' in filename or filename in ('.','..'):raise ValueError()
        credential_path=(work/filename).resolve()
        credentials=PlayCredentials(private_json(credential_path,work,65536))
        return BillingRuntime(policy,PlayVerifier(credentials,set(catalog)),**push)
    except Exception:
        raise RuntimeError('Invalid billing configuration or missing billing dependency; refusing to start paid mode.') from None
