from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import fitz

from app.models import DocumentAnalysis, DocumentCategory
from app.pdf.ocr import ocr_page
from app.pdf.table_parser import TableParser
from app.pdf.validator import validate_pdf


ProgressCallback = Callable[[int, str], None]
StageCallback = Callable[[str, str], None]


class PdfAnalysisError(RuntimeError):
    """A user-safe PDF analysis failure without local path details."""


class PdfAnalyzer:
    def __init__(self) -> None:
        self.table_parser = TableParser()

    def analyze(
        self,
        paths: list[str],
        progress: ProgressCallback | None = None,
        stage: StageCallback | None = None,
    ) -> list[DocumentAnalysis]:
        analyses: list[DocumentAnalysis] = []
        total_pages = 0
        reports = []
        if stage:
            stage("VALIDATING_DOCUMENTS", "Validando estructura, acceso y texto de los tres PDF…")
        for index, path in enumerate(paths):
            if progress:
                progress(index * 5, f"Validando {Path(path).name}…")
            report = validate_pdf(path)
            if not report.valid:
                raise ValueError(f"{report.info.filename}: {'; '.join(report.errors)}")
            reports.append(report)
            total_pages += report.info.page_count

        if stage:
            stage("EXTRACTING_TEXT", "Extrayendo celdas y reconstruyendo filas con su página de origen…")
        pages_done = 0
        for report in reports:
            if progress:
                progress(
                    15 + int(75 * pages_done / max(total_pages, 1)),
                    f"Reconstruyendo tablas de {report.info.filename}…",
                )
            try:
                document = fitz.open(report.info.path)
            except (fitz.FileDataError, fitz.EmptyFileError, OSError, RuntimeError) as exc:
                raise PdfAnalysisError(
                    "No fue posible abrir uno de los PDF durante el análisis. "
                    "Vuelva a seleccionar los documentos."
                ) from exc
            try:
                if report.info.image_only:
                    records = self._parse_ocr_fallback(document, report.info.category, report.info.filename)
                    report.info.used_ocr = True
                    pages_done += document.page_count
                else:
                    def page_progress(done: int, _total: int) -> None:
                        if progress:
                            progress(
                                15 + int(75 * (pages_done + done) / max(total_pages, 1)),
                                f"Leyendo página {done} de {_total}: {report.info.filename}",
                            )

                    records = self.table_parser.parse_document(
                        document,
                        report.info.category,
                        report.info.filename,
                        page_progress,
                    )
                    pages_done += document.page_count
                report.info.record_count = len(records)
                analyses.append(DocumentAnalysis(report.info, records, report.warnings))
            finally:
                document.close()
        if stage:
            stage(
                "IDENTIFYING_DOCUMENT_TYPES",
                "Confirmando títulos, categorías y fecha de la ronda detectada…",
            )
        if progress:
            progress(94, "Preparando la búsqueda exacta…")
        return analyses

    @staticmethod
    def _parse_ocr_fallback(
        document: fitz.Document, category: DocumentCategory, source_file: str
    ) -> list:
        """Conservative OCR fallback: retain low-confidence, ID-typed evidence only."""
        from app.models import DoctorRecord, RecordStatus
        from app.search.normalizer import normalize_id
        import re

        records = []
        pattern = re.compile(r"\b(CC|CE|PT|PA|TI|PPT)\s*[:\-]?\s*(\d[\d .,-]{4,18}\d)\b", re.I)
        for page_number, page in enumerate(document, start=1):
            text = ocr_page(page)
            for match in pattern.finditer(text):
                normalized = normalize_id(match.group(2))
                if not 5 <= len(normalized) <= 15:
                    continue
                status = (
                    RecordStatus.ASSIGNED
                    if category is DocumentCategory.ASSIGNED
                    else RecordStatus.NOT_SELECTED
                    if category is DocumentCategory.WITHOUT_POSITION
                    else RecordStatus.UNKNOWN
                )
                raw = text[max(0, match.start() - 120): match.end() + 220].strip()
                records.append(
                    DoctorRecord(
                        id_type=match.group(1).upper(),
                        id_number=match.group(2),
                        normalized_id_number=normalized,
                        official_status=(
                            "Plaza asignada (lectura OCR)"
                            if status is RecordStatus.ASSIGNED
                            else "Profesional sin plaza asignada (lectura OCR)"
                        ),
                        detected_status=status,
                        source_file=source_file,
                        source_page=page_number,
                        raw_text=raw,
                        confidence=0.45,
                    )
                )
        return records
