"""Explicit Google login configuration; disabled unless privately configured."""
from contextlib import closing
import sqlite3
from google_signin import GoogleSignIn
from signin_store import SignInStore
from account_reauth import GoogleAccountDeletion
from signin_http import signin_router,PATHS
from billing_config import private_json

class SignInRuntime:
    public_paths=PATHS
    def __init__(self,client_id,presenters,allow_signup=False):
        if type(allow_signup) is not bool:raise ValueError('Invalid signup setting')
        self.verifier=GoogleSignIn(client_id,presenters)
        self.allow_signup=allow_signup;self.bound=False
    def validate_storage(self,path):
        from billing_migration import validate_billing_schema
        from notification_migration import validate_notifications
        from signin_migration import validate_signin
        from reauth_migration import validate_reauth
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            for validate in (validate_billing_schema,validate_notifications,validate_signin,validate_reauth):validate(db)
    def bind(self,app,store):
        if self.bound:raise ValueError('Google login already bound')
        self.validate_storage(store.path)
        app.include_router(signin_router(SignInStore(store,self.verifier),GoogleAccountDeletion(store,self.verifier),self.verifier.client_id,allow_signup=self.allow_signup))
        self.bound=True

def load_signin(work):
    path=work/'signin-config.json'
    if not path.exists():return None
    try:
        config=private_json(path,work,16384)
        if not isinstance(config,dict):raise ValueError()
        if set(config)=={'enabled'} and config['enabled'] is False:return None
        if set(config)!={'enabled','client_id','presenters','allow_signup'} or config['enabled'] is not True:raise ValueError()
        from google.oauth2 import id_token  # Required dependency checked before serving.
        return SignInRuntime(config['client_id'],config['presenters'],config['allow_signup'])
    except Exception:
        raise RuntimeError('Invalid Google login configuration or dependency; refusing to enable login.') from None
