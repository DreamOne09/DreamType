"""Provider-independent organizer; all transcript state belongs to one call."""
import json
import re

import personalization as preferences
from spoken_corrections import comparison_source, validate_repair_values
from .atomic_literals_pipeline import organize_atomic
from .chinese_order_repair import prepare_order
from .complete_marker_contract import recover
from .single_pass import format_once
from .source_context_pipeline import validate_strict

MAX_SOURCE_CHARACTERS = 12000


def literal_terms(text, vocabulary, taiwan_places):
    terms = []
    if not preferences.NAME_REPAIR.search(text):
        terms.extend(term.strip() for term in re.split(r'[,，、;；\n\r]+', vocabulary)
                     if 2 <= len(term.strip()) <= 40 and term.strip() in text)
        if taiwan_places:
            terms.extend(name for name in preferences.TAIWAN_PLACES.split('、') if name in text)
            terms.extend(match[1] for match in preferences.DESTINATION_NAME.finditer(text))
        terms = [term for term in terms if not re.search(re.escape(term) + r'[\s，,]*' + re.escape(term), text)]
    return terms


async def organize(source, complete, personal_prompt='', vocabulary='', taiwan_places=True):
    """Return text only. Rejections propagate to the gateway's visible raw fallback.

    Completion is injected: this module opens no connections, reads no secrets,
    imports no server and never executes transcript text or generated Python.
    """
    if not isinstance(source, str) or len(source) > MAX_SOURCE_CHARACTERS:
        raise ValueError('Expected a transcript of at most 12000 characters')
    preferences.validate_preferences(personal_prompt, vocabulary, taiwan_places)
    if not source.strip():
        return ''
    source, order_repair = prepare_order(source)
    existing_repairs = []
    source = comparison_source(source, existing_repairs)

    async def adapter(text, protector):
        contract = {}

        def protect(value, prompt, vocab, places):
            masked, markers, prefix = protector(value, prompt, vocab,
                literal_terms=literal_terms(value, vocab, places))
            contract.update(source=masked, markers=list(markers), prefix=prefix)
            return masked, markers, prefix

        async def checked_complete(payload):
            if json.loads(payload['messages'][-1]['content'])['transcript'] != contract['source']:
                raise ValueError('Protected source mismatch')
            body = await complete(payload)
            if not isinstance(body, dict) or not isinstance(body.get('choices'), list) or len(body['choices']) != 1:
                raise ValueError('Invalid formatter response envelope')
            choice = body['choices'][0]
            if not isinstance(choice, dict) or not isinstance(choice.get('message'), dict):
                raise ValueError('Invalid formatter response message')
            content = choice['message'].get('content')
            if choice.get('finish_reason') != 'stop' or not isinstance(content, str) or not content.strip():
                raise ValueError('Incomplete or empty formatter response')
            rendered, _ = recover(contract['source'], content, contract['prefix'], contract['markers'])
            return {'choices': [{**choice, 'message': {**choice['message'], 'content': rendered}}]}

        return await format_once(text, personal_prompt, vocabulary, taiwan_places,
            complete=checked_complete, protect_formatting_literals=protect, validate_edit=validate_strict)

    result, _ = await organize_atomic(source, adapter)
    if order_repair:
        validate_repair_values(source, result, [order_repair['replacement']])
    if existing_repairs:
        validate_repair_values(source, result, existing_repairs)
    return result
