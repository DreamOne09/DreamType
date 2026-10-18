"""Latin literal boundaries; no experiment runner or path mutation."""
import re
import unicodedata
import personalization as preferences

# Latin letters, not a language detector. Keep combining accents attached to
# their base letter and never normalize spelling in the original transcript.
LATIN = ''.join(chr(i) for i in (*range(0x250), *range(0x1E00, 0x1F00))
                if unicodedata.category(chr(i)).startswith('L')
                and unicodedata.name(chr(i), '').startswith('LATIN '))
LETTER = '[' + re.escape(LATIN) + ']'
UNIT = LETTER + r'[\u0300-\u036f]*'
WORD = '(?:' + UNIT + r')+(?:[\x27’\-](?:' + UNIT + ')+)*'
BOUNDARY = re.escape(LATIN) + r'\u0300-\u036f0-9_'
PHRASE = re.compile('(?<![' + BOUNDARY + '])' + WORD + r'(?:[ \t]+' + WORD + ')+(?![' + BOUNDARY + '])')
ORIGINAL = preferences.protect_identifiers

# Experimental and deliberately narrow: do not deduplicate meaningful repeated
# verbs (had had), emphasis, quotations, or explicit repair narratives.
STUTTER = re.compile(r'(^|[。！？!?\n])[ \t]*(?P<run>I(?:[ \t]+I){1,5})'
                     r'(?=[ \t]+(?:think|want|need|will|can)(?=[ \t,.!?。！？]|$))')
AMBIGUOUS = re.compile(r'''[「」『』“”"'‘’`]|(?:他說|她說|原話|原文|引述|寫著|寫道|說道|表示|不對|不是|改成|改為|更正|口誤|說錯)'''
                       r'|\b(?:sorry|correction|quote|said|says|wrote|writes|reported|replied|replies)\b'
                       r'|[:：][ \t]*\r?\n', re.IGNORECASE)


def clean_stutter(text):
    """Candidate input only; never change saved ASR or infer a spoken repair."""
    if AMBIGUOUS.search(text):
        return text
    return STUTTER.sub(lambda m: m.group()[:m.start('run')-m.start()] + 'I', text)


def phrases(text):
    identifiers = [(m.start(), m.end()) for m in preferences.IDENTIFIER.finditer(text)]
    return [m.group() for m in PHRASE.finditer(text)
            if not any(m.start() < right and m.end() > left for left, right in identifiers)]


def candidate(text, *references, literal_terms=()):
    return ORIGINAL(text, *references, literal_terms=tuple(literal_terms) + tuple(phrases(text)))


def stutter_candidate(text, *references, literal_terms=()):
    return candidate(clean_stutter(text), *references, literal_terms=literal_terms)
