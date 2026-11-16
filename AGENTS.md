# Working in requirements-trace-agents

Fast feedback first: `python -m pytest -q` runs units, parsing, PDF and Word reading, the INCOSE rules, the guard,
trace links, compliance, conflicts, change impact, ReqIF, the HTTP service, the invariants and a quick evaluation in
a few seconds. `python -m rta.eval.cli evaluate --profile quick` runs all four designs on two specs.
`cd web && npm test && npm run typecheck` for the dashboard. After a change to the product, the world or the settings:

```bash
python -m rta.eval.cli evaluate && python -m rta.eval.cli readme && cp reports/dev.json web/public/dev.json
```

and commit `reports/dev.json`, `web/public/dev.json` and `README.md`. CI checks that the README matches the reports.

## Layout

| path | what it is | may import |
|---|---|---|
| `rta/world` | the customer specs (rendered to PDF and Word), the supplier's baseline (ReqIF), revision B, the engineers' truth, the stand-in model | `rta/keyed.py` |
| `rta/product` | reading, guard, parsing, INCOSE rules, trace links, compliance, conflicts, change impact, ReqIF, model adapters, HTTP service | nothing outside `rta/product` |
| `rta/eval` | the four designs, scoring against the truth, gate, README, CLI | everything |
| `web` | the dashboard: React, TypeScript, Motion, feature-first, reads `public/dev.json` | the report |
| `config` | world files, the product's settings, the gate | |

## Invariants (checked in `tests/test_service_and_invariants.py` and the tests)

1. **The truth stays in the world.** `rta/product` never imports `rta/world` or `rta/eval`. It gets file bytes and
   a ReqIF export, as it would from a customer portal and from DOORS or Polarion.
2. **The world does not read the product's settings.** `rta/world` reads its world file only.
3. **Same luck for every design.** Every draw is keyed by what it is about (`rta/keyed.py`): every design reads the
   same files, and the stand-in model misreads the same sentences for every design that asks it.
4. **The model reads and code decides.** The model answers two narrow questions (which subsystem, is this a
   requirement); the answer must be one of the offered options and fit the baseline, or the sentence goes to a
   person. Values, links, compliance, conflicts and impact are computed. Customer text reaches the model as data.
5. **Customer text is data.** A sentence that addresses an automated reader or tells it to change verdicts is held
   for a person before any parsing or model call.
6. **Settings in config.** Thresholds, the ReqIF attribute names and the effort assumptions live in
   `config/pipeline.yaml`; the dashboard's colours, sizes and durations in `web/src/shared/theme.css` and `tokens.ts`.
7. **Generated reports.** README numbers come from `reports/`.

## The held-out rule

`config/heldout.yaml` (world H1, a heat-pump compressor module) was written before the first result and is run once
(`python -m rta.eval.cli heldout`) with the code and settings dev ended on. It writes `config/heldout.lock` and
`reports/heldout.json`; findings go into `docs/heldout.md`. Fixes are made and measured on dev; the held-out world is
not run again and `config/gate.yaml` is not moved.
