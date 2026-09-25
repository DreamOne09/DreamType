"""Conservative edit budget: suspicious rewrites fall back to the transcript.
This checks textual drift, not semantic equivalence; it is deliberately fail-closed.
"""
import unicodedata
from difflib import SequenceMatcher


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold()
                   if not c.isspace() and unicodedata.category(c)[0] not in 'PS')


def validate_edit(source, edited):
    before, after = normalized(source), normalized(edited)
    if not before:
        if after: raise ValueError('Formatting invented content')
        return
    matches = sum(block.size for block in SequenceMatcher(None, before, after, autojunk=False).get_matching_blocks())
    # Punctuation/layout are free; substantive additions and omissions are bounded.
    if len(after)-matches > max(1, int(len(before)*0.15)) or len(before)-matches > max(1, int(len(before)*0.30)):
        raise ValueError('Formatting exceeded faithful editing budget')
