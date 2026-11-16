"""README from the reports: every number in it comes from reports/dev.json or reports/heldout.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMES = {"keyword": "Keyword script", "model_only": "Model alone", "agents_no_model": "Agents, no model",
         "trace_agents": "**Trace agents**"}


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def render() -> str:
    dev = json.loads((ROOT / "reports/dev.json").read_text())
    held_path = ROOT / "reports/heldout.json"
    held = json.loads(held_path.read_text()) if held_path.exists() else None
    t = dev["designs"]["trace_agents"]
    h = held["designs"]["trace_agents"] if held else None
    m = dev["designs"]["model_only"]
    k = dev["designs"]["keyword"]
    gate_dev = sum(g["pass"] for g in dev["gate"])
    gate_held = sum(g["pass"] for g in held["gate"]) if held else 0

    def row(label, f, fmt=pct):
        hv = fmt(f(h)) if h else "–"
        return f"| {label} | {fmt(f(t))} | {hv} |"

    designs = []
    for name, d in dev["designs"].items():
        designs.append(
            f"| {NAMES[name]} | {pct(d['extraction']['recall'])} | {pct(d['values']['accuracy'])} | "
            f"{pct(d['trace']['precision'])} / {pct(d['trace']['coverage'])} | {d['compliance']['false_compliant']} | "
            f"{pct(d['compliance']['noncompliant_recall'])} | {pct(d['conflicts']['recall'])} | "
            f"{d['injections']['held']} of {d['injections']['n']} | {pct(d['impact']['precision'])} / {pct(d['impact']['recall'])} | "
            f"{d['effort']['left_hours']} h |")
    gate_rows = []
    for i, g in enumerate(dev["gate"]):
        hg = held["gate"][i] if held else None
        def show(x):
            v = x["value"]
            return "–" if v is None else (f"{v:.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))
        gate_rows.append(f"| {g['name']} | {g['op']} {g['target'] if g['against'] == 'fixed' else g['against']} | "
                         f"{show(g)} {'✅' if g['pass'] else '❌'} | "
                         + (f"{show(hg)} {'✅' if hg['pass'] else '❌'} |" if hg else "– |"))
    ex = dev["example"]
    rules = t["quality"]["rules"]
    rule_rows = "\n".join(f"| {r} | {v['tp']} | {v['fp']} | {v['fn']} |" for r, v in rules.items())

    return f"""# requirements-trace-agents

Agents for requirements and systems engineering in manufacturing. A customer specification arrives as a PDF or
Word file. Out come atomic requirements with values in canonical units, INCOSE writing checks, trace links into the
supplier's own requirements and tests (ReqIF in and out), compliance computed rather than guessed, conflicting values
inside the spec, and what a new revision of the spec touches. Everything is measured against the engineers' ground
truth on {dev['specs']} customer specs plus a held-out product the code was not built against.

![dashboard](docs/dashboard.png)

## The numbers

| measured (trace agents) | dev ({dev['system']}) | held-out ({held['system'] if held else '–'}, run once) |
|---|---|---|
{row("requirements found", lambda d: d["extraction"]["recall"])}
{row("values and units read right", lambda d: d["values"]["accuracy"])}
{row("trace links that are right", lambda d: d["trace"]["precision"])}
{row("requirements with a trace link", lambda d: d["trace"]["coverage"])}
{row("compliance verdicts right, of those decided", lambda d: d["compliance"]["accuracy_decided"])}
{row("false 'compliant' verdicts", lambda d: d["compliance"]["false_compliant"], str)}
{row("non-compliant requirements caught", lambda d: d["compliance"]["noncompliant_recall"])}
{row("conflicting values found", lambda d: d["conflicts"]["recall"])}
{row("injected instructions held for a person", lambda d: d["injections"]["held_share"])}
{row("revision impact: precision", lambda d: d["impact"]["precision"])}
{row("revision impact: recall", lambda d: d["impact"]["recall"])}
{row("engineer hours left of the manual effort", lambda d: d["effort"]["left_hours"] / d["effort"]["manual_hours"])}
| gate lines passed | {gate_dev} of {len(dev['gate'])} | {gate_held} of {len(held['gate']) if held else 0} |

