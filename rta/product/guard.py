"""Customer text is data. A sentence that addresses an AI or a tool, or tells the reader to change its verdicts,
is held for a person and never reaches a model or a decision."""
from __future__ import annotations

import re

READER = r"(?:ai|a\.i\.|assistants?|chat ?bots?|bots?|language[- ]models?|llms?|gpts?|copilots?|agents?|" \
         r"(?:automated|automatic|machine|ai)[- ](?:\w+ )?(?:tools?|systems?|readers?|reviewers?|assistants?|agents?|parsers?)|" \
         r"(?:tools?|systems?|readers?|software) (?:reading|processing|parsing))"
ADDRESS = re.compile(rf"\b{READER}\b", re.I)
COMMAND = re.compile(r"\b(ignore|disregard|forget|override|bypass|skip)\b.{0,50}\b(instructions?|prompts?|rules?|"
                     r"guidance|previous|earlier|above|checks?|assessments?|reviews?|evaluation)\b|"
                     r"\b(mark|report|classify|rate|treat|declare|confirm|consider)\b.{0,60}\b(compliant|conform\w*|"
                     r"approved|pre-approved|fulfilled|accepted|ok)\b|"
                     r"\bdo not (?:raise|report|flag|mention)\b|\bsystem prompt\b|\byou are now\b", re.I)


def suspicious(text: str) -> str | None:
    if COMMAND.search(text):
        return "instruction to the reader"
    if ADDRESS.search(text) and re.search(r"\b(must|should|shall|please|need to)\b", text, re.I):
        return "addresses an automated reader"
    return None
