"""Create a fictitious 'profesionales sin plaza' PDF for UI demonstrations."""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz


DEMO_ID = "999999999999999"
DEMO_DATE = "16/04/2026"


def create_demo_pdf(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page(width=595, height=842)

    page.insert_text((52, 58), "RURALFINDME - DOCUMENTO FICTICIO DE DEMOSTRACION", fontsize=10)
    page.insert_text((52, 92), "Reporte de profesionales sin plaza asignada", fontsize=18)
    page.insert_text((52, 120), f"Ronda de asignacion: {DEMO_DATE}", fontsize=11)
    page.insert_text((52, 140), "Profesion: MEDICINA", fontsize=11)
    page.insert_text(
        (52, 166),
        "Todos los datos de esta pagina son ficticios y existen solo para probar la interfaz.",
        fontsize=9,
    )

    columns = [52, 140, 275, 455, 543]
    top, header_bottom, bottom = 200, 252, 304
    for x in columns:
        page.draw_line((x, top), (x, bottom), color=(0.15, 0.15, 0.15), width=0.8)
    for y in (top, header_bottom, bottom):
        page.draw_line((columns[0], y), (columns[-1], y), color=(0.15, 0.15, 0.15), width=0.8)

    headers = [
        "Tipo identificacion",
        "Numero de identificacion",
        "Nombre completo",
        "Estado",
    ]
    values = [
        "CC",
        DEMO_ID,
        "PERSONA FICTICIA DE DEMOSTRACION",
        "Sin plaza asignada",
    ]
    for index, text in enumerate(headers):
        page.insert_textbox(
            fitz.Rect(columns[index] + 5, top + 7, columns[index + 1] - 5, header_bottom - 5),
            text,
            fontsize=8,
            fontname="helv",
        )
    for index, text in enumerate(values):
        page.insert_textbox(
            fitz.Rect(columns[index] + 5, header_bottom + 9, columns[index + 1] - 5, bottom - 5),
            text,
            fontsize=8,
            fontname="helv",
        )

    page.insert_text(
        (52, 338),
        f"Para probar: cargue este PDF e ingrese la identificacion {DEMO_ID}.",
        fontsize=10,
    )
    document.set_metadata(
        {
            "title": "RuralFindMe - demo ficticia de profesional sin plaza",
            "subject": "Documento sintetico; no corresponde a una publicacion oficial",
        }
    )
    document.save(destination)
    document.close()
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path("fixtures/demo_profesionales_sin_plaza_16-04-2026.pdf"),
    )
    args = parser.parse_args()
    output = create_demo_pdf(args.output.resolve())
    print(f"Demo creada: {output}")
    print(f"Identificacion ficticia: {DEMO_ID}")


if __name__ == "__main__":
    main()
