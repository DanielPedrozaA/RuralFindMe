from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .doctor_record import DoctorRecord


class DocumentCategory(str, Enum):
    ASSIGNED = "PLAZAS_ASIGNADAS"
    VACANT = "PLAZAS_VACANTES"
    WITHOUT_POSITION = "PROFESIONALES_SIN_PLAZA"
    UNKNOWN = "DESCONOCIDO"

    @property
    def label(self) -> str:
        return {
            self.ASSIGNED: "Plazas asignadas",
            self.VACANT: "Plazas vacantes",
            self.WITHOUT_POSITION: "Profesionales sin plaza",
            self.UNKNOWN: "Documento no reconocido",
        }[self]


@dataclass
class DocumentInfo:
    path: str
    filename: str = ""
    size_bytes: int = 0
    page_count: int = 0
    category: DocumentCategory = DocumentCategory.UNKNOWN
    title: str = ""
    allocation_date: str = ""
    allocation_round: str = ""
    institution: str = ""
    profession: str = ""
    record_count: int = 0
    has_selectable_text: bool = False
    image_only: bool = False
    used_ocr: bool = False

    def __post_init__(self) -> None:
        if not self.filename and self.path:
            self.filename = Path(self.path).name


@dataclass
class ValidationReport:
    valid: bool
    info: DocumentInfo
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class DocumentAnalysis:
    info: DocumentInfo
    records: list[DoctorRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

