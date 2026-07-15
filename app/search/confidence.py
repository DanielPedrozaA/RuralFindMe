from __future__ import annotations

from app.models.doctor_record import DoctorRecord, RecordStatus


MANUAL_REVIEW_THRESHOLD = 0.60
MEDIUM_CONFIDENCE_THRESHOLD = 0.70
HIGH_CONFIDENCE_THRESHOLD = 0.90


def score_record(record: DoctorRecord) -> float:
    if record.detected_status is RecordStatus.ASSIGNED:
        score = 0.55
        score += 0.18 if record.normalized_id_number else 0
        score += 0.08 if record.id_type else 0
        score += 0.07 if record.vacancy_code else 0
        score += 0.06 if record.institution else 0
        score += 0.03 if record.municipality else 0
        score += 0.03 if record.department else 0
        return min(score, 0.99)
    if record.detected_status in (RecordStatus.EXEMPT, RecordStatus.NOT_SELECTED):
        score = 0.68
        score += 0.18 if record.normalized_id_number else 0
        score += 0.08 if record.id_type else 0
        score += 0.04 if record.official_status else 0
        return min(score, 0.98)
    if record.detected_status is RecordStatus.VACANT:
        score = 0.55
        score += 0.15 if record.vacancy_code else 0
        score += 0.12 if record.institution else 0
        score += 0.08 if record.municipality else 0
        score += 0.05 if record.department else 0
        return min(score, 0.95)
    return 0.4


def confidence_label(value: float) -> str:
    if value >= HIGH_CONFIDENCE_THRESHOLD:
        return "Alta"
    if value >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "Media"
    return "Baja"
