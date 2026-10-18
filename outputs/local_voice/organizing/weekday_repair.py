"""Narrow research baseline for explicit weekday repairs; not deployed."""
import re
from .latin_patterns import candidate, clean_stutter, preferences
from dictation_guard import validate_edit

DAY = r'Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday'
DAYS = re.compile(r'\b(?:' + DAY + r')\b', re.I)
REPAIR = re.compile(r'\b(?P<prep>on|for)[ \t]+(?:' + DAY + r')[ \t]*,[ \t]*'
                    r'(?:sorry|I mean)[ \t]*,[ \t]*(?P<day>' + DAY + r')\b', re.I)
UNSAFE = re.compile(r'''[「」『』“”"'‘’`]|\b(?:not|never|unless|if|only|said|says|wrote|writes|replied|reported|quote)\b|原文|原話|引述|寫道|回覆''', re.I)


def repair(text):
    matches = list(REPAIR.finditer(text))
    if len(matches) != 1 or UNSAFE.search(text):
        return text
    match = matches[0]
    return text[:match.start()] + match['prep'] + ' ' + match['day'] + text[match.end():]


def protect(text, *references, literal_terms=()):
    return candidate(clean_stutter(repair(text)), *references, literal_terms=literal_terms)


def validate(source, edited):
    revised = repair(source)
    if revised != source and [d.casefold() for d in DAYS.findall(revised)] != [d.casefold() for d in DAYS.findall(edited)]:
        raise ValueError('Formatting changed the explicit weekday replacement')
    validate_edit(revised, edited)
