"""One experimental composition entry point; repair policy uses original context."""
from dataclasses import dataclass
from .latin_patterns import STUTTER, AMBIGUOUS, ORIGINAL, phrases, preferences
from .latin_preservation import WORDS, baseline, tokens
from dictation_guard import validate_edit
from .quote_preservation import spans, format_quoted
from .punctuation_spacing import restore


@dataclass(frozen=True)
class Plan:
    original: str
    prepared: str
    policy: str
    approved_stutter_ranges: tuple


def prepare(source):
    quotes=spans(source)  # Fail on ambiguous/unbalanced quote syntax first.
    if not quotes:
        return Plan(source,baseline(source),'existing_unquoted_baseline',())
    # Preserve offsets and original sentence boundaries. Quote contents are
    # opaque data, but attribution/repair cues OUTSIDE them remain effective.
    visible=list(source)
    for a,b in quotes:
        visible[a:b]=' '*(b-a)
    if AMBIGUOUS.search(''.join(visible)):
        return Plan(source,source,'outside_ambiguity_preserved',())
    approved=[]
    for match in STUTTER.finditer(source):
        a,b=match.span('run')
        if not any(a<end and b>start for start,end in quotes):
            approved.append((a,b))
    prepared=source
    for a,b in reversed(approved):
        prepared=prepared[:a]+'I'+prepared[b:]
    # Weekday repair remains disabled for sources containing quotes, exactly as
    # before. Only existing I-stutter patterns outside quotes are enabled here.
    return Plan(source,prepared,'original_context_stutter_only',tuple(approved))


def protect_literals(text,*references,literal_terms=()):
    """Pure masking: never clean stutter or infer a repair from masked text."""
    identifiers=[(m.start(),m.end()) for m in preferences.IDENTIFIER.finditer(text)]
    singles=[m.group() for m in WORDS.finditer(text)
             if not any(m.start()<b and m.end()>a for a,b in identifiers)]
    return ORIGINAL(text,*references,literal_terms=tuple(literal_terms)+tuple(phrases(text))+tuple(singles))


def validate_strict(source,edited):
    # Exact identity cannot add/remove/reorder words, identifiers or conditions.
    # Do not normalize here: even punctuation-only differences use full guards.
    if isinstance(source, str) and source == edited:
        return
    if tokens(source)!=tokens(edited):
        raise ValueError('Formatting changed prepared Latin wording or order')
    validate_edit(source,edited)


async def organize(source,formatter):
    """Formatter adapter must use protect_literals and validate_strict.

    No service imports, global monkeypatches or authentication in this module.
    The bounded probe supplies the isolated production formatter implementation.
    """
    plan=prepare(source)
    if baseline(plan.prepared)!=plan.prepared:
        raise ValueError('Prepared repair policy is not stable')
    quoted=await format_quoted(formatter,plan.prepared)
    result,metadata=restore(plan.prepared,quoted)
    validate_strict(plan.prepared,result)
    if [source[a:b] for a,b in spans(source)]!=[result[a:b] for a,b in spans(result)]:
        raise ValueError('Original quotation changed')
    return result,{'prepared':plan.prepared,'policy':plan.policy,
                   'approved_stutter_ranges':list(plan.approved_stutter_ranges),
                   'punctuation':metadata}
