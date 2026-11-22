"""Small-signal / logic-level MOSFETs in SOT-23 (3-pin).

One row per base part. Symbol = the stock KiCad symbol named after the base part where it
exists (all of them extend Q_NMOS_GSD / Q_PMOS_GSD / TP0610T -> pins 1=G 2=S 3=D), else the
generic Q_NMOS_GSD / Q_PMOS_GSD. The generic Device:Q_NMOS/Q_PMOS (letter pins) are never used.

Pinout policy: every row has Pinout "1=G 2=S 3=D". Pinout_Source is the MPN datasheet page
that was actually read (VERIFIED below). Rows whose datasheet could not be read in the build
environment are kept but their Pinout_Source starts with "UNVERIFIED"; set
REQUIRE_VERIFIED = True to drop them (their slots then become gaps).
Maker preference: Nexperia, onsemi, Diodes, Vishay, Taiwan Semi, AOS; parts with
<1000 pcs on DigiKey Cut Tape rank after well-stocked ones.
"""
import re
from _common import mfr_rank
from dk_client import https

TABLE = "MOSFETs_SmallSignal"
QUERIES = [dict(keywords=k) for k in (
    "2N7002", "2N7002K", "BSS138", "BSS84", "BSS123", "AO3400A", "AO3401A", "DMG2302U", "DMG2301L",
    "SI2302", "SI2301", "PMV", "N-channel MOSFET SOT-23", "P-channel MOSFET SOT-23",
    "Nexperia MOSFET SOT-23", "Vishay MOSFET SOT-23", "onsemi MOSFET SOT-23")]
PREFERRED = ["Nexperia", "onsemi", "Diodes", "Vishay", "Taiwan", "Alpha"]
REQUIRE_VERIFIED = False
FOOTPRINT = "Package_TO_SOT_SMD:SOT-23"
PINOUT = "1=G 2=S 3=D"

# Datasheets read and checked (pin diagram matches symbol pins 1=G 2=S 3=D).
_VISHAY_P1 = " p.1 'SOT-23 (TO-236) Top View' pin diagram: 1=G 2=S 3=D"
VERIFIED = {
    "SI2302CDS": "https://www.vishay.com/docs/68645/si2302cds.pdf" + _VISHAY_P1,
    "SI2302DDS": "https://www.vishay.com/docs/63653/si2302dds.pdf" + _VISHAY_P1,
    "SI2301HDS": "https://www.vishay.com/docs/61626/si2301hds.pdf" + _VISHAY_P1,
    "SI2366DS": "https://www.vishay.com/docs/67509/si2366ds.pdf" + _VISHAY_P1,
    "SI2347DS": "https://www.vishay.com/docs/62827/si2347ds.pdf p.1 '(SOT-23) Top View' pin diagram: G 1, S 2, D 3",
}

# (part_id, value, symbol, channel, MPN regex)
_S = [
    ("Q-N-2N7002-SOT23", "2N7002", "Transistor_FET:2N7002", "N", r"2N7002(LT[13]G|-7-F(-W)?|,215|)"),
    ("Q-N-2N7002K-SOT23", "2N7002K", "Transistor_FET:2N7002K", "N", r"2N7002K(T[17]G|-7(-W)?|)"),
    ("Q-N-BSS138-SOT23", "BSS138", "Transistor_FET:BSS138", "N", r"BSS138(LT[13]G|-7-F|-13-F(-W)?|-G| RFG|)"),
    ("Q-N-BSS123-SOT23", "BSS123", "Transistor_FET:BSS123", "N", r"BSS123(LT[13]G|L|-7-F| RFG|)"),
    ("Q-N-AO3400A-SOT23", "AO3400A", "Transistor_FET:AO3400A", "N", r"AO3400A"),
    ("Q-N-SI2366DS-SOT23", "SI2366DS", "Transistor_FET:Q_NMOS_GSD", "N", r"SI2366DS-T1-[BG]?E3"),
    ("Q-N-SI2302-SOT23", "SI2302CDS", "Transistor_FET:Q_NMOS_GSD", "N", r"SI2302[CD]DS-T1-[BG]?E3"),
    ("Q-P-BSS84-SOT23", "BSS84", "Transistor_FET:BSS84", "P", r"BSS84(LT[13]G|-7-F(-W)?| RFG|)"),
    ("Q-P-AO3401A-SOT23", "AO3401A", "Transistor_FET:AO3401A", "P", r"AO3401A"),
    ("Q-P-SI2347DS-SOT23", "SI2347DS", "Transistor_FET:Q_PMOS_GSD", "P", r"SI2347DS-T1-[BG]?E3"),
    ("Q-P-SI2301-SOT23", "SI2301HDS", "Transistor_FET:Q_PMOS_GSD", "P", r"SI2301[CH]DS-T1-[BG]?E3"),
]


