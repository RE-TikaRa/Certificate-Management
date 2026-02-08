from pypinyin import lazy_pinyin


def build_pinyin(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        return ""
    try:
        return "".join(lazy_pinyin(cleaned))
    except Exception:
        return cleaned
