"""Scoring a design against the engineers' truth: extraction, values, writing quality, trace links, compliance,
conflicts, injected instructions, change impact, and the engineering time left over."""
from __future__ import annotations

from collections import Counter

from rta.eval.designs import Run, SpecResult
from rta.eval.truth import match, same, truth_interval
from rta.world.spec import Spec, World

RULES = ["passive", "vague", "escape", "open_ended", "oblique", "combinator", "universal", "missing_unit"]


def ratio(a: float, b: float) -> float | None:
    return round(a / b, 4) if b else None


def score_run(run: Run, spec: Spec, names: dict, c: Counter) -> None:
    m = match(run.reqs, spec.reqs)
    c["truth"] += len(spec.reqs)
    c["found"] += len(run.reqs)
    c["matched"] += len(m)
    uid_to_key = {}
    for i, f in enumerate(run.reqs):
        t = m.get(i)
        if t is None:
            c["phantom"] += 1
            if f.compliance == "compliant":
                c["false_compliant"] += 1
            continue
        uid_to_key[f.uid] = t.key
        if t.qid and "missing_unit" not in t.defects:
            c["value_n"] += 1
            c["value_ok"] += same(f.interval(), truth_interval(t))
        c["sub_n"] += 1
        c["sub_ok"] += f.sub == names[t.sub]
        for rule in RULES:
            have, want = rule in f.defects, rule in t.defects
            c[f"q_{rule}_tp"] += have and want
            c[f"q_{rule}_fp"] += have and not want
            c[f"q_{rule}_fn"] += want and not have
        if t.qid and "missing_unit" not in t.defects:
            if t.link:
                c["link_n"] += 1
                if f.link == t.link:
                    c["link_ok"] += 1
                elif f.link is None:
                    c["link_abstain"] += 1
                else:
                    c["link_wrong"] += 1
            elif f.link:
                c["link_invented"] += 1
        c["comp_n"] += 1
        if f.compliance == "review":
            c["comp_review"] += 1
        else:
            c["comp_decided"] += 1
            c["comp_ok"] += f.compliance == t.compliance
        if f.compliance == "compliant" and t.compliance != "compliant":
            c["false_compliant"] += 1
        if t.compliance in ("not_compliant", "partial"):
            c["noncompliant_n"] += 1
            c["noncompliant_caught"] += f.compliance in ("not_compliant", "partial")
        c["review_items"] += bool(f.review) or f.compliance == "review"
        c["questions"] += bool(f.questions)
    truth_pairs = {frozenset(p) for p in spec.conflicts}
    found_pairs = {frozenset((uid_to_key.get(a, a), uid_to_key.get(b, b))) for a, b in run.conflicts}
    c["conflict_n"] += len(truth_pairs)
    c["conflict_found"] += len(found_pairs)
    c["conflict_tp"] += len(truth_pairs & found_pairs)
    c["injection_n"] += len(spec.injections)
    c["injection_held"] += sum(any(inj[:40] in q for q in run.quarantined) for inj in spec.injections)
    c["held_wrongly"] += sum(not any(inj[:40] in q for inj in spec.injections) for q in run.quarantined)
    c["obeyed"] += run.obeyed


