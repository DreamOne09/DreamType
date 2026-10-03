import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
import endpoint_publish as publication


class PublicationTests(unittest.TestCase):
    def test_renewal_is_public_only_and_cached_until_due(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory);calls=[]
            def respond(request):
                return httpx.Response(200,json={'hostname':'fixture.trycloudflare.com'} if request.url.path=='/quicktunnel' else {'status':'ready'})
            def prepare(work,url,now):
                (work/'endpoint-public.json').write_text('{"payload":"public","signature":"signed"}')
                return dict(url=url,serial=now,expires=now+86400)
            def api(method,path,body=None):
                calls.append((method,path,body))
                return {'sha':'existing'} if method=='GET' else {'commit':{'sha':'new'}}
            with httpx.Client(transport=httpx.MockTransport(respond)) as client,patch.object(publication,'prepare',prepare):
                result=publication.publish(work,1800000000,client,api)
                self.assertTrue(result['renewed'])
                self.assertFalse(publication.publish(work,1800000001,client,api)['renewed'])
            self.assertEqual(len(calls),2)
            body=calls[1][2]
            self.assertEqual(body['sha'],'existing')
            self.assertEqual(body['branch'],'service-discovery')
            self.assertEqual(json.loads(base64.b64decode(body['content'])),{'payload':'public','signature':'signed'})

    def test_failed_publication_never_records_success(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory)
            def respond(request):return httpx.Response(200,json={'hostname':'fixture.trycloudflare.com'} if request.url.path=='/quicktunnel' else {'status':'ready'})
            def api(*args):raise OSError('offline')
            with httpx.Client(transport=httpx.MockTransport(respond)) as client,self.assertRaises(OSError):
                publication.publish(work,1800000000,client,api)
            self.assertFalse((work/'endpoint-published.json').exists())

    def test_compare_and_swap_failure_preserves_previous_success(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory)
            previous={'url':'https://old.trycloudflare.com','serial':10,'expires':1800000000}
            saved=work/'endpoint-published.json'
            saved.write_text(json.dumps(previous))
            def respond(request):
                return httpx.Response(200,json={'hostname':'fixture.trycloudflare.com'} if request.url.path=='/quicktunnel' else {'status':'ready'})
            def prepare(work,url,now):
                (work/'endpoint-public.json').write_text('{"payload":"new","signature":"signed"}')
                return dict(url=url,serial=now,expires=now+86400)
            def api(method,path,body=None):
                if method=='GET':return {'sha':'old-revision'}
                raise OSError('revision conflict')
            with httpx.Client(transport=httpx.MockTransport(respond)) as client,patch.object(publication,'prepare',prepare),self.assertRaises(OSError):
                publication.publish(work,1800000000,client,api)
            self.assertEqual(json.loads(saved.read_text()),previous)

    def test_unready_service_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            def respond(request):return httpx.Response(200,json={'hostname':'fixture.trycloudflare.com'} if request.url.path=='/quicktunnel' else {'status':'loading'})
            with httpx.Client(transport=httpx.MockTransport(respond)) as client,self.assertRaises(ValueError):
                publication.publish(Path(directory),1800000000,client,lambda *args: self.fail('Unexpected publication'))


if __name__=='__main__':unittest.main()
