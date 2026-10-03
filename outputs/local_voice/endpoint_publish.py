"""Renew public discovery through the existing authenticated GitHub CLI."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import httpx
from endpoint_cli import atomic, prepare
from endpoint_manifest import endpoint
from process_lock import exclusive

REPO='DreamOne09/DreamType'
BRANCH='service-discovery'


def github(method, route, body=None):
    executable=shutil.which('gh')
    if not executable and os.name=='nt':
        candidate=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'GitHub CLI/gh.exe'
        if candidate.is_file():executable=str(candidate)
    if not executable:raise OSError('GitHub CLI unavailable')
    args=[executable,'api','repos/'+REPO+'/'+route,'--method',method]
    if body is not None:args+=['--input','-']
    result=subprocess.run(args,input=None if body is None else json.dumps(body),text=True,
                          capture_output=True,timeout=25,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode:raise OSError('Discovery publication failed')
    return json.loads(result.stdout)


def publish(work, now=None, client=None, api=github):
    now=int(time.time()) if now is None else now
    work=Path(work)
    with exclusive(work/'endpoint-publish.lock'):
        own_client=client is None
        client=httpx.Client(timeout=10,follow_redirects=False,trust_env=False) if own_client else client
        try:
            reply=client.get('http://127.0.0.1:19872/quicktunnel');reply.raise_for_status()
            url=endpoint('https://'+reply.json()['hostname'])
            saved=work/'endpoint-published.json'
            previous=json.loads(saved.read_text()) if saved.exists() else {}
            if previous.get('url')==url and previous.get('expires',0)>now+43200 and previous.get('checked_at',now)<=now:
                return {**previous,'renewed':False}
            health=client.get(url+'/health');health.raise_for_status()
            if health.json().get('status')!='ready':raise ValueError('Public service not ready')
            # sha is a compare-and-swap guard: do not overwrite a concurrent publisher.
            current=api('GET','contents/endpoint.json?ref='+BRANCH)
            if not isinstance(current.get('sha'),str):raise ValueError('Missing discovery revision')
            details=prepare(work,url,now)
            data=(work/'endpoint-public.json').read_bytes()
            result=api('PUT','contents/endpoint.json',{
                'branch':BRANCH,'sha':current['sha'],'message':'Renew signed service address',
                'content':base64.b64encode(data).decode('ascii')})
            if not result.get('commit',{}).get('sha'):raise ValueError('Missing publication confirmation')
            status={k:details[k] for k in ('url','serial','expires')}
            status.update(checked_at=now,commit=result['commit']['sha'])
            atomic(saved,status)
            return {**status,'renewed':True}
        finally:
            if own_client:client.close()
