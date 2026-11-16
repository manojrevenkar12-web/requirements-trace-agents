"""Trace links from customer requirements to the supplier's own requirements, and the tests behind them.

A link is proposed only inside the subsystem and the physical dimension the requirement is about, and only when the
condition matches: "peak torque at -30 °C" is a different requirement from "peak torque". When two baseline items
score within the margin of each other the link is left to an engineer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rta.product.parse import Parsed, parse
from rta.product.reqif import ReqIF
from rta.product.units import locale_of

GENERIC = set("deliver have provide achieve reach supply use need cause keep limit operate within".split())


@dataclass
class Item:
    id: str
    sub: str
    text: str
    parsed: Parsed
    tests: list[str]
    label: frozenset


class Baseline:
    def __init__(self, rif: ReqIF, cfg: dict):
        a = cfg["reqif"]
        reqs = {k: v for k, v in rif.objects.items() if v.get(a["type"], "").lower() == a["requirement"]}
        loc = locale_of(" ".join(v.get(a["text"], "") for v in reqs.values()))
        self.subsystems = sorted({v.get(a["subsystem"], "") for v in reqs.values() if v.get(a["subsystem"])})
        self.items: dict[str, Item] = {}
        for k, v in reqs.items():
            text = v.get(a["text"], "")
            p = parse(text, loc)
            tests = rif.sources(a["verifies"], k)
            self.items[k] = Item(k, v.get(a["subsystem"], ""), text, p, tests, label_of(p, self.subsystems))

    def dims(self, sub: str) -> set[str]:
        return {i.parsed.dim for i in self.items.values() if i.sub == sub and i.parsed.dim}


def label_of(p: Parsed, subsystems: list[str]) -> frozenset:
    drop = {w for s in subsystems for w in s.lower().split()} | GENERIC
    return frozenset(w for w in p.label if w not in drop)


def subject(clause: str, subsystems: list[str]) -> str | None:
    """The subsystem named as the subject of the sentence, if it is one the supplier uses."""
    m = re.search(r"\bby the ([\w -]+?)(?:\s+(?:at|in|under|when|if|,)|$)", clause, re.I)
    head = m.group(1) if (m and re.search(r"\b(shall|must) be \w+", clause, re.I)) else \
        re.split(r"\b(?:shall|must)\b", clause, maxsplit=1, flags=re.I)[0]
    m2 = re.search(r"\bof the ([\w -]+?) (?:must|shall) not exceed", clause, re.I)
    if m2:
        head = m2.group(1)
    found = [s for s in sorted(subsystems, key=len, reverse=True) if re.search(rf"\b{re.escape(s)}\b", head, re.I)]
    return found[0] if found else None


def link(p: Parsed, sub: str | None, base: Baseline, cfg: dict) -> tuple[str | None, str, list[tuple[str, float]]]:
    """(baseline id or None, outcome, ranked candidates). outcome: linked | none_in_baseline | ambiguous | no_subsystem"""
    t = cfg["trace"]
    if p.dim is None:
        return None, "no_value", []
    lab = label_of(p, base.subsystems)
    cands = [i for i in base.items.values() if i.parsed.dim == p.dim and (sub is None or i.sub == sub)]
    scored = []
    for i in cands:
        union = lab | i.label
        s = len(lab & i.label) / len(union) if union else 0.0
        if s < t["min_label"]:
            continue
        s += t["cond_bonus"] if p.cond_sig == i.parsed.cond_sig else -t["cond_penalty"]
        s += t["kind_bonus"] if p.kind == i.parsed.kind or (p.kind == "eq") else 0
        scored.append((i.id, round(s, 3)))
    scored.sort(key=lambda x: -x[1])
    if not scored or scored[0][1] < t["min_score"]:
        return None, "none_in_baseline", scored[:3]
    if sub is None:
        return None, "no_subsystem", scored[:3]
    if len(scored) > 1 and scored[1][1] > scored[0][1] - t["margin"]:
        return None, "ambiguous", scored[:3]
    return scored[0][0], "linked", scored[:3]
