"""Turn the world's specs into the files a supplier actually receives: PDFs with running headers, footers and
hyphenated line breaks, Word files with real tables, and the supplier's baseline as a ReqIF 1.2 export."""
from __future__ import annotations

import io
import math
import textwrap
from xml.sax.saxutils import escape

import docx
import pymupdf as fitz

from rta.keyed import rng
from rta.world.spec import BaseReq, Spec

A4 = (595, 842)


def render(spec: Spec) -> bytes:
    return pdf(spec) if spec.fmt == "pdf" else word(spec)


def lines_of(spec: Spec, width: int = 92) -> list[tuple[str, str]]:
    """(style, text) lines, wrapped the way a word processor would, sometimes hyphenating a long word."""
    out = []
    r = rng("hyphen", spec.id, spec.rev)
    for b in spec.blocks:
        if b["kind"] in ("title", "heading"):
            out.append(("h", b["text"]))
            continue
        if b["kind"] == "row":
            out.append(("row", "\t".join(b["cells"])))
            continue
        wrapped = textwrap.wrap(b["text"], width=width, break_on_hyphens=False)
        fixed = []
        for k, ln in enumerate(wrapped):
            if k + 1 < len(wrapped) and r.random() < 0.25:
                nxt = wrapped[k + 1].split(" ", 1)
                w = nxt[0]
                if len(w) >= 9 and w.isalpha():
                    cut = len(w) // 2
                    ln = f"{ln} {w[:cut]}-"
                    wrapped[k + 1] = w[cut:] + (" " + nxt[1] if len(nxt) > 1 else "")
            fixed.append(ln)
        out.extend(("p", ln) for ln in fixed)
        out.append(("gap", ""))
    return out


def pdf(spec: Spec) -> bytes:
    """The built-in PDF fonts have no "≥", so authors type ">=" as they do in real specs."""
    doc = fitz.open()
    sub = {"≥": ">=", "≤": "<=", "…": "...", "±": "+/-"}
    lines = [(st, "".join(sub.get(ch, ch) for ch in t)) for st, t in lines_of(spec)]
    per_page = 52
    pages = math.ceil(len(lines) / per_page)
    for p in range(pages):
        page = doc.new_page(width=A4[0], height=A4[1])
        page.insert_text((50, 40), f"{spec.customer} | Lastenheft {spec.id} | Rev. {spec.rev} | Confidential",
                         fontsize=8, fontname="helv")
        y = 72
        for style, text in lines[p * per_page:(p + 1) * per_page]:
            if style == "gap":
                y += 6
                continue
            if style == "row":
                cells = text.split("\t")
                xs = [50, 110, 210, 420, 500] if len(cells) == 5 else [50, 150, 400, 490]
                for x, c in zip(xs, cells):
                    page.insert_text((x, y), c, fontsize=8.5, fontname="helv")
                y += 13
                continue
            page.insert_text((50, y), text, fontsize=10 if style == "h" else 9,
                             fontname="hebo" if style == "h" else "helv")
            y += 14 if style == "h" else 12.5
        page.insert_text((270, 815), f"Page {p + 1} of {pages}", fontsize=8, fontname="helv")
    return doc.tobytes()


