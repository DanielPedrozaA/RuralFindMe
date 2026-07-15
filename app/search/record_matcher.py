from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from rapidfuzz.fuzz import ratio

from app.config import load_json_config
from app.models import DoctorRecord, SearchResult
from app.search.classifier import classify_matches
from app.search.normalizer import normalize_id, normalize_name


@dataclass(frozen=True)
class DoctorQuery:
    id_number: str
    id_type: str = ""
    full_name: str = ""
    location: str = ""


def search_records(
    records: list[DoctorRecord],
    query: DoctorQuery,
    stage_callback: Callable[[str], None] | None = None,
) -> SearchResult:
    normalized_id = normalize_id(query.id_number)
    normalized_name = normalize_name(query.full_name)

    # Equality on normalized fields enforces complete-token matching. No contains
    # operation is used, so one ID cannot match a longer ID.
    exact_id = [record for record in records if record.normalized_id_number == normalized_id]
    if exact_id:
        if stage_callback:
            stage_callback("VERIFYING_EVIDENCE")
            stage_callback("CLASSIFYING_RESULT")
        result = classify_matches(
            exact_id, normalized_id, normalized_name, query.id_type.strip().upper()
        )
        return result

    if normalized_name:
        exact_names = [record for record in records if record.normalized_name == normalized_name]
        if exact_names:
            if stage_callback:
                stage_callback("VERIFYING_EVIDENCE")
                stage_callback("CLASSIFYING_RESULT")
            result = classify_matches(exact_names, normalized_id, normalized_name, query.id_type)
            result.reasons.append("Coincidencia secundaria por nombre; el número no coincidió.")
            if result.result_type.value != "AMBIGUOUS":
                from app.models import ResultType
                result.result_type = ResultType.AMBIGUOUS
            return result

        threshold = int(load_json_config("parser_config.json")["fuzzy_name_threshold"])
        fuzzy = [
            record
            for record in records
            if record.normalized_name
            and ratio(record.normalized_name, normalized_name) >= threshold
        ]
        if fuzzy:
            if stage_callback:
                stage_callback("VERIFYING_EVIDENCE")
                stage_callback("CLASSIFYING_RESULT")
            result = classify_matches(fuzzy, normalized_id, normalized_name, query.id_type)
            from app.models import ResultType
            result.result_type = ResultType.AMBIGUOUS
            result.reasons.append("Coincidencia aproximada por nombre; verifique manualmente.")
            return result

    if stage_callback:
        stage_callback("VERIFYING_EVIDENCE")
        stage_callback("CLASSIFYING_RESULT")
    return classify_matches([], normalized_id, normalized_name, query.id_type)
