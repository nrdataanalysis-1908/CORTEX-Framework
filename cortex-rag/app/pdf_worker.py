"""Child-process entry point for bounded PDF extraction."""

from __future__ import annotations

import json
import sys


def _apply_posix_limits() -> None:
    if sys.platform == "win32":
        return
    import resource

    from app.pdf_isolation import PDF_WORKER_CPU_SECONDS, PDF_WORKER_MEMORY_BYTES

    resource.setrlimit(
        resource.RLIMIT_AS,
        (PDF_WORKER_MEMORY_BYTES, PDF_WORKER_MEMORY_BYTES),
    )
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (PDF_WORKER_CPU_SECONDS, PDF_WORKER_CPU_SECONDS + 1),
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        _apply_posix_limits()
        header = sys.stdin.buffer.readline(8193)
        if not header or len(header) > 8192 or not header.endswith(b"\n"):
            raise ValueError("Metadados do arquivo ausentes ou inválidos.")
        metadata = json.loads(header.decode("utf-8"))
        data = sys.stdin.buffer.read(15 * 1024 * 1024 + 1)
        if len(data) > 15 * 1024 * 1024:
            raise ValueError("Arquivo excede o limite de 15 MB.")

        from app.upload_validation import extract_validated_text

        text, safe_filename = extract_validated_text(
            metadata["filename"],
            data,
            metadata.get("content_type"),
        )
        json.dump(
            {"text": text, "filename": safe_filename},
            sys.stdout,
            ensure_ascii=False,
        )
        return 0
    except ValueError as exc:
        json.dump({"error": str(exc), "error_type": "ValueError"}, sys.stdout, ensure_ascii=False)
        return 2
    except Exception:
        json.dump(
            {
                "error": "O processo isolado não conseguiu concluir a extração PDF.",
                "error_type": "WorkerError",
            },
            sys.stdout,
            ensure_ascii=False,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
