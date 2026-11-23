from io import BytesIO
import os
import subprocess

import pytest
from pypdf import PdfWriter

from app import pdf_isolation


def _make_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    # A blank page is a valid PDF; extraction is expected to reject empty text.
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_worker_runs_in_separate_process_and_returns_validation_error():
    with pytest.raises(ValueError, match="Nenhum texto extraível"):
        pdf_isolation.extract_validated_text_isolated(
            "blank.pdf", _make_pdf(), "application/pdf"
        )


def _make_text_pdf(text: str = "CORTEX validation text") -> bytes:
    """Build a minimal standards-compliant PDF containing an extractable text run."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def test_pdf_worker_extracts_text_in_child_process():
    text, filename = pdf_isolation.extract_validated_text_isolated(
        "worker.pdf", _make_text_pdf(), "application/pdf"
    )

    assert text == "isolated worker extraction"
    assert filename == "worker.pdf"


def test_txt_keeps_in_process_validation_path(monkeypatch):
    called = []
    monkeypatch.setattr(
        "app.upload_validation.extract_validated_text",
        lambda filename, data, content_type: (called.append(filename) or "txt", filename),
    )

    assert pdf_isolation.extract_validated_text_isolated(
        "notes.txt", b"content", "text/plain"
    ) == ("txt", "notes.txt")
    assert called == ["notes.txt"]


def test_worker_timeout_kills_child(monkeypatch):
    class FakeProcess:
        returncode = None
        killed = False

        def __init__(self, *args, **kwargs):
            pass

        def poll(self):
            return self.returncode

        def kill(self):
            self.killed = True
            self.returncode = -9

        def communicate(self, input=None, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired("worker", timeout)
            return b"", b""

    child = FakeProcess()
    monkeypatch.setattr(pdf_isolation.subprocess, "Popen", lambda *a, **k: child)
    monkeypatch.setattr(pdf_isolation, "PDF_WORKER_WALL_SECONDS", 1)
    monkeypatch.setattr(pdf_isolation.os, "name", "posix")

    with pytest.raises(pdf_isolation.PdfWorkerTimeoutError):
        pdf_isolation._run_pdf_worker("x.pdf", b"%PDF-", "application/pdf")
    assert child.killed


def test_worker_rejects_oversized_input_before_starting_process(monkeypatch):
    monkeypatch.setattr(pdf_isolation, "MAX_PDF_WORKER_INPUT_BYTES", 3)
    monkeypatch.setattr(
        pdf_isolation.subprocess,
        "Popen",
        lambda *a, **k: pytest.fail("worker must not start"),
    )

    with pytest.raises(ValueError, match="15 MB"):
        pdf_isolation._run_pdf_worker("x.pdf", b"four", "application/pdf")


@pytest.mark.skipif(os.name != "posix", reason="POSIX resource limits are platform-specific")
def test_worker_process_applies_cpu_and_address_space_limits(monkeypatch):
    import resource
    from app import pdf_worker

    calls = []
    monkeypatch.setattr(resource, "setrlimit", lambda kind, limits: calls.append((kind, limits)))
    pdf_worker._apply_posix_limits()

    assert [kind for kind, _ in calls] == [resource.RLIMIT_AS, resource.RLIMIT_CPU]
    assert calls[0][1][0] == pdf_isolation.PDF_WORKER_MEMORY_BYTES
    assert calls[1][1][0] == pdf_isolation.PDF_WORKER_CPU_SECONDS
