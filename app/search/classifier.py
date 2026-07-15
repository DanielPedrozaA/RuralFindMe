from __future__ import annotations

from app.models import DoctorRecord, RecordStatus, ResultType, SearchResult
from app.search.confidence import MANUAL_REVIEW_THRESHOLD


def classify_matches(
    matches: list[DoctorRecord],
    searched_id: str,
    query_name: str = "",
    id_type: str = "",
) -> SearchResult:
    if not matches:
        return SearchResult(
            ResultType.NOT_FOUND,
            reasons=[
                "El número de identificación no aparece en los registros reconstruidos de los tres PDF.",
                "Esto no demuestra una exoneración ni define por sí solo una situación legal.",
                "Posibles causas: número incorrecto, PDF faltante o ronda equivocada.",
                "También puede tratarse de una publicación incompleta, un fallo de extracción, "
                "un escaneo que requiere OCR o una persona que no figura en estas listas.",
            ],
            searched_id=searched_id,
            query_name=query_name,
        )

    unique: list[DoctorRecord] = []
    seen: set[tuple[str, str, str, str, int]] = set()
    for record in matches:
        key = (
            record.normalized_id_number or "",
            record.vacancy_code or "",
            record.detected_status.value,
            record.source_file,
            record.source_page,
        )
        if key not in seen:
            seen.add(key)
            unique.append(record)

    statuses = {record.detected_status for record in unique}
    reasons: list[str] = []
    if len(statuses) > 1:
        reasons.append("El mismo número aparece con estados incompatibles.")
    if len(unique) > 1:
        reasons.append("Se reconstruyó más de un registro para el mismo número.")
    if id_type and any(
        record.id_type and record.id_type.upper() != id_type.upper() for record in unique
    ):
        reasons.append("El tipo de identificación indicado no coincide con el documento.")
    normalized_query_name = query_name.strip()
    if normalized_query_name and any(
        record.normalized_name
        and record.normalized_name != normalized_query_name
        for record in unique
    ):
        reasons.append("El nombre indicado no coincide con el nombre del registro.")
    if any(record.confidence < MANUAL_REVIEW_THRESHOLD for record in unique):
        reasons.append("La extracción tiene confianza baja y requiere revisión manual.")
    if reasons:
        return SearchResult(
            ResultType.AMBIGUOUS,
            primary_record=unique[0],
            evidence=unique,
            reasons=reasons,
            searched_id=searched_id,
            query_name=query_name,
        )

    record = unique[0]
    if record.detected_status is RecordStatus.ASSIGNED:
        result_type = ResultType.ASSIGNED
    elif record.detected_status is RecordStatus.EXEMPT:
        result_type = ResultType.EXEMPT
    elif record.detected_status is RecordStatus.NOT_SELECTED:
        result_type = ResultType.NOT_SELECTED
    else:
        result_type = ResultType.AMBIGUOUS
        reasons.append("El registro existe, pero su estado no se pudo clasificar.")
    return SearchResult(
        result_type,
        primary_record=record,
        evidence=unique,
        reasons=reasons,
        searched_id=searched_id,
        query_name=query_name,
    )
