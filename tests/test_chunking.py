from app.service.chunking import chunk_transcript


def test_chunking_preserves_text_and_adds_overlap() -> None:
    first = "First paragraph. " * 20
    second = "Second paragraph. " * 20
    chunks = chunk_transcript(f"{first}\n\n{second}", target_size=400, overlap=40)

    assert len(chunks) == 2
    assert chunks[0].overlap_characters == 0
    assert chunks[1].overlap_characters == 40
    assert chunks[1].text.startswith(chunks[0].text[-40:])
    assert all(chunk.content_hash for chunk in chunks)


def test_empty_transcript_has_no_chunks() -> None:
    assert chunk_transcript(" \n ") == []

