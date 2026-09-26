"""Shared literal Chinese-number normalization; ambiguous shorthand stays literal."""
import re
import unicodedata

def integer_amount(text):
    text=unicodedata.normalize('NFKC',text).replace(',','').replace('，','')
    if re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',text):return text
    digits=dict(zip('零〇一二兩三四五六七八九',[0,0,1,2,2,3,4,5,6,7,8,9]))
    if '點' in text or '点' in text:
        whole,fraction=re.split('[點点]',text,maxsplit=1)
        if fraction and all(c in digits for c in fraction):return integer_amount(whole)+'.'+''.join(str(digits[c]) for c in fraction)
        return text
    if any(c.isdigit() for c in text):return text # Mixed shorthand is intentionally not guessed.
    if re.search(r'[百千萬億][一二兩三四五六七八九]$',text):return text # 一千五 is ambiguous.
    total=section=number=0
    if not any(c in text for c in '十百千萬億'):return ''.join(str(digits[c]) for c in text)
    for c in text:
        if c in digits:number=digits[c]
        elif c in '十百千':section+=(number or 1)*{'十':10,'百':100,'千':1000}[c];number=0
        elif c=='萬':total+=(section+number)*10000;section=number=0
        elif c=='億':total=(total+section+number)*100000000;section=number=0
        else:return text
    return str(total+section+number)

