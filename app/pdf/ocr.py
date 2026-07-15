from __future__ import annotations

import shutil
import subprocess
from math import sqrt

import fitz


OCR_TARGET_SCALE = 2.2
OCR_MAX_DIMENSION = 8_000
OCR_MAX_PIXELS = 20_000_000
OCR_TIMEOUT_SECONDS = 120


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_page(page: fitz.Page, language: str = "spa") -> str:
    executable = shutil.which("tesseract")
    if not executable:
        raise RuntimeError("Tesseract no está instalado o no está en PATH.")
    width, height = page.rect.width, page.rect.height
    if width <= 0 or height <= 0:
        raise RuntimeError("La página no tiene dimensiones válidas para OCR.")
    scale = min(
        OCR_TARGET_SCALE,
        OCR_MAX_DIMENSION / width,
        OCR_MAX_DIMENSION / height,
        sqrt(OCR_MAX_PIXELS / (width * height)),
    )
    try:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = pixmap.tobytes("png")
    except (MemoryError, RuntimeError, ValueError) as exc:
        raise RuntimeError(
            "La página es demasiado grande o compleja para procesarla con OCR."
        ) from exc
    try:
        process = subprocess.run(
            [executable, "stdin", "stdout", "-l", language, "--psm", "6"],
            input=image,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("El OCR excedió el tiempo máximo permitido.") from exc
    if process.returncode:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Tesseract no pudo procesar la página: {detail}")
    return process.stdout.decode("utf-8", errors="replace")
