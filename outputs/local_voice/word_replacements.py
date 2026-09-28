"""Explicit spelling alternatives for the client editor, never LLM instructions."""


def validate_word_replacements(value):
    if not isinstance(value, str) or len(value) > 1000:
        raise ValueError('用詞對照最多 1,000 字。')
    result, seen = [], set()
    for line in value.split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = line.split('→')
        if len(parts) != 2:
            raise ValueError('每行請使用「原詞 → 慣用寫法」。')
        source, target = [part.strip() for part in parts]
        if not source or not target or max(len(source), len(target)) > 40:
            raise ValueError('對照兩側都要填寫，每側最多 40 字。')
        if any(ord(c) < 32 for c in source + target) or source == target or source in seen:
            raise ValueError('原詞不可重複，兩側不可相同或包含控制字元。')
        seen.add(source)
        result.append(source + ' → ' + target)
    if len(result) > 20:
        raise ValueError('最多設定 20 組用詞對照。')
    return '\n'.join(result)