def word(spec: Spec) -> bytes:
    d = docx.Document()
    sec = d.sections[0]
    sec.header.paragraphs[0].text = f"{spec.customer} | Lastenheft {spec.id} | Rev. {spec.rev} | Confidential"
    table = None
    for b in spec.blocks:
        if b["kind"] == "title":
            d.add_heading(b["text"], level=0)
        elif b["kind"] == "heading":
            d.add_heading(b["text"], level=1)
            table = None
        elif b["kind"] == "row":
            if table is None:
                table = d.add_table(rows=0, cols=len(b["cells"]))
            row = table.add_row().cells
            for c, v in zip(row, b["cells"]):
                c.text = v
        else:
            d.add_paragraph(b["text"])
            table = None
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def reqif(system: dict, baseline: list[BaseReq], names: dict) -> bytes:
    """The supplier's requirements and tests as a DOORS or Polarion export would give them (ReqIF 1.2)."""
    code = system["code"]
    spec_objs, rels, children = [], [], []
    for b in baseline:
        spec_objs.append(obj(b.id, "REQ", {"ID": b.id, "TEXT": b.text, "SUBSYSTEM": names[b.sub]["name"], "TYPE": "requirement"}))
        children.append(b.id)
        for t in b.tests:
            spec_objs.append(obj(t, "TEST", {"ID": t, "TEXT": f"Verify on the test bench: {b.text}",
                                             "SUBSYSTEM": names[b.sub]["name"], "TYPE": "test"}))
            rels.append(f'<SPEC-RELATION IDENTIFIER="rel-{t}" LAST-CHANGE="2026-01-01T00:00:00Z"><TYPE>'
                        f'<SPEC-RELATION-TYPE-REF>verifies</SPEC-RELATION-TYPE-REF></TYPE><SOURCE><SPEC-OBJECT-REF>{t}'
                        f'</SPEC-OBJECT-REF></SOURCE><TARGET><SPEC-OBJECT-REF>{b.id}</SPEC-OBJECT-REF></TARGET>'
                        f'</SPEC-RELATION>')
    attrs = "".join(f'<ATTRIBUTE-DEFINITION-STRING IDENTIFIER="ad-{a}" LONG-NAME="{a}" LAST-CHANGE="2026-01-01T00:00:00Z">'
                    f'<TYPE><DATATYPE-DEFINITION-STRING-REF>dt-str</DATATYPE-DEFINITION-STRING-REF></TYPE>'
                    f'</ATTRIBUTE-DEFINITION-STRING>' for a in ("ID", "TEXT", "SUBSYSTEM", "TYPE"))
    hier = "".join(f'<SPEC-HIERARCHY IDENTIFIER="h-{c}" LAST-CHANGE="2026-01-01T00:00:00Z"><OBJECT>'
                   f'<SPEC-OBJECT-REF>{c}</SPEC-OBJECT-REF></OBJECT></SPEC-HIERARCHY>' for c in children)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd">
<THE-HEADER><REQ-IF-HEADER IDENTIFIER="hdr-{code}"><TITLE>{escape(system['name'])} system requirements</TITLE>
<REQ-IF-TOOL-ID>supplier-alm</REQ-IF-TOOL-ID><REQ-IF-VERSION>1.2</REQ-IF-VERSION></REQ-IF-HEADER></THE-HEADER>
<CORE-CONTENT><REQ-IF-CONTENT>
<DATATYPES><DATATYPE-DEFINITION-STRING IDENTIFIER="dt-str" MAX-LENGTH="4000" LAST-CHANGE="2026-01-01T00:00:00Z"/></DATATYPES>
<SPEC-TYPES><SPEC-OBJECT-TYPE IDENTIFIER="REQ" LONG-NAME="Requirement" LAST-CHANGE="2026-01-01T00:00:00Z"><SPEC-ATTRIBUTES>{attrs}</SPEC-ATTRIBUTES></SPEC-OBJECT-TYPE>
<SPEC-OBJECT-TYPE IDENTIFIER="TEST" LONG-NAME="Test case" LAST-CHANGE="2026-01-01T00:00:00Z"><SPEC-ATTRIBUTES>{attrs}</SPEC-ATTRIBUTES></SPEC-OBJECT-TYPE>
<SPEC-RELATION-TYPE IDENTIFIER="verifies" LONG-NAME="verifies" LAST-CHANGE="2026-01-01T00:00:00Z"/></SPEC-TYPES>
<SPEC-OBJECTS>{''.join(spec_objs)}</SPEC-OBJECTS>
<SPEC-RELATIONS>{''.join(rels)}</SPEC-RELATIONS>
<SPECIFICATIONS><SPECIFICATION IDENTIFIER="spec-{code}" LONG-NAME="System requirements" LAST-CHANGE="2026-01-01T00:00:00Z"><CHILDREN>{hier}</CHILDREN></SPECIFICATION></SPECIFICATIONS>
</REQ-IF-CONTENT></CORE-CONTENT></REQ-IF>"""
    return xml.encode()


def obj(ident: str, typ: str, values: dict) -> str:
    vals = "".join(f'<ATTRIBUTE-VALUE-STRING THE-VALUE="{escape(v, {chr(34): "&quot;"})}"><DEFINITION>'
                   f'<ATTRIBUTE-DEFINITION-STRING-REF>ad-{k}</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION>'
                   f'</ATTRIBUTE-VALUE-STRING>' for k, v in values.items())
    return (f'<SPEC-OBJECT IDENTIFIER="{ident}" LAST-CHANGE="2026-01-01T00:00:00Z"><TYPE><SPEC-OBJECT-TYPE-REF>{typ}'
            f'</SPEC-OBJECT-TYPE-REF></TYPE><VALUES>{vals}</VALUES></SPEC-OBJECT>')