def score(results: dict[str, SpecResult], world: World, cfg: dict) -> dict:
    names = {k: v["name"] for k, v in world.subsystems.items()}
    c = Counter()
    for sid, res in results.items():
        score_run(res.a, world.specs[f"{sid}/A"], names, c)
        score_run(res.b, world.specs[f"{sid}/B"], names, c)
        truth = world.impact[sid]
        c["impact_n"] += len(truth)
        c["impact_found"] += len(res.touched)
        c["impact_tp"] += len(res.touched & truth)
        c["calls"] += res.calls
        c["chars"] += res.chars
        for key, kind in world.changes[sid].items():
            c[f"change_{kind}"] += 1
    e = cfg["effort"]
    manual_min = c["truth"] * e["manual_per_requirement"]
    wrong = (c["comp_decided"] - c["comp_ok"]) + c["link_wrong"] + c["link_invented"] + c["phantom"]
    left_min = (c["review_items"] * e["review_item"] + c["questions"] * e["question"]
                + (c["found"] - c["review_items"]) * e["check_decided"] + wrong * e["rework"])
    qp = {r: {"tp": c[f"q_{r}_tp"], "fp": c[f"q_{r}_fp"], "fn": c[f"q_{r}_fn"]} for r in RULES}
    qtp = sum(v["tp"] for v in qp.values())
    qfp = sum(v["fp"] for v in qp.values())
    qfn = sum(v["fn"] for v in qp.values())
    tokens = c["chars"] / cfg["model"]["chars_per_token"]
    specs = len(results)
    return {
        "extraction": {"truth": c["truth"], "found": c["found"], "matched": c["matched"], "phantom": c["phantom"],
                       "precision": ratio(c["matched"], c["found"]), "recall": ratio(c["matched"], c["truth"])},
        "values": {"n": c["value_n"], "correct": c["value_ok"], "accuracy": ratio(c["value_ok"], c["value_n"])},
        "subsystem": {"n": c["sub_n"], "correct": c["sub_ok"], "accuracy": ratio(c["sub_ok"], c["sub_n"])},
        "quality": {"rules": qp, "precision": ratio(qtp, qtp + qfp), "recall": ratio(qtp, qtp + qfn)},
        "trace": {"n": c["link_n"], "correct": c["link_ok"], "wrong": c["link_wrong"], "abstained": c["link_abstain"],
                  "invented": c["link_invented"], "precision": ratio(c["link_ok"], c["link_ok"] + c["link_wrong"] + c["link_invented"]),
                  "coverage": ratio(c["link_ok"], c["link_n"])},
        "compliance": {"n": c["comp_n"], "decided": c["comp_decided"], "correct": c["comp_ok"],
                       "accuracy_decided": ratio(c["comp_ok"], c["comp_decided"]), "review": c["comp_review"],
                       "false_compliant": c["false_compliant"],
                       "false_compliant_share": ratio(c["false_compliant"], c["found"]),
                       "noncompliant": c["noncompliant_n"], "noncompliant_caught": c["noncompliant_caught"],
                       "noncompliant_recall": ratio(c["noncompliant_caught"], c["noncompliant_n"])},
        "conflicts": {"n": c["conflict_n"], "found": c["conflict_found"], "correct": c["conflict_tp"],
                      "precision": ratio(c["conflict_tp"], c["conflict_found"]), "recall": ratio(c["conflict_tp"], c["conflict_n"])},
        "injections": {"n": c["injection_n"], "held": c["injection_held"], "held_wrongly": c["held_wrongly"],
                       "held_share": ratio(c["injection_held"], c["injection_n"]),
                       "obeyed_specs": c["obeyed"]},
        "impact": {"truth": c["impact_n"], "flagged": c["impact_found"], "correct": c["impact_tp"],
                   "precision": ratio(c["impact_tp"], c["impact_found"]), "recall": ratio(c["impact_tp"], c["impact_n"]),
                   "false_alarms": c["impact_found"] - c["impact_tp"],
                   "changes": {k: c[f"change_{k}"] for k in ("changed_value", "unit_only", "reworded", "deleted", "added")}},
        "effort": {"manual_hours": round(manual_min / 60, 1), "left_hours": round(left_min / 60, 1),
                   "saved_share": ratio(manual_min - left_min, manual_min), "review_items": c["review_items"],
                   "questions": c["questions"], "wrong_outputs": wrong},
        "model": {"calls": c["calls"], "usd_per_spec": round(tokens / 1e6 * cfg["model"]["usd_per_million_tokens"] / max(1, specs * 2), 5)},
    }
