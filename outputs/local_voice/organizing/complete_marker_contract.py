"""Validate complete markers; recover missing markers only with textual anchors."""
import re
from opencc import OpenCC
from .english_punctuation import EQUIVALENTS

CONVERTER=OpenCC('s2tw')
CANON=str.maketrans({**{v:k for k,v in EQUIVALENTS.items()},'•':'●'})


def parse(text,expression):
    clean=[]
    canonical=[]
    offsets=[]
    anchors=[]
    cursor=0
    for match in list(expression.finditer(text))+[None]:
        end=match.start() if match else len(text)
        for char in text[cursor:end]:
            if not char.isspace():
                offsets.append(len(clean))
                canonical.append(char.translate(CANON))
            clean.append(char)
        if match:
            anchors.append((match.group(),len(canonical)))
            cursor=match.end()
    return ''.join(clean),''.join(canonical),offsets,anchors


def recover(protected_source,generated,prefix,known_markers):
    if not known_markers:return generated,{'recovered':0,'checked':0}
    expression=re.compile(re.escape(prefix)+r'\d+END')
    # Existing formatter already applies this conversion before literal restore.
    source=CONVERTER.convert(protected_source)
    output=CONVERTER.convert(generated)
    _,source_context,_,expected=parse(source,expression)
    clean,output_context,offsets,actual=parse(output,expression)
    expected_names=[name for name,_ in expected]
    actual_names=[name for name,_ in actual]
    if (len(expected_names)!=len(set(expected_names)) or set(expected_names)!=set(known_markers)):
        raise ValueError('Invalid source marker contract')
    if len(actual_names)!=len(set(actual_names)) or not set(actual_names)<=set(expected_names):
        raise ValueError('Unknown or duplicated generated marker')
    if actual_names == expected_names:
        # Complete markers require no reconstruction. Permit the punctuation
        # editing the product promises while anchoring every marker to the
        # exact same surrounding characters. Missing-marker recovery below
        # deliberately retains its stricter punctuation-aware proof.
        separators = '，。；：！？,.!?;:'
        def anchored(context, markers):
            plain = ''.join(c for c in context if c not in separators)
            positions = [(name, sum(c not in separators for c in context[:position]))
                         for name, position in markers]
            return plain, positions
        if anchored(source_context, expected) == anchored(output_context, actual):
            return output, {'recovered': 0, 'checked': len(expected_names), 'mode': 'validated_complete'}
    if source_context!=output_context:
        raise ValueError('Editable context changed; literal position is not provable')
    expected_positions=dict(expected)
    if any(expected_positions[name]!=position for name,position in actual):
        raise ValueError('Existing marker moved; do not move it back')
    if actual_names!=[name for name in expected_names if name in actual_names]:
        raise ValueError('Existing markers reordered')
    if actual_names == expected_names:
        return output, {'recovered': 0, 'checked': len(expected_names), 'mode': 'validated_complete'}
    if not any(c.isalnum() for c in source_context):
        raise ValueError('No editable textual anchor; do not reconstruct whole input')
    rebuilt=clean
    for name,position in reversed(expected):
        offset=offsets[position] if position<len(offsets) else len(clean)
        rebuilt=rebuilt[:offset]+name+rebuilt[offset:]
    return rebuilt,{'recovered':len(expected_names)-len(actual_names),'checked':len(expected_names),'mode':'recovered_missing'}
