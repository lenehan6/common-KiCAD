"""Small-signal switching diodes (1N4148W / 1N4148WS / 1N4148WT / BAS16 class).

One slot per SOD package: Vr 75..100V, Io 150..300mA, standard (non-Schottky) junction.
Preferred makers Vishay, Nexperia, onsemi, Diodes Inc; other makers fill gaps.
Within a maker the classic part family (1N4148W* / BAS16*) is preferred over
look-alikes, and non-automotive grades over AEC-Q101 ones.

Pinout: Device:D pin 1 = K, pin 2 = A; KiCad Diode_SMD:D_SOD-* pad 1 = cathode (the
silkscreen cathode bar is drawn at pad 1). SOD packages mark the cathode with a band.
"""
import re

import dk_client
from _common import num, mfr_rank

TABLE = "Diodes_Signal"
QUERIES = [dict(keywords=k) for k in (
    "switching diode SOD-123", "switching diode SOD-323", "1N4148W", "1N4148WS", "BAS16 SOD-323",
    "BAS16W", "BAV16W", "Vishay switching diode SOD-123", "Nexperia switching diode SOD-323")]

PREFERRED = ["Vishay", "Nexperia", "onsemi", "Diodes Inc", "Taiwan Semiconductor", "Toshiba", "Rohm",
             "Panjit", "Comchip", "Micro Commercial", "MCC", "Diotec"]

# code, DigiKey 'Package / Case', footprint, FP filter, family preference regexes
PACKAGES = [
    ("SOD123", "SOD-123", "Diode_SMD:D_SOD-123", "D*SOD?123*", [r"^1N4148W(?![ST])", r"^BAS16W", r"^BAV16W", r"^1N4148"]),
    ("SOD323", "SC-76, SOD-323", "Diode_SMD:D_SOD-323", "D*SOD?323*", [r"^1N4148WS", r"^BAS16", r"^1N4148"]),
    ("SOD323F", "SC-90, SOD-323F", "Diode_SMD:D_SOD-323F", "D*SOD?323*", [r"^BAS16J", r"^1N4148WS", r"^BAS16", r"^1N4148"]),
    ("SOD523", "SC-79, SOD-523", "Diode_SMD:D_SOD-523", "D*SOD?523*", [r"^1N4148WT", r"^BAS16", r"^1N4148"]),
]


def slots():
    return [dict(part_id=f"D-SIG-{code}-75V", code=code, pkg=pkg, fp=fp, flt=flt, fam=fam, pkgname=pkg.split(", ")[-1])
            for code, pkg, fp, flt, fam in PACKAGES]


def _auto(sp):
    return (sp["params"].get("Grade") == "Automotive") or bool(re.search(r"(-Q|Q-|-AQ|-AU|HE3|HG3|^S|^NSV)", sp["mpn"]))


def accept(sp, slot):
    p = sp["params"]
    vr = num(p.get("Voltage - DC Reverse (Vr) (Max)"), "V")
    io = num(p.get("Current - Average Rectified (Io)"), "A")
    tech = p.get("Technology") or ""
    return (p.get("Package / Case") == slot["pkg"] and vr is not None and 75 <= vr <= 100
            and io is not None and 0.15 <= io <= 0.3 and tech == "Standard"
            and not p.get("Diode Configuration") and "schottky" not in sp["desc"].lower())


def _fam_rank(sp, slot):
    for i, pat in enumerate(slot["fam"]):
        if re.search(pat, sp["mpn"]):
            return i
    return len(slot["fam"])


def rank(sp, slot):
    return (mfr_rank(sp, PREFERRED), _fam_rank(sp, slot), _auto(sp))


def _family(sp):
    m = re.match(r"(1N4148W[ST]?|1N4448W[ST]?|BAS16[A-Z]*|BAV16W)", sp["mpn"])
    return m.group(1) if m else sp["mpn"]


def make_row(sp, slot, var):
    p = sp["params"]
    vr = p.get("Voltage - DC Reverse (Vr) (Max)", "").replace(" ", "")
    io = p.get("Current - Average Rectified (Io)", "").replace(" ", "")
    vf = (p.get("Voltage - Forward (Vf) (Max) @ If") or "").replace(" ", "")
    trr = (p.get("Reverse Recovery Time (trr)") or "").replace(" ", "")
    fam = _family(sp)
    pk = slot["pkgname"]
    ds = dk_client.https(sp.get("datasheet")) or ""
    return dict(
        Symbol="Device:D", Footprint=slot["fp"], Value=fam, Package=pk,
        Description=f"Switching diode {vr} {io} {pk}, Vf {vf}" + (f", trr {trr}" if trr and trr != "-" else ""),
        Keywords=f"diode signal switching fast {fam} {pk}", Rating=f"{vr} {io}",
        TC_Dielectric=f"Vf {vf}" + (f", trr {trr}" if trr and trr != "-" else ""), FP_Filter=slot["flt"],
        Pinout="1=K 2=A",
        Pinout_Source=f"{ds} (package outline: cathode band = pin 1 = K); Device:D pin1=K/pin2=A; "
                      f"KiCad {slot['fp']} pad 1 = cathode (silk bar)")
