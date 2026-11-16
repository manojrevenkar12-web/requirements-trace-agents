"""python -m rta.eval.cli evaluate | gate | heldout | readme [--check] | analyse <spec> --baseline <reqif>"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rta.eval import gate, readme
from rta.eval.run import ROOT, evaluate, settings, write_report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rta")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("evaluate")
    e.add_argument("--profile", choices=["full", "quick"], default="full")
    sub.add_parser("gate")
    sub.add_parser("heldout")
    r = sub.add_parser("readme")
    r.add_argument("--check", action="store_true")
    a = sub.add_parser("analyse")
    a.add_argument("spec")
    a.add_argument("--baseline", required=True)
    a.add_argument("--reqif-out")
    args = ap.parse_args(argv)

    if args.cmd == "evaluate":
        rep = evaluate(quick=args.profile == "quick")
        rep["gate"] = gate.check(rep, ROOT / "config/gate.yaml")
        if args.profile == "full":
            write_report(rep, "dev")
        brief(rep)
        return 0
    if args.cmd == "gate":
        rep = json.loads((ROOT / "reports/dev.json").read_text())
        lines = gate.check(rep, ROOT / "config/gate.yaml")
        for ln in lines:
            print(("PASS " if ln["pass"] else "FAIL ") + f"{ln['name']}: {ln['value']} {ln['op']} {ln['target']}")
        return 0 if all(ln["pass"] for ln in lines) else 1
    if args.cmd == "heldout":
        lock = ROOT / "config/heldout.lock"
        if lock.exists():
            print(f"the held-out world was run once already ({lock.read_text().strip()}); it is not run again")
            return 1
        rep = evaluate("config/heldout.yaml")
        rep["gate"] = gate.check(rep, ROOT / "config/gate.yaml")
        write_report(rep, "heldout")
        import subprocess
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        lock.write_text(f"run once at commit {commit or 'unknown'}\n")
        brief(rep)
        return 0
    if args.cmd == "readme":
        text = readme.render()
        path = ROOT / "README.md"
        if args.check:
            if not path.exists() or path.read_text() != text:
                print("README.md does not match the reports: run python -m rta.eval.cli readme")
                return 1
            return 0
        path.write_text(text)
        return 0
    if args.cmd == "analyse":
        import os

        from rta.product import reqif as rif
        from rta.product.export import to_reqif
        from rta.product.model import NoModel, OpenAICompatible
        from rta.product.pipeline import analyse
        from rta.product.trace import Baseline
        cfg = settings()
        base = Baseline(rif.read(Path(args.baseline).read_bytes()), cfg)
        model = OpenAICompatible() if os.environ.get("RTA_MODEL_URL") else NoModel()
        res = analyse(Path(args.spec).read_bytes(), base, model, cfg, Path(args.spec).stem)
        json.dump(res.to_dict(), sys.stdout, indent=1, ensure_ascii=False)
        if args.reqif_out:
            Path(args.reqif_out).write_bytes(to_reqif(res))
        return 0
    return 2


def brief(rep: dict) -> None:
    for name, d in rep["designs"].items():
        print(f"{name:16} found {d['extraction']['recall']}  values {d['values']['accuracy']}  "
              f"trace {d['trace']['precision']}/{d['trace']['coverage']}  false compliant {d['compliance']['false_compliant']}  "
              f"impact {d['impact']['precision']}/{d['impact']['recall']}")
    for ln in rep.get("gate", []):
        print(("PASS " if ln["pass"] else "FAIL ") + f"{ln['name']}: {ln['value']} {ln['op']} {ln['target']}")


if __name__ == "__main__":
    sys.exit(main())
