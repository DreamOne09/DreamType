"""Keep a complete leading English sentence in place before generation."""
import re
from .source_context_pipeline import prepare, organize, validate_strict
from .english_punctuation import english_spans
from .latin_preservation import baseline
from .quote_preservation import spans, format_quoted
from .punctuation_spacing import restore


def partition(text):
    leading=len(text)-len(text.lstrip())
    candidates=english_spans(text)
    if not candidates:return None
    start,end,literal=candidates[0]
    # Not a product name, subordinate fragment, quote, or English embedded in
    # Chinese. Keep the original separator and all source positions untouched.
    if start!=leading or literal[-1:] not in '.!?':return None
    separator=re.match(r'\s*',text[end:]).group()
    tail=text[end+len(separator):]
    if not tail or not re.search(r'[\u3400-\u9fff]',tail):return None
    if baseline(tail)!=tail:return None  # Fragmenting must not widen repair policy.
    return text[:end],separator,tail


async def organize_positioned(source,formatter):
    plan=prepare(source)
    parts=partition(plan.prepared)
    if parts is None:
        result,trace=await organize(source,formatter)
        return result,{'path':'whole_input','composition':trace}
    prefix,separator,tail=parts
    # The model never produces the prefix, so it cannot move it. It still edits
    # the remainder; full-source guards run after source-order assembly.
    rendered=await format_quoted(formatter,tail)
    rendered,metadata=restore(tail,rendered)
    result=prefix+separator+rendered
    validate_strict(plan.prepared,result)
    if [source[a:b] for a,b in spans(source)]!=[result[a:b] for a,b in spans(result)]:
        raise ValueError('Source quotation changed')
    return result,{'path':'leading_sentence_anchored','prepared':plan.prepared,
                   'prefix':prefix,'separator':separator,'punctuation':metadata,
                   'policy':plan.policy,'approved_stutter_ranges':list(plan.approved_stutter_ranges)}
