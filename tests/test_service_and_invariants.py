"""The HTTP service, and the rules the code base keeps."""
import ast
import pathlib

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]


def imports(folder):
    for p in (ROOT / folder).rglob("*.py"):
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                yield p, node.module
            elif isinstance(node, ast.Import):
                for n in node.names:
                    yield p, n.name


def test_product_never_imports_the_truth():
    bad = [(str(p), m) for p, m in imports("rta/product") if m.startswith(("rta.world", "rta.eval"))]
    assert bad == []


def test_world_does_not_read_the_product_settings():
    for p in (ROOT / "rta/world").rglob("*.py"):
        assert "pipeline.yaml" not in p.read_text()
    assert [(str(p), m) for p, m in imports("rta/world") if m.startswith(("rta.product", "rta.eval"))] == []


def test_same_luck_for_every_design(world):
    from rta.world.model import StandInModel
    from rta.world.spec import load
    again = load(ROOT / "config/world.yaml", quick=True)
    assert [r.text for s in world.specs.values() for r in s.reqs] == [r.text for s in again.specs.values() for r in s.reqs]
    m1, m2 = StandInModel(world), StandInModel(again)
    q = "The e-axle shall deliver a continuous power of at least 150 kW"
    assert m1.ask("classify", q, ["drive unit", "inverter"]) == m2.ask("classify", q, ["drive unit", "inverter"])


def test_settings_live_in_config():
    src = (ROOT / "rta/product/trace.py").read_text()
    assert "min_score" in src and "0.35" not in src


def test_service_flow(world):
    from rta.product.service import create
    from rta.world.docs import render, reqif
    c = TestClient(create())
    assert c.post("/specs/x", content=b"x").status_code == 409
    assert c.post("/baseline", content=b"<not reqif").status_code == 422
    r = c.post("/baseline", content=reqif(world.system, world.baseline, world.subsystems))
    assert r.status_code == 200 and r.json()["requirements"] == len(world.baseline)
    sid = sorted(world.specs)[0].split("/")[0]
    a = c.post(f"/specs/{sid}", content=render(world.specs[f"{sid}/A"])).json()
    assert a["summary"]["requirements"] > 10 and a["summary"]["quarantined"] == len(world.specs[f"{sid}/A"].injections)
    assert c.get(f"/specs/{sid}/impact").status_code == 409
    c.post(f"/specs/{sid}", content=render(world.specs[f"{sid}/B"]))
    imp = c.get(f"/specs/{sid}/impact").json()
    assert set(imp) >= {"changed", "deleted", "added", "touched"}
    assert c.get(f"/specs/{sid}/reqif").text.startswith("<?xml")


def test_quick_evaluation_runs():
    from rta.eval.run import evaluate
    rep = evaluate(quick=True)
    d = rep["designs"]
    assert d["trace_agents"]["compliance"]["false_compliant"] <= d["model_only"]["compliance"]["false_compliant"]
    assert d["trace_agents"]["injections"]["held_share"] == 1.0
    assert rep["reqif_roundtrip"]["identical"] == rep["reqif_roundtrip"]["requirements"]
