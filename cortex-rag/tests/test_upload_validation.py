from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.upload_validation import extract_validated_text


def test_txt_upload_is_decoded_and_filename_is_sanitized():
    text, filename = extract_validated_text(
        "../../manual.TXT",
        b"\xef\xbb\xbfProcedimento operacional",
        "text/plain; charset=utf-8",
    )

    assert text == "Procedimento operacional"
    assert filename == "manual.TXT"


@pytest.mark.parametrize(
    ("filename", "data", "content_type", "message"),
    [
        ("manual.exe", b"content", "application/octet-stream", "Formato não suportado"),
        ("manual.txt", b"\xff", "text/plain", "UTF-8"),
        ("manual.txt", b"abc\x00def", "text/plain", "bytes nulos"),
        ("manual.txt", b"abc", "application/pdf", "tipo MIME"),
        ("manual.pdf", b"not a pdf", "application/pdf", "Assinatura"),
        ("manual.txt", b"", "text/plain", "vazio"),
        ("../" + "x" * 256 + ".txt", b"abc", "text/plain", "255 caracteres"),
    ],
)
def test_invalid_uploads_are_rejected(filename, data, content_type, message):
    with pytest.raises(ValueError, match=message):
        extract_validated_text(filename, data, content_type)


def test_pdf_with_valid_signature_is_parsed():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)

    with pytest.raises(ValueError, match="Nenhum texto extraível"):
        text, _ = extract_validated_text("blank.pdf", buffer.getvalue(), "application/pdf")
        if not text:
            raise ValueError("Nenhum texto extraível foi encontrado no arquivo.")


def test_malformed_pdf_is_rejected_after_signature_check():
    with pytest.raises(ValueError, match="PDF inválido"):
        extract_validated_text("broken.pdf", b"%PDF-1.7\nnot-a-real-pdf", "application/pdf")


def test_windows_path_is_reduced_to_filename():
    text, filename = extract_validated_text(
        r"C:\\fakepath\\document.txt",
        b"valid content",
        "text/plain",
    )

    assert text == "valid content"
    assert filename == "document.txt"
