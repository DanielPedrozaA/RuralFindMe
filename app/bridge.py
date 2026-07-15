from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Optional

from PySide6.QtCore import (
    QObject,
    QProcess,
    QRunnable,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget

from app.animations.sound_effects import play_reveal
from app.bridge_serialization import document_payload, result_payload
from app.config import AppSettings
from app.diagnostics import log_exception
from app.export import export_result, format_result
from app.models import (
    DocumentAnalysis,
    DocumentCategory,
    SearchResult,
    ValidationReport,
)
from app.pdf import PdfAnalyzer
from app.pdf.document_classifier import compare_allocation_rounds
from app.pdf.validator import validate_pdf
from app.search import DoctorQuery, normalize_id, search_records


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


STAGE_MESSAGES = {
    "VERIFYING_EVIDENCE": "Verificando coincidencias, fuentes y posibles contradicciones…",
    "CLASSIFYING_RESULT": "Aplicando las reglas deterministas de clasificación…",
}

SEARCH_FAILURE_MESSAGE = (
    "No fue posible completar el análisis local. "
    "Revise los PDF seleccionados e inténtelo nuevamente."
)
DOCUMENT_FAILURE_MESSAGE = (
    "No fue posible validar los PDF seleccionados. Los archivos no se modificaron."
)


class SearchWorkerSignals(QObject):
    stage = Signal(str, str)
    completed = Signal(object, object)
    failed = Signal(str)


class SearchWorker(QRunnable):
    def __init__(self, paths: list[str], query: DoctorQuery) -> None:
        super().__init__()
        self.paths = paths
        self.query = query
        self.signals = SearchWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            analyzer = PdfAnalyzer()
            analyses = analyzer.analyze(
                self.paths,
                stage=lambda name, message: self.signals.stage.emit(name, message),
            )
            self.signals.stage.emit(
                "SEARCHING_IDENTIFICATION",
                "Comparando la identificación normalizada como token numérico completo…",
            )
            records = [record for analysis in analyses for record in analysis.records]

            def search_stage(name: str) -> None:
                self.signals.stage.emit(name, STAGE_MESSAGES[name])

            result = search_records(records, self.query, search_stage)
            result.documents_summary = [
                f"{analysis.info.category.label}: {analysis.info.record_count} registros"
                for analysis in analyses
            ]
            self.signals.stage.emit(
                "READY_TO_REVEAL", "El resultado local está listo para ser revelado."
            )
            self.signals.completed.emit(analyses, result)
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            log_exception("SearchWorker expected failure", exc)
            self.signals.failed.emit(SEARCH_FAILURE_MESSAGE)


class DocumentBatchWorkerSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class DocumentBatchWorker(QRunnable):
    """Validate the three selected documents without blocking Qt WebEngine."""

    def __init__(self, paths: list[str]) -> None:
        super().__init__()
        self.paths = paths
        self.signals = DocumentBatchWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.completed.emit([validate_pdf(path) for path in self.paths])
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            log_exception("DocumentBatchWorker expected failure", exc)
            self.signals.failed.emit(DOCUMENT_FAILURE_MESSAGE)


CATEGORY_SLOTS = {
    DocumentCategory.ASSIGNED: 0,
    DocumentCategory.VACANT: 1,
    DocumentCategory.WITHOUT_POSITION: 2,
}


def arrange_reports(
    reports: list[ValidationReport],
) -> list[ValidationReport | None]:
    """Place recognized reports in their semantic UI slots, independent of selection order."""

    arranged: list[ValidationReport | None] = [None, None, None]
    deferred: list[ValidationReport] = []
    for report in reports:
        slot = CATEGORY_SLOTS.get(report.info.category)
        if slot is not None and arranged[slot] is None:
            arranged[slot] = report
            continue
        if slot is not None:
            report.valid = False
            report.errors.append(
                f"La categoría «{report.info.category.label}» está repetida."
            )
        deferred.append(report)

    for report in deferred:
        try:
            slot = arranged.index(None)
        except ValueError:
            break
        arranged[slot] = report
    return arranged


class DesktopBridge(QObject):
    """Narrow command/event boundary for the local React application."""

    stateSnapshot = Signal(str)
    documentSelected = Signal(int, str)
    documentBatchStateChanged = Signal(bool, str)
    documentValidationUpdated = Signal(str)
    processingStageChanged = Signal(str, str)
    searchCompleted = Signal(str)
    processingFailed = Signal(str)
    exportCompleted = Signal(str)

    def __init__(self, parent_window: QWidget, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.parent_window = parent_window
        self.settings = AppSettings()
        self._reports: list[ValidationReport | None] = [None, None, None]
        self._round_confirmed = False
        self._picker_scheduled = False
        self._picker_process: QProcess | None = None
        self._picker_result_path: Path | None = None
        self._batch_worker: DocumentBatchWorker | None = None
        self._worker: SearchWorker | None = None
        self._analyses: list[DocumentAnalysis] = []
        self._result: SearchResult | None = None

    @Slot(name="initialize")
    def initialize(self) -> None:
        self._emit_state()

    def handle_frontend_command(self, name: str, args: list[object]) -> None:
        """Dispatch a command collected by the host timer, outside DOM input handling."""

        if name == "selectPdfs" and not args:
            self.begin_pdf_selection()
        elif name == "validateDocuments" and len(args) == 1 and isinstance(args[0], bool):
            self.validate_documents(args[0])
        elif (
            name == "searchDoctor"
            and len(args) == 3
            and all(isinstance(value, str) for value in args)
        ):
            self.search_doctor(args[0], args[1], args[2])
        elif name == "resetApplication" and not args:
            self.reset_application()
        elif name == "exportResult" and not args:
            self.export_current_result()
        elif name == "copyResult" and not args:
            self.copy_current_result()
        elif name == "notifyReveal" and not args:
            self.notify_reveal()
        elif (
            name == "updatePreferences"
            and len(args) == 2
            and all(isinstance(value, bool) for value in args)
        ):
            self.update_preferences(args[0], args[1])

    def begin_pdf_selection(self) -> None:
        if (
            self._picker_scheduled
            or self._picker_process is not None
            or self._batch_worker is not None
            or self._worker is not None
        ):
            self._emit_document_error("Ya hay una operación en curso.")
            return
        # Called by the host-side request poll, never from a DOM input callback.
        self._picker_scheduled = True
        QTimer.singleShot(100, self._start_file_picker)

    def _start_file_picker(self) -> None:
        self._picker_scheduled = False
        self.documentBatchStateChanged.emit(
            True, "Abriendo un selector seguro para los tres PDF…"
        )
        descriptor, result_name = tempfile.mkstemp(
            prefix="ruralfindme-picker-", suffix=".json"
        )
        os.close(descriptor)
        self._picker_result_path = Path(result_name)
        process = QProcess(self)
        process.setProgram(sys.executable)
        if getattr(sys, "frozen", False):
            process.setArguments(
                ["--file-picker-helper", str(self._picker_result_path)]
            )
        else:
            process.setArguments(
                [
                    "-m",
                    "app.main",
                    "--file-picker-helper",
                    str(self._picker_result_path),
                ]
            )
        process.finished.connect(self._file_picker_process_finished)
        process.errorOccurred.connect(self._file_picker_process_error)
        self._picker_process = process
        process.start()

    def _file_picker_process_finished(
        self, exit_code: int, _exit_status: QProcess.ExitStatus
    ) -> None:
        if self._picker_process is None and self._picker_result_path is None:
            return
        process = self._picker_process
        result_path = self._picker_result_path
        self._picker_process = None
        self._picker_result_path = None
        if process is not None:
            process.deleteLater()
        try:
            if exit_code != 0 or result_path is None:
                raise RuntimeError("picker helper failed")
            payload = json.loads(result_path.read_text(encoding="utf-8") or "[]")
            if not isinstance(payload, list) or not all(
                isinstance(path, str) for path in payload
            ):
                raise ValueError("invalid picker result")
            self._files_selected(payload)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
            self._file_picker_failed(
                "No se pudo abrir el selector de archivos. La aplicación continúa abierta."
            )
        finally:
            if result_path is not None:
                result_path.unlink(missing_ok=True)

    def _file_picker_process_error(self, error: QProcess.ProcessError) -> None:
        if error != QProcess.ProcessError.FailedToStart:
            return
        result_path = self._picker_result_path
        self._picker_result_path = None
        self._picker_process = None
        if result_path is not None:
            result_path.unlink(missing_ok=True)
        self._file_picker_failed(
            "No se pudo iniciar el selector de archivos. La aplicación continúa abierta."
        )

    @Slot(object)
    def _files_selected(self, paths: list[str]) -> None:
        if not paths:
            self.documentBatchStateChanged.emit(False, "")
            return
        self._begin_document_batch(list(paths))

    @Slot(str)
    def _file_picker_failed(self, message: str) -> None:
        self.documentBatchStateChanged.emit(False, "")
        self._emit_document_error(message)

    def _begin_document_batch(self, paths: list[str]) -> None:
        if not paths:
            return
        if len(paths) != 3:
            self.documentBatchStateChanged.emit(False, "")
            self._emit_document_error(
                f"Seleccione exactamente tres PDF en la misma ventana; eligió {len(paths)}."
            )
            return
        try:
            canonical = [str(Path(path).resolve()).casefold() for path in paths]
        except OSError:
            self.documentBatchStateChanged.emit(False, "")
            self._emit_document_error("No se pudo acceder a uno de los archivos elegidos.")
            return
        if len(set(canonical)) != 3:
            self.documentBatchStateChanged.emit(False, "")
            self._emit_document_error("Los tres PDF deben ser archivos diferentes.")
            return

        self._reports = [None, None, None]
        self._round_confirmed = False
        self._analyses.clear()
        self._result = None
        self._emit_state()
        self.documentBatchStateChanged.emit(
            True, "Validando los tres PDF en este computador…"
        )
        worker = DocumentBatchWorker(paths)
        worker.signals.completed.connect(self._document_batch_completed)
        worker.signals.failed.connect(self._document_batch_failed)
        self._batch_worker = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(bool, name="validateDocuments")
    def validate_documents(self, allow_mismatch: bool = False) -> None:
        if any(report is None or not report.valid for report in self._reports):
            payload = {
                "valid": False,
                "requires_confirmation": False,
                "warnings": ["Se requieren exactamente tres PDF válidos."],
                "allocation_round": self._allocation_round(),
            }
            self.documentValidationUpdated.emit(_json(payload))
            return
        reports = [report for report in self._reports if report is not None]
        compatible, warnings = compare_allocation_rounds(reports)
        accepted = compatible or allow_mismatch
        self._round_confirmed = accepted
        payload = {
            "valid": accepted,
            "requires_confirmation": not compatible and not allow_mismatch,
            "warnings": warnings,
            "allocation_round": self._allocation_round(),
        }
        self.documentValidationUpdated.emit(_json(payload))
        self._emit_state()

    @Slot(str, str, str, name="searchDoctor")
    def search_doctor(self, id_type: str, id_number: str, full_name: str) -> None:
        normalized = normalize_id(id_number)
        if not 5 <= len(normalized) <= 15:
            self.processingFailed.emit("La identificación debe contener entre 5 y 15 dígitos.")
            return
        if not self._round_confirmed:
            self.processingFailed.emit("Los tres documentos deben validarse antes de consultar.")
            return
        if self._worker is not None:
            self.processingFailed.emit("Ya hay una consulta en curso.")
            return
        paths = [report.info.path for report in self._reports if report is not None]
        worker = SearchWorker(
            paths,
            DoctorQuery(
                id_number=normalized,
                id_type=id_type.strip().upper(),
                full_name=full_name.strip(),
            ),
        )
        worker.signals.stage.connect(self.processingStageChanged)
        worker.signals.completed.connect(self._search_completed)
        worker.signals.failed.connect(self._search_failed)
        self._worker = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(name="resetApplication")
    def reset_application(self) -> None:
        self._reports = [None, None, None]
        self._round_confirmed = False
        self._analyses.clear()
        self._result = None
        self._emit_state()

    @Slot(object)
    def _document_batch_completed(self, reports: list[ValidationReport]) -> None:
        self._batch_worker = None
        self._reports = arrange_reports(reports)
        for slot, report in enumerate(self._reports):
            self.documentSelected.emit(
                slot, _json(document_payload(report, slot)) if report else "null"
            )
        self.documentBatchStateChanged.emit(False, "")
        self._emit_state()

    @Slot(str)
    def _document_batch_failed(self, message: str) -> None:
        self._batch_worker = None
        self.documentBatchStateChanged.emit(False, "")
        self._emit_document_error(message)

    def _emit_document_error(self, message: str) -> None:
        self.documentValidationUpdated.emit(
            _json(
                {
                    "valid": False,
                    "requires_confirmation": False,
                    "warnings": [message],
                    "allocation_round": self._allocation_round(),
                }
            )
        )

    @Slot(name="exportResult")
    def export_current_result(self) -> None:
        if self._result is None:
            self.exportCompleted.emit("No hay un resultado para exportar.")
            return
        default = str(Path.home() / "resultado_ruralfindme.txt")
        path, _ = QFileDialog.getSaveFileName(
            self.parent_window, "Exportar resumen", default, "Archivo de texto (*.txt)"
        )
        if path:
            try:
                export_result(self._result, path)
            except (OSError, ValueError) as exc:
                log_exception("Result export failure", exc)
                self.exportCompleted.emit(
                    "No fue posible exportar el resumen en la ubicación seleccionada."
                )
                return
            self.exportCompleted.emit("Resumen exportado con la identificación enmascarada.")

    @Slot(name="copyResult")
    def copy_current_result(self) -> None:
        if self._result is None:
            self.exportCompleted.emit("No hay un resultado para copiar.")
            return
        QApplication.clipboard().setText(format_result(self._result))
        self.exportCompleted.emit("Resultado copiado con la identificación enmascarada.")

    @Slot(bool, bool, name="updatePreferences")
    def update_preferences(self, sound_enabled: bool, reduced_animation: bool) -> None:
        self.settings.sound_enabled = sound_enabled
        self.settings.reduced_animation = reduced_animation
        self._emit_state()

    @Slot(name="notifyReveal")
    def notify_reveal(self) -> None:
        play_reveal(self.settings.sound_enabled)

    @Slot(object, object)
    def _search_completed(
        self, analyses: list[DocumentAnalysis], result: SearchResult
    ) -> None:
        self._worker = None
        self._analyses = analyses
        self._result = result
        for report in self._reports:
            if report is None:
                continue
            matching = next(
                (
                    analysis
                    for analysis in analyses
                    if analysis.info.filename == report.info.filename
                ),
                None,
            )
            if matching:
                report.info.record_count = matching.info.record_count
        self._emit_state()
        self.searchCompleted.emit(_json(result_payload(result, analyses)))

    @Slot(str)
    def _search_failed(self, message: str) -> None:
        self._worker = None
        self.processingFailed.emit(message)

    def _allocation_round(self) -> str:
        rounds = {
            report.info.allocation_round
            for report in self._reports
            if report and report.info.allocation_round
        }
        return next(iter(rounds)) if len(rounds) == 1 else ""

    def _emit_state(self) -> None:
        payload = {
            "documents": [
                document_payload(report, index) if report else None
                for index, report in enumerate(self._reports)
            ],
            "can_continue": all(report and report.valid for report in self._reports),
            "allocation_round": self._allocation_round(),
            "sound_enabled": self.settings.sound_enabled,
            "reduced_animation": self.settings.reduced_animation,
        }
        self.stateSnapshot.emit(_json(payload))

    def clear_sensitive_state(self) -> None:
        if self._picker_process is not None:
            self._picker_process.kill()
            self._picker_process = None
        if self._picker_result_path is not None:
            self._picker_result_path.unlink(missing_ok=True)
            self._picker_result_path = None
        self._reports = [None, None, None]
        self._analyses.clear()
        self._result = None
        self._round_confirmed = False
