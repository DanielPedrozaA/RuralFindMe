from __future__ import annotations

import fitz

from app.models import DocumentCategory, DocumentInfo
from app.pdf.document_classifier import compare_allocation_rounds
from app.pdf.validator import validate_pdf


def test_corrupted_pdf(tmp_path):
    path = tmp_path / "corrupto.pdf"
    path.write_bytes(b"esto no es un PDF")
    report = validate_pdf(str(path))
    assert not report.valid
    assert any("dañado" in error.lower() or "válido" in error.lower() for error in report.errors)


def test_password_protected_pdf(make_text_pdf):
    path = make_text_pdf("protegido.pdf", "Reporte de Plazas Asignadas 16/04/2026", "secreto")
    report = validate_pdf(str(path))
    assert not report.valid
    assert any("contraseña" in error for error in report.errors)


def test_empty_pdf(tmp_path):
    path = tmp_path / "vacio.pdf"
    document = fitz.open()
    document.new_page()
    document.save(path)
    document.close()
    report = validate_pdf(str(path))
    assert not report.valid
    assert any("vacío" in error.lower() or "texto utilizable" in error.lower() for error in report.errors)


def test_image_only_pdf_is_detected(tmp_path, monkeypatch):
    path = tmp_path / "imagen.pdf"
    document = fitz.open()
    page = document.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), False)
    pix.clear_with(0x77AABB)
    page.insert_image(fitz.Rect(72, 72, 200, 200), stream=pix.tobytes("png"))
    document.save(path)
    document.close()
    monkeypatch.setattr("app.pdf.validator.tesseract_available", lambda: False)
    report = validate_pdf(str(path))
    assert report.info.image_only
    assert not report.valid


def info(category, date):
    return DocumentInfo("prueba.pdf", category=category, allocation_date=date, profession="MEDICINA")


def test_pdfs_from_different_rounds_are_rejected():
    compatible, warnings = compare_allocation_rounds(
        [
            info(DocumentCategory.ASSIGNED, "16/04/2026"),
            info(DocumentCategory.VACANT, "16/04/2026"),
            info(DocumentCategory.WITHOUT_POSITION, "17/04/2026"),
        ]
    )
    assert not compatible
    assert any("fechas" in warning.lower() for warning in warnings)


def test_matching_round_and_three_categories():
    compatible, warnings = compare_allocation_rounds(
        [
            info(DocumentCategory.ASSIGNED, "16/04/2026"),
            info(DocumentCategory.VACANT, "16/04/2026"),
            info(DocumentCategory.WITHOUT_POSITION, "16/04/2026"),
        ]
    )
    assert compatible
    assert warnings == []
