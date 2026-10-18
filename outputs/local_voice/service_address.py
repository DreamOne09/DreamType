"""Trusted service address configuration; never infer it from Host or old logs."""
import json
import time
from pathlib import Path
from endpoint_manifest import endpoint

def fixed_address(work):
    work=Path(work)
    settings_path=work/'endpoint-discovery.json'
    settings=json.loads(settings_path.read_text(encoding='utf-8-sig')) if settings_path.exists() else {}
    if not isinstance(settings,dict):raise ValueError('Invalid discovery settings')
    if 'public_url' in settings:
        url=endpoint(settings['public_url'])
        if not url.endswith('.dreamone.li'):raise ValueError('Fixed address must use dreamone.li')
        return url
    tunnel_path=work/'tunnel-config.json'
    if tunnel_path.exists():
        tunnel=json.loads(tunnel_path.read_text(encoding='utf-8-sig'))
        if not isinstance(tunnel,dict):raise ValueError('Invalid tunnel settings')
        if tunnel.get('mode')=='named':raise ValueError('Named tunnel needs a fixed public_url')
    return None

def admin_address(work,now=None):
    now=time.time() if now is None else now
    try:
        fixed=fixed_address(work)
        if fixed:return {'service_url':fixed,'service_url_source':'configured_fixed','service_url_message':'固定服務網址；請確認主機在線後提供給使用者。'}
        path=Path(work)/'endpoint-published.json'
        if not path.exists():return {'service_url':'','service_url_source':'unavailable','service_url_message':'尚無已發布的服務網址，請先完成通道與網址發布。'}
        saved=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(saved,dict):raise ValueError('Invalid publication')
        url=endpoint(saved.get('url'))
        expires=saved.get('expires');checked=saved.get('checked_at')
        if (not url.endswith('.trycloudflare.com') or type(expires) not in (int,float)
                or type(checked) not in (int,float) or not checked<=now<expires or expires-checked>86400):
            return {'service_url':'','service_url_source':'expired','service_url_message':'網址發布紀錄已過期或不符合目前通道設定，請重新發布後再邀請。'}
        return {'service_url':url,'service_url_source':'published_temporary','service_url_message':'臨時網址可能改變；這是尚未到期的發布紀錄，不代表服務目前在線。'}
    except (OSError,ValueError,TypeError):
        return {'service_url':'','service_url_source':'invalid','service_url_message':'服務網址設定無效。請修正設定，不要使用歷史通道網址。'}
