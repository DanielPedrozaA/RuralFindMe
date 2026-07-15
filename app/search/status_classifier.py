from __future__ import annotations

import unicodedata

from app.config import load_json_config
from app.models import DocumentCategory, RecordStatus


def _plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    return " ".join(
        "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().split()
    )


def detect_record_status(text: str, category: DocumentCategory) -> RecordStatus:
    """Classify only configured, explicit language, then use document semantics."""
    config = load_json_config("status_keywords.json")
    normalized = _plain(text)

    # Negative phrases must be checked before assignment phrases because
    # "no seleccionado" contains the positive token "seleccionado".
    if any(_plain(keyword) in normalized for keyword in config["exemption_keywords"]):
        return RecordStatus.EXEMPT
    if any(_plain(keyword) in normalized for keyword in config["non_selection_keywords"]):
        return RecordStatus.NOT_SELECTED
    if any(_plain(keyword) in normalized for keyword in config["pending_keywords"]):
        return RecordStatus.UNKNOWN
    if any(_plain(keyword) in normalized for keyword in config["vacancy_keywords"]):
        return RecordStatus.VACANT
    if any(_plain(keyword) in normalized for keyword in config["assignment_keywords"]):
        return RecordStatus.ASSIGNED

    if category is DocumentCategory.ASSIGNED:
        return RecordStatus.ASSIGNED
    if category is DocumentCategory.WITHOUT_POSITION:
        return RecordStatus.NOT_SELECTED
    if category is DocumentCategory.VACANT:
        return RecordStatus.VACANT
    return RecordStatus.UNKNOWN
