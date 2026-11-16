"""The designs compared on the same specifications.

keyword       what a supplier scripts today: sentences with "shall", the first number, the closest-sounding
              baseline item, text diff between revisions
model_only    one long-context model call reads the whole spec and returns requirements, links and verdicts
              (the stand-in model with the error rates in the world file; its numbers follow from those rates)
agents_no_model  the product with no model: unknown subject names go to an engineer
trace_agents  the product: the model answers narrow questions, code checks every answer and decides
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from rta.product import ingest
from rta.product.impact import diff
from rta.product.model import Counted, NoModel
from rta.product.pipeline import Requirement, analyse
from rta.product.trace import Baseline
from rta.product.units import UNITS, canonical

INF = math.inf


@dataclass
class Run:
    reqs: list[Requirement]
    conflicts: list[tuple[str, str]] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)
    obeyed: bool = False


@dataclass
class SpecResult:
    a: Run
    b: Run
    touched: set
    calls: int = 0
    chars: int = 0


def product(model):
    def run(sid: str, files: dict, base: Baseline, cfg: dict, world=None) -> SpecResult:
        counted = Counted(model) if model is not None else NoModel()
        ra = analyse(files["A"], base, counted, cfg, sid)
        rb = analyse(files["B"], base, counted, cfg, sid)
        imp = diff(ra, rb, base)
        wrap = lambda x: Run(x.requirements, x.conflicts, [t for t, _ in x.quarantined])  # noqa: E731
        return SpecResult(wrap(ra), wrap(rb), set(imp.touched), getattr(counted, "calls", 0), getattr(counted, "chars", 0))
    return run


# ------------------------------------------------------------------ keyword baseline

KW_MAX = re.compile(r"\b(maximum|max\.?|at most|no more than|not more than|up to|<=|≤)", re.I)
KW_MIN = re.compile(r"\b(minimum|min\.?|at least|not less than|>=|≥)", re.I)
KW_NUM = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)\s?([A-Za-z°%/()]+)?")
KW_VAGUE = re.compile(r"\b(sufficient|adequate|quickly|minimal|easy|as possible|if technically feasible|where possible)", re.I)


def keyword(sid: str, files: dict, base: Baseline, cfg: dict, world=None) -> SpecResult:
    def one(data: bytes) -> Run:
        out = []
        for k, b in enumerate(ingest.read(data)):
            text = " ".join(b.cells) if b.kind == "row" else b.text
            if b.kind not in ("row", "text") or (b.kind == "text" and not re.search(r"\b(shall|must)\b", text, re.I)):
                continue
            nums = [(float(n.replace(",", "")), u) for n, u in KW_NUM.findall(text) if u and not re.match(r"^\d", u)]
            kind, lo, hi, unit = "none", None, None, None
            m = re.search(r"between\s+(-?[\d,.]+)\s?(\S+)\s+and\s+(-?[\d,.]+)", text)
            if m:
                kind, lo, hi, unit = "range", float(m.group(1).replace(",", "")), float(m.group(3).replace(",", "")), m.group(2)
            elif nums:
                v, unit = nums[0]
                kind = "max" if KW_MAX.search(text) else "min" if KW_MIN.search(text) else "eq"
                lo, hi = (v, INF) if kind == "min" else (-INF, v) if kind == "max" else (v, v)
            sub = next((s for s in base.subsystems if s in text.lower()), None)
            words = set(re.findall(r"[a-z]+", text.lower()))
            best = max(base.items.values(), key=lambda i: len(words & set(re.findall(r"[a-z]+", i.text.lower()))))
            link = best.id if kind != "none" else None
            comp = "clarify" if kind == "none" else "review"
            if link and best.parsed.unit_written == unit and kind in ("min", "max"):
                cap = best.parsed
                comp = ("compliant" if (cap.lo >= lo if kind == "min" else cap.hi <= hi) else "not_compliant") \
                    if cap.kind == kind else "review"
            defects = ["vague"] if KW_VAGUE.search(text) else []
            out.append(Requirement(f"{sid}-{k}", b.rid, text, b.section, sub, "name" if sub else "none", kind, lo, hi,
                                   unit, None, "ubiquitous", (), (), defects, b.kind == "row", link=link,
                                   compliance=comp))
        return Run(out)
    a, b = one(files["A"]), one(files["B"])
    after = {r.text for r in b.reqs}
    touched = set()
    for r in a.reqs:
        if r.text not in after and r.link:
            touched.add(r.link)
            touched.update(base.items[r.link].tests)
    return SpecResult(a, b, touched)


# ------------------------------------------------------------------ the model alone

def model_only(sid: str, files: dict, base: Baseline, cfg: dict, world=None) -> SpecResult:
    w, model = world
    runs = {}
    links = {}
    chars = 0
    for rev in ("A", "B"):
        spec = w.specs[f"{sid}/{rev}"]
        got = model.read_spec(spec, w.baseline)
        chars += sum(len(b.get("text", "") or " ".join(b.get("cells", []))) for b in spec.blocks) + 2000
        reqs = []
        for k, d in enumerate(got["requirements"]):
            uid = d["key"] or f"{sid}-note-{k}"
            lo, hi, unit = d["lo"], d["hi"], d["unit"]
            cu = None
            if unit in UNITS:
                lo = canonical(lo, unit)[0] if lo is not None and not math.isinf(lo) else lo
                hi2 = canonical(hi, unit) if hi is not None and not math.isinf(hi) else (hi, None, None)
                hi = hi2[0]
                cu = canonical(1, unit)[1]
            reqs.append(Requirement(uid, d["rid"], d["text"], "", d["sub"], "model", d["kind"], lo, hi, cu, None,
                                    "ubiquitous", (), (), d["defects"], False, link=d["link"],
                                    compliance=d["compliance"]))
            if rev == "A" and d["key"]:
                links[d["key"]] = d["link"]
        runs[rev] = Run(reqs, got["conflicts"], [], got["obeyed_injection"])
    touched = model.diff_specs(sid, links)
    return SpecResult(runs["A"], runs["B"], touched, 2, chars * 2)


DESIGNS = {"keyword": keyword, "model_only": model_only, "agents_no_model": None, "trace_agents": None}
