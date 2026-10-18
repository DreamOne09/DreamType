"""Durable purchase encryption, separate from expiring audio/result keys."""
import hashlib
from private_crypto import key_file,encrypt,decrypt


class BillingCipher:
    def __init__(self,beta_directory,*,existing_records=False):
        path=beta_directory/'billing.key'
        if existing_records and not path.is_file():
            raise ValueError('Billing key missing; restore the original key before continuing')
        self._key=key_file(path)

    @staticmethod
    def context(uid,digest):
        return ('DreamType/google_play/purchase/v1/'+uid+'/'+digest).encode('ascii')

    def seal(self,uid,token):
        if not isinstance(token,str) or not 1<=len(token)<=4096 or any(c.isspace() for c in token):
            raise ValueError('Invalid purchase token')
        digest=hashlib.sha256(token.encode()).hexdigest()
        return digest,encrypt(self._key,token.encode(),self.context(uid,digest))

    def open(self,uid,digest,payload):
        token=decrypt(self._key,payload,self.context(uid,digest)).decode('utf-8')
        if hashlib.sha256(token.encode()).hexdigest()!=digest:raise ValueError('Purchase digest mismatch')
        return token
