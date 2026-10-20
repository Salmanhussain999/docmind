import pytest

from app.ingest.chunking import chunk_pages, split_units
from app.ingest.extract import ExtractionError, Page, clean_text, extract_pages
from tests.pdf_factory import make_pdf


def test_clean_text_rejoins_wrapped_lines_and_hyphenation():
    raw = "The quick brown\nfox jumps over the lazy dog. Inter-\nnational shipping.\n\nNew paragraph."
    assert (
        clean_text(raw)
        == "The quick brown fox jumps over the lazy dog. International shipping.\n\nNew paragraph."
    )


def test_headings_stay_separate_from_the_text_below():
    raw = "Leave policy\nFull-time employees receive 24 days of leave.\nThe year starts in\nJanuary."
    cleaned = clean_text(raw)
    assert (
        cleaned == "Leave policy\n\nFull-time employees receive 24 days of leave. The year starts in January."
    )
    chunk = chunk_pages([Page(1, cleaned)])[0]
    assert chunk.text.startswith("Leave policy\nFull-time employees")


def test_split_units_breaks_overlong_sentences_at_spaces():
    units = split_units("word " * 100, max_len=50)
    assert all(len(u) <= 50 for u in units)
    assert " ".join(units).split() == ["word"] * 100


def test_chunks_respect_size_and_carry_overlap():
    sentences = [f"Sentence number {i} talks about topic {i}." for i in range(40)]
    chunks = chunk_pages([Page(1, " ".join(sentences))], size=200, overlap=60)

    assert len(chunks) > 5
    assert all(len(c.text) <= 200 for c in chunks)
    # Each chunk starts with the tail of the previous one.
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        first_sentence = nxt.text.split(". ")[0]
        assert first_sentence in prev.text
    # Nothing lost.
    joined = " ".join(c.text for c in chunks)
    assert all(s in joined for s in sentences)


def test_chunks_never_span_pages_and_keep_order():
    chunks = chunk_pages([Page(1, "Alpha. " * 10), Page(3, "Beta. " * 10)], size=500, overlap=50)
    assert [c.page for c in chunks] == [1, 3]
    assert [c.ordinal for c in chunks] == [0, 1]


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_pages([Page(1, "x")], size=100, overlap=100)


def test_extracts_pdf_pages_with_numbers():
    pdf = make_pdf([["First page text."], [], ["Third page text."]])
    pages = extract_pages(pdf, ".pdf", max_pages=10)
    assert [(p.number, p.text) for p in pages] == [(1, "First page text."), (3, "Third page text.")]


def test_rejects_pdfs_over_the_page_limit():
    with pytest.raises(ExtractionError, match="limit is 2"):
        extract_pages(make_pdf([["a"], ["b"], ["c"]]), ".pdf", max_pages=2)


def test_rejects_pdfs_without_text():
    with pytest.raises(ExtractionError, match="scanned"):
        extract_pages(make_pdf([[], []]), ".pdf", max_pages=10)


def test_rejects_garbage_and_non_utf8():
    with pytest.raises(ExtractionError, match="couldn't be read"):
        extract_pages(b"%PDF-1.4 definitely not a pdf", ".pdf", max_pages=10)
    with pytest.raises(ExtractionError, match="UTF-8"):
        extract_pages("café".encode("latin-1"), ".txt", max_pages=10)
