from io import BytesIO
from pathlib import PurePosixPath

from pypdf import PdfReader

MAX_FILENAME_LENGTH = 255
MAX_PDF_PAGES = 500
MAX_PDF_EXTRACTED_CHARACTERS = 5_000_000
ALLOWED_CONTENT_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
}


class _PdfTextLimitExceeded(Exception):
    """Internal control-flow exception for bounded PDF text extraction."""


def _safe_filename(filename: str) -> str:
    if not filename or "\x00" in filename:
        raise ValueError("Nome de arquivo inválido.")
    normalized = filename.replace("\\", "/").strip()
    name = PurePosixPath(normalized).name
    if not name or name in {".", ".."} or len(name) > MAX_FILENAME_LENGTH:
        raise ValueError("Nome de arquivo inválido ou excede 255 caracteres.")
    return name


def _extract_pdf_text_bounded(reader: PdfReader) -> str:
    """Collect parser text callbacks without retaining more than the configured cap."""
    parts: list[str] = []
    extracted_characters = 0

    for page in reader.pages:
        def collect_text(text, *_):
            nonlocal extracted_characters
            if not isinstance(text, str) or not text:
                return
            if extracted_characters + len(text) > MAX_PDF_EXTRACTED_CHARACTERS:
                raise _PdfTextLimitExceeded
            parts.append(text)
            extracted_characters += len(text)

        try:
            page.extract_text(visitor_text=collect_text)
        except _PdfTextLimitExceeded as exc:
            raise ValueError(
                "PDF excede o limite de "
                f"{MAX_PDF_EXTRACTED_CHARACTERS:,} caracteres extraídos."
            ) from exc

    return "\n".join(parts).strip()


def extract_validated_text(
    filename: str,
    data: bytes,
    content_type: str | None = None,
) -> tuple[str, str]:
    """Validate upload metadata and file signature before parsing its content."""
    safe_name = _safe_filename(filename)
    extension = PurePosixPath(safe_name).suffix.lower()
    if extension not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Formato não suportado. Envie PDF ou TXT.")

    declared_type = (content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if declared_type not in ALLOWED_CONTENT_TYPES[extension]:
        raise ValueError("O tipo MIME informado não corresponde ao formato permitido.")

    if not data:
        raise ValueError("O arquivo está vazio.")

    if extension == ".txt":
        if b"\x00" in data:
            raise ValueError("Arquivo TXT contém bytes nulos e não é um texto UTF-8 válido.")
        try:
            text = data.decode("utf-8-sig").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("Arquivo TXT deve utilizar codificação UTF-8.") from exc
        if not text:
            raise ValueError("Nenhum texto foi encontrado no arquivo TXT.")
        return text, safe_name

    if not data.startswith(b"%PDF-"):
        raise ValueError("Assinatura do arquivo inválida: conteúdo não corresponde a PDF.")

    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("PDF protegido por senha não é aceito.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDF excede o limite de {MAX_PDF_PAGES} páginas.")
        text = _extract_pdf_text_bounded(reader)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF inválido, corrompido ou incompatível com o parser.") from exc

    if not text:
        raise ValueError("Nenhum texto extraível foi encontrado no arquivo PDF.")
    return text, safe_name
