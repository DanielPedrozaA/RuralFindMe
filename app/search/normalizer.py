from __future__ import annotations

import re
import unicodedata


def normalize_id(value: str) -> str:
    return "".join(re.findall(r"\d", value or ""))


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    alphanumeric = re.sub(r"[^A-Za-z0-9]+", " ", without_marks)
    return " ".join(alphanumeric.upper().split())


def mask_id(value: str) -> str:
    digits = normalize_id(value)
    if not digits:
        return "No disponible"
    if len(digits) <= 4:
        return digits[0] + "*" * max(1, len(digits) - 2) + digits[-1]
    if len(digits) <= 7:
        return digits[:2] + "*" * (len(digits) - 4) + digits[-2:]

    groups: list[str] = []
    remaining = digits
    while remaining:
        groups.insert(0, remaining[-3:])
        remaining = remaining[:-3]
    if len(groups) >= 3:
        # Match the product example: preserve the leading group(s) and final
        # three digits while replacing the penultimate three-digit block.
        groups[-2] = "***"
    return ".".join(groups)


def numeric_token_pattern(normalized_id: str) -> re.Pattern[str]:
    """Boundary-safe pattern for OCR/raw-text diagnostics, never substring matching."""
    escaped = re.escape(normalize_id(normalized_id))
    return re.compile(rf"(?<!\d){escaped}(?!\d)")
