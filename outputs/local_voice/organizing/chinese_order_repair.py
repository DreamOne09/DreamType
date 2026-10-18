"""Narrow whole-utterance explicit order repair. No general numeric relaxation."""
import re
from spoken_corrections import NUMBER, QUOTED, validate_repair_values
from .source_context_pipeline import validate_strict

# Whole utterance only: no dates, other actions, attribution or conditional context.
ORDER = re.compile(rf'(?P<hesitation>(?:(?:嗯|呃|那個)[，,\s]*)*)'
                   rf'(?P<stutter>我*)?(?P<prefix>想要|我要|要買|幫我買|請給我)'
                   rf'(?P<old>{NUMBER})(?P<unit>杯|份|個|張|盒|瓶|件)'
                   rf'(?P<item>[\u3400-\u9fff]{{1,12}}?)'
                   rf'[，,\s]*(?:啊\s*)?不對[，,\s]*(?:是|改成)?'
                   rf'(?P<new>{NUMBER})(?P=unit)就好(?P<end>[。！？!?]?)')
UNSAFE_ITEM = re.compile(r'不|沒|如果|但是|然後|再|或|還|才|只|之前|之後|除非|要|請|幫|先|[零〇一二兩三四五六七八九十百千萬億點時分年月日]')


def prepare_order(source):
    if QUOTED.search(source): return source, None
    match = ORDER.fullmatch(source)
    if not match or UNSAFE_ITEM.search(match['item']): return source, None
    stutter = match['stutter'] or ''
    prefix = match['prefix']
    if stutter:
        if prefix not in ('想要', '我要'): return source, None
        prefix = '我想要' if prefix == '想要' else '我要'
    replacement = match['new'] + match['unit']
    repaired = prefix + replacement + match['item'] + '就好' + match['end']
    return repaired, dict(original=source, prepared=repaired, replacement=replacement,
                          rule='whole_utterance_matching_unit_explicit_budui')
