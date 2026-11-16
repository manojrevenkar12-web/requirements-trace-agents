"""One evaluation: build the world, hand every design the same files, score against the truth, write a report."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import yaml

from rta.eval import designs
from rta.eval.score import score
from rta.product import reqif as rif
from rta.product.export import to_reqif
from rta.product.impact import diff
from rta.product.model import Counted
from rta.product.pipeline import analyse
from rta.product.trace import Baseline
from rta.world import docs
from rta.world.model import StandInModel
from rta.world.spec import load

ROOT = Path(__file__).resolve().parents[2]


def settings() -> dict:
    return yaml.safe_load((ROOT / "config/pipeline.yaml").read_text())


def files_of(world) -> tuple[bytes, dict]:
    base = docs.reqif(world.system, world.baseline, world.subsystems)
    files = {}
    for key, spec in world.specs.items():
        sid, rev = key.split("/")
        files.setdefault(sid, {})[rev] = docs.render(spec)
    return base, files


def clean(x):
    if isinstance(x, float) and math.isinf(x):
        return None
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def evaluate(world_file: str = "config/world.yaml", quick: bool = False) -> dict:
    cfg = settings()
    world = load(ROOT / world_file, quick)
    base_bytes, files = files_of(world)
    base = Baseline(rif.read(base_bytes), cfg)
    stand_in = StandInModel(world)
    runners = {"keyword": designs.keyword, "model_only": designs.model_only,
               "agents_no_model": designs.product(None), "trace_agents": designs.product(stand_in)}
    out = {"world": world.name, "system": world.system["name"], "specs": len(files),
           "formats": {f: sum(1 for k, s in world.specs.items() if s.fmt == f) for f in ("pdf", "docx")},
           "baseline": {"requirements": len(base.items), "tests": sum(len(i.tests) for i in base.items.values()),
                        "subsystems": base.subsystems},
           "designs": {}}
    timing = {}
    for name, fn in runners.items():
        t0 = time.perf_counter()
        results = {sid: fn(sid, f, base, cfg, (world, stand_in)) for sid, f in files.items()}
        timing[name] = round((time.perf_counter() - t0) / (2 * len(files)), 3)
        out["designs"][name] = score(results, world, cfg)
    out["seconds_per_spec"] = timing
    out["example"] = example(world, files, base, cfg, stand_in)
    out["reqif_roundtrip"] = roundtrip(world, files, base, cfg, stand_in)
    return clean(out)


def example(world, files, base, cfg, stand_in) -> dict:
    """One specification end to end, for the dashboard."""
    sid = sorted(files)[0]
    model = Counted(stand_in)
    a = analyse(files[sid]["A"], base, model, cfg, sid)
    b = analyse(files[sid]["B"], base, model, cfg, sid)
    imp = diff(a, b, base)
    spec = world.specs[f"{sid}/A"]
    rows = [{"uid": r.uid, "text": r.text, "sub": r.sub, "sub_by": r.sub_by, "kind": r.kind, "lo": r.lo, "hi": r.hi,
             "unit": r.unit, "defects": r.defects, "link": r.link, "compliance": r.compliance,
             "review": r.review, "questions": r.questions, "table": r.table} for r in a.requirements]
    return {"spec": sid, "customer": spec.customer, "format": spec.fmt, "locale": a.locale,
            "summary": a.summary(), "requirements": rows, "quarantined": a.quarantined, "dropped": a.dropped,
            "conflicts": a.conflicts, "model_calls": model.calls,
            "impact": {"changed": imp.changed, "reworded": imp.reworded, "deleted": imp.deleted, "added": imp.added,
                       "touched": imp.touched, "flips": imp.flips,
                       "truth": sorted(world.impact[sid]), "truth_changes": world.changes[sid]}}


def roundtrip(world, files, base, cfg, stand_in) -> dict:
    """Export the analysed requirements as ReqIF and read them back: nothing may change."""
    ok, n = 0, 0
    for sid, f in files.items():
        a = analyse(f["A"], base, stand_in, cfg, sid)
        data = to_reqif(a)
        back = rif.read(data)
        n += len(a.requirements)
        ok += sum(1 for r in a.requirements if back.objects.get(r.uid, {}).get("TEXT") == r.text
                  and back.targets("satisfied-by", r.uid) == ([r.link] if r.link else []))
    return {"requirements": n, "identical": ok}


def write_report(rep: dict, name: str) -> Path:
    p = ROOT / "reports" / f"{name}.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    return p
