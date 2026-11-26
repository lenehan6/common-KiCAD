"""Schottky rectifiers, single diode only (no dual/array parts), 0.2..3A, 20..60V.

Slots (current, Vr, package):
  0.2A/30V SOD-323 + SOD-523 (BAT54 class), 0.5A/40V SOD-123 (MBR0540 class),
  1A/20,40,60V SOD-123 and SOD-123F, 1A/40V SMA (SS14), 2A/40V SMA, 3A/40V + 60V SMA.
Vr must equal the slot voltage; Io must be >= slot current and <= 1.5x (2x for 0.2A).
Preferred makers Vishay, Nexperia, then onsemi, Diodes Inc, Taiwan Semiconductor; others fill gaps.
Within a maker the slot's classic family (BAT54 / SS1x / SS3x ...) and non-automotive grades first.

Pinout: Device:D_Schottky pin 1 = K, pin 2 = A; KiCad Diode_SMD:D_* pad 1 = cathode
(silkscreen cathode bar at pad 1). The package cathode band marks pin 1.
"""
import re

import dk_client
from _common import num, mfr_rank

TABLE = "Diodes_Schottky"
QUERIES = [dict(keywords=k) for k in (
    "schottky diode SOD-123", "schottky diode SOD-323", "schottky diode SMA", "Vishay schottky SOD-123",
    "Nexperia schottky SOD-123", "Nexperia schottky SOD-323", "BAT54W", "B5819W", "SS14 SMA", "SS34 SMA", "PMEG")]

PREFERRED = ["Vishay", "Nexperia", "onsemi", "Diodes Inc", "Taiwan Semiconductor", "STMicro", "Rohm", "Toshiba",
             "Panjit", "Comchip", "SMC Diode", "Micro Commercial", "MCC", "Diotec"]

PKG = {  # code: (DigiKey Package / Case, footprint, FP filter, display)
    "SOD323": ("SC-76, SOD-323", "Diode_SMD:D_SOD-323", "D*SOD?323*", "SOD-323"),
    "SOD523": ("SC-79, SOD-523", "Diode_SMD:D_SOD-523", "D*SOD?523*", "SOD-523"),
    "SOD123": ("SOD-123", "Diode_SMD:D_SOD-123", "D*SOD?123*", "SOD-123"),
    "SOD123F": ("SOD-123F", "Diode_SMD:D_SOD-123F", "D*SOD?123*", "SOD-123F"),
    "SMA": ("DO-214AC, SMA", "Diode_SMD:D_SMA", "D*SMA*", "SMA"),
}

# (package code, current A, current label, Vr, family preference regexes)
SLOTS = [
    ("SOD323", 0.2, "0A2", 30, [r"^BAT54WS", r"^BAT54", r"^BAT4[23]"]),
    ("SOD523", 0.2, "0A2", 30, [r"^BAT54", r"^BAT4[23]"]),
    ("SOD123", 0.5, "0A5", 40, [r"^(MBR|NRVB|SS|STPS|B)0540", r"0540"]),
    ("SOD123", 1.0, "1A", 20, [r"^(MBRX?|SS|B|STPS)1[02]0", r"120"]),
    ("SOD123", 1.0, "1A", 40, [r"^1N5819", r"^B5819", r"^(MBR|SS|B|STPS)1[04]0", r"140"]),
    ("SOD123", 1.0, "1A", 60, [r"^(MBR|SS|B)1[06]0", r"160"]),
    ("SOD123F", 1.0, "1A", 20, [r"^PMEG2010", r"^PMEG"]),
    ("SOD123F", 1.0, "1A", 40, [r"^PMEG4010", r"^PMEG"]),
    ("SOD123F", 1.0, "1A", 60, [r"^PMEG6010", r"^PMEG"]),
    ("SMA", 1.0, "1A", 40, [r"^SS14", r"^(MBRA|B)140"]),
    ("SMA", 2.0, "2A", 40, [r"^SS24", r"^(MBRA|B)240"]),
    ("SMA", 3.0, "3A", 40, [r"^SS34", r"^SSA34", r"^B340"]),
    ("SMA", 3.0, "3A", 60, [r"^SS36", r"^SSA36", r"^B360"]),
]


