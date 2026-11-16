"""HTTP service: load the supplier baseline (ReqIF), post customer specs (PDF or Word), get the analysis, the ReqIF
export and the impact of a new revision. Run: uvicorn rta.product.service:app"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Request, Response

from rta.product import reqif as rif
from rta.product.export import to_reqif
from rta.product.impact import diff
from rta.product.model import Counted, NoModel, OpenAICompatible
from rta.product.pipeline import Analysis, analyse
from rta.product.trace import Baseline

CFG = yaml.safe_load((Path(__file__).resolve().parents[2] / "config/pipeline.yaml").read_text())
MAX_BYTES = 20 * 1024 * 1024


def create(model=None) -> FastAPI:
    app = FastAPI(title="requirements-trace-agents")
    state: dict = {"baseline": None, "specs": {}, "model": Counted(model or (
        OpenAICompatible() if os.environ.get("RTA_MODEL_URL") else NoModel()))}

    async def body(req: Request) -> bytes:
        data = await req.body()
        if not data:
            raise HTTPException(400, "empty body")
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "file too large")
        return data

    def need_baseline() -> Baseline:
        if state["baseline"] is None:
            raise HTTPException(409, "load the supplier baseline first: POST /baseline with a ReqIF file")
        return state["baseline"]

    @app.get("/health")
    def health():
        return {"ok": True, "baseline": state["baseline"] is not None, "specs": len(state["specs"])}

    @app.post("/baseline")
    async def baseline(req: Request):
        try:
            b = Baseline(rif.read(await body(req)), CFG)
        except Exception as exc:          # malformed XML is the caller's problem, say so plainly
            raise HTTPException(422, f"not a readable ReqIF file: {exc}") from exc
        state["baseline"] = b
        return {"requirements": len(b.items), "subsystems": b.subsystems,
                "tests": sum(len(i.tests) for i in b.items.values())}

    @app.post("/specs/{name}")
    async def spec(name: str, req: Request):
        base = need_baseline()
        a = analyse(await body(req), base, state["model"], CFG, name)
        state["specs"].setdefault(name, []).append(a)
        return {"revision": len(state["specs"][name]), "summary": a.summary(), **a.to_dict()}

    def latest(name: str) -> Analysis:
        if name not in state["specs"]:
            raise HTTPException(404, f"no spec called {name}")
        return state["specs"][name][-1]

    @app.get("/specs/{name}/reqif")
    def export(name: str):
        return Response(to_reqif(latest(name)), media_type="application/xml")

    @app.get("/specs/{name}/impact")
    def impact(name: str):
        revs = state["specs"].get(name, [])
        if len(revs) < 2:
            raise HTTPException(409, "post a second revision of the spec first")
        d = diff(revs[-2], revs[-1], need_baseline())
        return d.__dict__

    return app


app = create()
