"""Ferrite beads: exactly 22/100/220/330/1k ohm @ 100 MHz in 0402 and 0805.
Würth WE-CBF/WE-CBA first, Vishay Dale fallback; highest current, then lowest DCR."""
from _common import num, close, pkg_is, mfr_rank

TABLE = "Ferrite_Beads"
WURTH, VISHAY_DALE = 732, 541
QUERIES = [dict(keywords=f"ferrite bead {s}", mfr_ids=[m]) for s in ("0402", "0805") for m in (WURTH, VISHAY_DALE)]
PREFERRED = ["Würth", "Vishay"]
IMPEDANCES = [("22R", 22), ("100R", 100), ("220R", 220), ("330R", 330), ("1K", 1000)]
FOOTPRINT = {"0402": "Inductor_SMD:L_0402_1005Metric", "0805": "Inductor_SMD:L_0805_2012Metric"}


def slots():
    return [dict(part_id=f"FB-{s}-{code}", size=s, code=code, ohms=z) for s in ("0402", "0805") for code, z in IMPEDANCES]


def accept(sp, slot):
    p = sp["params"]
    return (pkg_is(sp, slot["size"]) and "100MHz" in (p.get("Impedance @ Frequency") or "").replace(" ", "")
            and close(num(p.get("Impedance @ Frequency"), "Ohm"), slot["ohms"]) and (p.get("Number of Lines") in (None, "1")))


def rank(sp, slot):
    p = sp["params"]
    return (mfr_rank(sp, PREFERRED), -(num(p.get("Current Rating (Max)"), "A") or 0), num(p.get("DC Resistance (DCR) (Max)"), "Ohm") or 9e9)


def make_row(sp, slot, var):
    p = sp["params"]
    cur, dcr = p.get("Current Rating (Max)", ""), p.get("DC Resistance (DCR) (Max)", "")
    val = f"{slot['code'].replace('K', 'k')}@100MHz"
    return dict(Symbol="Device:FerriteBead", Footprint=FOOTPRINT[slot["size"]], Value=val, Package=slot["size"],
                Description=f"Ferrite bead {val} {cur} {slot['size']}", Keywords=f"FB ferrite bead EMI {slot['size']} {slot['code']}",
                Tolerance=p.get("Tolerance", "25%").lstrip("±"), Rating=cur, TC_Dielectric=f"DCR {dcr}", FP_Filter=f"L_{slot['size']}*")
