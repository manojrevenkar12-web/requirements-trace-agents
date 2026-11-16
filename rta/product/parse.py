"""One requirement clause into a structured requirement: condition, subject, comparator, value, unit, label.

The value of a requirement is the number a comparator governs. A number in a condition ("when the coolant
exceeds 65 °C", "at -30 °C") is part of the condition, not the requirement, and changes which baseline item it
traces to.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from rta.product.units import Mention, canonical, mentions

INF = math.inf
MODAL = re.compile(r"\b(shall|must|is required to|are required to|has to|have to)\b", re.I)
COND = re.compile(r"^(?P<kw>when|while|if|where|in case|during|as soon as)\b(?P<cond>[^,]+),\s*(?P<rest>.+)$", re.I)
EARS = {"when": "event", "as soon as": "event", "while": "state", "during": "state", "if": "unwanted",
        "in case": "unwanted", "where": "optional"}
MAX = r"no more than|not more than|at most|at the most|maximum(?: of)?|max\.?|<=|≤|less than or equal to|" \
      r"(?:must|shall) not exceed|not to exceed|not exceed|limited to|(?<![-\w])up to|no greater than|not greater than"
MIN = r"at least|not less than|no less than|minimum(?: of)?|min\.?|>=|≥|greater than or equal to|no lower than|" \
      r"not lower than|more than|above"
COMP = re.compile(rf"(?P<max>{MAX})|(?P<min>{MIN})", re.I)
ADJ = re.compile(r"(maximum|minimum)(?: of)?", re.I)
RANGE_SEP = re.compile(r"^\s*(?:and|to|\.\.\.|…|–|-|until)\s*$", re.I)
STOP = set("""a an the of to and or in on at for by with within from be is are shall must should will has have that this
its it as than not no least most more less maximum minimum max min which any all under each between""".split())


@dataclass
class Parsed:
    text: str
    kind: str = "none"            # min | max | range | eq | none
    lo: float | None = None
    hi: float | None = None
    unit: str | None = None       # canonical
    unit_written: str | None = None
    dim: str | None = None
    ears: str = "ubiquitous"
    condition: str | None = None
    cond_sig: tuple = ()
    label: tuple = ()
    values_seen: int = 0
    value_span: tuple[int, int] | None = None
    notes: list[str] = field(default_factory=list)


def is_candidate(text: str) -> bool:
    return bool(MODAL.search(text)) and not re.match(r"^(note|informative|hint|remark)\b", text, re.I)


def split(text: str) -> list[str]:
    """'The X shall A and shall B.' -> ['The X shall A', 'The X shall B']. A range ('between 1 and 2') is not split."""
    t = text.rstrip(". ")
    m = re.match(r"^(?P<head>.*?\b(?:shall|must)\b)(?P<a>.+?)\s+and\s+(?P<modal>shall|must)\b(?P<b>.+)$", t, re.I)
    if not m:
        return [t]
    subj = re.split(r"\b(?:shall|must)\b", m.group("head"), maxsplit=1, flags=re.I)[0].strip()
    first = f"{m.group('head')}{m.group('a')}".strip()
    second = f"{subj} {m.group('modal')}{m.group('b')}".strip()
    return [first] + split(second)


def parse(text: str, locale: str) -> Parsed:
    t = text.rstrip(". ")
    p = Parsed(text=t)
    body = t
    cm = COND.match(t)
    cond_mentions: list[Mention] = []
    if cm:
        p.ears = EARS[cm.group("kw").lower()]
        p.condition = f"{cm.group('kw')}{cm.group('cond')}".strip()
        cond_mentions = mentions(p.condition, locale)
        body = cm.group("rest")
    ms = mentions(body, locale)
    p.values_seen = sum(1 for m in ms if m.unit)
    # find the comparator that governs each number: the closest one in the text before it
    gov = []
    prev_end = 0
    pending = None                   # "a maximum winding temperature of 175 °C": the adjective waits for "of"
    for m in ms:
        window = body[prev_end:m.start]
        found = list(COMP.finditer(window))
        kind = None
        if found:
            last = found[-1]
            if window[last.end():].strip() in ("", "of", ":") and not ADJ.fullmatch(last.group(0).strip()):
                kind = "max" if last.group("max") else "min"
            else:
                adj = [f for f in found if ADJ.fullmatch(f.group(0).strip())]
                if adj:
                    pending = "max" if adj[0].group("max") else "min"
                if window[last.end():].strip() in ("", "of", ":") and ADJ.fullmatch(last.group(0).strip()) \
                        and len(adj) == 1:
                    kind, pending = pending, None
        if kind is None and pending and re.search(r"\b(of|:)\s*$", window):
            kind, pending = pending, None
        gov.append((m, kind, window))
        prev_end = m.end
    chosen = None
    for i, (m, kind, window) in enumerate(gov):
        nxt = gov[i + 1] if i + 1 < len(gov) else None
        if nxt and RANGE_SEP.match(nxt[2]) and (re.search(r"\b(between|from|range of)\s*$", window, re.I)
                                                 or nxt[2].strip() in ("...", "…")) and (m.unit or nxt[0].unit):
            unit = m.unit or nxt[0].unit
            lo, cu, dim = canonical(m.value, unit)
            hi, _, _ = canonical(nxt[0].value, nxt[0].unit or unit)
            p.kind, p.lo, p.hi, p.unit, p.dim, p.unit_written = "range", min(lo, hi), max(lo, hi), cu, dim, unit
            chosen = (m.start, nxt[0].end)
            break
        if kind and chosen is None:
            v, cu, dim = canonical(m.value, m.unit)
            p.kind, p.unit, p.dim, p.unit_written = kind, cu, dim, m.unit
            p.lo, p.hi = (v, INF) if kind == "min" else (-INF, v)
            chosen = (m.start, m.end)
    if chosen is None:
        with_unit = [m for m in ms if m.unit]
        if len(with_unit) == 1 and re.search(r"\b(of|be|is|equal to)\s*$", body[:with_unit[0].start], re.I):
            m = with_unit[0]
            v, cu, dim = canonical(m.value, m.unit)
            p.kind, p.lo, p.hi, p.unit, p.dim, p.unit_written = "eq", v, v, cu, dim, m.unit
            chosen = (m.start, m.end)
    p.value_span = chosen
    # the other numbers are conditions (at -30 °C) or part of the label (at 1 m, for 10 s)
    sig = []
    for m in cond_mentions + [m for m in ms if not chosen or not (chosen[0] <= m.start < chosen[1])]:
        v, cu, dim = canonical(m.value, m.unit)
        if dim:
            sig.append((dim, round(v, 3)))
    p.cond_sig = tuple(sorted(sig))
    label_text = body if chosen is None else body[:chosen[0]]
    label_text = COMP.sub(" ", label_text)
    # the subject is who must do it, not what is measured: "The ECU software shall have a start-up time"
    passive = re.search(r"\b(?:shall|must) be \w+.*?\bby the (.+)$", body, re.I)
    subject_text = passive.group(1) if passive else MODAL.split(body, maxsplit=1)[0]
    subject_words = set(re.findall(r"[a-zA-Z][a-zA-Z-]+", subject_text.lower())) if MODAL.search(body) else set()
    if not passive:
        label_text = MODAL.split(label_text, maxsplit=1)[-1]
    p.label = tuple(w for w in re.findall(r"[a-zA-Z][a-zA-Z-]+", label_text.lower())
                    if w not in STOP and w not in subject_words)
    return p


def row_clause(cells: list[str], header: list[str] | None) -> tuple[str | None, str, str | None]:
    """A technical-parameters row as (id, clause, subsystem as written)."""
    h = [c.lower() for c in (header or [])]
    get = {}
    if h and len(h) == len(cells):
        for name, c in zip(h, cells):
            get[name] = c
    else:
        names = ["id", "subsystem", "parameter", "requirement", "unit"][-len(cells):]
        get = dict(zip(names, cells))
    rid = get.get("id") or None
    sub = get.get("subsystem") or get.get("component")
    param = get.get("parameter", "")
    req = get.get("requirement") or get.get("value", "")
    unit = get.get("unit", "")
    req = req.replace("...", " to ").replace("…", " to ")
    if " to " in req:
        req = "between " + req.replace(" to ", f" {unit} and ", 1)
    subject = f"The {sub.lower()}" if sub else "It"
    lead = ""
    cm = re.search(r"\((?P<c>(?:when|while|if|during)\b[^)]*)\)", param, re.I)
    if cm:                           # "Phase current (when the coolant exceeds 65 °C)" -> an event-driven clause
        lead = cm.group("c")[0].upper() + cm.group("c")[1:] + ", "
        param = (param[:cm.start()] + param[cm.end():]).strip()
        subject = subject[0].lower() + subject[1:]
    clause = f"{lead}{subject} shall have a {param[0].lower() + param[1:] if param else 'value'} {req} {unit}"
    return rid, re.sub(r"\s+", " ", clause).strip(), sub
