from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from app.config import load_json_config
from app.models import DocumentCategory, DocumentInfo, ValidationReport


DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return " ".join(
        "".join(ch for ch in value if not unicodedata.combining(ch)).lower().split()
    )


def classify_document_text(text: str) -> tuple[DocumentCategory, str, str, str]:
    config = load_json_config("parser_config.json")
    plain = _plain(text)
    lines = text.splitlines()
    category = DocumentCategory.UNKNOWN
    title = "Documento no reconocido"
    title_line: int | None = None
    for category_name, phrases in config["expected_document_titles"].items():
        for phrase in phrases:
            if _plain(phrase) in plain:
                category = DocumentCategory(category_name)
                title = {
                    DocumentCategory.ASSIGNED: "Reporte de Plazas Asignadas",
                    DocumentCategory.VACANT: "Reporte de Plazas Vacantes",
                    DocumentCategory.WITHOUT_POSITION: "Reporte de profesionales sin plaza asignada",
                }[category]
                title_line = next(
                    (
                        index
                        for index, line in enumerate(lines)
                        if _plain(phrase) in _plain(line)
                    ),
                    None,
                )
                break
        if category is not DocumentCategory.UNKNOWN:
            break

    dated_lines = [
        (index, match.group(1))
        for index, line in enumerate(lines)
        for match in DATE_RE.finditer(line)
    ]
    if title_line is not None and dated_lines:
        _, allocation_date = min(
            dated_lines,
            key=lambda item: (abs(item[0] - title_line), item[0] < title_line),
        )
    else:
        date_match = DATE_RE.search(text)
        allocation_date = date_match.group(1) if date_match else ""
    profession = "MEDICINA" if "medicina" in plain else ""
    return category, title, allocation_date, profession


def compare_allocation_rounds(
    reports: Iterable[ValidationReport | DocumentInfo],
) -> tuple[bool, list[str]]:
    infos = [item.info if isinstance(item, ValidationReport) else item for item in reports]
    warnings: list[str] = []
    dates = {item.allocation_date for item in infos if item.allocation_date}
    professions = {item.profession.upper() for item in infos if item.profession}
    categories = {item.category for item in infos}
    expected = {
        DocumentCategory.ASSIGNED,
        DocumentCategory.VACANT,
        DocumentCategory.WITHOUT_POSITION,
    }

    if len(dates) > 1:
        warnings.append("Las fechas de la ronda no coinciden: " + ", ".join(sorted(dates)))
    if len(professions) > 1:
        warnings.append("Las profesiones detectadas no coinciden.")
    if categories != expected:
        missing = expected - categories
        duplicates = len(infos) != len(categories)
        if missing:
            warnings.append(
                "Faltan categorías esperadas: "
                + ", ".join(sorted(item.label for item in missing))
                + "."
            )
        if duplicates:
            warnings.append("Hay categorías de documento repetidas.")
        if DocumentCategory.UNKNOWN in categories:
            warnings.append("Al menos un documento no pudo reconocerse por su título.")
    return not warnings, warnings
