from __future__ import annotations

import json

from PySide6.QtWidgets import QApplication, QWidget

from app.bridge import (
    DesktopBridge,
    DocumentBatchWorker,
    SearchWorker,
    arrange_reports,
)
from app.bridge_serialization import document_payload, result_payload
from app.models import (
    DocumentAnalysis,
    DocumentCategory,
    DocumentInfo,
    DoctorRecord,
    RecordStatus,
    ResultType,
    SearchResult,
    ValidationReport,
)
from app.search import DoctorQuery


def test_document_payload_never_exposes_local_path():
    info = DocumentInfo(
        path=r"C:\sensible\reporte.pdf",
        filename="reporte.pdf",
        size_bytes=1234,
        page_count=2,
        category=DocumentCategory.ASSIGNED,
        allocation_round="16/04/2026",
    )
    payload = document_payload(ValidationReport(True, info), 0)
    assert "path" not in payload
    assert "sensible" not in json.dumps(payload)


def test_result_payload_masks_id_even_inside_raw_evidence(assigned_record):
    assigned_record.raw_text = "CC | 900000001 | ESE HOSPITAL DE PRUEBA"
    result = SearchResult(
        ResultType.ASSIGNED,
        primary_record=assigned_record,
        evidence=[assigned_record],
        searched_id="900000001",
    )
    analysis = DocumentAnalysis(
        DocumentInfo(
            "asignadas_prueba.pdf",
            allocation_round="16/04/2026",
            category=DocumentCategory.ASSIGNED,
        ),
        [assigned_record],
    )
    encoded = json.dumps(result_payload(result, [analysis]), ensure_ascii=False)
    assert "900000001" not in encoded
    assert "900.***.001" in encoded


def test_result_payload_masks_id_with_different_evidence_separators(assigned_record):
    assigned_record.id_number = "900000001"
    assigned_record.normalized_id_number = "900000001"
    assigned_record.raw_text = "CC | 900.000.001 | ESE HOSPITAL DE PRUEBA"
    result = SearchResult(
        ResultType.ASSIGNED,
        primary_record=assigned_record,
        evidence=[assigned_record],
        searched_id="900000001",
    )
    analysis = DocumentAnalysis(
        DocumentInfo(
            "asignadas_prueba.pdf",
            filename="asignadas_prueba.pdf",
            allocation_round="16/04/2026",
            category=DocumentCategory.ASSIGNED,
        ),
        [assigned_record],
    )
    encoded = json.dumps(result_payload(result, [analysis]), ensure_ascii=False)
    assert "900.000.001" not in encoded
    assert "900.***.001" in encoded


def test_bridge_initialize_emits_safe_state():
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    bridge = DesktopBridge(parent)
    snapshots: list[dict] = []
    bridge.stateSnapshot.connect(lambda value: snapshots.append(json.loads(value)))
    bridge.initialize()
    assert snapshots[-1]["documents"] == [None, None, None]
    assert snapshots[-1]["can_continue"] is False
    parent.close()
    del app


def test_worker_emits_real_stage_sequence(monkeypatch, assigned_record):
    analysis = DocumentAnalysis(
        DocumentInfo(
            "asignadas_prueba.pdf",
            filename="asignadas_prueba.pdf",
            allocation_round="16/04/2026",
            category=DocumentCategory.ASSIGNED,
            record_count=1,
        ),
        [assigned_record],
    )

    def fake_analyze(_self, _paths, progress=None, stage=None):
        del progress
        stage("VALIDATING_DOCUMENTS", "validando")
        stage("EXTRACTING_TEXT", "extrayendo")
        stage("IDENTIFYING_DOCUMENT_TYPES", "identificando")
        return [analysis]

    monkeypatch.setattr("app.bridge.PdfAnalyzer.analyze", fake_analyze)
    worker = SearchWorker(["prueba.pdf"], DoctorQuery("900000001"))
    stages: list[str] = []
    completed = []
    worker.signals.stage.connect(lambda stage, _message: stages.append(stage))
    worker.signals.completed.connect(lambda analyses, result: completed.append((analyses, result)))
    worker.run()
    assert stages == [
        "VALIDATING_DOCUMENTS",
        "EXTRACTING_TEXT",
        "IDENTIFYING_DOCUMENT_TYPES",
        "SEARCHING_IDENTIFICATION",
        "VERIFYING_EVIDENCE",
        "CLASSIFYING_RESULT",
        "READY_TO_REVEAL",
    ]
    assert completed[0][1].result_type is ResultType.ASSIGNED


def test_batch_reports_are_arranged_by_detected_category():
    reports = [
        ValidationReport(
            True,
            DocumentInfo("sin_plaza.pdf", category=DocumentCategory.WITHOUT_POSITION),
        ),
        ValidationReport(
            True,
            DocumentInfo("vacantes.pdf", category=DocumentCategory.VACANT),
        ),
        ValidationReport(
            True,
            DocumentInfo("asignadas.pdf", category=DocumentCategory.ASSIGNED),
        ),
    ]
    arranged = arrange_reports(reports)
    assert [report.info.category for report in arranged if report] == [
        DocumentCategory.ASSIGNED,
        DocumentCategory.VACANT,
        DocumentCategory.WITHOUT_POSITION,
    ]


def test_batch_worker_converts_validator_exception_to_safe_failure(monkeypatch):
    def fail_validation(_path):
        raise OSError(r"C:\sensible\reporte.pdf")

    monkeypatch.setattr("app.bridge.validate_pdf", fail_validation)
    worker = DocumentBatchWorker([r"C:\sensible\reporte.pdf"])
    failures: list[str] = []
    worker.signals.failed.connect(failures.append)
    worker.run()
    assert failures == [
        "No fue posible validar los PDF seleccionados. Los archivos no se modificaron."
    ]
    assert "sensible" not in failures[0]


def test_search_worker_converts_exception_to_safe_failure(monkeypatch):
    def fail_analysis(*_args, **_kwargs):
        raise OSError(r"C:\sensible\reporte.pdf")

    monkeypatch.setattr("app.bridge.PdfAnalyzer.analyze", fail_analysis)
    worker = SearchWorker([r"C:\sensible\reporte.pdf"], DoctorQuery("900000001"))
    failures: list[str] = []
    worker.signals.failed.connect(failures.append)
    worker.run()
    assert len(failures) == 1
    assert "sensible" not in failures[0]
    assert "reporte.pdf" not in failures[0]


def test_batch_picker_rejects_fewer_than_three_without_closing():
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    bridge = DesktopBridge(parent)
    payloads: list[dict] = []
    bridge.documentValidationUpdated.connect(
        lambda value: payloads.append(json.loads(value))
    )
    bridge._begin_document_batch(["uno.pdf", "dos.pdf"])
    assert payloads[-1]["valid"] is False
    assert "exactamente tres" in payloads[-1]["warnings"][0]
    assert parent.isVisible() is False
    parent.close()
    del app


def test_batch_picker_defers_isolated_worker(monkeypatch):
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    bridge = DesktopBridge(parent)
    scheduled = []

    monkeypatch.setattr(
        "app.bridge.QTimer.singleShot",
        lambda delay, callback: scheduled.append((delay, callback)),
    )
    bridge.begin_pdf_selection()
    assert bridge._picker_scheduled is True
    assert scheduled == [(100, bridge._start_file_picker)]
    parent.close()
    del app
