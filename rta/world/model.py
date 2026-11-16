"""The stand-in language model. It reads with the error rates in the world file, so every design that uses it meets
the same misreadings. A real model plugs in through rta.product.model.OpenAICompatible."""
from __future__ import annotations

import re

from rta.keyed import rng
from rta.world.spec import World


def tokens(text: str) -> frozenset:
    return frozenset(re.findall(r"[a-z0-9]+", text.lower()))


class StandInModel:
    def __init__(self, world: World):
        self.w = world
        self.m = world.model
        self.index = []
        for sk, spec in world.specs.items():
            for r in spec.reqs:
                text = r.text or " ".join(r.style.get("row", []))
                self.index.append((tokens(text), r))

    def lookup(self, text: str):
        t = tokens(text)
        best, score = None, 0.0
        for toks, r in self.index:
            s = len(t & toks) / max(1, len(t | toks))
            if s > score:
                best, score = r, s
        return best if score >= 0.5 else None

    def ask(self, task: str, text: str, options: list[str]) -> dict:
        r = self.lookup(text)
        g = rng(self.w.name, "model", task, text)
        names = {k: v["name"] for k, v in self.w.subsystems.items()}
        if r is None:
            return {"is_requirement": False, "subsystem": None}
        sub = names[r.sub]
        if g.random() < self.m["wrong_subsystem"]:
            sub = str(g.choice([o for o in options if o != sub] or options))
        return {"is_requirement": True, "subsystem": sub}


    # ------------------------------------------------------------ the model reading whole documents on its own

    def read_spec(self, spec, baseline) -> dict:
        """What one long-context call over the whole spec returns: requirements with values, links and verdicts."""
        m = self.m
        g = rng(self.w.name, "model-doc", spec.id, spec.rev)
        names = {k: v["name"] for k, v in self.w.subsystems.items()}
        obeys = bool(spec.injections) and g.random() < m["obeys_injection"]
        by_sub = {}
        for b in baseline:
            by_sub.setdefault(b.sub, []).append(b.id)
        out = []
        sentences = {}
        for r in spec.reqs:
            sentences.setdefault(r.sentence, []).append(r)
        for group in sentences.values():
            if len(group) > 1 and g.random() > m["split_compound"]:
                group = group[:1]
            for r in group:
                h = rng(self.w.name, "model-req", spec.id, spec.rev, r.key)
                if h.random() < m["miss"]:
                    continue
                lo, hi = r.lo, r.hi
                if r.kind != "none" and h.random() < m["wrong_value"]:
                    f = float(h.choice([0.9, 1.1, 0.5, 2.0]))
                    lo, hi = (lo * f if lo not in (None,) and abs(lo) != float("inf") else lo,
                              hi * f if hi not in (None,) and abs(hi) != float("inf") else hi)
                elif r.kind != "none" and h.random() < m["wrong_unit_scale"]:
                    lo, hi = (lo * 1000 if abs(lo) != float("inf") else lo, hi * 1000 if abs(hi) != float("inf") else hi)
                sub = r.sub if h.random() >= m["wrong_subsystem"] else str(h.choice(list(names)))
                link = r.link
                if link and h.random() < m["link_wrong"]:
                    others = [x for x in by_sub.get(r.sub, []) if x != link]
                    link = str(h.choice(others)) if others else link
                elif link is None and r.kind != "none" and h.random() < m["invents_link"]:
                    pool = by_sub.get(r.sub, [])
                    link = str(h.choice(pool)) if pool else None
                verdict = r.compliance
                if obeys or (verdict != "compliant" and h.random() < m["compliant_bias"]):
                    verdict = "compliant"
                defects = {d for d in r.defects if h.random() < m["flags_defect"]}
                if h.random() < m["false_defect"]:
                    defects.add(str(h.choice(["vague", "passive", "universal"])))
                text = r.text or " ".join(r.style.get("row", []))
                out.append({"key": r.key, "text": text, "sub": names[sub], "kind": r.kind, "lo": lo, "hi": hi,
                            "unit": r.unit, "link": link, "compliance": verdict, "defects": sorted(defects),
                            "rid": r.rid})
        for note in spec.notes:
            h = rng(self.w.name, "model-note", spec.id, spec.rev, note)
            if h.random() < m["note_as_req"]:
                out.append({"key": None, "text": note, "sub": str(h.choice(list(names.values()))), "kind": "none",
                            "lo": None, "hi": None, "unit": None, "link": None, "compliance": "compliant",
                            "defects": [], "rid": None})
        conflicts = [(a, b) for a, b in spec.conflicts if g.random() < m["finds_conflict"]]
        return {"requirements": out, "conflicts": conflicts, "obeyed_injection": obeys}

    def diff_specs(self, sid: str, links: dict) -> set:
        """What the model, shown both revisions, says the change touches."""
        touched = set()
        base = {b.id: b for b in self.w.baseline}
        for key, kind in self.w.changes[sid].items():
            h = rng(self.w.name, "model-diff", sid, key)
            if h.random() < self.m["diff"][kind] and links.get(key):
                touched.add(links[key])
                touched.update(base[links[key]].tests)
        return touched
