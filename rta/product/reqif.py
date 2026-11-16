"""ReqIF 1.2 in and out: the supplier's baseline comes from DOORS, Polarion or Codebeamer as ReqIF, and the
analysed customer requirements go back the same way, with their trace links as SPEC-RELATIONs."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

NS = "{http://www.omg.org/spec/ReqIF/20110401/reqif.xsd}"
STAMP = "2026-01-01T00:00:00Z"


@dataclass
class ReqIF:
    title: str
    objects: dict[str, dict[str, str]]                      # identifier -> attribute long name -> value
    types: dict[str, str]                                    # identifier -> spec object type
    relations: list[tuple[str, str, str]] = field(default_factory=list)   # (type, source, target)

    def of_type(self, attr: str, value: str) -> dict[str, dict[str, str]]:
        return {k: v for k, v in self.objects.items() if v.get(attr) == value}

    def targets(self, rel: str, source: str) -> list[str]:
        return [t for r, s, t in self.relations if r == rel and s == source]

    def sources(self, rel: str, target: str) -> list[str]:
        return [s for r, s, t in self.relations if r == rel and t == target]


def read(data: bytes) -> ReqIF:
    root = ET.fromstring(data)
    title = root.findtext(f".//{NS}TITLE") or ""
    defs = {}
    for tag in ("ATTRIBUTE-DEFINITION-STRING", "ATTRIBUTE-DEFINITION-XHTML", "ATTRIBUTE-DEFINITION-INTEGER",
                "ATTRIBUTE-DEFINITION-REAL", "ATTRIBUTE-DEFINITION-ENUMERATION"):
        for d in root.iter(f"{NS}{tag}"):
            defs[d.get("IDENTIFIER")] = d.get("LONG-NAME") or d.get("IDENTIFIER")
    objects, types = {}, {}
    for o in root.iter(f"{NS}SPEC-OBJECT"):
        ident = o.get("IDENTIFIER")
        types[ident] = o.findtext(f"{NS}TYPE/{NS}SPEC-OBJECT-TYPE-REF") or ""
        vals = {}
        values = o.find(f"{NS}VALUES")
        for v in (list(values) if values is not None else []):
            ref = next((x.text for x in v.iter() if x.tag.endswith("-REF") and x.tag.startswith(f"{NS}ATTRIBUTE-DEFINITION")), None)
            if ref is None:
                continue
            if v.tag == f"{NS}ATTRIBUTE-VALUE-XHTML":
                text = "".join(v.find(f"{NS}THE-VALUE").itertext()) if v.find(f"{NS}THE-VALUE") is not None else ""
            else:
                text = v.get("THE-VALUE", "")
            vals[defs.get(ref, ref)] = text
        objects[ident] = vals
    rels = []
    for r in root.iter(f"{NS}SPEC-RELATION"):
        rels.append((r.findtext(f"{NS}TYPE/{NS}SPEC-RELATION-TYPE-REF") or "",
                     r.findtext(f"{NS}SOURCE/{NS}SPEC-OBJECT-REF") or "",
                     r.findtext(f"{NS}TARGET/{NS}SPEC-OBJECT-REF") or ""))
    return ReqIF(title, objects, types, rels)


def write(title: str, objects: dict[str, dict[str, str]], relations: list[tuple[str, str, str]],
          obj_type: str = "CUSTOMER-REQ") -> bytes:
    names = sorted({k for v in objects.values() for k in v})
    attrs = "".join(f'<ATTRIBUTE-DEFINITION-STRING IDENTIFIER="ad-{n}" LONG-NAME="{escape(n)}" LAST-CHANGE="{STAMP}">'
                    f'<TYPE><DATATYPE-DEFINITION-STRING-REF>dt-str</DATATYPE-DEFINITION-STRING-REF></TYPE>'
                    f'</ATTRIBUTE-DEFINITION-STRING>' for n in names)
    q = {'"': "&quot;"}
    objs = "".join(
        f'<SPEC-OBJECT IDENTIFIER="{escape(i, q)}" LAST-CHANGE="{STAMP}"><TYPE><SPEC-OBJECT-TYPE-REF>{obj_type}'
        f'</SPEC-OBJECT-TYPE-REF></TYPE><VALUES>'
        + "".join(f'<ATTRIBUTE-VALUE-STRING THE-VALUE="{escape(v, q)}"><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>'
                  f'ad-{escape(k)}</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>'
                  for k, v in vals.items())
        + "</VALUES></SPEC-OBJECT>" for i, vals in objects.items())
    rel_types = sorted({r for r, _, _ in relations})
    rtypes = "".join(f'<SPEC-RELATION-TYPE IDENTIFIER="{r}" LONG-NAME="{r}" LAST-CHANGE="{STAMP}"/>' for r in rel_types)
    rels = "".join(f'<SPEC-RELATION IDENTIFIER="rel-{k}" LAST-CHANGE="{STAMP}"><TYPE><SPEC-RELATION-TYPE-REF>{r}'
                   f'</SPEC-RELATION-TYPE-REF></TYPE><SOURCE><SPEC-OBJECT-REF>{escape(s)}</SPEC-OBJECT-REF></SOURCE>'
                   f'<TARGET><SPEC-OBJECT-REF>{escape(t)}</SPEC-OBJECT-REF></TARGET></SPEC-RELATION>'
                   for k, (r, s, t) in enumerate(relations))
    hier = "".join(f'<SPEC-HIERARCHY IDENTIFIER="h-{escape(i, q)}" LAST-CHANGE="{STAMP}"><OBJECT><SPEC-OBJECT-REF>'
                   f'{escape(i)}</SPEC-OBJECT-REF></OBJECT></SPEC-HIERARCHY>' for i in objects)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd">'
           f'<THE-HEADER><REQ-IF-HEADER IDENTIFIER="hdr"><TITLE>{escape(title)}</TITLE><REQ-IF-TOOL-ID>'
           f'requirements-trace-agents</REQ-IF-TOOL-ID><REQ-IF-VERSION>1.2</REQ-IF-VERSION></REQ-IF-HEADER></THE-HEADER>'
           f'<CORE-CONTENT><REQ-IF-CONTENT><DATATYPES><DATATYPE-DEFINITION-STRING IDENTIFIER="dt-str" MAX-LENGTH="4000" '
           f'LAST-CHANGE="{STAMP}"/></DATATYPES><SPEC-TYPES><SPEC-OBJECT-TYPE IDENTIFIER="{obj_type}" LONG-NAME="{obj_type}" '
           f'LAST-CHANGE="{STAMP}"><SPEC-ATTRIBUTES>{attrs}</SPEC-ATTRIBUTES></SPEC-OBJECT-TYPE>{rtypes}</SPEC-TYPES>'
           f'<SPEC-OBJECTS>{objs}</SPEC-OBJECTS><SPEC-RELATIONS>{rels}</SPEC-RELATIONS><SPECIFICATIONS>'
           f'<SPECIFICATION IDENTIFIER="spec" LONG-NAME="{escape(title)}" LAST-CHANGE="{STAMP}"><CHILDREN>{hier}</CHILDREN>'
           f'</SPECIFICATION></SPECIFICATIONS></REQ-IF-CONTENT></CORE-CONTENT></REQ-IF>')
    return xml.encode()
