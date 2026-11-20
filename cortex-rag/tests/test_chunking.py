import pytest

from app.chunking import split_text


def test_empty_text_returns_no_chunks():
    assert split_text(" \n\t ") == []


def test_short_text_returns_one_chunk():
    assert split_text("  NR   TECH  ") == ["NR TECH"]


def test_long_text_respects_chunk_size_and_overlap():
    chunks = split_text("abcdefghij", chunk_size=6, chunk_overlap=2)
    assert chunks == ["abcdef", "efghij"]
    assert all(len(chunk) <= 6 for chunk in chunks)


def test_invalid_chunk_size_is_rejected():
    with pytest.raises(ValueError, match="chunk_size"):
        split_text("texto", chunk_size=0)


@pytest.mark.parametrize("overlap", [-1, 5])
def test_invalid_overlap_is_rejected(overlap):
    with pytest.raises(ValueError, match="chunk_overlap"):
        split_text("texto", chunk_size=5, chunk_overlap=overlap)
