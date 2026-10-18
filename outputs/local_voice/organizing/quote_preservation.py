"""Keep balanced quotations opaque until all candidate formatting is done."""
import re
from .latin_preservation import validate

PAIRS = {'「': '」', '『': '』', '“': '”', '‘': '’', '"': '"', "'": "'"}


def spans(text):
    stack = []
    found = []
    start = 0
    for i, char in enumerate(text):
        if char in "'’" and i and i+1 < len(text) and text[i-1].isalpha() and text[i+1].isalpha():
            continue  # Contraction, not a quote delimiter.
        if stack and char == stack[-1]:
            stack.pop()
            if not stack:
                found.append((start, i+1))
        elif char in PAIRS:
            if not stack:
                start = i
            stack.append(PAIRS[char])
        elif char in '」』”’':
            raise ValueError('Unbalanced quotation; retain original')
    if stack:
        raise ValueError('Unbalanced quotation; retain original')
    return found


async def format_quoted(formatter, source):
    ranges = spans(source)
    prefix = 'DTQUOTE'
    while prefix in source:
        prefix += 'X'
    values = {f'{prefix}-{i}': source[a:b] for i, (a,b) in enumerate(ranges)}
    masked = source
    for i, (a,b) in reversed(list(enumerate(ranges))):
        masked = masked[:a] + f'{prefix}-{i}' + masked[b:]
    result = await formatter(masked)
    markers = re.findall(re.escape(prefix) + r'-\d+', result)
    if markers != list(values) or result.count(prefix) != len(values):
        raise ValueError('Quotation marker changed, moved or duplicated')
    restored = re.sub(re.escape(prefix) + r'-\d+', lambda m: values[m.group()], result)
    # Restoration happens AFTER typography and language conversion.
    if [restored[a:b] for a,b in spans(restored)] != list(values.values()):
        raise ValueError('Quotation contents changed')
    validate(source, restored)
    return restored
