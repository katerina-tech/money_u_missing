"""Splitting knowledge documents into citable passages.

Chunking is a citation problem before it is a retrieval problem. If a passage
straddles two topics, the citation attached to an answer points at text that
only half supports it - and this corpus is German tax guidance, where "half
supports it" is how someone ends up registering the wrong legal form.

So the splitter is structure-aware: it breaks on Markdown headings first and
only falls back to paragraph and sentence boundaries inside an over-long
section. Each chunk carries its heading trail, so a retrieved passage arrives
with the context that makes it interpretable - "25,000 EUR" means nothing
without "Kleinunternehmerregelung / previous calendar year" above it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])")


@dataclass(frozen=True)
class TextChunk:
    text: str
    ordinal: int
    #: e.g. ``"Umsatzsteuer > Kleinunternehmerregelung"``. Prepended to the
    #: chunk text so retrieval sees it and citations can show it.
    heading_path: str

    @property
    def token_estimate(self) -> int:
        # Four characters per token is close enough for a budget check and
        # needs no tokeniser dependency.
        return max(1, len(self.text) // 4)


@dataclass
class _Section:
    heading_path: str
    body: str


def _sections(markdown: str) -> list[_Section]:
    """Split on headings, tracking the heading hierarchy."""
    matches = list(_HEADING.finditer(markdown))
    if not matches:
        return [_Section("", markdown.strip())]

    sections: list[_Section] = []
    preamble = markdown[: matches[0].start()].strip()
    if preamble:
        sections.append(_Section("", preamble))

    trail: list[str] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        trail = trail[: level - 1]
        trail.append(title)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = markdown[match.end() : end].strip()
        if body:
            sections.append(_Section(" > ".join(trail), body))
    return sections


def _split_long(body: str, size: int, overlap: int) -> list[str]:
    """Paragraph-first splitting, with a sentence-level fallback.

    Overlap is applied between windows so a fact that lands on a boundary is
    retrievable from both sides - the alternative is a threshold that is
    invisible until an answer is silently missing its qualifying clause.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    windows: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > size:
            if current:
                windows.append(current)
                current = ""
            sentences = _SENTENCE.split(paragraph)
            buffer = ""
            for sentence in sentences:
                if len(buffer) + len(sentence) + 1 > size and buffer:
                    windows.append(buffer.strip())
                    buffer = buffer[-overlap:] if overlap else ""
                buffer = f"{buffer} {sentence}".strip()
            if buffer:
                current = buffer
            continue

        if len(current) + len(paragraph) + 2 > size and current:
            windows.append(current)
            current = current[-overlap:] if overlap else ""
        current = f"{current}\n\n{paragraph}".strip()

    if current:
        windows.append(current)
    return [w for w in windows if w.strip()]


def chunk_markdown(markdown: str, *, size: int = 900, overlap: int = 150) -> list[TextChunk]:
    """Split a document into citable chunks, each prefixed with its heading trail."""
    chunks: list[TextChunk] = []
    ordinal = 0
    for section in _sections(markdown):
        for window in _split_long(section.body, size, overlap) or [section.body]:
            prefix = f"{section.heading_path}\n\n" if section.heading_path else ""
            chunks.append(
                TextChunk(
                    text=(prefix + window).strip(),
                    ordinal=ordinal,
                    heading_path=section.heading_path,
                )
            )
            ordinal += 1
    return chunks
