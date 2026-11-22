"""ESD protection: single-line low-capacitance ESD diodes plus a few multi-line arrays.

Single-line slots: working (standoff) voltage 3.3V (3.3..3.6V) and 5V (5.0..5.5V), packages
SOD-323, SOD-523 and 0402/DFN1006-2 (DigiKey "0402 (1006 Metric)" or "SOD-882"),
unidirectional and bidirectional, one channel, C <= 50pF (lower capacitance preferred).
Preferred makers Nexperia, Littelfuse, ST, TI, onsemi; others fill gaps.

Symbols / pinout:
* bidirectional: Device:D_TVS (KiCad bidirectional TVS symbol, pins A1/A2) -> "1=A1 2=A2", symmetric.
* unidirectional: Device:D_Zener (pin 1 = K, pin 2 = A); Device:D_TVS has no polarity, so it is not
  used for unidirectional parts. The cathode (signal/IO side) is pin 1 = band / pad 1.
* footprints: Diode_SMD:D_SOD-323 / D_SOD-523 / D_SOD-882 (pad 1 = cathode); TI X1SON-2 (DPY)
  parts use Package_SON:Texas_DPY0002A_0.6x1mm_P0.65mm (TI pin 1 = IO = cathode, pin 2 = GND).
* arrays use the exact-MPN KiCad stock symbol from Power_Protection with its default footprint;
  stock symbol pin numbers were checked against the datasheet pin tables (see Pinout_Source).
"""
import re

import dk_client
from _common import num, mfr_rank

TABLE = "ESD_Protection"
QUERIES = [dict(keywords=k) for k in (
    "ESD protection diode SOD-323", "ESD protection diode SOD-523", "ESD suppressor 0402", "PESD5V0",
    "PESD3V3", "USBLC6-2", "PRTR5V0U2X", "TPD2E", "TPD4E", "Littelfuse ESD SOD-323")]

PREFERRED = ["Nexperia", "Littelfuse", "STMicro", "Texas Instruments", "onsemi", "Diodes Inc", "Vishay",
             "Rohm", "Toshiba", "Infineon", "Semtech", "Bourns"]

SINGLE_PKG = {  # code: (DigiKey Package / Case values, footprint, FP filter, display)
    "SOD323": (("SC-76, SOD-323",), "Diode_SMD:D_SOD-323", "D*SOD?323*", "SOD-323"),
    "SOD523": (("SC-79, SOD-523",), "Diode_SMD:D_SOD-523", "D*SOD?523*", "SOD-523"),
    "0402": (("0402 (1006 Metric)", "SOD-882"), "Diode_SMD:D_SOD-882", "D*SOD?882* *DPY0002A*", "0402/DFN1006-2"),
}
VOLTS = [("3V3", 3.3, 3.6), ("5V", 5.0, 5.5)]
TI_DPY_FP = "Package_SON:Texas_DPY0002A_0.6x1mm_P0.65mm"

ST, NXP, TI = "STMicroelectronics", "Nexperia", "Texas Instruments"
ARRAYS = [  # part_id, MPN regex, maker substring, symbol, footprint, package, pinout, datasheet, note
    ("ESD-SOT23-6-USBLC6-2", r"^USBLC6-2SC6Y?$", "STMicro", "Power_Protection:USBLC6-2SC6",
     "Package_TO_SOT_SMD:SOT-23-6", "SOT-23-6", "1=I/O1 2=GND 3=I/O2 4=I/O2 5=VBUS 6=I/O1",
     "https://www.st.com/resource/en/datasheet/usblc6-2.pdf",
     "2-line USB 2.0 ESD array, Vbus clamp", "USBLC6-2SC6Y = AEC-Q101 grade, same die/package/pinout"),
    ("ESD-SOT143-PRTR5V0U2X", r"^PRTR5V0U2X", "Nexperia", "Power_Protection:PRTR5V0U2X",
     "Package_TO_SOT_SMD:SOT-143", "SOT-143", "1=GND 2=I/O1 3=I/O2 4=VCC",
     "https://assets.nexperia.com/documents/data-sheet/PRTR5V0U2X.pdf",
     "2-line USB ESD rail-to-rail array", ""),
    ("ESD-DRT3-TPD2EUSB30A", r"^TPD2EUSB30ADRT[RT]$", "Texas", "Power_Protection:TPD2EUSB30A",
     "Package_TO_SOT_SMD:Texas_DRT-3", "DRT-3 (SOT-1123 like)", "1=D+ 2=D- 3=GND",
     "https://www.ti.com/lit/ds/symlink/tpd2eusb30a.pdf",
     "2-ch USB 3.0 ESD, 0.7pF", ""),
    ("ESD-USON10-TPD4E05U06", r"^TPD4E05U06Q?DQAR(Q1)?$", "Texas", "Power_Protection:TPD4E05U06DQA",
     "Package_SON:USON-10_2.5x1.0mm_P0.5mm", "USON-10", "1=D1+ 2=D1- 3=GND 4=D2+ 5=D2- 6=NC 7=NC 8=GND 9=NC 10=NC",
     "https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf",
     "4-ch high-speed ESD, 0.5pF, flow-through", "TPD4E05U06QDQARQ1 = AEC-Q100 grade, same DQA pinout"),
]


