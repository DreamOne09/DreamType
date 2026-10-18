"""Restore only aligned English punctuation after formatting, without new inference."""
import re
from .latin_patterns import LATIN, LETTER
from .latin_preservation import WORDS, baseline, validate
from .quote_preservation import spans

EQUIVALENTS={'.':'。', ',':'，', ';':'；', ':':'：', '?':'？', '!':'！'}
WORD_EDGE='['+re.escape(LATIN)+'0-9_]'
RUN=re.compile('(?<!'+WORD_EDGE+')'+LETTER+'['+re.escape(LATIN)+r"0-9\u0300-\u036f \t.,;:!?%_/@+()\[\]'’\-]*")


def english_spans(text):
    quoted=spans(text)
    result=[]
    for match in RUN.finditer(text):
        start,end=match.span()
        if any(start<b and end>a for a,b in quoted):
            continue
        # A trailing comma/colon/semicolon before Chinese belongs to the mixed
        # sentence boundary; leave it for Chinese typography. Sentence-ending
        # .?! and punctuation internal to English remain source-controlled.
        literal=match.group().rstrip(' \t,;:')
        if len(WORDS.findall(literal))>=2 and any(c in EQUIVALENTS for c in literal):
            result.append((start,start+len(literal),literal))
    return result


def restore(source, edited):
    revised=baseline(source)
    quoted_before=[edited[a:b] for a,b in spans(edited)]
    cursor=0
    matched=0
    changed=0
    missing=[]
    for _,_,literal in english_spans(revised):
        pattern=[]
        punctuation=[]
        in_space=False
        for char in literal:
            if char.isspace():
                if not in_space:pattern.append(r'\s+')
                in_space=True
                continue
            in_space=False
            if char in EQUIVALENTS:
                pattern.append('(['+re.escape(char+EQUIVALENTS[char])+'])')
                punctuation.append(char)
            else:
                pattern.append(re.escape(char))
        expression=re.compile('(?<!'+WORD_EDGE+')'+''.join(pattern)+'(?!'+WORD_EDGE+')')
        excluded=spans(edited)
        match=next((m for m in expression.finditer(edited,cursor)
                    if not any(m.start()<b and m.end()>a for a,b in excluded)),None)
        if match is None:
            missing.append(literal)
            continue  # No fuzzy guessing, word changes, or deleted punctuation insertion.
        matched+=1
        for group,char in reversed(list(enumerate(punctuation,1))):
            a,b=match.span(group)
            if edited[a:b]!=char:
                edited=edited[:a]+char+edited[b:]
                changed+=1
        cursor=match.end()
    if [edited[a:b] for a,b in spans(edited)]!=quoted_before:
        raise ValueError('Punctuation repair touched quotation')
    validate(source,edited)
    return edited,{'matched_spans':matched,'changed_punctuation':changed,'unmatched_spans':missing}
