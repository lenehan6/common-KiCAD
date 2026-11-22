"""Shrouded (4-wall box) IDC headers, 2.54mm, vertical THT, DIN 41651 / IEC 60603-13 style.
One slot per pin count with a KiCad Connector_IDC:IDC-Header_2xNN_P2.54mm_Vertical footprint
(2x03..2x13, 2x15, 2x17, 2x20). KiCad has no 1.27mm IDC box-header footprints, so none here.
Preferred Würth WR-BHD, then Amphenol, TE, On Shore; latch/ejector types and 2-wall
(friction-lock) headers are excluded. SMD box headers are not used (KiCad's generic
IDC-Header_*_SMD land pattern is not verified against any stocked part).

Note: Würth WR-BHD THT box headers (6120xx21621) are sold only in "Tray" at DigiKey,
which the engine does not treat as orderable."""
import re
from _common import mfr_rank

TABLE = "Headers_IDC_Shrouded"
QUERIES = [dict(keywords=k) for k in (
    "Wurth WR-BHD", "Wurth box header 2.54mm", "shrouded header 2.54mm", "box header 2.54mm",
    "Amphenol box header 2.54mm", "box header 1.27mm")]
PREFERRED = ["Würth", "Amphenol", "TE Connectivity", "On Shore", "3M", "Molex", "Samtec"]
KICAD_IDC = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 17, 20]


def slots():
    return [dict(part_id=f"IDC-2.54-2x{n:02d}", cols=n) for n in KICAD_IDC]


def accept(sp, slot):
    p = sp["params"]
    try:
        rows, pos = int(p.get("Number of Rows")), int(p.get("Number of Positions"))
    except (TypeError, ValueError):
        return False
    text = f"{sp['desc']} {sp['detail']}".upper()
    return (p.get("Contact Type") == "Male Pin" and "2.54" in (p.get("Pitch - Mating") or "")
            and "2.54" in (p.get("Row Spacing - Mating") or "")
            and rows == 2 and pos == 2 * slot["cols"] and p.get("Number of Positions Loaded") == "All"
            and p.get("Shrouding") == "Shrouded - 4 Wall" and p.get("Mounting Type") == "Through Hole"
            and (p.get("Fastening Type") or "Push-Pull") == "Push-Pull"
            and p.get("Termination", "Solder") == "Solder"
            and not ("R/A" in text or "RIGHT ANGLE" in text or "LATCH" in text or "EJECT" in text))


def rank(sp, slot):
    gold = 0 if "Gold" in (sp["params"].get("Contact Finish - Mating") or "") else 1
    return (mfr_rank(sp, PREFERRED), gold)


def make_row(sp, slot, var):
    p = sp["params"]
    n = slot["cols"]
    tag = f"2x{n:02d}"
    cur = p.get("Current Rating (Amps)")
    cur = "" if cur in (None, "-") else cur
    return dict(
        Symbol=f"Connector_Generic:Conn_02x{n:02d}_Odd_Even",
        Footprint=f"Connector_IDC:IDC-Header_{tag}_P2.54mm_Vertical",
        Value=f"IDC {tag} P2.54mm", Package=f"THT box header {tag} 2.54mm",
        Description=f"Shrouded IDC box header {tag} ({2 * n} pins) 2.54mm male vertical THT, polarized",
        Keywords=f"IDC box header shrouded connector 2.54mm {tag} {2 * n}pin vertical THT ribbon",
        Rating=cur, FP_Filter=f"IDC*Header*{tag}*P2.54mm*", Pinout="Odd_Even (1,3,5.. in row A; 2 opposite 1)",
        Pinout_Source=("DIN 41651 / IEC 60603-13 numbering (pin 2 across from pin 1) = KiCad IDC-Header footprint "
                       "(pin 1 square pad, polarization key notch drawn on the long wall at the pin-1 row) + "
                       "Connector_Generic Odd_Even symbol; check key side vs. cable on first layout; mfr datasheet "
                       + (sp.get("datasheet") or "")))