def _verified(sp):
    for k, src in VERIFIED.items():
        if sp["mpn"].upper().startswith(k):
            return src
    return None


def slots():
    return [dict(part_id=p, value=v, symbol=s, ch=c, rx=re.compile(r"^(" + rx + r")$", re.I)) for p, v, s, c, rx in _S]


def _sot23(sp):
    pc = sp["params"].get("Package / Case") or ""
    return pc.startswith("TO-236") or "SOT-23-3" in pc


def accept(sp, slot):
    p = sp["params"]
    if not (slot["rx"].match(sp["mpn"]) and _sot23(sp)):
        return False
    if not (p.get("FET Type") or "").startswith(slot["ch"] + "-Channel"):
        return False
    return bool(_verified(sp)) or not REQUIRE_VERIFIED


def _qty(sp):
    return max([v.get("qty") or 0 for v in sp["variations"] if "Cut Tape" in v["pkg"] or "Bulk" in v["pkg"]] or [0])


def rank(sp, slot):
    return (_verified(sp) is None, _qty(sp) < 1000, mfr_rank(sp, PREFERRED),
            (sp["params"].get("Grade") or "-") == "Automotive")


def _short(t):
    return (t or "").split(" (")[0].replace(" ", "")


def make_row(sp, slot, var):
    p = sp["params"]
    vds = (p.get("Drain to Source Voltage (Vdss)") or "").replace(" ", "")
    if slot["ch"] == "P" and vds and not vds.startswith("-"):
        vds = "-" + vds
    idc = _short(p.get("Current - Continuous Drain (Id) @ 25°C"))
    if slot["ch"] == "P" and idc and not idc.startswith("-"):
        idc = "-" + idc
    rds = p.get("Rds On (Max) @ Id, Vgs") or ""
    m = re.match(r"([\d.]+)\s*(mOhm|Ohm)\s*@\s*[^,]+,\s*([\d.]+V)", rds)
    rds_s = f"{m.group(1)}{'mR' if m.group(2) == 'mOhm' else 'R'}@{m.group(3)}" if m else rds
    vth = (p.get("Vgs(th) (Max) @ Id") or "").split(" @")[0]
    kind = "N-MOSFET" if slot["ch"] == "N" else "P-MOSFET"
    src = _verified(sp) or ("UNVERIFIED (MPN datasheet not readable from build env: "
                            f"{https(sp.get('datasheet')) or 'n/a'}); pins per KiCad symbol {slot['symbol']} = {PINOUT}")
    return dict(Symbol=slot["symbol"], Footprint=FOOTPRINT, Value=slot["value"], Package="SOT-23",
                Description=f"{kind} {vds} {idc} Rds(on) {rds_s} SOT-23 {slot['value']}",
                Keywords=f"MOSFET {kind} {'NMOS' if slot['ch'] == 'N' else 'PMOS'} SOT-23 {slot['value']}",
                Rating=f"{vds} {idc}", TC_Dielectric=f"Rds {rds_s}, Vgs(th) max {vth}",
                FP_Filter="SOT?23*", Pinout=PINOUT, Pinout_Source=src)
