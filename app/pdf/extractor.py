from __future__ import annotations

from dataclasses import dataclass

import fitz

from app.pdf.ocr import ocr_page


@dataclass
class PageContent:
    page_number: int
    text: str
    used_ocr: bool = False


def extract_pages(document: fitz.Document, allow_ocr: bool = True) -> list[PageContent]:
    pages: list[PageContent] = []
    for number, page in enumerate(document, start=1):
        text = page.get_text("text")
        used_ocr = False
        if allow_ocr and len(text.strip()) < 20 and page.get_images(full=True):
            text = ocr_page(page)
            used_ocr = True
        pages.append(PageContent(number, text, used_ocr))
    return pages
