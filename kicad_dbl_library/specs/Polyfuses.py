"""Resettable PTC fuses (polyfuses), Littelfuse (incl. ex-Raychem PolySwitch) preferred.

Slots = (package, hold current, minimum voltage rating), chosen from what Littelfuse
stocks at DigiKey: signal protection from 10mA hold up to 2.6A, voltage classes
6V / 9-16V / 24-36V / 60V. Per slot: exact hold current, Vmax >= slot voltage;
prefer non-automotive (no ASMD / -A), then the lowest voltage class that qualifies,
then lowest post-trip resistance R1max.
Not stocked anywhere in SMD: >=1A hold at 60V (largest 60V part is 1812 500mA).
"""
import re
from _common import num, close, pkg_is, mfr_rank

TABLE = "Polyfuses"
QUERIES = [dict(keywords=k) for k in (
    [f"Littelfuse PTC resettable fuse {s}" for s in ("0402", "0603", "0805", "1206", "1210", "1812")]
    + [f"Littelfuse {s}" for s in ("femtoSMD", "picoSMD", "nanoSMD", "microSMD", "miniSMD")]
    + [f"Littelfuse {s}L" for s in ("1206", "1210", "1812", "0805", "0603")])]
PREFERRED = ["Littelfuse", "Bourns"]
FOOTPRINT = {s: f"Fuse:Fuse_{s}_{m}Metric" for s, m in
             (("0402", "1005"), ("0603", "1608"), ("0805", "2012"), ("1206", "3216"), ("1210", "3225"), ("1812", "4532"))}

# size -> [(hold A, min V)]
SLOTS = {
    "0402": [(0.1, 6), (0.5, 6), (1.0, 6)],
    "0603": [(0.01, 60), (0.05, 15), (0.1, 15), (0.2, 9), (0.5, 6), (1.0, 6)],
    "0805": [(0.05, 30), (0.1, 24), (0.2, 16), (0.35, 6), (0.75, 6), (1.1, 6), (2.0, 6)],
    "1206": [(0.05, 60), (0.1, 60), (0.2, 30), (0.35, 16), (0.5, 15), (0.5, 24), (0.75, 16), (1.1, 16),
             (1.5, 12), (2.0, 6)],
    "1210": [(0.5, 30), (0.75, 24), (1.1, 16), (1.5, 16)],
    "1812": [(0.1, 60), (0.2, 60), (0.35, 60), (0.5, 60), (0.75, 33), (1.1, 33), (1.5, 24), (2.0, 16), (2.6, 16)],
}


def _code(a):
    """0.01 -> '10MA', 0.5 -> '500MA', 1.0 -> '1A', 1.1 -> '1A1', 2.6 -> '2A6'."""
    if a < 1:
        return f"{round(a * 1000)}MA"
    whole, frac = divmod(round(a * 10), 10)
    return f"{whole}A{frac}" if frac else f"{whole}A"


def _txt(a):
    return f"{round(a * 1000)}mA" if a < 1 else f"{a:g}A"


def slots():
    return [dict(part_id=f"PTC-{s}-{_code(a)}-{v}V", size=s, hold=a, vmin=v)
            for s, lst in SLOTS.items() for a, v in lst]


def _auto(sp):
    m = sp["mpn"]
    return "ASMD" in m or m.endswith("-A") or "AUTO" in m


def accept(sp, slot):
    p = sp["params"]
    if p.get("Type") not in (None, "Polymeric") or "Surface" not in (p.get("Mounting Type") or ""):
        return False
    v = num(p.get("Voltage - Max"), "V")
    return pkg_is(sp, slot["size"]) and close(num(p.get("Current - Hold (Ih) (Max)"), "A"), slot["hold"]) \
        and v is not None and v >= slot["vmin"]


def rank(sp, slot):
    p = sp["params"]
    return (mfr_rank(sp, PREFERRED), _auto(sp), num(p.get("Voltage - Max"), "V"),
            num(p.get("Resistance - Post Trip (R1) (Max)"), "Ohm") or 9e9)


def _ohm(t):
    r = num(t, "Ohm")
    return f"{r:g}R" if r is not None else "?"


def make_row(sp, slot, var):
    p = sp["params"]
    ih, s = _txt(slot["hold"]), slot["size"]
    it = (p.get("Current - Trip (It)") or "").replace(" ", "")
    vmax = (p.get("Voltage - Max") or "").replace(" ", "")
    imax = (p.get("Current - Max") or "").replace(" ", "")
    val = f"{ih} {slot['vmin']}V"
    return dict(Symbol="Device:Polyfuse", Footprint=FOOTPRINT[s], Value=val, Package=s,
                Description=f"PTC resettable fuse Ihold {ih} Itrip {it} {vmax} {s} ({sp['series'] or ''})".replace(" ()", ""),
                Keywords=f"PTC polyfuse resettable fuse polyswitch {s} {ih}",
                Rating=f"Ihold {ih} / Itrip {it} / {vmax}",
                TC_Dielectric=f"R1max {_ohm(p.get('Resistance - Post Trip (R1) (Max)'))}, Imax {imax}",
                FP_Filter=f"Fuse_{s}*")
