"""Explicit tunnel mode; no credential values enter arguments or status."""
import json
from pathlib import Path


def configuration(work):
    work=Path(work)
    path=work/'tunnel-config.json'
    data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'mode':'quick'}
    if not isinstance(data,dict) or set(data)!={'mode'} or data['mode'] not in ('quick','named'):
        raise ValueError('Tunnel configuration must specify quick or named mode')
    named=data['mode']=='named'
    token=work/'dreamtype-tunnel.token'
    if named and (not token.is_file() or token.stat().st_size==0):
        raise ValueError('Named tunnel credential file is missing or empty')
    metrics='127.0.0.1:19874' if named else '127.0.0.1:19872'
    args=[str(work/'cloudflared.exe'),'tunnel','--no-autoupdate','--protocol','http2','--metrics',metrics]
    args+=['run','--token-file',str(token.resolve())] if named else ['--url','http://127.0.0.1:19870']
    return {'mode':data['mode'],'ready_url':'http://'+metrics+'/ready','arguments':args}


def is_owned(work,exe,args):
    work=Path(work)
    if str(exe).lower()!=str(work/'cloudflared.exe').lower():return False
    if '--url' in args:
        i=args.index('--url')
        return i+1<len(args) and args[i+1]=='http://127.0.0.1:19870'
    if '--token-file' in args:
        i=args.index('--token-file')
        return i+1<len(args) and args[i+1].lower()==str((work/'dreamtype-tunnel.token').resolve()).lower()
    return False
