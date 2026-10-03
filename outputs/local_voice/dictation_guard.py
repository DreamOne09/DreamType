"""Conservative edit budget: suspicious rewrites fall back to the transcript.
This checks textual drift, not semantic equivalence; it is deliberately fail-closed.
"""
import re
from bisect import bisect_right
import unicodedata
from difflib import SequenceMatcher
from numeric_literals import validate_numeric_literals, canonical_numeric_text
from spoken_corrections import comparison_source, validate_repair_values


# Literal guard, not a semantic parser. Conservative rejection intentionally
# keeps the original when a synonym or unsupported self-correction touches these.
LOGIC = re.compile('除非|否則|如果|只有|只要|必須|不得|不能|不要|不會|不是|沒有|尚未|未經|之前|之後|最後|然後|先|再|不|沒|勿|僅|只|若|才')
ENGLISH_LOGIC = re.compile(r"(?<![a-z])(?:not|no|never|unless|only|until|before|after|must|cannot|(?:can|won|don|doesn|didn|isn|aren|wasn|weren|shouldn|wouldn|couldn|hasn|haven|hadn|mustn|needn)['’]t)(?![a-z])", re.IGNORECASE)
REPEATED_LOGIC = re.compile('(' + LOGIC.pattern + r')\1+')


def _logic_changed(text, start, end, english_spans=()):
    return any((start < term.end() and end > term.start()) or
               (start == end and term.start() < start < term.end())
               for term in LOGIC.finditer(text)) or any(
               (start < right and end > left) or (start == end and left < start < right)
               for left,right in english_spans)


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold()
                   if not c.isspace() and unicodedata.category(c)[0] not in 'PS')


def english_logic_spans(text):
    # Find word boundaries before punctuation/space removal; "notebook" is not "not".
    text=unicodedata.normalize('NFKC',canonical_numeric_text(text)).casefold()
    offsets=[0]
    for char in text:
        offsets.append(offsets[-1]+int(not char.isspace() and unicodedata.category(char)[0] not in 'PS'))
    collapsed_ends=[];removed=[0]
    for match in REPEATED_LOGIC.finditer(normalized(text)):
        collapsed_ends.append(match.end())
        removed.append(removed[-1]+len(match.group(0))-len(match.group(1)))
    def offset(index):
        value=offsets[index]
        return value-removed[bisect_right(collapsed_ends,value)]
    return [(offset(term.start()),offset(term.end())) for term in ENGLISH_LOGIC.finditer(text)]


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
    source_logic, edited_logic = english_logic_spans(source), english_logic_spans(edited)
    alignment = SequenceMatcher(None, before, after, autojunk=False)
    for tag, begin, end, new_begin, new_end in alignment.get_opcodes():
        if tag != 'equal' and (_logic_changed(before, begin, end, source_logic) or _logic_changed(after, new_begin, new_end, edited_logic)):
            raise ValueError('Formatting changed a negation or condition')
    matches = sum(block.size for block in alignment.get_matching_blocks())
    # Punctuation/layout are free; substantive additions and omissions are bounded.
    if len(after)-matches > max(1, int(len(before)*0.15)) or len(before)-matches > max(1, int(len(before)*0.30)):
        raise ValueError('Formatting exceeded faithful editing budget')
