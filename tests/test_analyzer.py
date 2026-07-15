from pathlib import Path

import fitz
import pytest

from app.models import (
    DocumentCategory,
    DocumentInfo,
    DoctorRecord,
    RecordStatus,
    ValidationReport,
)
from app.pdf.analyzer import PdfAnalysisError, PdfAnalyzer


def test_analyzer_opens_real_documents_and_reports_progress(tmp_path, monkeypatch):
    categories = [
        DocumentCategory.ASSIGNED,
        DocumentCategory.VACANT,
        DocumentCategory.WITHOUT_POSITION,
    ]
    paths = []
    reports = {}
    for index, category in enumerate(categories):
        path = tmp_path / f"report-{index}.pdf"
        document = fitz.open()
        document.new_page().insert_text((72, 72), "Contenido de prueba suficiente")
        document.save(path)
        document.close()
        paths.append(str(path))
        reports[str(path)] = ValidationReport(
            True,
            DocumentInfo(
                str(path),
                category=category,
                page_count=1,
                allocation_round="16/04/2026",
            ),
        )

    monkeypatch.setattr("app.pdf.analyzer.validate_pdf", lambda path: reports[path])
    analyzer = PdfAnalyzer()
    analyzer.table_parser.parse_document = lambda document, category, source, progress: [
        DoctorRecord(
            normalized_id_number="900000001",
            detected_status=RecordStatus.ASSIGNED,
            source_file=source,
            source_page=1,
            confidence=0.9,
        )
    ]
    stages = []
    analyses = analyzer.analyze(paths, stage=lambda name, _message: stages.append(name))
    assert [analysis.info.category for analysis in analyses] == categories
    assert all(analysis.info.record_count == 1 for analysis in analyses)
    assert stages == [
        "VALIDATING_DOCUMENTS",
        "EXTRACTING_TEXT",
        "IDENTIFYING_DOCUMENT_TYPES",
    ]


def test_analyzer_sanitizes_open_failure(monkeypatch):
    report = ValidationReport(
        True,
        DocumentInfo(r"C:\private\report.pdf", page_count=1, category=DocumentCategory.ASSIGNED),
    )
    monkeypatch.setattr("app.pdf.analyzer.validate_pdf", lambda _path: report)
    monkeypatch.setattr("app.pdf.analyzer.fitz.open", lambda _path: (_ for _ in ()).throw(OSError(r"C:\private\report.pdf")))
    with pytest.raises(PdfAnalysisError) as error:
        PdfAnalyzer().analyze([report.info.path])
    assert "private" not in str(error.value).lower()
