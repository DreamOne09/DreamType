"""Public account workspace assets; no keys or user data are embedded."""
from pathlib import Path
from fastapi.responses import FileResponse

def install_web_pages(app):
    root = Path(__file__).parent
    headers = {
        'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
        'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        'Permissions-Policy': 'microphone=(self), camera=(), geolocation=()',
    }
    @app.get('/')
    @app.get('/dictate')
    async def workspace():
        return FileResponse(root / 'dictate.html', headers=headers)

    @app.get('/web/dictate.mjs')
    async def controller():
        return FileResponse(root / 'dictate.mjs', media_type='text/javascript', headers=headers)

    @app.get('/web/web_dictation.mjs')
    async def session():
        return FileResponse(root / 'web_dictation.mjs', media_type='text/javascript', headers=headers)
