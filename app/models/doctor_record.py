from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RecordStatus(str, Enum):
    ASSIGNED = "ASSIGNED"
    EXEMPT = "EXEMPT"
    NOT_SELECTED = "NOT_SELECTED"
    VACANT = "VACANT"
    UNKNOWN = "UNKNOWN"


@dataclass
class DoctorRecord:
    full_name: Optional[str] = None
    normalized_name: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    normalized_id_number: Optional[str] = None
    official_status: Optional[str] = None
    detected_status: RecordStatus = RecordStatus.UNKNOWN
    institution: Optional[str] = None
    hospital: Optional[str] = None
    municipality: Optional[str] = None
    department: Optional[str] = None
    vacancy_code: Optional[str] = None
    profession: Optional[str] = None
    reps_code: Optional[str] = None
    reps_site: Optional[str] = None
    modality: Optional[str] = None
    assignment_date: Optional[str] = None
    start_date: Optional[str] = None
    duration: Optional[str] = None
    contact: Optional[str] = None
    observations: Optional[str] = None
    source_file: str = ""
    source_page: int = 0
    raw_text: str = ""
    confidence: float = 0.0

    def identity_key(self) -> tuple[str, str, str]:
        return (
            self.normalized_id_number or "",
            self.vacancy_code or "",
            self.detected_status.value,
        )
