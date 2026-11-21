from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.upload_validation import extract_validated_text


def make_text_pdf(text: str = "CORTEX validation text") -> bytes:
    """Build a minimal standards-compliant PDF containing an extractable text run."""
    escaped = text.replace("\\\\", "\\\\\\\\").replace("(", "\\\\(").replace(")", "\\\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\\nstream\\n" + stream + b"\\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\\nendobj\\n")

    xref_offset = len(output)
    output.extend(f"xref\\n0 {len(objects) + 1}\\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \\n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \\n".encode("ascii"))
    output.extend(
        f"trailer\\n<< /Size {len(objects) + 1} /Root 1 0 R >>\\n"
        f"startxref\\n{xref_offset}\\n%%EOF\\n".encode("ascii")
    )
    return bytes(output)


def test_txt_upload_is_decoded_and_filename_is_sanitized():
    text, filename = extract_validated_text(
        "../../manual.TXT",
        b"\\xef\\xbb\\xbfProcedimento operacional",
        "text/plain; charset=utf-8",
    )

    assert text == "Procedimento operacional"
    assert filename == "manual.TXT"


@pytest.mark.parametrize(
    ("filename", "data", "content_type", "message"),
    [
        ("manual.exe", b"content", "application/octet-stream", "Formato não suportado"),
        ("manual.txt", b"\\xff", "text/plain", "UTF-8"),
        ("manual.txt", b"abc\\x00def", "text/plain", "bytes nulos"),
        ("manual.txt", b"abc", "application/pdf", "tipo MIME"),
        ("manual.pdf", b"not a pdf", "application/pdf", "Assinatura"),
        ("manual.txt", b"", "text/plain", "vazio"),
        ("../" + "x" * 256 + ".txt", b"abc", "text/plain", "255 caracteres"),
    ],
)
def test_invalid_uploads_are_rejected(filename, data, content_type, message):
    with pytest.raises(ValueError, match=message):
        extract_validated_text(filename, data, content_type)


def test_valid_pdf_extracts_actual_page_text():
    text, filename = extract_validated_text(
        "manual.pdf", make_text_pdf(), "application/pdf"
    )

    assert text == "CORTEX validation text"
    assert filename == "manual.pdf"


def test_encrypted_pdf_is_rejected():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("test-password")
    buffer = BytesIO()
    writer.write(buffer)

    with pytest.raises(ValueError, match="protegido por senha"):
        extract_validated_text("encrypted.pdf", buffer.getvalue(), "application/pdf")


def test_pdf_over_page_limit_is_rejected_before_text_extraction():
    writer = PdfWriter()
    for _ in range(501):
        writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)

    with pytest.raises(ValueError, match="excede o limite de 500 páginas"):
        extract_validated_text("too-many-pages.pdf", buffer.getvalue(), "application/pdf")


def test_malformed_pdf_is_rejected_after_signature_check():
    with pytest.raises(ValueError, match="PDF inválido"):
        extract_validated_text("broken.pdf", b"%PDF-1.7\\nnot-a-real-pdf", "application/pdf")


def test_windows_path_is_reduced_to_filename():
    text, filename = extract_validated_text(
        r"C:\\fakepath\\document.txt",
        b"valid content",
        "text/plain",
    )

    assert text == "valid content"
    assert filename == "document.txt"
