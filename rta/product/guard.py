"""Customer text is data. A sentence that addresses an AI or a tool, or tells the reader to change its verdicts,
is held for a person and never reaches a model or a decision."""
from __future__ import annotations

import re

ADDRESS = re.compile(r"\b(ai|a\.i\.|assistant|chatbot|language model|llm|gpt|automated (?:tool|system|reader)s?|"
                     r"bot|copilot|agent)s?\b", re.I)
COMMAND = re.compile(r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instruction|prompt|rule|previous|above)s?\b|"
                     r"\b(mark|report|classify|rate|treat)\b.{0,60}\b(compliant|approved|fulfilled|accepted|ok)\b|"
                     r"\bdo not (?:raise|report|flag|mention)\b|\bsystem prompt\b|\byou are now\b", re.I)


def suspicious(text: str) -> str | None:
    if COMMAND.search(text):
        return "instruction to the reader"
    if ADDRESS.search(text) and re.search(r"\b(must|should|shall|please|need to)\b", text, re.I):
        return "addresses an automated reader"
    return None