def slots():
    out = []
    for code, amps, alabel, vr, fam in SLOTS:
        pkg, fp, flt, disp = PKG[code]
        out.append(dict(part_id=f"D-SCH-{code}-{alabel}-{vr}V", code=code, amps=amps, alabel=alabel, vr=vr,
                        fam=fam, pkg=pkg, fp=fp, flt=flt, disp=disp))
    return out


def _single(sp):
    p = sp["params"]
    d = (sp["desc"] + " " + (sp["detail"] or "")).lower()
    return not p.get("Diode Configuration") and not p.get("Current - Average Rectified (Io) (per Diode)") \
        and not re.search(r"array|dual|common|series|2 indep", d)


def _auto(sp):
    return (sp["params"].get("Grade") == "Automotive") or bool(re.search(r"(-Q|Q-|-AQ|-AU|HE3|HM3|HG3|^NRV|^SZ|^NSV|Y$)", sp["mpn"]))


def accept(sp, slot):
    p = sp["params"]
    vr = num(p.get("Voltage - DC Reverse (Vr) (Max)"), "V")
    io = num(p.get("Current - Average Rectified (Io)"), "A")
    hi = slot["amps"] * (2.0 if slot["amps"] < 0.3 else 1.5)
    return (p.get("Package / Case") == slot["pkg"] and (p.get("Technology") or "") == "Schottky"
            and vr is not None and abs(vr - slot["vr"]) < 0.01 and io is not None
            and slot["amps"] - 1e-9 <= io < hi - 1e-9 and _single(sp))


def _fam_rank(sp, slot):
    for i, pat in enumerate(slot["fam"]):
        if re.search(pat, sp["mpn"]):
            return i
    return len(slot["fam"])


def rank(sp, slot):
    vf = num(sp["params"].get("Voltage - Forward (Vf) (Max) @ If"), "V") or 9.0
    return (mfr_rank(sp, PREFERRED), _fam_rank(sp, slot), _auto(sp), round(vf, 3))


def _family(sp):
    fam = re.split(r"[-_ ,/]", sp["mpn"])[0]
    if fam.startswith("PMEG"):
        return re.sub(r"X$", "", fam)
    return re.sub(r"(H[EM]3|T[13]G)$", "", fam)


def make_row(sp, slot, var):
    p = sp["params"]
    vr = p.get("Voltage - DC Reverse (Vr) (Max)", "").replace(" ", "")
    io = p.get("Current - Average Rectified (Io)", "").replace(" ", "")
    vf = (p.get("Voltage - Forward (Vf) (Max) @ If") or "").replace(" ", "")
    ir = (p.get("Current - Reverse Leakage @ Vr") or "").replace(" ", "")
    fam = _family(sp)
    ds = dk_client.https(sp.get("datasheet")) or ""
    return dict(
        Symbol="Device:D_Schottky", Footprint=slot["fp"], Value=fam, Package=slot["disp"],
        Description=f"Schottky diode {vr} {io} {slot['disp']}, Vf {vf}",
        Keywords=f"diode schottky rectifier {fam} {slot['disp']} {vr} {io}", Rating=f"{vr} {io}",
        TC_Dielectric=f"Vf {vf}" + (f", Ir {ir}" if ir and ir != "-" else ""), FP_Filter=slot["flt"],
        Pinout="1=K 2=A",
        Pinout_Source=f"{ds} (package outline: cathode band = pin 1 = K); Device:D_Schottky pin1=K/pin2=A; "
                      f"KiCad {slot['fp']} pad 1 = cathode (silk bar)")
