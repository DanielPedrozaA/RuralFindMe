from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .doctor_record import DoctorRecord


class ResultType(str, Enum):
    ASSIGNED = "ASSIGNED"
    EXEMPT = "EXEMPT"
    NOT_SELECTED = "NOT_SELECTED"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    ERROR = "ERROR"


@dataclass
class SearchResult:
    result_type: ResultType
    primary_record: Optional[DoctorRecord] = None
    evidence: list[DoctorRecord] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    searched_id: str = ""
    query_name: str = ""
    documents_summary: list[str] = field(default_factory=list)
