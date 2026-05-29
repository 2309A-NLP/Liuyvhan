from __future__ import annotations

import re


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ASCII_WORD_RE = re.compile(r"\b[A-Za-z]{2,}\b")
_BROKEN_PLACEHOLDER_RE = re.compile(r"(?:\?{4,}|�+|锟+)")
_FRAGMENTED_LATIN_RE = re.compile(r"(?:\b[A-Za-z]\b[\s,，。？！?]*){3,}")
_HTML_BREAK_RE = re.compile(r"(?i)<br\s*/?>")
_ARTIFACT_TOKEN_RE = re.compile(r"(?i)\b(?:response|assistant|kuk)\b")
_EMPTY_NUMBERING_RE = re.compile(r"^\s*[\d一二三四五六七八九十]+[.、:：-]?\s*$")


def normalize_text(text: str) -> str:
    normalized = str(text or "")
    normalized = _HTML_BREAK_RE.sub("\n", normalized)
    normalized = normalized.replace("\r\n", "\n").replace("\ufeff", "").replace("\u3000", " ")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    normalized = re.sub(r"([，。！？；,.!?;:])\1{1,}", r"\1", normalized)
    return normalized.strip()


def prefers_chinese_reply(message: str) -> bool:
    lowered = normalize_text(message).lower()
    if not lowered:
        return True
    english_request_markers = (
        "english",
        "in english",
        "英文",
        "英语",
        "translate to english",
        "用英文",
    )
    return not any(marker in lowered for marker in english_request_markers)


def strip_generation_artifacts(text: str, *, expect_chinese: bool = True) -> str:
    normalized = normalize_text(text)
    if not normalized or not expect_chinese:
        return normalized

    if not _CJK_RE.search(normalized):
        return normalized

    cleaned_lines: list[str] = []
    for raw_line in normalized.split("\n"):
        line = _ARTIFACT_TOKEN_RE.sub("", raw_line)
        line = re.sub(r"[ \t]{2,}", " ", line).strip(" .,:;：，")
        if not line or _EMPTY_NUMBERING_RE.fullmatch(line):
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def looks_corrupted_text(text: str, *, expect_chinese: bool = True) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True

    if _BROKEN_PLACEHOLDER_RE.search(normalized):
        return True

    if _FRAGMENTED_LATIN_RE.search(normalized):
        return True

    cjk_count = len(_CJK_RE.findall(normalized))
    ascii_words = _ASCII_WORD_RE.findall(normalized)
    question_count = normalized.count("?") + normalized.count("？")

    if len(normalized) >= 12 and question_count / max(len(normalized), 1) > 0.08:
        return True

    if expect_chinese:
        if cjk_count == 0 and len(ascii_words) >= 4:
            return True
        if len(ascii_words) >= 8 and cjk_count < len(ascii_words) * 2:
            return True

    return False
