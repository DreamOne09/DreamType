from pathlib import Path
import time,re,html
import httpx,qrcode
work=Path(__file__).resolve().parents[1]/'work'
for attempt in range(90):
 try:
  log=(work/'logs/tunnel.err.log').read_text(encoding='utf-8')
  url=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',log).group(0)
  if 'Registered tunnel connection' in log:
   response=httpx.get(url+'/health',timeout=5)
   if response.status_code==200 and response.json().get('status')=='ready':break
 except (OSError,AttributeError,ValueError,httpx.HTTPError):pass
 time.sleep(2)
else:raise SystemExit('Tunnel not ready. Check work/logs/tunnel.err.log')
key=(work/'local-voice.key').read_text().strip()
qrcode.make(url+'/#key='+key).save(work/'pairing.png')
(work/'pairing.html').write_text('<!doctype html><meta charset="utf-8"><title>DreamType 私人連線</title><style>body{font:18px/1.7 system-ui;max-width:640px;margin:40px auto;padding:24px;color:#18181b;background:#fafafa}input{width:100%;padding:12px;box-sizing:border-box}img{width:280px}</style><h1>連接 DreamType</h1><p>在 App 填入以下資料，或用手機相機掃描 QR 碼後按配對。這份資料請保留自用。</p><label>電腦網址<input readonly value="'+html.escape(url,quote=True)+'"></label><label>私人金鑰<input readonly type="password" value="'+html.escape(key,quote=True)+'"></label><p>點選金鑰欄位可全選複製。</p><img src="pairing.png" alt="私人配對 QR 碼"><p>電腦需保持開啟。通道重開後，請使用新網址重新配對。</p>',encoding='utf-8')
print('Pairing ready: work/pairing.html (private; do not upload)')
