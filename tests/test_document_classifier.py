from app.models import DocumentCategory
from app.pdf.document_classifier import classify_document_text


def test_allocation_date_is_selected_near_document_title():
    text = """Aviso legal actualizado el 01/01/2020
Texto introductorio
Reporte de Plazas Asignadas
Ronda de asignación: 16/04/2026
MEDICINA
"""
    category, _title, date, profession = classify_document_text(text)
    assert category is DocumentCategory.ASSIGNED
    assert date == "16/04/2026"
    assert profession == "MEDICINA"
