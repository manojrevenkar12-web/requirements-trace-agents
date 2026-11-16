# SKILLS.md

## Connect a customer's ALM export

Point `config/pipeline.yaml` `reqif` at the attribute names in their export (DOORS uses `ReqIF.Text` and
`ReqIF.ForeignID`, Polarion and Codebeamer their own). `rta.product.reqif.read` keeps every attribute by its
LONG-NAME and every SPEC-RELATION by type, so only the names change. Check with `POST /baseline`: the response lists
the subsystems and the count of requirements and tests it found.

## Plug in a real model

Set `RTA_MODEL_URL` (an Azure OpenAI or any OpenAI-compatible chat completions URL), `RTA_MODEL_KEY` and
`RTA_MODEL_NAME`. The product asks one question per sentence whose subject it cannot name itself; answers outside the
offered options are ignored. Run `python -m rta.eval.cli evaluate` with the stand-in first so the numbers to compare
against are on record.

## Add a unit or a phrasing

Units: `rta/product/units.py` `UNITS` (dimension, canonical unit, factor, offset). Comparators: `MIN` and `MAX` in
`rta/product/parse.py`. Add a test in `tests/test_reading.py` with the sentence as the customer wrote it, then
re-run the dev evaluation; the held-out world is not re-run.

## Add an INCOSE rule

`rta/product/quality.py`: a pattern and an entry in `RULES` with its GtWR code. The world records the defect in the
truth when it writes it (`rta/world/spec.py` `write`), so precision and recall per rule appear in the report.

## Answer "what does revision C change?"

`POST /specs/<name>` with each revision, then `GET /specs/<name>/impact`: changed values after unit conversion, the
supplier requirements and tests they touch, compliance verdicts that flip, and rewordings that touch nothing.
