"""A customer specification in, a reviewed requirement set out.

read -> guard -> candidate sentences -> split compounds -> parse values -> subject (by name, else the model, checked)
-> quality rules -> trace link -> compliance (code) -> conflicts -> review queue and questions to the customer.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from rta.product import guard, ingest, quality
from rta.product.model import Model
from rta.product.parse import Parsed, is_candidate, parse, row_clause, split
from rta.product.trace import Baseline, link, subject
from rta.product.units import locale_of

INF = math.inf


@dataclass
class Requirement:
    uid: str
    rid: str | None
    text: str
    section: str
    sub: str | None
    sub_by: str                      # name | model | row | none
    kind: str
    lo: float | None
    hi: float | None
    unit: str | None
    dim: str | None
    ears: str
    cond_sig: tuple
    label: tuple
    defects: list[str]
    table: bool
    link: str | None = None
    link_outcome: str = ""
    candidates: list = field(default_factory=list)
    compliance: str = "clarify"      # compliant | partial | not_compliant | open | clarify | review
    review: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)

    def interval(self) -> tuple:
        return self.kind, self.lo, self.hi, self.unit


@dataclass
class Analysis:
    name: str
    locale: str
    requirements: list[Requirement]
    conflicts: list[tuple[str, str]]
    quarantined: list[tuple[str, str]]
    dropped: list[str]
    model_calls: int = 0

    def summary(self) -> dict:
        rs = self.requirements
        return {"requirements": len(rs), "review": sum(1 for r in rs if r.review),
                "questions": sum(1 for r in rs if r.questions), "conflicts": len(self.conflicts),
                "quarantined": len(self.quarantined),
                "compliance": {k: sum(1 for r in rs if r.compliance == k) for k in
                               ("compliant", "partial", "not_compliant", "open", "clarify", "review")}}

    def to_dict(self) -> dict:
        d = asdict(self)
        for r in d["requirements"]:
            r["lo"] = None if r["lo"] in (INF, -INF) else r["lo"]
            r["hi"] = None if r["hi"] in (INF, -INF) else r["hi"]
        return d


def analyse(data: bytes, base: Baseline, model: Model, cfg: dict, name: str) -> Analysis:
    blocks = ingest.read(data)
    loc = locale_of(" ".join(b.text for b in blocks))
    out: list[Requirement] = []
    quarantined, dropped = [], []
    header = None
    n = 0
    dimless = set(cfg["dimensionless"])
    for b in blocks:
        if b.kind == "heading":
            header = None
            continue
        if b.kind == "header-row":
            header = b.cells
            continue
        if b.kind == "row":
            rid, clause, _ = row_clause(b.cells, header)
            parts, compound, table, rid = [clause], False, True, rid
        else:
            why = guard.suspicious(b.text)
            if why:
                quarantined.append((b.text, why))
                continue
            if not is_candidate(b.text):
                continue
            parts, table, rid = split(b.text), False, b.rid
            compound = len(parts) > 1
        for k, clause in enumerate(parts):
            n += 1
            uid = (f"{rid}.{k + 1}" if compound else rid) if rid else f"{name}-{n:03d}"
            p = parse(clause, loc)
            sub = subject(clause, base.subsystems)
            by = "row" if (table and sub) else ("name" if sub else "none")
            review = []
            if sub is None:
                ans = model.ask("classify", clause, base.subsystems)
                if ans.get("is_requirement") is False and p.kind == "none":
                    dropped.append(clause)
                    continue
                s = ans.get("subsystem")
                known = {d for x in base.subsystems for d in base.dims(x)}
                if s in base.subsystems and (p.dim is None or p.dim in base.dims(s) or p.dim not in known):
                    sub, by = s, "model"
                elif s in base.subsystems:
                    review.append(f"model said '{s}' but the supplier has no {p.dim} requirement there")
                else:
                    review.append("subject is not a known subsystem")
            r = Requirement(uid, rid, clause, b.section, sub, by, p.kind, p.lo, p.hi, p.unit, p.dim, p.ears,
                            p.cond_sig, p.label, quality.check(clause, p, compound, dimless), table, review=review)
            decide(r, p, base, cfg)
            out.append(r)
    conflicts = find_conflicts(out)
    for a, b in conflicts:
        for r in out:
            if r.uid in (a, b):
                other = b if r.uid == a else a
                r.questions.append(f"states a different value from {other} for the same quantity")
    return Analysis(name, loc, out, conflicts, quarantined, dropped)


def decide(r: Requirement, p: Parsed, base: Baseline, cfg: dict) -> None:
    """Compliance is computed, never asked: the customer's interval against the supplier's own requirement."""
    if "vague" in r.defects or r.kind == "none":
        r.compliance = "clarify"
        r.questions.append("no measurable acceptance criterion")
        return
    if "missing_unit" in r.defects or r.dim is None:
        r.compliance = "clarify"
        r.questions.append("value has no unit")
        return
    r.link, r.link_outcome, r.candidates = link(p, r.sub, base, cfg)
    if r.link_outcome == "none_in_baseline" and r.sub:
        r.compliance = "open"
        return
    if r.link is None:
        r.compliance = "review"
        r.review.append({"ambiguous": "two baseline requirements fit equally well",
                         "no_subsystem": "subsystem unknown, trace not proposed"}.get(r.link_outcome, r.link_outcome))
        return
    item = base.items[r.link]
    r.compliance = comply(r.kind, r.lo, r.hi, item.parsed)
    if r.compliance == "review":
        r.review.append("customer and supplier state the value in different forms")
    if r.review and r.compliance != "review":
        r.compliance = "review"


def comply(kind: str, lo: float, hi: float, cap: Parsed) -> str:
    eps = 1e-9
    if kind == "min" and cap.kind == "min":
        return "compliant" if cap.lo >= lo - eps else "not_compliant"
    if kind == "max" and cap.kind == "max":
        return "compliant" if cap.hi <= hi + eps else "not_compliant"
    if kind == "range" and cap.kind == "range":
        if cap.lo <= lo + eps and cap.hi >= hi - eps:
            return "compliant"
        return "partial" if (cap.lo < hi and cap.hi > lo) else "not_compliant"
    return "review"


def same_value(a: Requirement, b: Requirement) -> bool:
    def close(x, y):
        if x is None or y is None or math.isinf(x) or math.isinf(y):
            return x == y
        return abs(x - y) <= 1e-6 * max(1.0, abs(x), abs(y))
    return a.kind == b.kind and a.unit == b.unit and close(a.lo, b.lo) and close(a.hi, b.hi)


def quantity_key(r: Requirement) -> tuple | None:
    if r.dim is None or r.sub is None:
        return None
    if r.link:
        return ("link", r.link)
    return ("label", r.sub, r.dim, frozenset(r.label) - {w for w in (r.sub or "").lower().split()}, r.cond_sig)


def find_conflicts(reqs: list[Requirement]) -> list[tuple[str, str]]:
    """The same quantity, under the same condition, stated twice with different values."""
    groups: dict[tuple, list[Requirement]] = {}
    for r in reqs:
        k = quantity_key(r)
        if k:
            groups.setdefault(k, []).append(r)
    out = []
    for g in groups.values():
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if not same_value(g[i], g[j]):
                    out.append((g[i].uid, g[j].uid))
    return out
