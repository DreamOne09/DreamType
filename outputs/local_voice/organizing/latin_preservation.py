"""Experimental Latin wording conservation; no deployment or new repair scope."""
import re
import unicodedata
from .latin_patterns import WORD, BOUNDARY, ORIGINAL, phrases, clean_stutter, preferences
from .weekday_repair import repair, validate as validate_repair

WORDS = re.compile('(?<![' + BOUNDARY + '])' + WORD + '(?![' + BOUNDARY + '])')


def tokens(text):
    return [unicodedata.normalize('NFC', m.group()).casefold().replace('’', "'")
            for m in WORDS.finditer(text)]


def baseline(text):
    return clean_stutter(repair(text))


def protect(text, *references, literal_terms=()):
    revised = baseline(text)
    identifiers = [(m.start(), m.end()) for m in preferences.IDENTIFIER.finditer(revised)]
    singles = [m.group() for m in WORDS.finditer(revised)
               if not any(m.start() < end and m.end() > start for start, end in identifiers)]
    return ORIGINAL(revised, *references,
                    literal_terms=tuple(literal_terms) + tuple(phrases(revised)) + tuple(singles))


def validate(source, edited):
    if tokens(baseline(source)) != tokens(edited):
        raise ValueError('Formatting changed protected Latin wording or order')
    validate_repair(source, edited)
