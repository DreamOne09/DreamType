"""Bind the faithful organizer to the existing local provider and translation path."""
import httpx
from .engine import organize


def bind_formatter(previous_formatter, key, complete=None):
    async def local_complete(payload):
        async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
            response = await client.post('http://127.0.0.1:19871/v1/chat/completions',
                headers={'Authorization': 'Bearer ' + key}, json=payload)
            response.raise_for_status()
            return response.json()

    provider = complete if complete is not None else local_complete

    async def format_text(text, personal_prompt='', vocabulary='', taiwan_places=True,
                          mode='organize', target_language='en', source_language='zh'):
        if mode == 'translate':
            return await previous_formatter(text, personal_prompt, vocabulary, taiwan_places,
                                            mode, target_language, source_language)
        if mode != 'organize':
            raise ValueError('Unknown formatting mode')
        return await organize(text, provider, personal_prompt, vocabulary, taiwan_places)

    return format_text
