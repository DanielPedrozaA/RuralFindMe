from copy import deepcopy

from app.models import DoctorRecord, RecordStatus, ResultType
from app.search import DoctorQuery, search_records


def test_assigned_doctor(assigned_record):
    result = search_records([assigned_record], DoctorQuery("900.000.001", "CC"))
    assert result.result_type is ResultType.ASSIGNED


def test_canonical_anonymized_fixture_matches_assigned_flow(anonymized_records):
    data = anonymized_records["assigned"]
    record = DoctorRecord(
        full_name=data["full_name"],
        id_type=data["id_type"],
        id_number=data["id_number"],
        normalized_id_number=data["id_number"],
        vacancy_code=data["vacancy_code"],
        institution=data["institution"],
        detected_status=RecordStatus.ASSIGNED,
        confidence=0.99,
        source_file="fixture.pdf",
        source_page=1,
    )
    result = search_records([record], DoctorQuery(data["id_number"], data["id_type"]))
    assert result.result_type is ResultType.ASSIGNED


def test_explicitly_non_selected_doctor():
    record = DoctorRecord(
        id_type="CC",
        id_number="900000002",
        normalized_id_number="900000002",
        official_status="No seleccionado",
        detected_status=RecordStatus.NOT_SELECTED,
        confidence=0.97,
        source_file="sin_plaza_prueba.pdf",
        source_page=1,
    )
    result = search_records([record], DoctorQuery("900000002"))
    assert result.result_type is ResultType.NOT_SELECTED
    assert result.primary_record.official_status == "No seleccionado"


def test_exempt_wording_is_preserved_not_invented():
    record = DoctorRecord(
        id_type="CE",
        id_number="900000003",
        normalized_id_number="900000003",
        official_status="Exonerada",
        detected_status=RecordStatus.EXEMPT,
        confidence=0.96,
        source_file="sin_plaza_prueba.pdf",
        source_page=1,
    )
    result = search_records([record], DoctorQuery("900000003"))
    assert result.result_type is ResultType.EXEMPT
    assert result.primary_record.official_status == "Exonerada"


def test_doctor_not_found_is_not_called_exempt(assigned_record):
    result = search_records([assigned_record], DoctorQuery("900000099"))
    assert result.result_type is ResultType.NOT_FOUND
    assert any("no demuestra" in reason.lower() for reason in result.reasons)


def test_conflicting_statuses_are_ambiguous(assigned_record):
    conflict = deepcopy(assigned_record)
    conflict.detected_status = RecordStatus.NOT_SELECTED
    conflict.official_status = "Sin plaza asignada"
    conflict.source_file = "sin_plaza_prueba.pdf"
    result = search_records([assigned_record, conflict], DoctorQuery("900000001"))
    assert result.result_type is ResultType.AMBIGUOUS
    assert len(result.evidence) == 2


def test_duplicate_records_do_not_create_false_conflict(assigned_record):
    duplicate = deepcopy(assigned_record)
    result = search_records([assigned_record, duplicate], DoctorQuery("900000001"))
    assert result.result_type is ResultType.ASSIGNED


def test_multiple_assignments_are_ambiguous(assigned_record):
    second = deepcopy(assigned_record)
    second.vacancy_code = "9900000000011-2"
    second.source_page = 3
    result = search_records([assigned_record, second], DoctorQuery("900000001"))
    assert result.result_type is ResultType.AMBIGUOUS


def test_name_and_id_disagreement_is_ambiguous(assigned_record):
    result = search_records(
        [assigned_record], DoctorQuery("900000001", "CC", "OTRA PERSONA PRUEBA")
    )
    assert result.result_type is ResultType.AMBIGUOUS


def test_search_does_not_use_partial_id_match(assigned_record):
    result = search_records([assigned_record], DoctorQuery("90000000"))
    assert result.result_type is ResultType.NOT_FOUND
