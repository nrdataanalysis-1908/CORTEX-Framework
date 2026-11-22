import pytest

from app import upload_validation


class FakePage:
    def __init__(self, fragments):
        self.fragments = fragments
        self.visited = False

    def extract_text(self, visitor_text):
        self.visited = True
        for fragment in self.fragments:
            visitor_text(fragment, None, None, None, None)


class FakeReader:
    def __init__(self, pages):
        self.pages = pages


def test_pdf_extraction_accepts_exact_per_page_and_document_limits(monkeypatch):
    monkeypatch.setattr(upload_validation, "MAX_PDF_PAGE_TEXT_CHARS", 3)
    monkeypatch.setattr(upload_validation, "MAX_EXTRACTED_TEXT_CHARS", 6)
    reader = FakeReader([FakePage(["ab", "c"]), FakePage(["de", "f"])])

    assert upload_validation._extract_pdf_text_bounded(reader) == "abc\ndef"


def test_pdf_extraction_rejects_per_page_overflow_during_callback(monkeypatch):
    monkeypatch.setattr(upload_validation, "MAX_PDF_PAGE_TEXT_CHARS", 3)
    monkeypatch.setattr(upload_validation, "MAX_EXTRACTED_TEXT_CHARS", 20)
    reader = FakeReader([FakePage(["ab", "cd"])])

    with pytest.raises(ValueError, match="Página 1 excede o limite de 3 caracteres"):
        upload_validation._extract_pdf_text_bounded(reader)


def test_pdf_extraction_rejects_document_overflow_before_later_page(monkeypatch):
    monkeypatch.setattr(upload_validation, "MAX_PDF_PAGE_TEXT_CHARS", 4)
    monkeypatch.setattr(upload_validation, "MAX_EXTRACTED_TEXT_CHARS", 5)
    later_page = FakePage(["x"])
    reader = FakeReader([FakePage(["abc"]), FakePage(["def"]), later_page])

    with pytest.raises(ValueError, match="Texto extraído excede o limite de 5 caracteres"):
        upload_validation._extract_pdf_text_bounded(reader)

    assert later_page.visited is False
