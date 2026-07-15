from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

from app.diagnostics import install_diagnostics


SOFTWARE_RENDERING = os.environ.get("RURALFINDME_SOFTWARE_RENDERING", "").lower() in {
    "1",
    "true",
    "yes",
}


def _configure_safe_rendering() -> None:
    """Enable the opt-in software fallback for incompatible GPU drivers."""

    if not SOFTWARE_RENDERING:
        return
    os.environ.setdefault("QT_OPENGL", "software")
    existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    required = ("--disable-gpu", "--disable-gpu-compositing", "--disable-features=Vulkan")
    additions = [flag for flag in required if flag not in existing]
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(
        part for part in (existing, *additions) if part
    )


_configure_safe_rendering()
install_diagnostics()

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from app import __version__
from app.config import resource_path

QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
if SOFTWARE_RENDERING:
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL)


def is_valid_picker_target(result_name: str) -> bool:
    try:
        target = Path(result_name).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return (
        target.parent == temp_root
        and target.name.startswith("ruralfindme-picker-")
        and target.suffix == ".json"
    )


def file_picker_helper(result_name: str) -> int:
    """Isolated dialog mode used by the main process to avoid WebEngine/COM crashes."""

    try:
        if not is_valid_picker_target(result_name):
            return 2
        target = Path(result_name).resolve()
        app = QApplication([sys.argv[0]])
        app.setApplicationName("RuralFindMe — Seleccionar PDF")
        dialog = QFileDialog()
        dialog.setWindowTitle("Seleccionar los tres reportes PDF")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilter("Documentos PDF (*.pdf)")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        selected = dialog.selectedFiles() if accepted else []
        target.write_text(
            json.dumps(selected, ensure_ascii=False), encoding="utf-8"
        )
        return 0
    except (OSError, RuntimeError, ValueError):
        return 3


def main() -> int:
    from app.web_window import WebMainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("RuralFindMe")
    app.setApplicationDisplayName("RuralFindMe — ¿Dónde me tocó?")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("RuralFindMe")
    icon_path = resource_path("app/assets/app-icon.ico")
    if not icon_path.exists():
        icon_path = resource_path("app/assets/app-icon.svg")
    app.setWindowIcon(QIcon(str(icon_path)))
    window = WebMainWindow()
    window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    return app.exec()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--file-picker-helper":
        raise SystemExit(file_picker_helper(sys.argv[2]))
    raise SystemExit(main())
