from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Callable, Optional

import fitz

from app.config import load_json_config
from app.models import DocumentCategory, DoctorRecord, RecordStatus
from app.search.normalizer import normalize_id, normalize_name
from app.search.status_classifier import detect_record_status


VACANCY_RE = re.compile(r"^\d{8,15}-\d{1,3}$")
ID_RE = re.compile(r"^\d{5,15}$")
MAX_CONTINUATION_ROWS = 2
FOOTER_MARKERS = (
    "reporte de",
    "fecha de generacion",
    "generado el",
    "ministerio de salud",
    "total de registros",
    "fin del reporte",
)
PAGE_FOOTER_RE = re.compile(r"^pagina\s+\d+\s+(?:de|/)\s*\d+$")


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())


def _key(value: object) -> str:
    plain = unicodedata.normalize("NFKD", _clean(value))
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


class TableParser:
    def __init__(self) -> None:
        self.config = load_json_config("parser_config.json")
        self.aliases = {
            name: [_key(alias) for alias in values]
            for name, values in self.config["column_aliases"].items()
        }

    def _header_map(self, row: list[object]) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for index, cell in enumerate(row):
            normalized = _key(cell)
            if not normalized:
                continue
            for field, aliases in self.aliases.items():
                if any(alias == normalized or alias in normalized for alias in aliases):
                    mapping.setdefault(field, index)
        return mapping

    @staticmethod
    def _minimum_header(category: DocumentCategory, mapping: dict[str, int]) -> bool:
        if category is DocumentCategory.ASSIGNED:
            return {"vacancy_code", "id_type", "id_number"}.issubset(mapping)
        if category is DocumentCategory.VACANT:
            return {"vacancy_code", "municipality"}.issubset(mapping)
        if category is DocumentCategory.WITHOUT_POSITION:
            return {"id_type", "id_number"}.issubset(mapping)
        return "id_number" in mapping or "vacancy_code" in mapping

    @staticmethod
    def _is_data_row(
        row: list[object], category: DocumentCategory, mapping: dict[str, int]
    ) -> bool:
        def cell(field: str) -> str:
            index = mapping.get(field, -1)
            return _clean(row[index]) if 0 <= index < len(row) else ""

        if category in (DocumentCategory.ASSIGNED, DocumentCategory.VACANT):
            return bool(VACANCY_RE.fullmatch(cell("vacancy_code")))
        if category is DocumentCategory.WITHOUT_POSITION:
            return bool(ID_RE.fullmatch(normalize_id(cell("id_number"))))
        return bool(ID_RE.fullmatch(normalize_id(cell("id_number"))))

    def _record_from_row(
        self,
        row: list[object],
        mapping: dict[str, int],
        category: DocumentCategory,
        source_file: str,
        page_number: int,
    ) -> DoctorRecord:
        def value(field: str) -> Optional[str]:
            index = mapping.get(field, -1)
            result = _clean(row[index]) if 0 <= index < len(row) else ""
            return result or None

        id_number = value("id_number")
        full_name = value("full_name")
        if category is DocumentCategory.ASSIGNED:
            official = value("official_status") or "Plaza asignada"
        elif category is DocumentCategory.WITHOUT_POSITION:
            official = value("official_status") or "Profesional sin plaza asignada"
        elif category is DocumentCategory.VACANT:
            official = "Plaza vacante"
        else:
            official = value("official_status")
        status = detect_record_status(official or "", category)

        record = DoctorRecord(
            full_name=full_name,
            normalized_name=normalize_name(full_name or "") or None,
            id_type=value("id_type"),
            id_number=id_number,
            normalized_id_number=normalize_id(id_number or "") or None,
            official_status=official,
            detected_status=status,
            institution=value("institution"),
            hospital=value("institution"),
            municipality=value("municipality"),
            department=value("department"),
            vacancy_code=value("vacancy_code"),
            profession=value("profession"),
            reps_code=value("reps_code"),
            reps_site=value("reps_site"),
            modality=value("modality"),
            assignment_date=value("assignment_date"),
            start_date=value("start_date"),
            duration=value("duration"),
            contact=value("contact"),
            observations=value("observations"),
            source_file=source_file,
            source_page=page_number,
            raw_text=" | ".join(_clean(cell) for cell in row if _clean(cell)),
        )
        from app.search.confidence import score_record

        record.confidence = score_record(record)
        return record

    def parse_table_rows(
        self,
        rows: list[list[object]],
        category: DocumentCategory,
        source_file: str,
        page_number: int,
        existing: Optional[list[DoctorRecord]] = None,
    ) -> list[DoctorRecord]:
        records = existing if existing is not None else []
        mapping: dict[str, int] = {}
        continuation_rows = 0
        for row in rows:
            candidate_map = self._header_map(row)
            if self._minimum_header(category, candidate_map):
                mapping = candidate_map
                continue
            if not mapping:
                continue
            if self._is_data_row(row, category, mapping):
                records.append(
                    self._record_from_row(row, mapping, category, source_file, page_number)
                )
                continuation_rows = 0
                continue
            # A physical continuation row can occur after an Excel page break. Keep
            # it as evidence on the preceding record without inventing new columns.
            continuation = " | ".join(_clean(cell) for cell in row if _clean(cell))
            if (
                continuation
                and records
                and not candidate_map
                and continuation_rows < MAX_CONTINUATION_ROWS
            ):
                continuation_key = _key(continuation)
                if not any(
                    marker in continuation_key for marker in FOOTER_MARKERS
                ) and not PAGE_FOOTER_RE.fullmatch(continuation_key):
                    records[-1].raw_text = f"{records[-1].raw_text} | {continuation}"
                    continuation_rows += 1
        return records

    def parse_document(
        self,
        document: fitz.Document,
        category: DocumentCategory,
        source_file: str,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> list[DoctorRecord]:
        records: list[DoctorRecord] = []
        for page_index, page in enumerate(document):
            tables = page.find_tables().tables
            for table in tables:
                self.parse_table_rows(
                    table.extract(), category, Path(source_file).name, page_index + 1, records
                )
            if progress:
                progress(page_index + 1, document.page_count)
        # Remove accidental exact duplicates caused by overlapping table detections.
        deduplicated: list[DoctorRecord] = []
        seen: set[tuple[str, str, str, int, str]] = set()
        for record in records:
            key = (*record.identity_key(), record.source_page, record.source_file)
            if key not in seen:
                seen.add(key)
                deduplicated.append(record)
        return deduplicated
