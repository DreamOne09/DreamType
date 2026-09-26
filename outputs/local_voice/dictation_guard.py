"""Conservative edit budget: suspicious rewrites fall back to the transcript.
This checks textual drift, not semantic equivalence; it is deliberately fail-closed.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from numeric_literals import validate_numeric_literals, canonical_numeric_text
from spoken_corrections import comparison_source, validate_repair_values


# Literal guard, not a semantic parser. Conservative rejection intentionally
# keeps the original when a synonym or unsupported self-correction touches these.
LOGIC = re.compile('除非|否則|如果|只有|只要|必須|不得|不能|不要|不會|不是|沒有|尚未|未經|之前|之後|不|沒|勿|僅|只|若|才')
REPEATED_LOGIC = re.compile('(' + LOGIC.pattern + r')\1+')


def _logic_changed(text, start, end):
    return any((start < term.end() and end > term.start()) or
               (start == end and term.start() < start < term.end())
               for term in LOGIC.finditer(text))


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold()
                   if not c.isspace() and unicodedata.category(c)[0] not in 'PS')


def validate_edit(source, edited):
    try:
        _validate_edit(source, edited)
    except ValueError:
        replacements = []
        repaired = comparison_source(source, replacements)
        if repaired == source:
            raise
        validate_repair_values(repaired, edited, replacements)
        _validate_edit(repaired, edited)


def _validate_edit(source, edited):
    validate_numeric_literals(source, edited)
    before, after = (REPEATED_LOGIC.sub(r'\1', normalized(canonical_numeric_text(value))) for value in (source, edited))
    if not before:
        if after: raise ValueError('Formatting invented content')
        return
    # Removing a request cue can turn a dictated request into an answer even
    # when most of a long sentence is copied unchanged.
    for cue in ('請', '幫我', '麻煩', '協助我', '告訴我', '回答我',
                'please', 'canyou', 'couldyou', 'wouldyou'):
        if cue in before and cue not in after:
            raise ValueError('Formatting removed a dictated request cue')
    alignment = SequenceMatcher(None, before, after, autojunk=False)
    for tag, begin, end, new_begin, new_end in alignment.get_opcodes():
        if tag != 'equal' and (_logic_changed(before, begin, end) or _logic_changed(after, new_begin, new_end)):
            raise ValueError('Formatting changed a negation or condition')
    matches = sum(block.size for block in alignment.get_matching_blocks())
    # Punctuation/layout are free; substantive additions and omissions are bounded.
    if len(after)-matches > max(1, int(len(before)*0.15)) or len(before)-matches > max(1, int(len(before)*0.30)):
        raise ValueError('Formatting exceeded faithful editing budget')
