"""The analysed customer requirements back out as ReqIF, with "satisfied-by" links to the supplier's items."""
from __future__ import annotations

import math

from rta.product import reqif as rif
from rta.product.pipeline import Analysis


def to_reqif(a: Analysis) -> bytes:
    def num(x):
        return "" if x is None or math.isinf(x) else repr(x)
    objs = {r.uid: {"ID": r.uid, "TEXT": r.text, "SUBSYSTEM": r.sub or "", "KIND": r.kind, "LOW": num(r.lo),
                    "HIGH": num(r.hi), "UNIT": r.unit or "", "DEFECTS": ",".join(r.defects),
                    "COMPLIANCE": r.compliance, "QUESTIONS": " | ".join(r.questions),
                    "REVIEW": " | ".join(r.review)} for r in a.requirements}
    rels = [("satisfied-by", r.uid, r.link) for r in a.requirements if r.link]
    return rif.write(f"Customer requirements {a.name}", objs, rels)
