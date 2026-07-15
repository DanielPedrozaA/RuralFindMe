from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from app.models import DoctorRecord, RecordStatus


@pytest.fixture
def anonymized_records() -> dict:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "anonymized_records.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


@pytest.fixture
def assigned_record() -> DoctorRecord:
    return DoctorRecord(
        full_name="ANA MARÍA PRUEBA LÓPEZ",
        normalized_name="ANA MARIA PRUEBA LOPEZ",
        id_type="CC",
        id_number="900000001",
        normalized_id_number="900000001",
        official_status="Plaza asignada",
        detected_status=RecordStatus.ASSIGNED,
        institution="ESE HOSPITAL DE PRUEBA",
        municipality="MUNICIPIO PRUEBA",
        department="DEPARTAMENTO PRUEBA",
        vacancy_code="9900000000011-1",
        profession="Medicina",
        source_file="asignadas_prueba.pdf",
        source_page=2,
        raw_text="Fila anonimizada de prueba",
        confidence=0.98,
    )


@pytest.fixture
def make_text_pdf(tmp_path):
    def factory(name: str, text: str, password: str = ""):
        path = tmp_path / name
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), text)
        if password:
            document.save(
                path,
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw="propietario-prueba",
                user_pw=password,
            )
        else:
            document.save(path)
        document.close()
        return path

    return factory
