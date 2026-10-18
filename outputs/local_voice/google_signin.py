"""Verify a Google login proof; account creation/session issuance live elsewhere."""
from dataclasses import dataclass
import re
import secrets
import time
from billing_identity import certificates, google_identity

CLIENT = re.compile(r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com')
NONCE = re.compile(r'[A-Za-z0-9_-]{43}')

@dataclass(frozen=True)
class GoogleSubject:
    # Never use email/name to find or automatically link an existing account.
    subject: str
    provider: str = 'google'

class GoogleSignIn:
    def __init__(self, client_id, presenters=(), request=certificates):
        if not isinstance(client_id,str) or not CLIENT.fullmatch(client_id):
            raise ValueError('Invalid Google login client')
        if not isinstance(presenters,(tuple,list)) or len(presenters)>10:
            raise ValueError('Invalid Google login presenters')
        if any(not isinstance(p,str) or not CLIENT.fullmatch(p) for p in presenters):
            raise ValueError('Invalid Google login presenters')
        self.client_id=client_id
        self.presenters=frozenset((client_id,*presenters))
        self.request=request

    def verify(self, token, expected_nonce):
        """Nonce must come from a server challenge, consumed atomically by caller.

        This function is intentionally not an HTTP login endpoint: it cannot by
        itself prevent replay, create accounts, link identities or issue sessions.
        """
        try:
            if not isinstance(token,str) or not 1<=len(token)<=16384 or not token.isascii():
                raise ValueError()
            if not isinstance(expected_nonce,str) or not NONCE.fullmatch(expected_nonce):
                raise ValueError()
            claims=google_identity(token,self.client_id,self.request)
            if claims.get('aud')!=self.client_id:raise ValueError()
            if 'azp' in claims and claims['azp'] not in self.presenters:raise ValueError()
            nonce=claims.get('nonce')
            if not isinstance(nonce,str) or not NONCE.fullmatch(nonce):raise ValueError()
            if not secrets.compare_digest(nonce,expected_nonce):raise ValueError()
            # Require a recent interactive proof, not any still-valid hour-old ID token.
            issued,expires=claims.get('iat'),claims.get('exp')
            if type(issued) is not int or type(expires) is not int:raise ValueError()
            now=time.time()
            if not 0<=now-issued<=300 or expires<=now or expires<=issued:raise ValueError()
            subject=claims.get('sub')
            if not isinstance(subject,str) or not 1<=len(subject)<=255:raise ValueError()
            if not subject.isascii() or any(ord(c)<33 or ord(c)>126 for c in subject):raise ValueError()
            return GoogleSubject(subject)
        except Exception:
            # Do not expose the token, raw claims or certificate transport errors.
            raise ValueError('Google sign-in proof invalid or unavailable') from None
