import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    content_hash: str
    overlap_characters: int


def chunk_transcript(text: str, target_size: int = 4000, overlap: int = 400) -> list[TextChunk]:
    """Split on paragraph boundaries, then apply a bounded character overlap."""
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    if not paragraphs:
        return []

    groups: list[str] = []
    current = ""
    for paragraph in paragraphs:
        pieces = (
            [paragraph[i : i + target_size] for i in range(0, len(paragraph), target_size)]
            if len(paragraph) > target_size
            else [paragraph]
        )
        for piece in pieces:
            candidate = f"{current}\n\n{piece}" if current else piece
            if current and len(candidate) > target_size:
                groups.append(current)
                current = piece
            else:
                current = candidate
    if current:
        groups.append(current)

    chunks: list[TextChunk] = []
    previous = ""
    for index, group in enumerate(groups):
        prefix = previous[-overlap:] if previous else ""
        chunk_text = f"{prefix}\n\n{group}" if prefix else group
        chunks.append(
            TextChunk(
                index=index,
                text=chunk_text,
                content_hash=hashlib.sha256(chunk_text.encode()).hexdigest(),
                overlap_characters=len(prefix),
            )
        )
        previous = group
    return chunks

