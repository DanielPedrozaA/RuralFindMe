from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import ResultType, SearchResult
from app.search.confidence import confidence_label
from app.search.normalizer import mask_id


STATUS_TITLES = {
    ResultType.ASSIGNED: "Encontramos una asignación",
    ResultType.EXEMPT: "El documento registra una exoneración",
    ResultType.NOT_SELECTED: "El documento registra una no selección o ausencia de plaza",
    ResultType.NOT_FOUND: "No se encontró el número",
    ResultType.AMBIGUOUS: "Resultado ambiguo — verificación manual requerida",
    ResultType.ERROR: "No fue posible completar la consulta",
}


class ExportPathError(ValueError):
    """Raised when an export destination is unsafe or unusable."""


def format_result(result: SearchResult) -> str:
    record = result.primary_record
    lines = [
        "RuralFindMe — Resumen de consulta",
        STATUS_TITLES[result.result_type],
        f"Identificación: {mask_id(result.searched_id)}",
    ]
    if record:
        fields = [
            ("Nombre", record.full_name),
            ("Estado oficial detectado", record.official_status),
            ("Institución / IPS", record.institution),
            ("Municipio", record.municipality),
            ("Departamento", record.department),
            ("Código de plaza", record.vacancy_code),
            ("Profesión", record.profession),
            ("Código REPS", record.reps_code),
            ("Sede REPS", record.reps_site),
            ("Modalidad", record.modality),
            ("Fecha de asignación", record.assignment_date),
            ("Fecha prevista de inicio", record.start_date),
            ("Duración", record.duration),
            ("Contacto", record.contact),
            ("Observaciones", record.observations),
            ("Fuente", record.source_file),
            ("Página", str(record.source_page) if record.source_page else None),
            (
                "Confianza",
                f"{confidence_label(record.confidence)} ({record.confidence:.0%})",
            ),
        ]
        lines.extend(f"{label}: {value}" for label, value in fields if value)
    if result.reasons:
        lines.append("Notas:")
        lines.extend(f"- {reason}" for reason in result.reasons)
    lines.extend(
        [
            "",
            "Herramienta no oficial. El resultado depende exclusivamente de los PDF cargados.",
            "No constituye certificación ni determina una exoneración legal.",
            f"Generado localmente: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ]
    )
    return "\n".join(lines)


def export_result(result: SearchResult, path: str) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ExportPathError("Seleccione una ruta de exportación válida.")
    destination = Path(path).expanduser()
    if destination.suffix.lower() != ".txt":
        destination = destination.with_suffix(".txt")
    try:
        parent = destination.parent.resolve(strict=True)
    except OSError as exc:
        raise ExportPathError("La carpeta de exportación no existe o no es accesible.") from exc
    if not parent.is_dir():
        raise ExportPathError("La carpeta de exportación no es válida.")
    destination = parent / destination.name
    if destination.exists() and (not destination.is_file() or destination.is_symlink()):
        raise ExportPathError("El destino de exportación no es un archivo de texto seguro.")
    destination.write_text(format_result(result), encoding="utf-8")
    return destination