The held-out run failed 7 of 16 gate lines, and the reasons are written up in [docs/heldout.md](docs/heldout.md):
- sentences where the quantity is the subject ("The mass of the compressor shall be limited to 27 kg");
- dimensionless values;
- "±" tolerances;
- injected text worded differently from anything in dev.

Those shapes were fixed afterwards and are measured on dev. The held-out world is not run again, so the held-out
column keeps the numbers from its one run.

## Four designs on the same specs (dev)

Every design reads the same {dev['specs'] * 2} files: {dev['formats']['pdf']} PDFs and {dev['formats']['docx']} Word
files, each spec in revisions A and B. All of them use the same baseline of {dev['baseline']['requirements']} supplier
requirements and {dev['baseline']['tests']} tests.

| design | found | values right | links right / covered | false "compliant" | non-compliant caught | conflicts found | injections held | impact precision / recall | engineer time left |
|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(designs)}

- **Keyword script**: sentences with "shall", the first number, the closest-sounding baseline item and a text diff.
  It reads "92,5 %" as 925 and "a maximum speed of not less than" as a maximum. Only
  {pct(k['values']['accuracy'])} of its values are right.
- **Model alone**: one long-context call returns requirements, links and verdicts. It is the stand-in model with the
  error rates in `config/world.yaml`, so its numbers follow from those rates. It claims "compliant" falsely
  {m['compliance']['false_compliant']} times and follows {m['injections']['obeyed_specs']} injected instructions.
  The engineer time it leaves is {m['effort']['left_hours']} h because every wrong verdict costs rework later.
- **Agents, no model**: the product with no model. A subject the supplier does not use, such as "e-axle" or "coolant
  loop", goes to an engineer, so trace coverage drops to {pct(dev['designs']['agents_no_model']['trace']['coverage'])}.
- **Trace agents**: the model answers one narrow question per sentence it cannot name itself
  ({t['model']['calls']} calls in total, ${t['model']['usd_per_spec']} per spec). Code checks each answer against the
  baseline. Values, links, verdicts, conflicts and impact are computed.

Engineer time uses the assumptions in `config/pipeline.yaml`: {dev['designs']['trace_agents']['effort']['manual_hours']} h
by hand, 4 minutes per review item, 2 per question to the customer, and 30 to find and fix a wrong output later. The
time is an estimate. The counts behind it are measured.

## Gate

Written before the first held-out result (`config/gate.yaml`).

| line | target | dev | held-out |
|---|---|---|---|
{chr(10).join(gate_rows)}

## What it does

1. **Read.** PDFs lose their structure; Word files keep it. Both are read into the same blocks:
   - running headers and footers are found by repetition at the page edges;
   - hyphenated line breaks are joined;
   - a page break does not end a sentence;
   - table columns are recovered from the spacing.

   The locale is decided once per document: is "300.000 km" three hundred thousand, and is "91,5 %" a decimal?
2. **Guard.** A sentence that addresses an automated reader, or tells it to change verdicts, is held for a person.
   It is never parsed and never sent to a model.
