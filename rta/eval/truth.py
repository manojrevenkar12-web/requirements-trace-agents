"""Pairing what a design found with what the engineers know, one specification at a time."""
from __future__ import annotations

import math
import re

from rta.product.units import UNITS, canonical
from rta.world.spec import Req

STOP = set("a an the of to and or in on at for by with within shall must be is are have has".split())


def toks(text: str) -> frozenset:
    return frozenset(w for w in re.findall(r"[a-z0-9]+", text.lower().replace("-", " ")) if w not in STOP)


def truth_text(r: Req) -> str:
    return r.text or " ".join(r.style.get("row", []))


def conv(v: float, unit: str | None) -> tuple:
    """Truth values in the product's canonical units; a unit the product does not know stays as written."""
    if math.isinf(v):
        return v, None
    if not unit:
        return v, None
    if unit not in UNITS:
        return v, unit
    x, u, _ = canonical(v, unit)
    return x, u


def truth_interval(r: Req) -> tuple:
    if r.kind == "none":
        return ("none", None, None, None)
    lo, u = conv(r.lo, r.unit)
    hi, u2 = conv(r.hi, r.unit)
    return (r.kind, lo, hi, u or u2)


def same(a: tuple, b: tuple) -> bool:
    if a[0] != b[0] or a[3] != b[3]:
        return False
    for x, y in ((a[1], b[1]), (a[2], b[2])):
        if x is None or y is None:
            if x != y:
                return False
        elif math.isinf(x) or math.isinf(y):
            if x != y:
                return False
        elif abs(x - y) > 1e-6 * max(1, abs(x)):
            return False
    return True


def match(found: list, truth: list[Req]) -> dict[int, Req]:
    """index into found -> truth requirement, one to one, by words and then by value."""
    tt = [(toks(truth_text(r)), truth_interval(r), r) for r in truth]
    cands = []
    for i, f in enumerate(found):
        ft = toks(f.text)
        fi = f.interval()
        for j, (t, ti, r) in enumerate(tt):
            jac = len(ft & t) / max(1, len(ft | t))
            if jac >= 0.4:
                cands.append((jac + (0.5 if same(fi, ti) else 0), i, j))
    cands.sort(reverse=True)
    out, used = {}, set()
    for s, i, j in cands:
        if i in out or j in used:
            continue
        out[i] = tt[j][2]
        used.add(j)
    return out
