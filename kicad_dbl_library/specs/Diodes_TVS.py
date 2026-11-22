"""TVS diodes: SMAJ (SMA, 400W) and SMBJ (SMB, 600W), unidirectional (..A) and
bidirectional (..CA), 5% breakdown tolerance ("A" suffix) only.

Standoff voltages 3.3, 5.0, 6.0, 12, 15, 18, 24, 26, 33, 36, 48, 58V. The MPN must be the
standard SMxJ<V>[C]A designation (maker suffixes allowed; see ALT_MPN for the one exception) and DigiKey's standoff voltage,
peak pulse power and uni/bi channel count must agree.
Preferred makers Littelfuse, then Vishay, Bourns, onsemi; others fill gaps. Base
(non-automotive, non-HE3) part numbers first.

Symbols / pinout:
* Device:D_TVS is KiCad's BIDIRECTIONAL TVS symbol (pins A1/A2, no polarity) -> used for ..CA
  parts only; Pinout "1=A1 2=A2" (symmetric).
* Unidirectional SMAJ: KiCad stock symbol Diode:SMAJ<V>A (pin 1 is the cathode-bar side of
  the graphic, default footprint Diode_SMD:D_SMA) -> Pinout "1=K 2=A".
* Unidirectional SMBJ: no generic unidirectional TVS symbol exists in KiCad, so Device:D_Zener
  (pin 1 = K, pin 2 = A) is used.
KiCad Diode_SMD:D_SMA / D_SMB pad 1 = cathode (silk bar); package cathode band = pin 1.
"""
import re

import dk_client
from _common import num, mfr_rank

TABLE = "Diodes_TVS"
QUERIES = [dict(keywords=k) for k in (
    "Littelfuse SMAJ", "Littelfuse SMBJ", "SMAJ CA", "SMBJ CA", "Vishay SMAJ", "Vishay SMBJ",
    "TVS diode SMA unidirectional", "TVS diode SMB bidirectional")]
# targeted gap-fill queries (tools/harvest/requests_Diodes_TVS.json)
QUERIES += [dict(keywords=k) for k in (
    'SMAJ3.3A',
    'SMAJ3.3CA',
    'SMBJ3.3A',
    'SMBJ3.3CA',
    'Bourns SMAJ',
    'Bourns SMBJ',
)]

PREFERRED = ["Littelfuse", "Vishay", "Bourns", "onsemi", "STMicro", "Taiwan Semiconductor", "Diodes Inc",
             "SMC Diode", "Micro Commercial", "MCC"]

VOLTS = ["3.3", "5.0", "6.0", "12", "15", "18", "24", "26", "33", "36", "48", "58"]
SERIES = {  # code: (prefix, DigiKey Package / Case, footprint, FP filter, display, peak W)
    "SMA": ("SMAJ", "DO-214AC, SMA", "Diode_SMD:D_SMA", "D*SMA*", "SMA", 400),
    "SMB": ("SMBJ", "DO-214AA, SMB", "Diode_SMD:D_SMB", "D*SMB*", "SMB", 600),
}


def slots():
    out = []
    for code, (pre, pkg, fp, flt, disp, w) in SERIES.items():
        for v in VOLTS:
            for bi in (False, True):
                vid = v.replace(".", "V") if "." in v else v + "V"  # 3V3, 5V0, 15V
                out.append(dict(part_id=f"TVS-{code}-{vid}-{'BI' if bi else 'UNI'}",
                                code=code, pre=pre, pkg=pkg, fp=fp, flt=flt, disp=disp, w=w, v=float(v), vs=v, bi=bi,
                                value=f"{pre}{v}{'C' if bi else ''}A"))
    return out


def _auto(sp):
    return (sp["params"].get("Grade") == "Automotive") or bool(re.search(r"(HE3|HM3|-Q|Q1|-AU|-HR)", sp["mpn"]))


# Exception: no SMBJ3.3A (5% "A" grade) is stocked; Vishay's low-voltage TRANSZORB SMBJ3V3
# (3.3V standoff, 600W, unidirectional, DO-214AA) fills the SMB 3.3V uni slot under its own name.
ALT_MPN = {"TVS-SMB-3V3-UNI": (r"^SMBJ3V3-[EM]3/", "Vishay", "SMBJ3V3")}


def _alt(sp, slot):
    a = ALT_MPN.get(slot["part_id"])
    return bool(a and re.match(a[0], sp["mpn"]) and a[1].lower() in sp["mfr"].lower())


def accept(sp, slot):
    p = sp["params"]
    if not (re.match(rf"^{slot['value'].replace('.', r'[.]')}(?![0-9A-Z])", sp["mpn"]) or _alt(sp, slot)):
        return False
    vrwm = num(p.get("Voltage - Reverse Standoff (Typ)"), "V")
    w = num(p.get("Power - Peak Pulse"), "W")
    uni, bid = p.get("Unidirectional Channels"), p.get("Bidirectional Channels")
    dir_ok = (bid == "1" and not uni) if slot["bi"] else (uni == "1" and not bid)
    return (p.get("Package / Case") == slot["pkg"] and vrwm is not None and abs(vrwm - slot["v"]) < 1e-3
            and w is not None and abs(w - slot["w"]) < 1 and dir_ok)


def rank(sp, slot):
    return (mfr_rank(sp, PREFERRED), _auto(sp), sp["mpn"] != slot["value"])


def make_row(sp, slot, var):
    p = sp["params"]
    vbr = (p.get("Voltage - Breakdown (Min)") or "").replace(" ", "")
    vc = (p.get("Voltage - Clamping (Max) @ Ipp") or "").replace(" ", "")
    ipp = (p.get("Current - Peak Pulse (10/1000µs)") or "").replace(" ", "")
    v = slot["vs"].replace(".0", "") + "V"
    d = "bidirectional" if slot["bi"] else "unidirectional"
    ds = dk_client.https(sp.get("datasheet")) or ""
    fpnote = f"KiCad {slot['fp']} pad 1 = cathode (silk bar)"
    if slot["bi"]:
        sym, pin = "Device:D_TVS", "1=A1 2=A2"
        src = f"Bidirectional, symmetric (no polarity): Device:D_TVS pins A1/A2; {ds}"
    elif slot["code"] == "SMA":
        sym, pin = f"Diode:{slot['value']}", "1=K 2=A"
        src = (f"KiCad stock symbol Diode:{slot['value']} (pin 1 on cathode-bar side, default fp Diode_SMD:D_SMA); "
               f"{ds} (cathode band = pin 1 = K); {fpnote}")
    else:
        sym, pin = "Device:D_Zener", "1=K 2=A"
        src = (f"{ds} (cathode band = pin 1 = K); Device:D_Zener pin1=K/pin2=A (no generic unidirectional TVS "
               f"symbol in KiCad); {fpnote}")
    value, tol = slot["value"], "5%"
    if _alt(sp, slot):
        value, tol = ALT_MPN[slot["part_id"]][2], ""   # Vishay low-voltage part: no "A" 5% Vbr grade
    return dict(
        Symbol=sym, Footprint=slot["fp"], Value=value, Package=slot["disp"],
        Description=f"TVS diode {d} {v} standoff {slot['w']}W {slot['disp']}, Vbr {vbr} min, Vc {vc}",
        Keywords=f"TVS transient suppressor {d} {value} {slot['disp']} {v}",
        Tolerance=tol, Rating=f"{slot['w']}W {v}", TC_Dielectric=f"Vc {vc}" + (f" @ {ipp}" if ipp else ""),
        FP_Filter=slot["flt"], Pinout=pin, Pinout_Source=src)
