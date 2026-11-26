"""Fast-acting SMD chip fuses, Littelfuse, 0402 / 0603 / 1206, 0.25-5A, >=32V DC.

Series preference per size (first stocked wins):
  0402: 0435;  0603: 0467, then 0494 / 0438 / 0441;  1206: 0466 (SlimLine), then 0437 / 0440 / 0458.
Non-automotive (no 'A' suffix) preferred; HF (halogen-free) and standard parts are equivalent.
Note: 32V DC is the table minimum (0435/0467 and 0466 >=3A); 0466 <=2A parts are 63-125V, 0467 1.5A is 65V.
"""
import re
from _common import num, close, pkg_is

TABLE = "Fuses_Chip"
QUERIES = [dict(keywords=k) for k in (
    "Littelfuse fuse 0603 fast", "Littelfuse fuse 1206 fast", "Littelfuse 0466", "Littelfuse 0467",
    "Littelfuse 0435", "Littelfuse 0437", "Littelfuse fuse 0402")]
SERIES = {"0402": ["0435"], "0603": ["0467", "0494", "0438", "0441"], "1206": ["0466", "0437", "0440", "0458"]}
FOOTPRINT = {"0402": "Fuse:Fuse_0402_1005Metric", "0603": "Fuse:Fuse_0603_1608Metric",
             "1206": "Fuse:Fuse_1206_3216Metric"}
AMPS = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5]
MIN_V = 32


def _code(a):
    if a < 1:
        return f"{round(a * 1000)}MA"
    whole, frac = divmod(round(a * 10), 10)
    return f"{whole}A{frac}" if frac else f"{whole}A"


def _txt(a):
    return f"{round(a * 1000)}mA" if a < 1 else f"{a:g}A"


def slots():
    return [dict(part_id=f"FUSE-{s}-{_code(a)}-FAST", size=s, amps=a) for s in ("0402", "0603", "1206") for a in AMPS]


def _series(sp, slot):
    for i, pre in enumerate(SERIES[slot["size"]]):
        if sp["mpn"].startswith(pre):
            return i
    return None


def accept(sp, slot):
    p = sp["params"]
    v = num(p.get("Voltage Rating - DC"), "V")
    return ("Littelfuse" in sp["mfr"] and _series(sp, slot) is not None and pkg_is(sp, slot["size"])
            and p.get("Response Time") == "Fast Blow" and close(num(p.get("Current Rating (Amps)"), "A"), slot["amps"])
            and v is not None and v >= MIN_V)


def _auto(sp):
    return bool(re.search(r"[A-Z]A$", sp["mpn"].split(".")[-1])) or sp["mpn"].endswith("GT")


def rank(sp, slot):
    return (_series(sp, slot), _auto(sp))


def make_row(sp, slot, var):
    p = sp["params"]
    a, s = _txt(slot["amps"]), slot["size"]
    vdc = (p.get("Voltage Rating - DC") or "").replace(" ", "")
    brk = p.get("Breaking Capacity @ Rated Voltage") or ""
    i2t = (p.get("Melting I²t") or "").replace(" ", "")
    ser = sp["mpn"][:4]
    return dict(Symbol="Device:Fuse", Footprint=FOOTPRINT[s], Value=f"{a} fast", Package=s,
                Description=f"Fuse fast-acting {a} {vdc} {s} Littelfuse {ser}",
                Keywords=f"fuse chip fast-acting {s} {a} {ser}",
                Rating=f"{a} / {vdc}DC", TC_Dielectric=", ".join(x for x in (f"Breaking {brk}" if brk else "", f"I2t {i2t}A2s" if i2t else "") if x),
                FP_Filter=f"Fuse_{s}*")
