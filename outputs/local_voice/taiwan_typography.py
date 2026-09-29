"""Deterministic punctuation cleanup, without rewriting dictated content."""
import re
from personalization import IDENTIFIER

HAN = re.compile(r'[\u3400-\u9fff]')
PROTECTED = re.compile(
    # Incomplete dictated/pasted code remains literal through the end of input.
    r'```[\s\S]*?(?:```|$)|`[^`]*(?:`|$)|'
    # Unquoted English phrases embedded in Chinese still retain their literal
    # punctuation. A single product name does not make a Chinese sentence English.
    r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_]*(?:['’-][A-Za-z0-9_]+)*"
    r"(?:[ \t,;:]+[A-Za-z][A-Za-z0-9_]*(?:['’-][A-Za-z0-9_]+)*)+[.?!]*|"
    + IDENTIFIER.pattern +
    r'|(?<![A-Za-z0-9_])[A-Za-z]:\\[^\s，。！？]+|'
    r'(?<![A-Za-z0-9_])\d+(?:[.,:/-]\d+)+(?:%|％)?|'
    r'(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_]*(?:[._/-][A-Za-z0-9_]+)+')


def normalize_taiwan_typography(text):
    """Chinese prose only; retain code, identifiers and numeric separators.

    This does not guess where missing sentences/topics end. That remains the
    formatter's job. Existing list/paragraph boundaries are never flattened.
    """
    saved = []
    prefix = 'DTTYPO'
    while prefix in text:
        prefix += 'X'

    def protect(match):
        saved.append(match.group())
        return f'{prefix}{len(saved)-1}END'

    masked = PROTECTED.sub(protect, text)
    lines = []
    for line in masked.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if HAN.search(line):
            # Leave explicitly quoted English fragments intact.
            fragments = re.split(r'("[^"\n]*"|\'[^\'\n]*\')', line)
            for i, part in enumerate(fragments):
                if i % 2 and not HAN.search(part):
                    continue
                part = re.sub(r'\(([^()]*[\u3400-\u9fff][^()]*)\)', r'（\1）', part)
                part = part.translate(str.maketrans(',;:!?', '，；：！？'))
                # Preserve numbered-list markers and periods inside Latin text.
                part = re.sub(r'(?<=[\u3400-\u9fff）」』])\.(?!\.)|(?<!\.)\.(?=\s*$)', '。', part)
                if i % 2 and HAN.search(part):
                    part = ('「' + part[1:-1] + '」') if part[0] == '"' else ('『' + part[1:-1] + '』')
                fragments[i] = part
            line = ''.join(fragments)
            line = re.sub(r'([，。！？；：])[ \t]+(?=[\u3400-\u9fff])', r'\1', line)
        lines.append(line.rstrip())
    result = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()
    return re.sub(re.escape(prefix) + r'(\d+)END', lambda m: saved[int(m[1])], result)


def preserve_prose_layout(source, edited, personal_prompt=''):
    """Remove invented bullets only when complete source prose is otherwise identical."""
    from spoken_corrections import comparison_source
    if personal_prompt.strip() or '\n' in source or '\r' in source:
        return edited
    # Ambiguous lists, topic changes and literal markup remain model/user-controlled.
    if source.count('。') < 2 or re.search(r'[、：:；;•`「」『』]|第[一二三四五六七八九]|[一二三四五六七八九]、|另外|另一方面|至於|除此之外|以下|清單|條列', source):
        return edited
    if '\n\n' in edited or not re.search(r'(?m)^\s*• ', edited):
        return edited
    baseline = normalize_taiwan_typography(comparison_source(source))
    without_bullets = re.sub(r'(?m)^[ \t]*• ', '', edited)
    # No fuzzy comparison: never hide a changed word, number, negation or punctuation.
    if re.sub(r'\s+', '', baseline) != re.sub(r'\s+', '', without_bullets):
        return edited
    return baseline


def chinese_bullet_style(text):
    """Render prose bullets with a solid dot and ideographic space; code is literal."""
    pattern = r'```[\s\S]*?(?:```|$)|`[^`]*(?:`|$)|(?m:^(?P<indent>[ \t]*)[•●][ \t\u3000]+(?=\S))'
    return re.sub(pattern, lambda match: match.group(0) if match['indent'] is None
                  else match['indent'] + '●\u3000', text)


def readable_layout(text, personal_prompt=''):
    """Whitespace-only defaults for Chinese prose and flat bullet lists.

    Blank paragraphs, incomplete lines, quotations, code and custom styles
    remain literal. This is not a semantic topic classifier.
    """
    if personal_prompt.strip() or re.search(r'[`「」『』]|(?m:^[ \t]+\S)', text):
        return text
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    bullet = re.compile(r'^[•●][ \t\u3000]+\S')
    transition = re.compile(r'^(?:另外|另一方面|至於|除此之外|接下來談|換個話題)')
    result = []
    for line in lines:
        if result and line and result[-1]:
            previous = result[-1]
            if bool(bullet.match(previous)) != bool(bullet.match(line)):
                result.append('')
            elif not bullet.match(line) and re.search(r'[。！？]$', previous) and HAN.match(line):
                if transition.match(line):
                    result.append('')
                else:
                    result[-1] += line
                    continue
        result.append(line)
    return '\n'.join(result)
