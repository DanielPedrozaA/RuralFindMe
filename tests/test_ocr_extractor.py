from types import SimpleNamespace

import fitz
import pytest

from app.pdf.extractor import extract_pages
from app.pdf.ocr import OCR_MAX_DIMENSION, ocr_page


class FakePixmap:
    def tobytes(self, _format: str) -> bytes:
        return b"png"


class FakePage:
    rect = SimpleNamespace(width=100_000, height=50_000)

    def __init__(self) -> None:
        self.matrix = None

    def get_pixmap(self, matrix, alpha=False):
        assert alpha is False
        self.matrix = matrix
        return FakePixmap()


def test_ocr_caps_large_page_raster_and_invokes_tesseract(monkeypatch):
    page = FakePage()
    monkeypatch.setattr("app.pdf.ocr.shutil.which", lambda _name: "tesseract")
    monkeypatch.setattr(
        "app.pdf.ocr.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="texto".encode(), stderr=b""),
    )
    assert ocr_page(page) == "texto"
    assert page.matrix.a * page.rect.width <= OCR_MAX_DIMENSION
    assert page.matrix.d * page.rect.height <= OCR_MAX_DIMENSION


def test_ocr_timeout_has_safe_message(monkeypatch):
    page = FakePage()
    monkeypatch.setattr("app.pdf.ocr.shutil.which", lambda _name: "tesseract")

    def timeout(*_args, **_kwargs):
        raise __import__("subprocess").TimeoutExpired("private-path", 120)

    monkeypatch.setattr("app.pdf.ocr.subprocess.run", timeout)
    with pytest.raises(RuntimeError, match="tiempo máximo") as error:
        ocr_page(page)
    assert "private-path" not in str(error.value)


def test_extract_pages_uses_ocr_only_for_image_page(monkeypatch):
    document = fitz.open()
    page = document.new_page()
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), False)
    page.insert_image(fitz.Rect(10, 10, 30, 30), stream=pixmap.tobytes("png"))
    monkeypatch.setattr("app.pdf.extractor.ocr_page", lambda _page: "texto por OCR")
    pages = extract_pages(document)
    document.close()
    assert pages[0].used_ocr is True
    assert pages[0].text == "texto por OCR"
