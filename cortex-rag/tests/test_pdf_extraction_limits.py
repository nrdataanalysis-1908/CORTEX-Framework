import pytest

from app import upload_validation


class FakePage:
    def __init__(self, fragments):
        self.fragments = fragments

    def extract_text(self, visitor_text):
        for fragment in self.fragments:
            visitor_text(fragment, None, None, None, None)
        return "".join(self.fragments)


class FakeReader:
    def __init__(self, pages):
        self.pages = pages


def test_bounded_pdf_extraction_accepts_exact_character_limit(monkeypatch):
    monkeypatch.setattr(upload_validation, "MAX_PDF_EXTRACTED_CHARACTERS", 5)
    reader = FakeReader([FakePage(["ab", "c"]), FakePage(["de"])])

    assert upload_validation._extract_pdf_text_bounded(reader) == "abc\nde"


def test_bounded_pdf_extraction_rejects_over_limit_without_retaining_overflow(monkeypatch):
    monkeypatch.setattr(upload_validation, "MAX_PDF_EXTRACTED_CHARACTERS", 5)
    reader = FakeReader([FakePage(["abc", "def"])])

    with pytest.raises(ValueError, match="excede o limite de 5 caracteres"):
        upload_validation._extract_pdf_text_bounded(reader)


def test_bounded_pdf_extraction_stops_before_processing_later_pages(monkeypatch):
    monkeypatch.setattr(upload_validation, "MAX_PDF_EXTRACTED_CHARACTERS", 3)

    class MustNotRunPage:
        def extract_text(self, visitor_text):
            raise AssertionError("A extração deveria ter sido interrompida na página anterior.")

    reader = FakeReader([FakePage(["abcd"]), MustNotRunPage()])

    with pytest.raises(ValueError, match="excede o limite de 3 caracteres"):
        upload_validation._extract_pdf_text_bounded(reader)
