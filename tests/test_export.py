import pytest

from app.export import export_result, format_result
from app.models import ResultType, SearchResult


def test_export_masks_identification_by_default(assigned_record):
    result = SearchResult(
        ResultType.ASSIGNED,
        primary_record=assigned_record,
        evidence=[assigned_record],
        searched_id="900000001",
    )
    exported = format_result(result)
    assert "900000001" not in exported
    assert "900.***.001" in exported


def test_export_validates_destination_and_adds_text_suffix(tmp_path, assigned_record):
    result = SearchResult(ResultType.ASSIGNED, primary_record=assigned_record, searched_id="900000001")
    destination = export_result(result, str(tmp_path / "resultado"))
    assert destination.suffix == ".txt"
    assert destination.parent == tmp_path.resolve()


def test_export_rejects_missing_parent(tmp_path, assigned_record):
    result = SearchResult(ResultType.ASSIGNED, primary_record=assigned_record, searched_id="900000001")
    with pytest.raises(ValueError, match="carpeta"):
        export_result(result, str(tmp_path / "missing" / "resultado.txt"))
