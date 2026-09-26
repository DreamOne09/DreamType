"""Conservative numeric-literal preservation for same-language dictation edits.
No arithmetic, unit conversion or date guessing; Chinese quantities require a unit.
"""
import re
import unicodedata
from number_words import integer_amount

_NUMBER = re.compile(
    r'(?P<sign1>[-+負正])?\s*(?P<prefix>百分之|千分之)?\s*'
    r'(?P<sign2>[-+負正])?\s*(?P<value>[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?|[零〇一二兩三四五六七八九十百千萬億]+(?:[點点][零〇一二兩三四五六七八九]+)?)'
    r'\s*(?P<suffix>[%‰萬億])?')
_LIST = re.compile(r'(?m)^[ \t]*([0-9]{1,2})(?:[.)][ \t]+|、[ \t]*|[.)](?=[^0-9\s]))(?=\S)')
_SPOKEN_LIST = re.compile(r'(^|[，,。；;！？!?\n])[ \t]*第([一二三四五六七八九])[、，,：:]')


def strip_list_labels(text):
    labels = list(_LIST.finditer(text))
    if len(labels) >= 2 and [int(m[1]) for m in labels] == list(range(1, len(labels)+1)):
        text = _LIST.sub('', text)
    spoken = list(_SPOKEN_LIST.finditer(text))
    if len(spoken) >= 2 and ''.join(m[2] for m in spoken) == '一二三四五六七八九'[:len(spoken)]:
        text = _SPOKEN_LIST.sub(lambda m:m[1], text)
    return text


_UNIT = re.compile(r'(?:公斤|公升|公尺|公分|公里|毫升|個|人|次|件|份|元|杯|張|盒|瓶)')


def _scan(text):
    text = strip_list_labels(unicodedata.normalize('NFKC', text).replace('−', '-'))
    values = []
    def replace(match):
        value = match['value']
        if not value[0].isascii() and not (match['prefix'] or match['suffix'] or _UNIT.match(text, match.end())):
            return match[0]
        sign = ((match['sign1'] or '') + (match['sign2'] or '')).replace('負', '-').replace('正', '+')
        unit = {'百分之':'%', '千分之':'‰', None:''}[match['prefix']] + (match['suffix'] or '')
        literal = sign + integer_amount(value) + unit
        values.append(literal)
        return literal
    normalized_text = _NUMBER.sub(replace, text)
    return normalized_text, values


def numeric_literals(text):
    return _scan(text)[1]


def canonical_numeric_text(text):
    return _scan(text)[0]


def validate_numeric_literals(source, edited):
    if numeric_literals(source) != numeric_literals(edited):
        raise ValueError('Formatting changed a numeric literal')
