"""What a revision of the customer specification changes, and what it touches on the supplier's side.

Requirements are paired by the customer's requirement ID when the spec has them (identifiers decide), otherwise by
trace link, subsystem and label (names propose). A pair is a change only when the value changed after unit
conversion: "85 °C" rewritten as "358.15 K", or a reworded sentence, is not a change and touches nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rta.product.pipeline import Analysis, Requirement, same_value
from rta.product.trace import Baseline


@dataclass
class Impact:
    changed: list[tuple[str, str]] = field(default_factory=list)
    reworded: list[tuple[str, str]] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    touched: list[str] = field(default_factory=list)          # baseline requirements and tests to revisit
    flips: list[tuple[str, str, str]] = field(default_factory=list)   # (uid, before, after) compliance changes


def similarity(a: Requirement, b: Requirement) -> float:
    if a.sub != b.sub or a.dim != b.dim or a.cond_sig != b.cond_sig:
        return 0.0
    if a.link and a.link == b.link:
        return 2.0
    la, lb = set(a.label), set(b.label)
    return len(la & lb) / max(1, len(la | lb))


def pair(a: Analysis, b: Analysis, min_sim: float = 0.6) -> tuple[list[tuple[Requirement, Requirement]], list, list]:
    left, right = list(a.requirements), list(b.requirements)
    pairs = []
    if all(r.rid for r in left) and all(r.rid for r in right) and left and right:
        idx = {r.uid: r for r in right}
        for r in left:
            if r.uid in idx:
                pairs.append((r, idx.pop(r.uid)))
        rest_l = [r for r in left if r.uid not in {p[0].uid for p in pairs}]
        return pairs, rest_l, list(idx.values())
    scored = sorted(((similarity(x, y) + (0.5 if x.text == y.text else 0), i, j)
                     for i, x in enumerate(left) for j, y in enumerate(right)), reverse=True)
    used_l, used_r = set(), set()
    for s, i, j in scored:
        if s < min_sim or i in used_l or j in used_r:
            continue
        used_l.add(i)
        used_r.add(j)
        pairs.append((left[i], right[j]))
    return pairs, [x for i, x in enumerate(left) if i not in used_l], [y for j, y in enumerate(right) if j not in used_r]


def diff(a: Analysis, b: Analysis, base: Baseline) -> Impact:
    out = Impact()
    pairs, gone, new = pair(a, b)
    touched = set()
    for x, y in pairs:
        if same_value(x, y):
            if x.text != y.text:
                out.reworded.append((x.uid, y.uid))
            continue
        out.changed.append((x.uid, y.uid))
        if x.compliance != y.compliance:
            out.flips.append((y.uid, x.compliance, y.compliance))
        for lk in {x.link, y.link} - {None}:
            touched.add(lk)
            touched.update(base.items[lk].tests)
    for x in gone:
        out.deleted.append(x.uid)
        if x.link:
            touched.add(x.link)
            touched.update(base.items[x.link].tests)
    out.added = [y.uid for y in new]
    out.touched = sorted(touched)
    return out
