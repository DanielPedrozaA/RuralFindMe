from app.models import DocumentCategory, RecordStatus
from app.pdf.table_parser import TableParser


ASSIGNED_HEADER = [
    "Código Plaza",
    "Tipo identificación profesional asignado",
    "Número de identificación profesional asignado",
    "Nombre Departamento",
    "Nombre Municipio",
    "Profesión",
    "Código de Habilitación (REPS)",
    "Número Sede (REPS)",
    "Nombre de la IPS - Sede",
]


def assigned_row(identifier="900000010", institution="ESE HOSPITAL DE PRUEBA"):
    return [
        "9900000000011-1",
        "CC",
        identifier,
        "DPTO PRUEBA",
        "MUNICIPIO PRUEBA",
        "Medicina",
        "9900000000",
        "01",
        institution,
    ]


def test_repeated_headers_are_ignored():
    rows = [ASSIGNED_HEADER, assigned_row(), ASSIGNED_HEADER, assigned_row("900000011")]
    records = TableParser().parse_table_rows(
        rows, DocumentCategory.ASSIGNED, "asignadas_prueba.pdf", 1
    )
    assert [record.normalized_id_number for record in records] == ["900000010", "900000011"]


def test_rows_divided_across_lines_are_reconstructed_in_cells():
    row = assigned_row(institution="ESE HOSPITAL\nSEDE DE PRUEBA")
    records = TableParser().parse_table_rows(
        [ASSIGNED_HEADER, row], DocumentCategory.ASSIGNED, "asignadas_prueba.pdf", 1
    )
    assert records[0].institution == "ESE HOSPITAL SEDE DE PRUEBA"
    assert records[0].detected_status is RecordStatus.ASSIGNED


def test_rows_divided_across_pages_keep_continuation_evidence():
    parser = TableParser()
    records = parser.parse_table_rows(
        [ASSIGNED_HEADER, assigned_row()],
        DocumentCategory.ASSIGNED,
        "asignadas_prueba.pdf",
        1,
    )
    parser.parse_table_rows(
        [ASSIGNED_HEADER, ["", "", "", "", "", "", "", "", "CONTINÚA EN PÁGINA 2"]],
        DocumentCategory.ASSIGNED,
        "asignadas_prueba.pdf",
        2,
        records,
    )
    assert "CONTINÚA EN PÁGINA 2" in records[0].raw_text


def test_column_order_is_driven_by_headers():
    header = [ASSIGNED_HEADER[2], ASSIGNED_HEADER[1], ASSIGNED_HEADER[0], *ASSIGNED_HEADER[3:]]
    row = ["900000012", "CC", "9900000000011-2", *assigned_row()[3:]]
    records = TableParser().parse_table_rows(
        [header, row], DocumentCategory.ASSIGNED, "asignadas_prueba.pdf", 1
    )
    assert records[0].normalized_id_number == "900000012"
    assert records[0].vacancy_code == "9900000000011-2"


def test_without_position_document_uses_explicit_category_status():
    rows = [["Tipo identificación", "Número de identificación"], ["CC", "900000013"]]
    records = TableParser().parse_table_rows(
        rows, DocumentCategory.WITHOUT_POSITION, "sin_plaza_prueba.pdf", 1
    )
    assert records[0].official_status == "Profesional sin plaza asignada"
    assert records[0].detected_status is RecordStatus.NOT_SELECTED


def test_explicit_exemption_column_is_preserved_from_configuration():
    rows = [
        ["Tipo identificación", "Número de identificación", "Estado"],
        ["CE", "900000014", "Exonerada"],
    ]
    records = TableParser().parse_table_rows(
        rows, DocumentCategory.WITHOUT_POSITION, "sin_plaza_prueba.pdf", 1
    )
    assert records[0].official_status == "Exonerada"
    assert records[0].detected_status is RecordStatus.EXEMPT


def test_footer_and_excess_continuations_are_not_added_to_evidence():
    rows = [
        ASSIGNED_HEADER,
        assigned_row(),
        ["", "", "", "", "", "", "", "", "Primera continuación"],
        ["", "", "", "", "", "", "", "", "Segunda continuación"],
        ["", "", "", "", "", "", "", "", "Tercera continuación"],
        ["", "", "", "", "", "", "", "", "Página 1 de 2"],
    ]
    record = TableParser().parse_table_rows(
        rows, DocumentCategory.ASSIGNED, "asignadas_prueba.pdf", 1
    )[0]
    assert "Primera continuación" in record.raw_text
    assert "Segunda continuación" in record.raw_text
    assert "Tercera continuación" not in record.raw_text
    assert "Página 1 de 2" not in record.raw_text
