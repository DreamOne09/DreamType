"""Permit missing whitespace only after a present source punctuation separator."""
import re
from .english_punctuation import EQUIVALENTS, WORD_EDGE, english_spans
from .latin_patterns import LATIN
from .latin_preservation import baseline, validate, tokens
from .quote_preservation import spans


def restore(source, edited):
    # The upstream formatter's guards are unchanged. Check lexical order here
    # before aligning, then run the complete validator on the restored result.
    if tokens(baseline(source)) != tokens(edited):
        raise ValueError('Spacing repair cannot change or reorder words')
    quoted_before=[edited[a:b] for a,b in spans(edited)]
    cursor=matched=changed=inserted=0
    missing=[]
    for _,_,literal in english_spans(baseline(source)):
        pattern=[]
        actions=[]
        i=0
        while i<len(literal):
            char=literal[i]
            name='g'+str(len(actions))
            if char.isspace():
                end=i+1
                while end<len(literal) and literal[end].isspace():end+=1
                # The punctuation itself is mandatory. Never permit zero space
                # between words, before punctuation, or before a digit.
                eligible=(i>0 and literal[i-1] in EQUIVALENTS
                          and end<len(literal) and literal[end] in LATIN)
                if eligible:
                    pattern.append('(?P<'+name+r'>\s*)')
                    actions.append((name,'space',' '))
                else:
                    pattern.append(r'\s+')
                i=end
                continue
            if char in EQUIVALENTS:
                pattern.append('(?P<'+name+'>['+re.escape(char+EQUIVALENTS[char])+'])')
                actions.append((name,'punctuation',char))
            else:
                pattern.append(re.escape(char))
            i+=1
        expression=re.compile('(?<!'+WORD_EDGE+')'+''.join(pattern)+'(?!'+WORD_EDGE+')')
        excluded=spans(edited)
        match=next((m for m in expression.finditer(edited,cursor)
                    if not any(m.start()<b and m.end()>a for a,b in excluded)),None)
        if match is None:
            missing.append(literal)
            continue
        matched+=1
        delta=0
        for name,kind,value in reversed(actions):
            a,b=match.span(name)
            if kind=='space':
                if a==b:
                    edited=edited[:a]+value+edited[b:]
                    inserted+=1
                    delta+=1
            elif edited[a:b]!=value:
                edited=edited[:a]+value+edited[b:]
                changed+=1
        cursor=match.end()+delta
    if [edited[a:b] for a,b in spans(edited)]!=quoted_before:
        raise ValueError('Spacing repair touched quotation')
    validate(source, edited)
    return edited,{'matched_spans':matched,'changed_punctuation':changed,
                   'inserted_spaces':inserted,'unmatched_spans':missing}
