"""Numbers and units as engineers write them: decimal commas, thousands separators, °C next to K, mbar next to kPa.

Every value is kept in a canonical unit per dimension so that "82 kg" and "82.000 g" are the same requirement and
"85 °C" and "358.15 K" are not a change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# unit as written -> (dimension, canonical unit, factor, offset): canonical = value * factor + offset
UNITS: dict[str, tuple[str, str, float, float]] = {
    "kW": ("power", "kW", 1, 0), "W": ("power", "kW", 1e-3, 0), "MW": ("power", "kW", 1e3, 0),
    "kWh": ("energy", "kWh", 1, 0), "Wh": ("energy", "kWh", 1e-3, 0),
    "Nm": ("torque", "Nm", 1, 0), "N·m": ("torque", "Nm", 1, 0), "kNm": ("torque", "Nm", 1e3, 0),
    "kg": ("mass", "kg", 1, 0), "g": ("mass", "kg", 1e-3, 0), "t": ("mass", "kg", 1e3, 0),
    "°C": ("temperature", "°C", 1, 0), "K": ("temperature", "°C", 1, -273.15),
    "°F": ("temperature", "°C", 5 / 9, -32 * 5 / 9),
    "V": ("voltage", "V", 1, 0), "kV": ("voltage", "V", 1e3, 0), "mV": ("voltage", "V", 1e-3, 0),
    "A": ("current", "A", 1, 0), "mA": ("current", "A", 1e-3, 0), "kA": ("current", "A", 1e3, 0),
    "Hz": ("frequency", "kHz", 1e-3, 0), "kHz": ("frequency", "kHz", 1, 0), "MHz": ("frequency", "kHz", 1e3, 0),
    "ms": ("time", "s", 1e-3, 0), "s": ("time", "s", 1, 0), "min": ("time", "s", 60, 0), "h": ("time", "s", 3600, 0),
    "rpm": ("speed", "rpm", 1, 0), "1/min": ("speed", "rpm", 1, 0), "min-1": ("speed", "rpm", 1, 0),
    "min^-1": ("speed", "rpm", 1, 0), "U/min": ("speed", "rpm", 1, 0),
    "l/min": ("flow", "l/min", 1, 0), "l/h": ("flow", "l/min", 1 / 60, 0), "l/s": ("flow", "l/min", 60, 0),
    "m³/h": ("flow", "l/min", 1000 / 60, 0), "m3/h": ("flow", "l/min", 1000 / 60, 0),
    "mbar": ("pressure", "mbar", 1, 0), "bar": ("pressure", "mbar", 1e3, 0), "Pa": ("pressure", "mbar", 1e-2, 0),
    "kPa": ("pressure", "mbar", 10, 0), "MPa": ("pressure", "mbar", 1e4, 0), "psi": ("pressure", "mbar", 68.9476, 0),
    "dB(A)": ("sound", "dB(A)", 1, 0), "dBA": ("sound", "dB(A)", 1, 0), "dB": ("sound", "dB(A)", 1, 0),
    "%": ("ratio", "%", 1, 0),
    "km": ("distance", "km", 1, 0), "m": ("length", "mm", 1e3, 0), "mm": ("length", "mm", 1, 0),
    "arcmin": ("angle", "arcmin", 1, 0), "arcsec": ("angle", "arcmin", 1 / 60, 0),
    "years": ("duration", "years", 1, 0), "a": ("duration", "years", 1, 0),
    "cycles": ("count", "cycles", 1, 0),
    "mm/s": ("velocity", "mm/s", 1, 0), "m/s": ("velocity", "mm/s", 1e3, 0), "km/h": ("vehicle speed", "km/h", 1, 0),
    "g/a": ("leak rate", "g/a", 1, 0), "g/year": ("leak rate", "g/a", 1, 0), "g/yr": ("leak rate", "g/a", 1, 0),
    "kg/h": ("mass flow", "kg/h", 1, 0), "kg/s": ("mass flow", "kg/h", 3600, 0), "g/s": ("mass flow", "kg/h", 3.6, 0),
}
_UNIT_RE = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
NUM = r"[-−+]?\d{1,3}(?:[.,\u202f ]\d{3})+(?:[.,]\d+)?(?!\d)|[-−+]?\d+(?:[.,]\d+)?"
MENTION = re.compile(rf"(?P<num>{NUM})(?:\s?(?P<unit>{_UNIT_RE})(?![A-Za-z0-9]))?")


@dataclass(frozen=True)
class Mention:
    value: float
    unit: str | None          # as written
    start: int
    end: int

    @property
    def dimension(self) -> str | None:
        return UNITS[self.unit][0] if self.unit else None


def locale_of(text: str) -> str:
    """'de' when the document writes decimal commas (91,5 %), 'en' otherwise. Decided once per document."""
    de = len(re.findall(r"\d,\d{1,2}(?!\d)", text)) + len(re.findall(r"\d{1,3}\.\d{3}(?![\d,])\b", text)) * 0.5
    en = len(re.findall(r"\d\.\d{1,2}(?!\d)", text)) + len(re.findall(r"\d{1,3},\d{3}(?![\d.])\b", text)) * 0.5
    return "de" if de > en else "en"


def parse_number(s: str, locale: str) -> float | None:
    s = s.replace("−", "-").replace(" ", "").replace("\xa0", "").replace(" ", "").strip()
    if locale == "de":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def mentions(text: str, locale: str) -> list[Mention]:
    out = []
    for m in MENTION.finditer(text):
        raw = m.group("num")
        if " " in raw and locale == "en" and "," in raw:
            continue
        v = parse_number(raw, locale)
        if v is None:
            continue
        prev = text[max(0, m.start() - 1):m.start()]
        if prev and (prev.isalpha() or prev in "-_/"):
            if not (prev == "-" and m.group("num").startswith("-")):
                continue                     # part of an identifier such as AUR-012 or IP67
        out.append(Mention(v, m.group("unit"), m.start(), m.end()))
    return out


def canonical(value: float, unit: str | None) -> tuple[float, str | None, str | None]:
    if unit is None:
        return value, None, None
    dim, cu, f, off = UNITS[unit]
    return round(value * f + off, 6), cu, dim
