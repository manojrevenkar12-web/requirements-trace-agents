"""The simulated customer specifications, the supplier's baseline and the engineers' ground truth.

Everything the product is scored against is made here. The product never imports this module: it gets document
bytes and a ReqIF file, as it would from a customer portal and from DOORS or Polarion.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from rta.keyed import rng

INF = math.inf

# the world's own unit table for writing values in another unit (the product has its own, independently written)
ALT = {
    ("kg", "g"): lambda v: v * 1000, ("°C", "K"): lambda v: v + 273.15, ("rpm", "1/min"): lambda v: v,
    ("l/min", "l/h"): lambda v: v * 60, ("mbar", "kPa"): lambda v: v / 10, ("bar", "MPa"): lambda v: v / 10,
    ("kW", "W"): lambda v: v * 1000, ("h", "min"): lambda v: v * 60, ("kg", "t"): lambda v: v / 1000,
    ("g", "kg"): lambda v: v / 1000, ("ms", "s"): lambda v: v / 1000, ("s", "ms"): lambda v: v * 1000, ("dB(A)", "dB(A)"): lambda v: v,
}
PAST = {"deliver": "delivered", "provide": "provided", "achieve": "achieved", "reach": "reached",
        "supply": "supplied", "use": "used", "need": "needed", "cause": "caused", "limit": "limited",
        "keep": "kept", "maintain": "maintained", "transfer": "transferred", "store": "stored"}


@dataclass
class Quantity:
    id: str
    sub: str
    label: str
    verb: str
    unit: str
    kind: str
    cap: object
    around: object
    alt: str | None = None
    cond: str | None = None
    event: str | None = None
    baseline: bool = True
    decimals: int = 0
    step: float = 1


@dataclass
class Req:
    key: str
    spec: str
    qid: str | None
    sub: str
    kind: str                       # min | max | range | none
    lo: float | None
    hi: float | None
    unit: str | None
    text: str                       # the clause as the engineers read it
    sentence: int                   # compound requirements share a sentence
    defects: frozenset = frozenset()
    compliance: str = "clarify"     # compliant | partial | not_compliant | open | clarify
    link: str | None = None
    rid: str | None = None
    role: str = "main"              # main | conflict | restated
    table: bool = False
    style: dict = field(default_factory=dict)


@dataclass
class BaseReq:
    id: str
    sub: str
    qid: str | None
    text: str
    kind: str
    lo: float | None
    hi: float | None
    unit: str | None
    tests: list[str]


@dataclass
class Spec:
    id: str
    customer: str
    rev: str
    comma: bool
    ids: bool
    fmt: str
    blocks: list[dict]              # heading / para / row, in reading order
    reqs: list[Req]
    notes: list[str]
    injections: list[str]
    conflicts: list[tuple[str, str]]


@dataclass
class World:
    name: str
    system: dict
    subsystems: dict
    quantities: dict[str, Quantity]
    baseline: list[BaseReq]
    specs: dict[str, Spec]          # "<spec>/A" and "<spec>/B"
    changes: dict[str, dict]        # spec -> key -> change kind
    impact: dict[str, set]          # spec -> baseline ids and tests a real change touches
    model: dict


def load(path: str | Path, quick: bool = False) -> World:
    cfg = yaml.safe_load(Path(path).read_text())
    return build(cfg, quick)


# ---------------------------------------------------------------- numbers and phrases

def fmt_num(v: float, comma: bool, decimals: int = 0) -> str:
    if decimals == 0 and abs(v - round(v)) < 1e-9:
        s = f"{int(round(v)):,}"
        return s.replace(",", "." if comma else ",") if abs(v) >= 10000 else s.replace(",", "")
    s = f"{v:.{max(decimals, 1)}f}".rstrip("0").rstrip(".") if decimals == 0 else f"{v:.{decimals}f}"
    return s.replace(".", ",") if comma else s


def phrase(kind: str, how: str, label: str, a: str, b: str | None, unit: str) -> str:
    u = f" {unit}" if unit else ""
    if kind == "range" and how == "tolerance":
        return f"{'an' if label[0] in 'aeiou' else 'a'} {label} of {a}{u} ± {b}{u}"
    if kind == "range":
        if how in ("between", "at_least", "minimum", "not_less", "no_more", "maximum", "up_to_max"):
            return f"an {label} between {a}{u} and {b}{u}" if label[0] in "aeiou" else f"a {label} between {a}{u} and {b}{u}"
        return f"an {label} from {a}{u} to {b}{u}" if label[0] in "aeiou" else f"a {label} from {a}{u} to {b}{u}"
    art = "an" if label[0] in "aeiou" else "a"
    table = {
        "at_least": f"{art} {label} of at least {a}{u}",
        "not_less": f"{art} {label} of not less than {a}{u}",
        "minimum": f"a minimum {label} of {a}{u}",
        "no_more": f"{art} {label} of no more than {a}{u}",
        "maximum": f"a maximum {label} of {a}{u}",
        "up_to_max": f"{art} {label} of at most {a}{u}",
        "min_abbr": f"{art} {label} of min. {a}{u}",
        "max_abbr": f"{art} {label} of max. {a}{u}",
        "symbol": f"{art} {label} {'≥' if kind == 'min' else '≤'} {a}{u}",
        "greater_equal": f"{art} {label} greater than or equal to {a}{u}",
        "less_equal": f"{art} {label} less than or equal to {a}{u}",
    }
    return table[how]


RANGE_HOW = {"between", "from_to", "tolerance"}
MIN_HOW = {"at_least", "not_less", "minimum", "min_abbr", "symbol", "greater_equal"}
MAX_HOW = {"no_more", "maximum", "up_to_max", "max_abbr", "symbol", "less_equal", "must_not_exceed", "limited_to"}


def clause(q: Quantity, subj: str, how: str, a: str, b: str | None, unit: str, passive: bool, defects: set) -> str:
    """One requirement clause (no trailing full stop)."""
    if q.kind == "max" and how == "must_not_exceed":
        return f"The {q.label} of the {subj} must not exceed {a} {unit}".replace(" %", " %")
    if q.kind == "max" and how == "limited_to":
        return f"The {q.label} of the {subj} shall be limited to {a} {unit}"
    obj = phrase(q.kind, how, q.label, a, b, unit)
    verb = q.verb
    if passive and verb in PAST:
        head, *rest = verb.split()
        tail = (" " + " ".join(rest)) if rest else ""
        s = f"{obj[0].upper()}{obj[1:]} shall be {PAST[head]}{tail} by the {subj}"
        defects.add("passive")
        return s
    return f"The {subj} shall {verb} {obj}"


# ---------------------------------------------------------------- the world

def build(cfg: dict, quick: bool = False) -> World:
    name = cfg["name"]
    code = cfg["system"]["code"]
    qs = {q["id"]: Quantity(**q) for q in cfg["quantities"]}
    subs = cfg["subsystems"]
    baseline = make_baseline(name, code, qs, subs)
    by_q = {b.qid: b for b in baseline if b.qid}
    n = cfg["quick_specs"] if quick else cfg["specs"]
    specs, changes, impact = {}, {}, {}
    for i in range(n):
        sid = f"{code}-LH-{i + 1:02d}"
        a = make_spec(cfg, name, sid, cfg["customers"][i % len(cfg["customers"])], qs, subs, by_q)
        b, ch = revise(cfg, name, a, qs, subs, by_q)
        specs[f"{sid}/A"], specs[f"{sid}/B"] = a, b
        changes[sid] = ch
        hit = set()
        for key, kind in ch.items():
            if kind in ("changed_value", "deleted"):
                r = next(r for r in a.reqs if r.key == key)
                if r.link:
                    hit.add(r.link)
                    hit.update(next(x for x in baseline if x.id == r.link).tests)
        impact[sid] = hit
    return World(name, cfg["system"], subs, qs, baseline, specs, changes, impact, cfg["model"])


def interval(kind: str, v) -> tuple[float, float]:
    if kind == "min":
        return float(v), INF
    if kind == "max":
        return -INF, float(v)
    return float(v[0]), float(v[1])


def comply(q: Quantity, lo: float, hi: float) -> str:
    if q.kind == "min":
        return "compliant" if q.cap >= lo - 1e-9 else "not_compliant"
    if q.kind == "max":
        return "compliant" if q.cap <= hi + 1e-9 else "not_compliant"
    c_lo, c_hi = q.cap
    if c_lo <= lo + 1e-9 and c_hi >= hi - 1e-9:
        return "compliant"
    return "partial" if (c_lo < hi and c_hi > lo) else "not_compliant"


def make_baseline(name: str, code: str, qs: dict, subs: dict) -> list[BaseReq]:
    out, t = [], 0
    for i, q in enumerate(qs.values()):
        if not q.baseline:
            continue
        lo, hi = interval(q.kind, q.cap)
        u = q.unit
        how = {"min": "at_least", "max": "no_more", "range": "from_to"}[q.kind]
        a = fmt_num(q.cap[0] if q.kind == "range" else q.cap, False, q.decimals)
        b = fmt_num(q.cap[1], False, q.decimals) if q.kind == "range" else None
        text = clause(q, subs[q.sub]["name"], how, a, b, u, False, set())
        text = (f"{q.event}, t{text[1:]}" if q.event else text) + (f" {q.cond}" if q.cond else "") + "."
        tests = []
        for k in range(1 + (i % 2)):
            t += 1
            tests.append(f"TC-{code}-{t:04d}")
        out.append(BaseReq(f"SYS-{code}-{len(out) + 1:04d}", q.sub, q.id, text, q.kind, lo, hi, u, tests))
    # requirements the customers do not ask about, close enough to confuse a naive matcher
    r = rng(name, "baseline-extra")
    for sub, s in subs.items():
        if sub == "drive_unit" or not s.get("has_mass", True):
            continue
        m = float(r.integers(6, 46))
        t += 1
        out.append(BaseReq(f"SYS-{code}-{len(out) + 1:04d}", sub, None,
                           f"The {s['name']} shall have a mass of no more than {m:.0f} kg.", "max", -INF, m, "kg",
                           [f"TC-{code}-{t:04d}"]))
    return out


def draw_value(name: str, sid: str, q: Quantity, salt: str = "") -> object:
    r = rng(name, sid, q.id, "value", salt)
    if q.kind == "range":
        lo0, hi0 = q.around
        lo = lo0 + float(r.choice([0, 0, 0, -5, 5, -10]))
        hi = hi0 + float(r.choice([0, 0, 0, 5, -5, 10, 15]))
        return [lo, hi]
    rel = float(r.normal(0, 0.035))
    v = q.around * (1 + rel)
    step = q.step
    v = round(v / step) * step if q.decimals == 0 else round(v, q.decimals)
    return v


def render_value(q: Quantity, v, unit: str, comma: bool) -> tuple[str, str | None]:
    conv = ALT.get((q.unit, unit), lambda x: x) if unit != q.unit else (lambda x: x)
    dec = q.decimals
    if q.kind == "range":
        a, b = conv(v[0]), conv(v[1])
        dec = 2 if unit == "K" else dec
        return fmt_num(a, comma, dec if abs(a - round(a)) > 1e-9 else 0), fmt_num(b, comma, dec if abs(b - round(b)) > 1e-9 else 0)
    x = conv(v)
    if abs(x - round(x)) > 1e-9:
        dec = max(dec, 2 if unit in ("K", "kPa") else 1)
    return fmt_num(x, comma, dec if abs(x - round(x)) > 1e-9 else 0), None


def make_spec(cfg, name, sid, customer, qs, subs, by_q, rev="A") -> Spec:
    st = cfg["style"]
    r = rng(name, sid, "spec")
    comma = bool(r.random() < st["decimal_comma"])
    ids = bool(r.random() < st["ids"])
    fmt = str(r.choice(st["formats"]))
    reqs: list[Req] = []
    n = 0

    def new_key():
        nonlocal n
        n += 1
        return f"{sid}:{n:03d}"

    order = [q for q in qs.values()]
    # each spec asks for most quantities, not all
    asked = [q for q in order if rng(name, sid, q.id, "asked").random() < 0.9]
    sentence = 0
    for q in asked:
        rq = rng(name, sid, q.id, "style")
        v = draw_value(name, sid, q)
        lo, hi = interval(q.kind, v)
        base = by_q.get(q.id)
        comp = comply(q, lo, hi) if base else "open"
        reqs.append(Req(new_key(), sid, q.id, q.sub, q.kind, lo, hi, q.unit, "", 0, frozenset(), comp,
                        base.id if base else None, style={"v": v, "r": float(rq.random())}))
    # vague requirements
    for vg in cfg["vague"]:
        if rng(name, sid, vg["text"], "asked").random() < 0.7:
            reqs.append(Req(new_key(), sid, None, vg["sub"], "none", None, None, None, "", 0,
                            frozenset({"vague"}), "clarify", None, style={"vague": vg["text"], "r": 0.5}))
    # write every requirement
    written: list[Req] = []
    i = 0
    main = list(reqs)
    while i < len(main):
        rq = main[i]
        rr = rng(name, sid, rq.key, "write")
        if rq.qid and i + 1 < len(main) and main[i + 1].qid and main[i + 1].sub == rq.sub \
                and rr.random() < st["compound"] and not qs[rq.qid].event and not qs[main[i + 1].qid].event:
            pair = [rq, main[i + 1]]
            i += 2
        else:
            pair = [rq]
            i += 1
        sentence += 1
        written.extend(write(cfg, name, sid, pair, qs, subs, comma, sentence, rev))
    reqs = written
    # the same quantity stated again: once with another value (a conflict), once in another unit (not a conflict)
    conflicts = []
    cands = [x for x in reqs if x.qid and x.kind != "range" and not x.table and "missing_unit" not in x.defects and len(
        [y for y in reqs if y.qid == x.qid]) == 1]
    rc = rng(name, sid, "conflicts")
    picks = list(rc.permutation(len(cands)))[: st["conflicts"] + st["restated"]]
    for j, pi in enumerate(picks):
        x = cands[int(pi)]
        q = qs[x.qid]
        v0 = x.style["v"]
        if j < st["conflicts"]:
            if q.decimals:
                v = round(v0 + (1.5 if q.kind == "min" else -1.5), q.decimals)
            else:
                v = round(v0 * (1.08 if q.kind == "min" else 0.92) / q.step) * q.step
            unit, role = q.unit, "conflict"
        else:
            v, unit, role = v0, (q.alt or q.unit), "restated"
        lo, hi = interval(q.kind, v)
        sentence += 1
        y = write(cfg, name, sid, [Req(new_key(), sid, q.id, q.sub, q.kind, lo, hi, q.unit, "", 0, frozenset(),
                                         comply(q, lo, hi) if by_q.get(q.id) else "open",
                                         x.link, role=role, style={"v": v, "r": 0.9, "force_unit": unit,
                                                                   "force_table": True})],
                  qs, subs, comma, sentence, rev)[0]
        reqs.append(y)
        if role == "conflict":
            conflicts.append((x.key, y.key))
    injections = [str(s) for s in rng(name, sid, "inj").permutation(cfg["injections"])[: st["injections"]]]
    notes = [str(s) for s in rng(name, sid, "notes").permutation(cfg["notes"])[:4]]
    if ids:
        for k, x in enumerate(sorted({x.sentence for x in reqs})):
            for y in reqs:
                if y.sentence == x:
                    y.rid = f"{customer.split()[0][:3].upper()}-{k + 1:03d}"
    blocks = layout(cfg, name, sid, customer, rev, reqs, notes, injections, subs, comma)
    return Spec(sid, customer, rev, comma, ids, fmt, blocks, reqs, notes, injections, conflicts)


def write(cfg, name, sid, group: list[Req], qs, subs, comma, sentence, rev) -> list[Req]:
    """Write one sentence (one requirement, or two joined by 'and') and record its defects in the truth."""
    st = cfg["style"]
    first = group[0]
    r = rng(name, sid, first.key, "words", rev, first.style.get("salt", ""))
    sname = subs[first.sub]["name"]
    syn = first.sub != "drive_unit" or True
    subj = str(r.choice(subs[first.sub]["synonyms"])) if (syn and r.random() < st["synonym_subject"]) else sname
    if first.qid is None:
        text = first.style["vague"].replace("{S}", subj)
        return [replace(first, text=text.rstrip("."), sentence=sentence, defects=frozenset({"vague"}),
                        style={**first.style, "sentence_text": text, "subject": subj})]
    q = qs[first.qid]
    table = bool(first.style.get("force_table")) or (len(group) == 1 and r.random() < st["table"] and not q.event)
    out = []
    parts = []
    for k, rq in enumerate(group):
        q = qs[rq.qid]
        defects = set()
        unit = rq.style.get("force_unit") or (q.alt if (q.alt and r.random() < st["alt_unit"]) else q.unit)
        a, b = render_value(q, rq.style["v"], unit, comma)
        if table:
            out.append(replace(rq, text="", sentence=sentence, table=True, defects=frozenset(),
                               style={**rq.style, "row": table_row(q, subs, a, b, unit, r), "unit_written": unit}))
            continue
        pool = {"range": RANGE_HOW, "min": MIN_HOW, "max": MAX_HOW}[q.kind]
        hows = [h for h in st["phrasings"] if h in pool] or [{"range": "between", "min": "at_least", "max": "no_more"}[q.kind]]
        how = str(r.choice(hows))
        if how == "tolerance":
            if unit in ("°C", "K"):
                how = "between"
            else:
                conv = ALT.get((q.unit, unit), lambda x: x) if unit != q.unit else (lambda x: x)
                lo_, hi_ = conv(rq.style["v"][0]), conv(rq.style["v"][1])
                a, b = fmt_num((lo_ + hi_) / 2, comma, q.decimals), fmt_num((hi_ - lo_) / 2, comma, q.decimals)
        shown_unit = unit
        if r.random() < st["no_unit"] and len(group) == 1 and q.unit:
            shown_unit = ""
            defects.add("missing_unit")
        passive = r.random() < st["passive"] and len(group) == 1
        c = clause(q, subj, how, a, b, shown_unit, passive, defects)
        if q.event:
            c = f"{q.event}, {c[0].lower()}{c[1:]}"
        if q.cond:
            c += f" {q.cond}"
        if k == 0 and len(group) == 1:
            x = r.random()
            if x < st["escape"]:
                c += str(r.choice([", if technically feasible", ", where possible", ", as far as practicable"]))
                defects.add("escape")
            elif x < st["escape"] + st["universal"]:
                c += " under all operating conditions"
                defects.add("universal")
            elif x < st["escape"] + st["universal"] + st["open_ended"]:
                c += ", including but not limited to trailer operation"
                defects.add("open_ended")
            elif x < st["escape"] + st["universal"] + st["open_ended"] + st["oblique"]:
                c += " in normal and/or degraded mode"
                defects.add("oblique")
        if len(group) == 2:
            defects.add("combinator")
        parts.append(c)
        out.append(replace(rq, text=c, sentence=sentence, defects=frozenset(defects), table=False,
                           compliance="clarify" if "missing_unit" in defects else rq.compliance,
                           style={**rq.style, "subject": subj, "unit_written": unit}))
    if table:
        return out
    if len(parts) == 2:
        second = parts[1]
        for lead in (f"The {subj} shall ",):
            if second.startswith(lead):
                second = "shall " + second[len(lead):]
        sentence_text = f"{parts[0]} and {second}."
    else:
        sentence_text = parts[0] + "."
    return [replace(x, style={**x.style, "sentence_text": sentence_text}) for x in out]


def table_row(q: Quantity, subs, a, b, unit, r) -> list[str]:
    if q.kind == "range":
        val = f"{a} … {b}"
    else:
        mark = str(r.choice(["≥", "min."])) if q.kind == "min" else str(r.choice(["≤", "max."]))
        val = f"{mark} {a}"
    label = q.label[0].upper() + q.label[1:] + (f" ({q.event[0].lower()}{q.event[1:]})" if q.event else "")
    label += f" {q.cond}" if q.cond else ""
    return [subs[q.sub]["name"].capitalize(), label, val, unit]


def layout(cfg, name, sid, customer, rev, reqs, notes, injections, subs, comma) -> list[dict]:
    r = rng(name, sid, "layout", rev)
    blocks = [{"kind": "title", "text": f"Lastenheft {cfg['system']['name']} for {customer}"},
              {"kind": "para", "text": f"Document {sid}, revision {rev}. Customer: {customer}."}]
    chapters = ["Scope", "General requirements"] + (["Definitions"] if rev == "B" else []) + \
               list(dict.fromkeys(s["section"] for s in subs.values())) + ["Technical parameters", "Document control"]
    body = {c: [] for c in chapters}
    body["Scope"].append({"kind": "para", "text": f"This document specifies the {cfg['system']['name']} "
                                                   f"that {customer} procures for its next vehicle platform."})
    for k, note in enumerate(notes):
        secs = ["Scope"] + list(dict.fromkeys(s["section"] for s in subs.values()))
        body[secs[k % len(secs)]].append({"kind": "para", "text": note})
    if rev == "B":
        body["Definitions"].append({"kind": "para", "text": "Terms follow ISO/IEC/IEEE 29148 unless stated otherwise."})
    seen = set()
    for x in reqs:
        if x.sentence in seen:
            continue
        seen.add(x.sentence)
        group = [y for y in reqs if y.sentence == x.sentence]
        if x.table:
            row = x.style["row"]
            body["Technical parameters"].append({"kind": "row", "cells": ([x.rid] if x.rid else []) + row,
                                                 "keys": [y.key for y in group]})
            continue
        chap = "General requirements" if x.qid is None else subs[x.sub]["section"]
        text = x.style["sentence_text"]
        if x.rid:
            text = f"[{x.rid}] {text}"
        body[chap].append({"kind": "para", "text": text, "keys": [y.key for y in group]})
    for inj in injections:
        body["Document control"].append({"kind": "para", "text": inj, "injection": True})
    body["Document control"].append({"kind": "para", "text": f"Revision {rev} released by {customer} engineering."})
    for c in body:
        if c not in ("Scope", "Technical parameters", "Document control", "Definitions"):
            paras = body[c]
            perm = list(r.permutation(len(paras)))
            body[c] = [paras[int(p)] for p in perm]
    for k, c in enumerate(chapters):
        blocks.append({"kind": "heading", "text": f"{k + 1} {c}"})
        if c == "Technical parameters" and body[c]:
            head = (["ID"] if any(len(b["cells"]) == 5 for b in body[c]) else []) + ["Subsystem", "Parameter", "Requirement", "Unit"]
            blocks.append({"kind": "row", "cells": head, "header": True})
            for b in body[c]:
                if len(b["cells"]) < len(head):
                    b["cells"] = [""] + b["cells"]
        blocks.extend(body[c])
    return blocks


# ---------------------------------------------------------------- revision B

def revise(cfg, name, a: Spec, qs, subs, by_q) -> tuple[Spec, dict]:
    rv = cfg["revision"]
    twins = {x.qid for x in a.reqs if x.role != "main"}
    changes, reqs = {}, []
    sentences = {}
    for x in a.reqs:
        sentences.setdefault(x.sentence, []).append(x)
    for s, group in sentences.items():
        x = group[0]
        u = float(rng(name, a.id, x.key, "revise").random())
        single = len(group) == 1 and x.role == "main" and x.qid and x.qid not in twins and not x.defects & {"missing_unit"}
        kind = None
        if single:
            if u < rv["changed_value"]:
                kind = "changed_value"
            elif u < rv["changed_value"] + rv["unit_only"] and qs[x.qid].alt and not x.table:
                kind = "unit_only"
            elif u < rv["changed_value"] + rv["unit_only"] + rv["reworded"] and not x.table:
                kind = "reworded"
            elif u < rv["changed_value"] + rv["unit_only"] + rv["reworded"] + rv["deleted"]:
                kind = "deleted"
        if kind is None:
            reqs.extend(group)
            continue
        changes[x.key] = kind
        if kind == "deleted":
            continue
        q = qs[x.qid]
        v = x.style["v"]
        style = {**x.style, "salt": kind}
        if kind == "changed_value":
            if q.kind == "range":
                v = [v[0], v[1] + 10]
            else:
                f = 1.06 if (q.kind == "min") == (u < rv["changed_value"] / 2) else 0.94
                v = v * f
                v = round(v / q.step) * q.step if q.decimals == 0 else round(v, q.decimals)
                if v == x.style["v"]:
                    v = v + q.step if q.decimals == 0 else v + 0.1
            style["v"] = v
        if kind == "unit_only":
            style["force_unit"] = q.alt
        lo, hi = interval(q.kind, v)
        y = replace(x, lo=lo, hi=hi, compliance=comply(q, lo, hi) if x.link else "open", style=style)
        new = write(cfg, name, a.id, [y], qs, subs, a.comma, x.sentence, "B")
        reqs.extend(replace(z, rid=x.rid) for z in new)
    # two new requirements in revision B: a quantity the spec did not ask about, or a vague one
    asked = {x.qid for x in a.reqs}
    r = rng(name, a.id, "added")
    fresh = [q for q in qs.values() if q.id not in asked]
    fresh = [fresh[int(i)] for i in r.permutation(len(fresh))]
    nmax = max(x.sentence for x in a.reqs)
    for k in range(min(rv["added"], len(fresh))):
        q = fresh[k]
        v = draw_value(name, a.id, q, f"added{k}")
        lo, hi = interval(q.kind, v)
        key = f"{a.id}:B{k + 1:02d}"
        base = by_q.get(q.id)
        y = Req(key, a.id, q.id, q.sub, q.kind, lo, hi, q.unit, "", 0, frozenset(),
                comply(q, lo, hi) if base else "open", base.id if base else None, style={"v": v, "r": 0.5})
        new = write(cfg, name, a.id, [y], qs, subs, a.comma, nmax + k + 1, "B")
        if a.ids:
            new = [replace(z, rid=f"{a.customer.split()[0][:3].upper()}-{900 + k + 1:03d}") for z in new]
        reqs.extend(new)
        changes[key] = "added"
    blocks = layout(cfg, name, a.id, a.customer, "B", reqs, a.notes, a.injections, subs, a.comma)
    conflicts = [(p, q2) for p, q2 in a.conflicts if p not in changes and q2 not in changes]
    return Spec(a.id, a.customer, "B", a.comma, a.ids, a.fmt, blocks, reqs, a.notes, a.injections, conflicts), changes
