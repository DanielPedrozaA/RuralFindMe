from __future__ import annotations

from pathlib import Path

import fitz

from app.config import load_json_config
from app.models import DocumentInfo, ValidationReport
from app.pdf.document_classifier import classify_document_text
from app.pdf.ocr import tesseract_available


def validate_pdf(path: str) -> ValidationReport:
    candidate = Path(path)
    info = DocumentInfo(
        path=str(candidate),
        filename=candidate.name,
    )
    errors: list[str] = []
    warnings: list[str] = []

    try:
        if not candidate.is_file():
            return ValidationReport(False, info, ["El archivo no existe o no es accesible."], [])
        info.size_bytes = candidate.stat().st_size
    except OSError:
        return ValidationReport(False, info, ["El archivo no existe o no es accesible."], [])
    if candidate.suffix.lower() != ".pdf":
        return ValidationReport(False, info, ["El archivo no tiene extensión PDF."], [])

    try:
        document = fitz.open(candidate)
    except (fitz.FileDataError, RuntimeError, ValueError, OSError):
        return ValidationReport(False, info, ["PDF dañado, vacío o no válido."], [])

    try:
        if document.needs_pass:
            errors.append("El PDF está protegido con contraseña.")
            return ValidationReport(False, info, errors, warnings)
        info.page_count = document.page_count
        if not info.page_count:
            errors.append("El PDF no contiene páginas.")
            return ValidationReport(False, info, errors, warnings)

        preview_parts: list[str] = []
        total_text = 0
        total_images = 0
        for index, page in enumerate(document):
            page_text = page.get_text("text")
            total_text += len(page_text.strip())
            total_images += len(page.get_images(full=True))
            if index < 2:
                preview_parts.append(page_text)

        threshold = int(
            load_json_config("parser_config.json").get(
                "minimum_text_characters_per_document", 40
            )
        )
        info.has_selectable_text = total_text >= threshold
        info.image_only = total_text < threshold and total_images > 0
        if total_text < threshold:
            if info.image_only and tesseract_available():
                warnings.append("PDF basado en imágenes; se usará OCR local con Tesseract.")
            elif info.image_only:
                errors.append(
                    "El PDF parece escaneado y no hay texto utilizable. Instale Tesseract para OCR local."
                )
            else:
                errors.append("El PDF está vacío o no contiene texto utilizable.")

        preview = "\n".join(preview_parts)
        category, title, date, profession = classify_document_text(preview)
        info.category = category
        info.title = title
        info.allocation_date = date
        info.allocation_round = date
        info.profession = profession
        # The supplied exports show the Colombian "Salud" mark as an image; it is not
        # promoted to a more specific institution name that the text does not contain.
        info.institution = "Salud (identidad visual del documento)"
        if not date:
            warnings.append("No se detectó una fecha de asignación en el texto.")
        if category.value == "DESCONOCIDO":
            warnings.append("El título no coincide con una categoría configurada.")
    finally:
        document.close()

    return ValidationReport(not errors, info, errors, warnings)
