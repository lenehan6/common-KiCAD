"""Zener diodes, E24 voltages 2.4V..36V, SOD-123 (~400-500mW, BZT52/MMSZ class) and
SOD-323 (~200-300mW, BZX384/MMSZ..S/MM3Z class), tolerance <= 5%.

Vz must equal the slot voltage; power >= 300mW (SOD-123) / >= 200mW (SOD-323).
Preferred makers Vishay, Nexperia, then onsemi, Diodes Inc; others fill gaps.
Within a maker one series is preferred so a slot column stays consistent
(SOD-123: BZT52C.. then MMSZ52xxB; SOD-323: BZX384C.. then others), 5% before 2%,
non-automotive first. Low-current MMSZ46xx/1N46xx parts are excluded.

Pinout: Device:D_Zener pin 1 = K, pin 2 = A; KiCad Diode_SMD:D_SOD-* pad 1 = cathode.
"""
import re

import dk_client
from _common import num, mfr_rank

TABLE = "Diodes_Zener"
QUERIES = [dict(keywords=k) for k in (
    "zener diode SOD-123", "zener diode SOD-323", "BZT52C", "MMSZ52", "BZX384", "BZT52H",
    "Vishay zener SOD-123", "Nexperia zener SOD-323", "Nexperia zener SOD-123")]

PREFERRED = ["Vishay", "Nexperia", "onsemi", "Diodes Inc", "Taiwan Semiconductor", "Rohm", "Panjit",
             "Comchip", "Micro Commercial", "MCC", "Diotec", "SMC Diode"]

E24_V = [2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
         10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36]

PACKAGES = [  # code, DigiKey Package / Case, footprint, filter, display, min power W, series prefs
    ("SOD123", "SOD-123", "Diode_SMD:D_SOD-123", "D*SOD?123*", "SOD-123", 0.3,
     [r"^BZT52C\d", r"^MMSZ52\d\dB", r"^MMSZ\d", r"^BZT52"]),
    ("SOD323", "SC-76, SOD-323", "Diode_SMD:D_SOD-323", "D*SOD?323*", "SOD-323", 0.2,
     [r"^BZX384-?C\d", r"^BZX38450-C", r"^MM3Z\d+V?\d*T1G", r"^MM3Z", r"^BZT52C.*S", r"^PZU"]),
]


def vcode(v):
    """2.4 -> '2V4', 10 -> '10V'."""
    return f"{int(v)}V{int(round(v * 10)) % 10}" if v < 10 else f"{int(v)}V"


def slots():
    return [dict(part_id=f"D-ZEN-{code}-{vcode(v)}", code=code, v=v, pkg=pkg, fp=fp, flt=flt, disp=disp,
                 pmin=pmin, fam=fam)
            for code, pkg, fp, flt, disp, pmin, fam in PACKAGES for v in E24_V]


def _tol(sp):
    return num((sp["params"].get("Tolerance") or "").replace("±", ""), "%")


def _auto(sp):
    return (sp["params"].get("Grade") == "Automotive") or bool(re.search(r"(-Q|Q-|-AQ|-AU|HE3|HG3|^SZ|^NSV)", sp["mpn"]))


def accept(sp, slot):
    p = sp["params"]
    vz = num(p.get("Voltage - Zener (Nom) (Vz)"), "V")
    pw = num(p.get("Power - Max"), "W")
    tol = _tol(sp)
    return (p.get("Package / Case") == slot["pkg"] and not p.get("Type") and vz is not None
            and abs(vz - slot["v"]) < 1e-3 and tol is not None and tol <= 5.0 + 1e-9
            and pw is not None and pw >= slot["pmin"] - 1e-9
            and not re.match(r"^(MMSZ46|1N46|DDZ9[67])", sp["mpn"])
            and "array" not in sp["desc"].lower())


def _fam_rank(sp, slot):
    for i, pat in enumerate(slot["fam"]):
        if re.search(pat, sp["mpn"]):
            return i
    return len(slot["fam"])


def rank(sp, slot):
    tol = _tol(sp)
    return (mfr_rank(sp, PREFERRED), _fam_rank(sp, slot), _auto(sp), 0 if abs(tol - 5.0) < 1e-6 else 1)


def make_row(sp, slot, var):
    p = sp["params"]
    pw = p.get("Power - Max", "").replace(" ", "")
    tol = (p.get("Tolerance") or "").lstrip("±")
    zz = (p.get("Impedance (Max) (Zzt)") or "").replace(" Ohms", "R").replace(" ", "")
    ir = (p.get("Current - Reverse Leakage @ Vr") or "").replace(" ", "")
    val = vcode(slot["v"])
    ds = dk_client.https(sp.get("datasheet")) or ""
    extra = ", ".join(x for x in (f"Zzt {zz}" if zz and zz != "-" else "", f"Ir {ir}" if ir and ir != "-" else "") if x)
    return dict(
        Symbol="Device:D_Zener", Footprint=slot["fp"], Value=val, Package=slot["disp"],
        Description=f"Zener diode {slot['v']:g}V {tol} {pw} {slot['disp']}",
        Keywords=f"diode zener {val} {slot['v']:g}V {slot['disp']} {sp['mpn']}", Tolerance=tol, Rating=pw,
        TC_Dielectric=extra, FP_Filter=slot["flt"], Pinout="1=K 2=A",
        Pinout_Source=f"{ds} (package outline: cathode band = pin 1 = K); Device:D_Zener pin1=K/pin2=A; "
                      f"KiCad {slot['fp']} pad 1 = cathode (silk bar)")
