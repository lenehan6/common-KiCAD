"""Small-signal BJTs in SOT-23 (3-pin), one row per base part / hFE group.

Symbol = stock KiCad symbol named after the base part (all extend Q_NPN_BEC / Q_PNP_BEC ->
pins 1=B 2=E 3=C), else Transistor_BJT:Q_NPN_BEC / Q_PNP_BEC. Generic letter-pin symbols
are never used.

Pinout policy: Pinout "1=B 2=E 3=C". Pinout_Source is the MPN datasheet page actually read
(VERIFIED); rows whose datasheet could not be read are kept with Pinout_Source starting
"UNVERIFIED". Set REQUIRE_VERIFIED = True to drop them.
Maker preference: Nexperia, onsemi, Taiwan Semi, Bourns, Diodes; <1000 pcs ranks last.
"""
import re
from _common import mfr_rank
from dk_client import https

TABLE = "BJTs_SmallSignal"
QUERIES = [dict(keywords=k) for k in (
    "MMBT3904", "MMBT3906", "BC847", "BC857", "BC817", "BC807", "MMBT2222A", "PMBT3904", "PMBT3906",
    "PMBT2222A", "NPN transistor SOT-23", "PNP transistor SOT-23", "Nexperia transistor SOT-23",
    "Taiwan Semiconductor transistor SOT-23")]
PREFERRED = ["Nexperia", "onsemi", "Taiwan", "Bourns", "Diodes"]
REQUIRE_VERIFIED = False
FOOTPRINT = "Package_TO_SOT_SMD:SOT-23"
PINOUT = "1=B 2=E 3=C"
VERIFIED = {}  # MPN prefix -> "datasheet URL + page/figure" once read

# (part_id, value, symbol, type, MPN base)
_S = [
    ("Q-NPN-MMBT3904-SOT23", "MMBT3904", "Transistor_BJT:MMBT3904", "NPN", "MMBT3904"),
    ("Q-NPN-BC847B-SOT23", "BC847B", "Transistor_BJT:BC847", "NPN", "BC847B"),
    ("Q-NPN-BC847C-SOT23", "BC847C", "Transistor_BJT:BC847", "NPN", "BC847C"),
    ("Q-NPN-BC817-25-SOT23", "BC817-25", "Transistor_BJT:BC817", "NPN", "BC817-25"),
    ("Q-NPN-BC817-40-SOT23", "BC817-40", "Transistor_BJT:BC817", "NPN", "BC817-40"),
    ("Q-NPN-MMBT2222A-SOT23", "MMBT2222A", "Transistor_BJT:MMBT2222A", "NPN", "MMBT2222A"),
    ("Q-NPN-PMBT2222A-SOT23", "PMBT2222A", "Transistor_BJT:PMBT2222A", "NPN", "PMBT2222A"),
    ("Q-PNP-MMBT3906-SOT23", "MMBT3906", "Transistor_BJT:MMBT3906", "PNP", "MMBT3906"),
    ("Q-PNP-BC857B-SOT23", "BC857B", "Transistor_BJT:BC857", "PNP", "BC857B"),
    ("Q-PNP-BC807-25-SOT23", "BC807-25", "Transistor_BJT:BC807", "PNP", "BC807-25"),
    ("Q-PNP-BC807-40-SOT23", "BC807-40", "Transistor_BJT:BC807", "PNP", "BC807-40"),
    ("Q-PNP-MMBT2907A-SOT23", "MMBT2907A", "Transistor_BJT:Q_PNP_BEC", "PNP", "MMBT2907A"),
]
# Ordering suffixes that keep the plain SOT-23 part (H = AEC-Q101 variant of the same die/package).
_SUFFIX = r"(,2[13]5|LT[13][GH]|-7-F(-W)?|-13-F(-W)?|-7|VL|-QR|-QVL|Q-7-F|Q-13-F| RFG|H RFG|HR|H-QR|)"


def _verified(sp):
    for k, src in VERIFIED.items():
        if sp["mpn"].upper().startswith(k):
            return src
    return None


def slots():
    return [dict(part_id=p, value=v, symbol=s, typ=t, rx=re.compile("^" + re.escape(b) + _SUFFIX + "$", re.I))
            for p, v, s, t, b in _S]


def accept(sp, slot):
    p = sp["params"]
    if not slot["rx"].match(sp["mpn"]):
        return False
    if not (p.get("Package / Case") or "").startswith("TO-236"):
        return False
    if (p.get("Transistor Type") or "") != slot["typ"]:
        return False
    return bool(_verified(sp)) or not REQUIRE_VERIFIED


def _qty(sp):
    return max([v.get("qty") or 0 for v in sp["variations"] if "Cut Tape" in v["pkg"] or "Bulk" in v["pkg"]] or [0])


def rank(sp, slot):
    return (_verified(sp) is None, _qty(sp) < 1000, mfr_rank(sp, PREFERRED),
            (sp["params"].get("Grade") or "-") == "Automotive", not sp.get("datasheet"))


def make_row(sp, slot, var):
    p = sp["params"]
    vce = (p.get("Voltage - Collector Emitter Breakdown (Max)") or "").replace(" ", "")
    ic = (p.get("Current - Collector (Ic) (Max)") or "").replace(" ", "")
    if slot["typ"] == "PNP":
        vce, ic = ("-" + x if x and not x.startswith("-") else x for x in (vce, ic))
    hfe = p.get("DC Current Gain (hFE) (Min) @ Ic, Vce") or ""
    m = re.match(r"(\d+)\s*@\s*(.*)", hfe)
    hfe_s = f"hFE min {m.group(1)} @ {m.group(2)}" if m else hfe
    ft = p.get("Frequency - Transition")
    tc = hfe_s + (f", fT {ft}" if ft and ft != "-" else "")
    src = _verified(sp) or ("UNVERIFIED (MPN datasheet not readable from build env: "
                            f"{https(sp.get('datasheet')) or 'n/a'}); pins per KiCad symbol {slot['symbol']} = {PINOUT}")
    return dict(Symbol=slot["symbol"], Footprint=FOOTPRINT, Value=slot["value"], Package="SOT-23",
                Description=f"{slot['typ']} BJT {vce} {ic} {hfe_s} SOT-23 {slot['value']}",
                Keywords=f"BJT transistor {slot['typ']} SOT-23 {slot['value']}",
                Rating=f"{vce} {ic}", TC_Dielectric=tc, FP_Filter="SOT?23*", Pinout=PINOUT, Pinout_Source=src)