def slots():
    out = []
    for code, (pkgs, fp, flt, disp) in SINGLE_PKG.items():
        for vl, vmin, vmax in VOLTS:
            for bi in (False, True):
                out.append(dict(part_id=f"ESD-{code}-{vl}-1L-{'BI' if bi else 'UNI'}", kind="single", code=code,
                                pkgs=pkgs, fp=fp, flt=flt, disp=disp, vl=vl, vmin=vmin, vmax=vmax, bi=bi))
    for pid, pat, mk, sym, fp, pkg, pin, ds, desc, note in ARRAYS:
        out.append(dict(part_id=pid, kind="array", pat=pat, mk=mk, sym=sym, fp=fp, disp=pkg, pin=pin, ds=ds,
                        desc=desc, note=note))
    return out


def _cap(sp):
    c = sp["params"].get("Capacitance @ Frequency") or ""
    return num(c, "F")


def _auto(sp):
    return (sp["params"].get("Grade") == "Automotive") or bool(re.search(r"(-Q|Q1|-AU|Y$|^SZ)", sp["mpn"]))


def accept(sp, slot):
    p = sp["params"]
    if slot["kind"] == "array":
        return slot["mk"].lower() in sp["mfr"].lower() and bool(re.match(slot["pat"], sp["mpn"]))
    v = num(p.get("Voltage - Reverse Standoff (Typ)"), "V")
    uni, bid = p.get("Unidirectional Channels"), p.get("Bidirectional Channels")
    dir_ok = (bid == "1" and not uni) if slot["bi"] else (uni == "1" and not bid)
    c = _cap(sp)
    return (p.get("Package / Case") in slot["pkgs"] and v is not None
            and slot["vmin"] - 1e-6 <= v <= slot["vmax"] + 1e-6 and dir_ok
            and (c is None or c <= 50e-12) and (p.get("Number of Circuits") in (None, "1")))


def rank(sp, slot):
    if slot["kind"] == "array":
        return (_moq_penalty(sp), _auto(sp))
    c = _cap(sp)
    return (mfr_rank(sp, PREFERRED), _moq_penalty(sp), c if c is not None else 1.0, _auto(sp))


def _moq_penalty(sp):
    """Bulk-only marketplace listings with a large MOQ rank behind cut-tape parts of the same maker."""
    v = dk_client.orderable_variation(sp)
    return bool(v and "Cut Tape" not in v["pkg"] and (v.get("moq") or 1) > 10)


def _base(mpn):
    return re.split(r"[,/ ]", mpn)[0]


def make_row(sp, slot, var):
    p = sp["params"]
    ds = dk_client.https(sp.get("datasheet")) or slot.get("ds", "")
    vrwm = (p.get("Voltage - Reverse Standoff (Typ)") or "").replace(" (Max)", "").replace(" ", "")
    vc = (p.get("Voltage - Clamping (Max) @ Ipp") or "").replace(" ", "")
    cap = (p.get("Capacitance @ Frequency") or "").replace(" ", "")
    capt = cap.split("@")[0] if cap and cap != "-" else ""
    extra = ", ".join(x for x in (f"C {capt}" if capt else "", f"Vc {vc}" if vc and vc != "-" else "") if x)
    if slot["kind"] == "array":
        note = f" ({slot['note']})" if slot["note"] and _auto(sp) else ""
        val = slot["sym"].split(":")[1]
        return dict(
            Symbol=slot["sym"], Footprint=slot["fp"], Value=val, Package=slot["disp"],
            Description=f"ESD array {slot['desc']}, {vrwm} {slot['disp']}{note}",
            Keywords=f"ESD TVS protection array USB {val} {sp['mpn']}", Rating=f"{vrwm}",
            TC_Dielectric=extra, FP_Filter=slot["fp"].split(":")[1] + "*", Pinout=slot["pin"],
            Pinout_Source=f"KiCad stock symbol {slot['sym']} (pin numbers match datasheet pin table, default fp "
                          f"{slot['fp']}); {slot['ds']}")
    fp = slot["fp"]
    if sp["mfr"] == TI and "DPY" in sp["mpn"]:
        fp = TI_DPY_FP
    d = "bidirectional" if slot["bi"] else "unidirectional"
    if slot["bi"]:
        sym, pin = "Device:D_TVS", "1=A1 2=A2"
        src = f"Bidirectional, symmetric (no polarity): Device:D_TVS pins A1/A2; {ds}"
    else:
        sym, pin = "Device:D_Zener", "1=K 2=A"
        src = (f"{ds} (pin 1 = cathode = I/O side, band/pin-1 mark); Device:D_Zener pin1=K/pin2=A "
               f"(Device:D_TVS is unpolarised); KiCad {fp} pad 1 = cathode/I-O")
    return dict(
        Symbol=sym, Footprint=fp, Value=_base(sp["mpn"]), Package=slot["disp"],
        Description=f"ESD protection diode {d} {vrwm} 1-line {slot['disp']}" + (f", {extra}" if extra else ""),
        Keywords=f"ESD TVS protection {d} {slot['vl']} {slot['disp']} {sp['mpn']}", Rating=vrwm,
        TC_Dielectric=extra, FP_Filter=slot["flt"], Pinout=pin, Pinout_Source=src)
