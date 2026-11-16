"""Writing-quality checks on each requirement, after the INCOSE Guide to Writing Requirements (GtWR).

Rule codes follow GtWR v3. Each check is a pattern a reviewer can read; a requirement that fails one is not wrong,
it is a question back to the customer before anyone quotes against it.
"""
from __future__ import annotations

import re

from rta.product.parse import Parsed

RULES = {
    "passive": ("R2", "Active voice: name the responsible entity as the subject"),
    "vague": ("R7", "Vague terms: no measurable acceptance criterion"),
    "escape": ("R8", "Escape clauses: 'where possible', 'if technically feasible'"),
    "open_ended": ("R9", "Open-ended clauses: 'including but not limited to', 'etc.'"),
    "oblique": ("R17", "Oblique symbol: 'and/or'"),
    "combinator": ("R19", "Combinators: two requirements in one sentence"),
    "universal": ("R32", "Universal qualification: 'all', 'always', 'any'"),
    "missing_unit": ("R34", "Measurable performance: a value without a unit"),
}
VAGUE = re.compile(r"\b(sufficient(?:ly)?|adequate(?:ly)?|appropriate(?:ly)?|quick(?:ly)?|fast|minimal|minimi[sz]ed?|"
                   r"easy|easily|user[- ]friendly|robust(?:ly)?|reasonabl[ey]|as (?:\w+ )?as possible|state of the art|"
                   r"optimal|optimi[sz]ed?|flexible|seamless(?:ly)?|high quality|low noise|significant(?:ly)?)\b", re.I)
ESCAPE = re.compile(r"\b(if (?:technically )?(?:feasible|possible|practicable|practical)|where (?:possible|feasible|"
                    r"practicable)|as far as (?:possible|practicable|feasible)|as appropriate|if necessary|where necessary)\b",
                    re.I)
OPEN = re.compile(r"\b(including but not limited to|etc\.?|and so on|among others|such as)\b", re.I)
OBLIQUE = re.compile(r"\b(and/or|or/and)\b", re.I)
UNIVERSAL = re.compile(r"\b(all|always|every|any|never)\b(?! (?:of the following))", re.I)
PASSIVE = re.compile(r"\b(?:shall|must) be (\w+(?:ed|en|t))\b(?:[\w\s]{0,30})\bby the\b", re.I)


def check(clause: str, parsed: Parsed, compound: bool, dimensionless: set[str]) -> list[str]:
    found = []
    if PASSIVE.search(clause):
        found.append("passive")
    if VAGUE.search(clause) or (parsed.kind == "none" and not parsed.values_seen):
        found.append("vague")
    if ESCAPE.search(clause):
        found.append("escape")
    if OPEN.search(clause):
        found.append("open_ended")
    if OBLIQUE.search(clause):
        found.append("oblique")
    if compound:
        found.append("combinator")
    if UNIVERSAL.search(clause):
        found.append("universal")
    if parsed.kind in ("min", "max", "eq") and parsed.unit_written is None and not (set(parsed.label) & dimensionless):
        found.append("missing_unit")
    return found
