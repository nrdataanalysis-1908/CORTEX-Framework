"""Pure text chunking utilities used by the RAG ingestion pipeline."""

def split_text(text: str, chunk_size: int = 800, chunk_overlap: int = 120) -> list[str]:
    """Normalize text and split it into overlapping character windows."""
    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser maior que zero.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap deve estar entre zero e chunk_size - 1.")

    clean = " ".join(text.split())
    if not clean:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = end - chunk_overlap
    return chunks
