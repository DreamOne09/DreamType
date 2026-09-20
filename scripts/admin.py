"""Create a private local management shortcut; never share work/admin-access.html."""
from pathlib import Path
import html
import sys
import webbrowser
import httpx

root=Path(__file__).resolve().parents[1]
key=root/'work/beta/admin.key'
if not key.exists():raise SystemExit('Start DreamType first; work/beta/admin.key is not ready.')
try:httpx.get('http://127.0.0.1:19870/health',timeout=3).raise_for_status()
except httpx.HTTPError:raise SystemExit('DreamType is not running. Start the service first.')
url='http://127.0.0.1:19870/admin#key='+key.read_text().strip()
target=root/'work/admin-access.html'
target.write_text('<!doctype html><meta charset="utf-8"><title>DreamType 管理入口</title>'
    '<style>body{font:18px/1.7 system-ui;max-width:600px;margin:60px auto;padding:24px}a{display:block;padding:20px;background:#18181b;color:white;border-radius:12px;text-align:center}</style>'
    '<h1>DreamType 管理入口</h1><p>這是主機管理者專用的私人檔案，請勿上傳或分享。</p>'
    '<a href="'+html.escape(url,quote=True)+'">開啟管理介面</a><p>進入後按「連接管理服務」，即可建立試用帳號。</p>',encoding='utf-8')
if '--no-open' not in sys.argv:webbrowser.open(target.as_uri())
print('Private management shortcut saved to work/admin-access.html')
