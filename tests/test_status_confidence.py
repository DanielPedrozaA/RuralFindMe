import pytest

from app.models import DocumentCategory, DoctorRecord, RecordStatus
from app.search.confidence import (
    HIGH_CONFIDENCE_THRESHOLD,
    MANUAL_REVIEW_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    confidence_label,
    score_record,
)
from app.search.status_classifier import detect_record_status


@pytest.mark.parametrize(
    ("text", "category", "expected"),
    [
        ("No seleccionado", DocumentCategory.ASSIGNED, RecordStatus.NOT_SELECTED),
        ("Profesional exonerada", DocumentCategory.WITHOUT_POSITION, RecordStatus.EXEMPT),
        ("Plaza vacante", DocumentCategory.UNKNOWN, RecordStatus.VACANT),
        ("Pendiente de revisión", DocumentCategory.ASSIGNED, RecordStatus.UNKNOWN),
        ("Sin texto explícito", DocumentCategory.ASSIGNED, RecordStatus.ASSIGNED),
    ],
)
def test_status_keyword_precedence_and_category_fallback(text, category, expected):
    assert detect_record_status(text, category) is expected


def test_confidence_thresholds_are_consistent():
    assert confidence_label(HIGH_CONFIDENCE_THRESHOLD) == "Alta"
    assert confidence_label(MEDIUM_CONFIDENCE_THRESHOLD) == "Media"
    assert confidence_label(MANUAL_REVIEW_THRESHOLD) == "Baja"


def test_assigned_record_score_uses_available_evidence(assigned_record):
    assert score_record(assigned_record) == pytest.approx(0.99)
    sparse = DoctorRecord(detected_status=RecordStatus.ASSIGNED)
    assert score_record(sparse) == pytest.approx(0.55)
