"""Run PDF parsing in a resource-bounded child process on Linux and Windows."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import PurePath

MAX_PDF_WORKER_INPUT_BYTES = 15 * 1024 * 1024
PDF_WORKER_MEMORY_BYTES = 512 * 1024 * 1024
PDF_WORKER_CPU_SECONDS = 30
PDF_WORKER_WALL_SECONDS = 45
_MAX_METADATA_BYTES = 8192


class PdfWorkerExecutionError(RuntimeError):
    """The isolated parser could not be started or returned an invalid result."""


class PdfWorkerTimeoutError(TimeoutError):
    """The PDF parser exceeded its wall-clock deadline."""


def _windows_job(process: subprocess.Popen):
    """Create a Windows Job Object that caps memory/CPU and kills children on close."""
    import ctypes
    from ctypes import wintypes

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise PdfWorkerExecutionError(
            f"Não foi possível criar Windows Job Object (erro {ctypes.get_last_error()})."
        )

    limits = ExtendedLimitInformation()
    # JOB_OBJECT_LIMIT_PROCESS_TIME | JOB_OBJECT_LIMIT_PROCESS_MEMORY |
    # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    limits.BasicLimitInformation.LimitFlags = 0x0002 | 0x0100 | 0x2000
    limits.BasicLimitInformation.PerProcessUserTimeLimit = (
        PDF_WORKER_CPU_SECONDS * 10_000_000
    )
    limits.ProcessMemoryLimit = PDF_WORKER_MEMORY_BYTES

    try:
        if not kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            raise PdfWorkerExecutionError(
                f"Não foi possível configurar limites do worker (erro {ctypes.get_last_error()})."
            )
        if not kernel32.AssignProcessToJobObject(job, wintypes.HANDLE(int(process._handle))):
            raise PdfWorkerExecutionError(
                f"Não foi possível associar o worker ao Job Object (erro {ctypes.get_last_error()})."
            )
    except Exception:
        kernel32.CloseHandle(job)
        raise

    return job, kernel32.CloseHandle


def _run_pdf_worker(filename: str, data: bytes, content_type: str | None) -> tuple[str, str]:
    if len(data) > MAX_PDF_WORKER_INPUT_BYTES:
        raise ValueError("Arquivo excede o limite de 15 MB.")

    metadata = json.dumps(
        {"filename": filename, "content_type": content_type},
        ensure_ascii=False,
    ).encode("utf-8")
    if len(metadata) > _MAX_METADATA_BYTES:
        raise ValueError("Metadados do arquivo excedem o limite permitido.")
    payload = metadata + b"\n" + data

    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.pdf_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
    except OSError as exc:
        raise PdfWorkerExecutionError("Não foi possível iniciar o processo isolado de PDF.") from exc
    job_handle = None
    close_job = None
    try:
        if os.name == "nt":
            job_handle, close_job = _windows_job(process)

        try:
            stdout, stderr = process.communicate(
                input=payload,
                timeout=PDF_WORKER_WALL_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate()
            raise PdfWorkerTimeoutError(
                f"Extração PDF excedeu {PDF_WORKER_WALL_SECONDS} segundos."
            ) from exc
    except Exception:
        if process.poll() is None:
            process.kill()
            process.communicate()
        raise
    finally:
        if job_handle is not None and close_job is not None:
            close_job(job_handle)

    try:
        result = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        detail = stderr.decode("utf-8", errors="replace")[-1000:]
        raise PdfWorkerExecutionError(
            f"Worker PDF encerrou sem resposta válida. {detail}"
        ) from exc

    if process.returncode != 0:
        message = result.get("error", "Falha inesperada no worker PDF.")
        if result.get("error_type") == "ValueError":
            raise ValueError(message)
        raise PdfWorkerExecutionError(message)

    text = result.get("text")
    safe_filename = result.get("filename")
    if not isinstance(text, str) or not isinstance(safe_filename, str):
        raise PdfWorkerExecutionError("Resposta do worker PDF possui formato inválido.")
    return text, safe_filename


def extract_validated_text_isolated(
    filename: str,
    data: bytes,
    content_type: str | None = None,
) -> tuple[str, str]:
    """Isolate PDF parsing; retain the existing lightweight path for TXT files."""
    from app.upload_validation import extract_validated_text

    if PurePath(filename.replace("\\", "/")).suffix.lower() != ".pdf":
        return extract_validated_text(filename, data, content_type)
    return _run_pdf_worker(filename, data, content_type)
