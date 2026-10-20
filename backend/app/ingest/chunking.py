"""Splits page text into overlapping chunks that stay inside one page, so every chunk has a page to cite."""

import re
from dataclasses import dataclass

from .extract import Page


@dataclass(frozen=True)
class Chunk:
    page: int
    ordinal: int  # position within the document
    text: str


# Split after sentence-ending punctuation, or at paragraph breaks.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])|\n\n")


def split_units(text: str, max_len: int) -> list[str]:
    """Sentences, with any sentence longer than `max_len` broken at word boundaries."""
    units: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > max_len:
            cut = sentence.rfind(" ", 0, max_len)
            if cut <= 0:
                cut = max_len
            units.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            units.append(sentence)
    return units


def chunk_pages(pages: list[Page], size: int = 900, overlap: int = 150) -> list[Chunk]:
    """
    Greedy packing of whole sentences up to `size` characters. Each new chunk starts with the
    last sentences of the previous one (up to `overlap` characters) so an answer that spans a
    boundary is still retrievable from one chunk.
    """
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    chunks: list[Chunk] = []
    for page in pages:
        for text in _pack(split_units(page.text, size), size, overlap):
            chunks.append(Chunk(page=page.number, ordinal=len(chunks), text=text))
    return chunks


def _pack(units: list[str], size: int, overlap: int) -> list[str]:
    packed: list[str] = []
    current: list[str] = []
    length = 0
    for unit in units:
        added = len(unit) + (1 if current else 0)
        if current and length + added > size:
            packed.append(_join(current))
            # Carry trailing sentences forward as overlap.
            carried: list[str] = []
            carried_len = 0
            for previous in reversed(current):
                if carried_len + len(previous) + 1 > overlap:
                    break
                carried.insert(0, previous)
                carried_len += len(previous) + 1
            if carried_len + len(unit) > size:  # no room for overlap next to a long sentence
                carried, carried_len = [], 0
            current, length = carried, max(carried_len - 1, 0)
            added = len(unit) + (1 if current else 0)
        current.append(unit)
        length += added
    if current:
        packed.append(_join(current))
    return packed


def _join(units: list[str]) -> str:
    """Sentences join with a space; a heading (no closing punctuation) keeps its own line."""
    text = units[0]
    for previous, unit in zip(units, units[1:], strict=False):
        text += ("\n" if not re.search(r"[.!?:;\"')\]]$", previous) else " ") + unit
    return text
