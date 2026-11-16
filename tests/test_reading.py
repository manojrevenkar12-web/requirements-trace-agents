"""Numbers, units, clauses and files as engineers write them."""
import math

from rta.product.ingest import read
from rta.product.parse import parse, row_clause, split
from rta.product.units import canonical, locale_of, mentions


def test_locale_and_numbers():
    assert locale_of("91,5 % und 310.000 km") == "de"
    assert locale_of("92.5 % and 17,250 rpm") == "en"
    assert [(m.value, m.unit) for m in mentions("at least 310.000 km and 91,5 %", "de")] == [(310000, "km"), (91.5, "%")]
    assert [(m.value, m.unit) for m in mentions("not less than 17,250 1/min", "en")] == [(17250, "1/min")]
    assert mentions("[AUR-012] The gearbox", "en") == []


def test_units_are_canonical():
    assert canonical(82000, "g")[:2] == (82, "kg")
    assert canonical(358.15, "K")[:2] == (85, "°C")
    assert canonical(15.5, "kPa")[:2] == (155, "mbar")
    assert canonical(240, "ms")[:2] == (0.24, "s")


def test_comparator_nearest_the_number_wins():
    p = parse("The electric motor shall reach a maximum speed of not less than 17,250 1/min", "en")
    assert (p.kind, p.lo, p.unit) == ("min", 17250, "rpm")
    p = parse("The motor shall keep a maximum winding temperature of 175 °C", "en")
    assert (p.kind, p.hi) == ("max", 175)
    p = parse("The motor shall reach a minimum maximum speed of 16.000 rpm", "de")
    assert (p.kind, p.lo) == ("min", 16000)
    p = parse("The drive unit shall deliver a minimum peak power for 10 s of 222 kW", "en")
    assert (p.kind, p.lo, p.unit) == ("min", 222, "kW") and ("time", 10.0) in p.cond_sig


def test_conditions_are_not_values():
    p = parse("When the coolant inlet temperature exceeds 65 °C, the inverter shall limit a phase current of at most 406 A", "en")
    assert (p.ears, p.kind, p.hi, p.unit) == ("event", "max", 406, "A")
    assert p.cond_sig == (("temperature", 65.0),)
    p = parse("The electric motor shall provide a minimum peak torque of 364 Nm at a coolant temperature of -30 °C", "en")
    assert p.lo == 364 and p.cond_sig == (("temperature", -30.0),)


def test_ranges_and_rows():
    p = parse("The drive unit shall operate within an ambient operating temperature between -35 °C and 85 °C", "en")
    assert (p.kind, p.lo, p.hi) == ("range", -35, 85)
    rid, clause, sub = row_clause(["AUR-009", "Inverter", "Phase current", ">= 529", "A"], None)
    assert rid == "AUR-009" and parse(clause, "en").lo == 529
    _, clause, _ = row_clause(["Inverter", "Phase current (when the coolant inlet temperature exceeds 65 °C)", "max. 390", "A"],
                              ["Subsystem", "Parameter", "Requirement", "Unit"])
    p = parse(clause, "en")
    assert p.ears == "event" and p.hi == 390


def test_split_compound_but_not_ranges():
    parts = split("The drive unit shall deliver a peak power of at least 217 kW and shall have a mass of at most 84 kg.")
    assert parts == ["The drive unit shall deliver a peak power of at least 217 kW", "The drive unit shall have a mass of at most 84 kg"]
    assert len(split("The inverter shall operate between 250 V and 460 V.")) == 1
    assert not math.isinf(parse(parts[1], "en").hi)


def test_pdf_and_word_read_the_same(world):
    from rta.world.docs import pdf, word
    spec = world.specs[sorted(world.specs)[0]]
    def body(blocks):
        start = next(i for i, x in enumerate(blocks) if x.kind == "heading" and x.text.startswith("1 "))
        return [x.text for x in blocks[start:] if x.kind == "text"]
    a, b = body(read(pdf(spec))), body(read(word(spec)))
    assert a == b
    assert not any("Confidential" in t or t.startswith("Page ") for t in a)
    assert sum(1 for x in read(pdf(spec)) if x.kind == "row") == sum(1 for x in read(word(spec)) if x.kind == "row")
