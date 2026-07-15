from io import StringIO

from app import diagnostics


def test_diagnostics_log_omits_exception_values_and_absolute_paths(monkeypatch):
    output = StringIO()
    monkeypatch.setattr(diagnostics, "_HANDLE", output)
    try:
        raise OSError(r"C:\private\patient.pdf")
    except OSError as error:
        diagnostics.log_exception("worker failure", error)
    logged = output.getvalue()
    assert "OSError" in logged
    assert "worker failure" in logged
    assert "patient.pdf" not in logged
    assert "C:\\private" not in logged
