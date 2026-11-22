"""SMD tactile switches (SPST-NO). One slot per size/height for which KiCad's Button_Switch_SMD
library has a footprint drawn for that exact maker series; a row is only added when the MPN
belongs to that series (MPN regex per slot). Preference order Würth WS-TASV, C&K, E-Switch,
Omron - but KiCad has no WS-TASV footprint, so no Würth slot exists. C&K PTS526 (5.2x5.2)
is likewise skipped: no KiCad footprint.

4-pad footprints are numbered 1,1,2,2 by KiCad (same-number pads = the internally connected
terminal pair), so they work with the 2-pin Switch:SW_Push symbol directly."""
import re

TABLE = "Switches_Tactile"
QUERIES = [dict(keywords=k) for k in (
    "tactile switch SMD 6x6", "tactile switch SMD 4x4", "tactile switch SMD 3x6", "Wurth tactile switch SMD",
    "Wurth WS-TASV", "C&K tactile switch SMD", "E-Switch tactile switch SMD", "Omron B3FS",
    "C&K PTS526", "C&K PTS810", "C&K PTS645")]

FP = "Button_Switch_SMD:"
# part_id, size, height, MPN regex, footprint, pads, preferred MPN order (operating-force codes)
SLOTS = [
    ("SW-TACT-6x6-SMD-H4.3", "6x6mm", "4.3mm", r"^PTS645S([LMHK])43SMTR92 LFS$", "SW_SPST_PTS645Sx43SMTR92", 4, "MKHL"),
    ("SW-TACT-6x6-SMD-H3.1", "6x6mm", "3.1mm", r"^B3FS-100([025])P$", "SW_SPST_Omron_B3FS-100xP", 4, "205"),
    ("SW-TACT-6x6-SMD-H7.3", "6x6mm", "7.3mm", r"^B3FS-105([025])P$", "SW_SPST_Omron_B3FS-105xP", 4, "205"),
    ("SW-TACT-6x3.5-SMD-H2.5", "6x3.5mm", "2.5mm", r"^PTS636S([LMKP])25SMTR LFS$",
     "SW_Tactile_SPST_NO_Straight_CK_PTS636Sx25SMTRLFS", 2, "MKLP"),
    ("SW-TACT-4.5x4.5-SMD-H3.8", "4.5x4.5mm", "3.8mm", r"^PTS647S([NMK])38SMTR2N? LFS$", "SW_SPST_PTS647_Sx38", 4, "MKN"),
    ("SW-TACT-4.5x4.5-SMD-H5.0", "4.5x4.5mm", "5.0mm", r"^PTS647S([NMK])50SMTR2N? LFS$", "SW_SPST_PTS647_Sx50", 4, "MKN"),
    ("SW-TACT-4.2x3.2-SMD-H2.5", "4.2x3.2mm", "2.5mm", r"^PTS810SJ([MKGS])250SMTR LFS$", "SW_SPST_PTS810", 4, "MKGS"),
    ("SW-TACT-4.9x4.9-SMD-H1.5", "4.9x4.9mm", "1.5mm", r"^TL3342F(160|260|450)QG(/TR)?$", "SW_SPST_TL3342", 4, None),
    ("SW-TACT-4.6x2.8-SMD-H1.9", "4.6x2.8mm", "1.9mm", r"^KMR2([1-4])1NG LFS$", "SW_Push_1P1T_NO_CK_KMR2", 4, "2134"),
    ("SW-TACT-3x2-SMD-H0.6", "3.0x2.0mm", "0.6mm", r"^KXT 3([1-4])1 LHS$", "SW_SPST_CK_KXT3", 2, "2314"),
]
FORCE_ORDER_TL3342 = ["160", "260", "450"]


def slots():
    return [dict(part_id=pid, size=s, h=h, rx=rx, fp=fp, pads=pads, order=o) for pid, s, h, rx, fp, pads, o in SLOTS]


def accept(sp, slot):
    return bool(re.match(slot["rx"], sp["mpn"])) and "Surface Mount" in (sp["params"].get("Mounting Type") or "") \
        and (sp["params"].get("Circuit") or "SPST-NO") == "SPST-NO"


def rank(sp, slot):
    code = re.match(slot["rx"], sp["mpn"]).group(1)
    order = slot["order"] or FORCE_ORDER_TL3342
    return (list(order).index(code) if code in order else 9,)


def make_row(sp, slot, var):
    p = sp["params"]
    force = p.get("Operating Force", "")
    rating = p.get("Contact Rating @ Voltage", "")
    if slot["pads"] == 4:
        pin, src = "1,1=A 2,2=B (4 pads; same-number pads internally connected)", \
            "KiCad footprint " + slot["fp"] + " pad numbering 1,1,2,2 (drawn for this series)"
    else:
        pin, src = "1=A 2=B (2 pads)", "KiCad footprint " + slot["fp"] + " (2 pads, drawn for this series)"
    return dict(
        Symbol="Switch:SW_Push", Footprint=FP + slot["fp"], Value=f"SW_Push {force}".strip(),
        Package=f"SMD {slot['size']} H{slot['h']}",
        Description=f"Tactile switch SPST-NO SMD {slot['size']} H{slot['h']} {force} {sp['series'] or ''}".strip(),
        Keywords=f"tactile switch tact push button SMD {slot['size']} {sp['series'] or ''}".strip(),
        Rating=rating, TC_Dielectric=f"Operating force {force}" if force else None,
        FP_Filter=slot["fp"] + "*", Pinout=pin, Pinout_Source=src + "; datasheet " + (sp.get("datasheet") or ""))
