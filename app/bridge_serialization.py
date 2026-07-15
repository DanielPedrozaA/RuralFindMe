from __future__ import annotations

from typing import Any
import re

from app.models import DocumentAnalysis, DoctorRecord, SearchResult, ValidationReport
from app.search.confidence import confidence_label
from app.search.normalizer import mask_id, normalize_id


ID_LIKE_TOKEN = re.compile(r"(?<!\d)(?:\d[\s.\-]*){4,14}\d(?!\d)")


def _mask_identifier_in_text(text: str, identifier: str) -> str:
    target = normalize_id(identifier)
    if not target:
        return text

    def replace(match: re.Match[str]) -> str:
        return mask_id(target) if normalize_id(match.group(0)) == target else match.group(0)

    return ID_LIKE_TOKEN.sub(replace, text)


def document_payload(report: ValidationReport, slot: int) -> dict[str, Any]:
    info = report.info
    state = "ERROR" if report.errors else "WARNING" if report.warnings else "READY"
    return {
        "slot": slot,
        "filename": info.filename,
        "size_bytes": info.size_bytes,
        "page_count": info.page_count,
        "valid": report.valid,
        "validation_state": state,
        "category": info.category.value,
        "category_label": info.category.label,
        "allocation_round": info.allocation_round,
        "record_count": info.record_count,
        "warnings": list(report.warnings),
        "errors": list(report.errors),
    }


def record_payload(record: DoctorRecord) -> dict[str, Any]:
    identifier = record.normalized_id_number or record.id_number or ""
    raw_text = _mask_identifier_in_text(record.raw_text, identifier)
    optional = {
        "full_name": record.full_name,
        "masked_id": mask_id(identifier),
        "id_type": record.id_type,
        "official_status": record.official_status,
        "institution": record.institution,
        "municipality": record.municipality,
        "department": record.department,
        "vacancy_code": record.vacancy_code,
        "profession": record.profession,
        "reps_code": record.reps_code,
        "reps_site": record.reps_site,
        "modality": record.modality,
        "assignment_date": record.assignment_date,
        "start_date": record.start_date,
        "duration": record.duration,
        "contact": record.contact,
        "observations": record.observations,
        "raw_text": raw_text,
    }
    payload = {key: value for key, value in optional.items() if value not in (None, "")}
    payload.update(
        {
            "source_file": record.source_file,
            "source_page": record.source_page,
            "confidence": record.confidence,
            "confidence_label": confidence_label(record.confidence),
        }
    )
    return payload


def result_payload(
    result: SearchResult, analyses: list[DocumentAnalysis]
) -> dict[str, Any]:
    rounds = {
        analysis.info.allocation_round
        for analysis in analyses
        if analysis.info.allocation_round
    }
    allocation_round = next(iter(rounds)) if len(rounds) == 1 else ""
    return {
        "result_type": result.result_type.value,
        "masked_id": mask_id(result.searched_id),
        "allocation_round": allocation_round,
        "record": record_payload(result.primary_record) if result.primary_record else None,
        "evidence": [record_payload(record) for record in result.evidence],
        "reasons": list(result.reasons),
        "document_summary": list(result.documents_summary),
    }