3. **Split and parse.** Compound sentences are split ("… and shall …", "…, and the mass of the unit shall …"). The
   value is the number that the nearest comparator governs. Numbers inside conditions ("when the coolant exceeds
   65 °C", "at -30 °C") are part of the condition. Ranges and "±" tolerances become intervals, and every unit is
   converted to a canonical one: "82.000 g" is 82 kg, and "358,15 K" is 85 °C.
4. **Name the subsystem.** By name when the customer uses the supplier's word. Otherwise the model is asked, with the
   sentence as data and the subsystems as options. The answer is used only if it is an option and that subsystem has
   requirements of that kind; otherwise an engineer decides.
5. **Check the writing** against INCOSE GtWR rules: active voice R2, vague terms R7, escape clauses R8, open-ended
   R9, "and/or" R17, combinators R19, universal qualifiers R32, and measurable values with units R34. Each finding is
   a question back to the customer.
6. **Trace** inside the subsystem and the physical dimension. The condition must match: "peak torque at -30 °C" is
   not "peak torque". When two candidates are within the margin of each other, an engineer chooses.
7. **Decide compliance in code.** The customer's interval is compared with the supplier's own requirement. The
   outcomes are compliant, partial, not compliant, open (the supplier has no such requirement yet), or a question.
8. **Find conflicts.** The same quantity under the same condition stated twice with different values. A value that is
   only restated in another unit is not a conflict.
9. **Diff revisions.** Requirements are paired by the customer's IDs when the spec has them; otherwise by link and
   label. The diff lists:
   - changes after unit conversion;
   - the supplier requirements and tests each change touches;
   - verdicts that flip.

   Rewording and unit-only rewrites touch nothing.
10. **Export** the requirement set as ReqIF 1.2 with "satisfied-by" links. All
    {dev['reqif_roundtrip']['identical']} of {dev['reqif_roundtrip']['requirements']} requirements come back identical
    on re-import.

Writing checks on dev, per rule:

| rule | found | flagged wrongly | missed |
|---|---|---|---|
{rule_rows}

The worked example in the report is {ex['spec']}, a {ex['format'].upper()} from {ex['customer']}. It holds
{ex['summary']['requirements']} requirements:
- {ex['summary']['compliance']['compliant']} compliant;
- {ex['summary']['compliance']['not_compliant']} not compliant;
- {ex['summary']['compliance']['partial']} partial;
- {ex['summary']['compliance']['open']} open;
- {ex['summary']['questions']} with questions for the customer;
- {ex['summary']['conflicts']} conflicts;
- {ex['summary']['quarantined']} injected sentences held.

Revision B touches {len(ex['impact']['touched'])} supplier items.

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q                                  # every check, a few seconds
python -m rta.eval.cli evaluate                      # four designs on dev, writes reports/dev.json, prints the gate
python -m rta.eval.cli analyse spec.pdf --baseline system.reqif --reqif-out customer.reqif
uvicorn rta.product.service:app                      # POST /baseline, POST /specs/<name>, GET /specs/<name>/impact
cd web && npm ci && npm run dev                      # the dashboard
```

To use a real model, set `RTA_MODEL_URL`, `RTA_MODEL_KEY` and `RTA_MODEL_NAME`. Any Azure OpenAI or
OpenAI-compatible chat endpoint works. Without them the product runs with no model, and unknown subject names go to
an engineer.

Where the code lives: `rta/world` holds the customer specs, the supplier baseline and the truth. `rta/product` holds
what would ship, and it never imports the world. `rta/eval` holds the designs, scoring, gate and README. `web` holds
the dashboard. The rules the code keeps are in [AGENTS.md](AGENTS.md), and the repeatable tasks, such as connecting
a DOORS export, plugging in a model, or adding a unit or an INCOSE rule, are in [SKILLS.md](SKILLS.md).

## Limits

- The specs, the baseline and the truth are simulated. They are built from the shapes real Lastenhefte have, but they
  are not customer documents. A first engagement would replay a customer's past tenders, with the bid engineers'
  answers as the truth, before anything goes live.
- The model in the numbers is a stand-in with fixed error rates. The adapter for a real model is there and tested
  for its contract, not for a particular model's accuracy.
- The guard is a set of patterns, and it missed new wording on the held-out run. The defences that do not depend on
  wording are structural:
  - text reaches the model only as data;
  - the model only picks from options;
  - every verdict is computed.
- Requirements with no number, such as functional behaviour, interfaces and processes, are extracted, checked for
  writing quality and sent to the customer as questions. They are not traced semantically yet.
"""
