"""Read a customer specification (PDF or Word) into headings, sentences and table rows in reading order.

PDFs lose their structure: running headers and footers repeat on every page, words are hyphenated across lines,
table cells become runs of spaces. Word files keep it. Both end up as the same list of blocks.
"""
from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass, field

HEADING = re.compile(r"^(?:\d+(?:\.\d+)*|Appendix [A-Z])\s+[A-Z][\w ,&/()-]{2,80}$")
RID = re.compile(r"^\[(?P<rid>[A-Z][A-Z0-9]*-[A-Z0-9-]*\d)\]\s*")
PAGE = re.compile(r"^(page|seite)\s+\d+(\s+(of|von)\s+\d+)?$", re.I)


@dataclass
class Block:
    kind: str                     # heading | text | row | header-row
    text: str
    section: str = ""
    cells: list[str] = field(default_factory=list)
    rid: str | None = None


def read(data: bytes) -> list[Block]:
    if data[:4] == b"%PDF":
        return _structure(_pdf_lines(data))
    if data[:2] == b"PK":
        return _docx(data)
    return _structure(data.decode("utf-8", "replace").splitlines())


def _pdf_lines(data: bytes) -> list[str]:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(data))
    pages = [p.extract_text(extraction_mode="layout").splitlines() for p in reader.pages]
    # a running header or footer is a line that repeats (digits aside) on most pages
    norm = Counter()
    for lines in pages:
        filled = [x.strip() for x in lines if x.strip()]
        for ln in {re.sub(r"\d+", "#", x) for x in filled[:2] + filled[-2:]}:   # only the page edges
            norm[ln] += 1
    repeated = {k for k, c in norm.items() if len(pages) > 1 and c >= max(2, len(pages) * 0.6)}
    out = []
    for lines in pages:
        idx = [i for i, x in enumerate(lines) if x.strip()]
        edge = set(idx[:2] + idx[-2:])
        kept = [x.rstrip() for i, x in enumerate(lines)
                if not (i in edge and (re.sub(r"\d+", "#", x.strip()) in repeated or PAGE.match(x.strip())))]
        while kept and not kept[0].strip():
            kept.pop(0)
        while kept and not kept[-1].strip():
            kept.pop()
        out.extend(kept)
        out.append("\f")            # a page break does not end a sentence
    return out


def _structure(lines: list[str]) -> list[Block]:
    """Join wrapped lines into sentences, undo hyphenation, keep headings and table rows apart."""
    blocks: list[Block] = []
    section = ""
    buf = ""
    header: list[str] | None = None

    def flush():
        nonlocal buf
        if buf.strip():
            for sent in sentences(buf.strip()):
                rid = RID.match(sent)
                blocks.append(Block("text", RID.sub("", sent).strip(), section, rid=rid.group("rid") if rid else None))
        buf = ""

    for raw in lines:
        if raw == "\f":
            continue
        if not raw.strip():
            flush()
            continue
        cells = [c.strip() for c in re.split(r"\s{2,}", raw.strip()) if c.strip()]
        line = re.sub(r"\s+", " ", raw.strip())
        if not buf and HEADING.match(line) and not line.endswith("."):
            flush()
            section = line
            header = None
            blocks.append(Block("heading", line, section))
            continue
        if len(cells) >= 3 and not buf:
            if header is None and _looks_like_header(cells):
                header = cells
                blocks.append(Block("header-row", line, section, cells=cells))
                continue
            if header is not None:
                blocks.append(Block("row", line, section, cells=cells))
                continue
        if buf.endswith("-") and len(buf) > 1 and buf[-2].isalpha() and line[:1].islower():
            buf = buf[:-1] + line
        else:
            buf = f"{buf} {line}" if buf else line
        if buf.endswith((".", ":", ";")):
            flush()
    flush()
    return blocks


def _looks_like_header(cells: list[str]) -> bool:
    words = {c.lower() for c in cells}
    return len(words & {"parameter", "requirement", "unit", "value", "id", "subsystem", "component"}) >= 2


def sentences(text: str) -> list[str]:
    # a full stop ends a sentence unless it is part of a number, an abbreviation or "No."
    parts = re.split(r"(?<!\bmin)(?<!\bmax)(?<!\bNo)(?<!\bca)(?<!\be\.g)(?<!\bi\.e)(?<=[.;])\s+(?=[\[A-Z])", text)
    return [p.strip() for p in parts if p.strip()]


def _docx(data: bytes) -> list[Block]:
    import docx
    d = docx.Document(io.BytesIO(data))
    blocks: list[Block] = []
    section = ""
    body = d.element.body
    for el in body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            from docx.text.paragraph import Paragraph
            p = Paragraph(el, d)
            text = p.text.strip()
            if not text:
                continue
            style = (p.style.name or "").lower() if p.style is not None else ""
            if style.startswith("heading") or style == "title":
                if style.startswith("heading"):
                    section = text
                blocks.append(Block("heading", text, section))
                continue
            for sent in sentences(text):
                rid = RID.match(sent)
                blocks.append(Block("text", RID.sub("", sent).strip(), section, rid=rid.group("rid") if rid else None))
        elif tag == "tbl":
            from docx.table import Table
            t = Table(el, d)
            rows = [[c.text.strip() for c in r.cells] for r in t.rows]
            if not rows:
                continue
            start = 0
            if _looks_like_header(rows[0]):
                blocks.append(Block("header-row", " ".join(rows[0]), section, cells=rows[0]))
                start = 1
            for r in rows[start:]:
                blocks.append(Block("row", " ".join(r), section, cells=r))
    return blocks
