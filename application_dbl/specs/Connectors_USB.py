"""USB receptacles for the application DB (table Connectors_USB).

Build:  python3 tools/build_commodity.py Connectors_USB --lib application_dbl [--offline]

* Candidates come ONLY from the cached DigiKey queries in tools/harvest/usb_queries.json
  (exact keyword strings, no manufacturer filter, in-stock search option as cached).
* A part is used only when the official KiCad library (10.0.8, Connector_USB.pretty) has a
  footprint made for exactly that MPN / MPN family (FOOTPRINTS below). Parts without one are
  skipped, which is why there are no Würth USB-C rows: KiCad has no Würth USB-C footprint.
* One slot per (connector type, maker) so each type gets 2-3 different makers where KiCad
  footprints exist. Maker preference: Würth (WR-COM) > GCT > Amphenol > Molex > Hirose > others.
* The symbol's pin numbers were compared with the footprint's pad numbers (KiCad 10.0.8
  sources, fetched from gitlab.com/kicad/libraries). The result goes to Pinout / Pinout_Source.
"""
import datetime as _dt
import json
import os

from _common import key_params

TABLE = "Connectors_USB"
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
QUERIES = [dict(keywords=q) for q in json.load(open(os.path.join(_ROOT, "tools", "harvest", "usb_queries.json")))]
KICAD_REF = "10.0.8"
CHECKED = "2026-11-22"

# KiCad symbol pin numbers (Connector.kicad_symdir/<name>.kicad_sym @ 10.0.8)
SYMBOL_PINS = {
    "USB_C_Receptacle_USB2.0_16P": "A1 A4 A5 A6 A7 A8 A9 A12 B1 B4 B5 B6 B7 B8 B9 B12 SH",
    "USB_C_Receptacle_PowerOnly_6P": "A5 A9 A12 B5 B9 B12 SH",
    "USB_C_Receptacle": "A1 A2 A3 A4 A5 A6 A7 A8 A9 A10 A11 A12 B1 B2 B3 B4 B5 B6 B7 B8 B9 B10 B11 B12 SH",
    "USB_B_Micro": "1 2 3 4 5 SH",
    "USB_A": "1 2 3 4 SH",
}

# Numbered pads of the KiCad footprint (Connector_USB.pretty/<name>.kicad_mod @ 10.0.8);
# unnumbered ("") mechanical / NPTH pads are not listed.
FOOTPRINT_PADS = {
    "USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal": SYMBOL_PINS["USB_C_Receptacle_USB2.0_16P"],
    "USB_C_Receptacle_GCT_USB4110": SYMBOL_PINS["USB_C_Receptacle_USB2.0_16P"],
    "USB_C_Receptacle_Amphenol_124019772112A": SYMBOL_PINS["USB_C_Receptacle_USB2.0_16P"],
    "USB_C_Receptacle_Amphenol_12401948E412A": SYMBOL_PINS["USB_C_Receptacle_USB2.0_16P"],
    "USB_C_Receptacle_JAE_DX07S016JA1R1500": SYMBOL_PINS["USB_C_Receptacle_USB2.0_16P"],
    "USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal": SYMBOL_PINS["USB_C_Receptacle_PowerOnly_6P"],
    "USB_C_Receptacle_GCT_USB4135-GF-A_6P_TopMnt_Horizontal": SYMBOL_PINS["USB_C_Receptacle_PowerOnly_6P"],
    "USB_C_Receptacle_Amphenol_12401610E4-2A": SYMBOL_PINS["USB_C_Receptacle"],
    "USB_C_Receptacle_Molex_105450-0101": SYMBOL_PINS["USB_C_Receptacle"],
    "USB_Micro-B_Wuerth_629105150521": SYMBOL_PINS["USB_B_Micro"],
    "USB_Micro-B_GCT_USB3076-30-A": SYMBOL_PINS["USB_B_Micro"],
    "USB_Micro-B_Amphenol_10118194_Horizontal": SYMBOL_PINS["USB_B_Micro"],
    "USB_Micro-B_Molex-105017-0001": SYMBOL_PINS["USB_B_Micro"],
    "USB_A_Wuerth_614004134726_Horizontal": SYMBOL_PINS["USB_A"],
    "USB_A_Molex_67643_Horizontal": SYMBOL_PINS["USB_A"],
    "USB_A_Stewart_SS-52100-001_Horizontal": SYMBOL_PINS["USB_A"],
    "USB_A_Kycon_KUSBX-AS1N-B_Horizontal": SYMBOL_PINS["USB_A"],
}

# DigiKey MPN -> exact KiCad footprint (footprint named after / documented for that MPN).
FOOTPRINTS = {
    "USB4105-GF-A": "USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
    "USB4110-GF-A": "USB_C_Receptacle_GCT_USB4110",
    "124019772112A": "USB_C_Receptacle_Amphenol_124019772112A",
    "12401948E412A": "USB_C_Receptacle_Amphenol_12401948E412A",
    "DX07S016JA1R1500": "USB_C_Receptacle_JAE_DX07S016JA1R1500",
    "USB4125-GF-A": "USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal",
    "USB4135-GF-A": "USB_C_Receptacle_GCT_USB4135-GF-A_6P_TopMnt_Horizontal",
    "12401610E4#2A": "USB_C_Receptacle_Amphenol_12401610E4-2A",   # DigiKey '#' = Amphenol '~'/'-'
    "1054500101": "USB_C_Receptacle_Molex_105450-0101",
    "629105150521": "USB_Micro-B_Wuerth_629105150521",
    "USB3076-30-A": "USB_Micro-B_GCT_USB3076-30-A",
    "10118194-0011LF": "USB_Micro-B_Amphenol_10118194_Horizontal",  # listed in the footprint descr
    "1050170001": "USB_Micro-B_Molex-105017-0001",
    "614004134726": "USB_A_Wuerth_614004134726_Horizontal",
    "0676433910": "USB_A_Molex_67643_Horizontal",                  # footprint descr cites 676433910
    "SS-52100-001": "USB_A_Stewart_SS-52100-001_Horizontal",
    "KUSBX-AS1N-B": "USB_A_Kycon_KUSBX-AS1N-B_Horizontal",
}

KINDS = {
    # kind: (symbol, DigiKey "Connector Type" prefix, description, package text)
    "C16": ("USB_C_Receptacle_USB2.0_16P", "USB-C", "USB 2.0 Type-C receptacle, 16 contacts, horizontal",
            "USB-C 16P SMD/THT-shell, horizontal"),
    "C6": ("USB_C_Receptacle_PowerOnly_6P", "USB-C", "USB Type-C power-only receptacle, 6 contacts, horizontal",
           "USB-C 6P power-only, horizontal"),
    "C24": ("USB_C_Receptacle", "USB-C", "USB 3.x full-featured Type-C receptacle, 24 contacts, horizontal",
            "USB-C 24P SMD/THT-shell, horizontal"),
    "MICROB": ("USB_B_Micro", "USB - micro B", "USB 2.0 Micro-B receptacle, SMD, horizontal",
               "USB Micro-B SMD, horizontal"),
    "A": ("USB_A", "USB-A", "USB 2.0 Type-A receptacle, through-hole, horizontal", "USB-A THT, horizontal"),
}

# (part_id, kind, maker label, MPNs in preference order)
_SLOTS = [
    ("USB-C16-GCT", "C16", "GCT", ["USB4105-GF-A", "USB4110-GF-A"]),
    ("USB-C16-AMPHENOL", "C16", "Amphenol", ["124019772112A", "12401948E412A"]),
    ("USB-C16-JAE", "C16", "JAE", ["DX07S016JA1R1500"]),
    ("USB-C6-GCT-1", "C6", "GCT", ["USB4125-GF-A"]),
    ("USB-C6-GCT-2", "C6", "GCT", ["USB4135-GF-A"]),
    ("USB-C24-AMPHENOL", "C24", "Amphenol", ["12401610E4#2A"]),
    ("USB-C24-MOLEX", "C24", "Molex", ["1054500101"]),
    ("USB-MICROB-WURTH", "MICROB", "Würth", ["629105150521"]),
    ("USB-MICROB-GCT", "MICROB", "GCT", ["USB3076-30-A"]),
    ("USB-MICROB-AMPHENOL", "MICROB", "Amphenol", ["10118194-0011LF"]),
    ("USB-A-WURTH", "A", "Würth", ["614004134726"]),
    ("USB-A-MOLEX", "A", "Molex", ["0676433910"]),
    ("USB-A-STEWART", "A", "Stewart/Bel", ["SS-52100-001"]),
]

KEY_PARAMS = ["Specifications", "Number of Contacts", "Current Rating (Amps)", "Voltage - Rated", "Mounting Type",
              "Mounting Feature", "Mating Cycles", "Shielding", "Features", "Operating Temperature"]


def _pads(s):
    return set(s.split())


def pin_check(symbol, footprint):
    sym, fp = _pads(SYMBOL_PINS[symbol]), _pads(FOOTPRINT_PADS[footprint])
    if sym == fp:
        return True, f"{len(sym)} pins match: {' '.join(SYMBOL_PINS[symbol].split())}"
    return False, f"MISMATCH symbol-only {sorted(sym - fp)} footprint-only {sorted(fp - sym)}"


def slots():
    out = []
    for pid, kind, maker, mpns in _SLOTS:
        sym = KINDS[kind][0]
        ok_mpns = [m for m in mpns if pin_check(sym, FOOTPRINTS[m])[0]]
        out.append(dict(part_id=pid, kind=kind, maker=maker, mpns=ok_mpns))
    return out


def accept(sp, slot):
    if sp["mpn"] not in slot["mpns"]:
        return False
    p = sp["params"]
    return (p.get("Connector Type") or "").startswith(KINDS[slot["kind"]][1]) and p.get("Gender", "Receptacle") == "Receptacle"


def rank(sp, slot):
    return (slot["mpns"].index(sp["mpn"]),)


def make_row(sp, slot, var):
    sym, _, desc, pkg = KINDS[slot["kind"]]
    fp = FOOTPRINTS[sp["mpn"]]
    ok, pins = pin_check(sym, fp)
    pkgname = var["pkg"].replace(" (CT)", "")
    cands = [m for pid, kind, _, mpns in _SLOTS if kind == slot["kind"] for m in mpns if m != sp["mpn"]]
    cur = sp["params"].get("Current Rating (Amps)", "")
    return dict(
        Symbol=f"Connector:{sym}", Footprint=f"Connector_USB:{fp}", Value=sp["mpn"],
        Description=f"{desc}, {sp['mfr']} {sp['mpn']}" + (f", {cur}" if cur and cur != "-" else ""),
        Keywords=f"USB connector receptacle {slot['kind']} {slot['maker']} {sp['series'] or ''}".strip(),
        Package=pkg, FP_Filter="USB*", KiCad_Library="Connector", Lifecycle=sp["status"],
        Key_Params=key_params(sp, KEY_PARAMS, 10), Candidates="; ".join(cands[:10]), Packaging=pkgname,
        Review_Status="Unreviewed",
        Pinout=("OK " if ok else "") + pins,
        Pinout_Source=(f"KiCad {KICAD_REF} Connector:{sym} pin numbers vs Connector_USB:{fp} pad numbers "
                       f"(checked {CHECKED}); verify against the maker drawing during review"),
    )


if __name__ == "__main__":  # quick self-check of the symbol/footprint table
    for m, fp in FOOTPRINTS.items():
        kind = next(k for _, k, _, ms in _SLOTS if m in ms) if any(m in ms for *_, ms in _SLOTS) else None
        if kind:
            print(m, fp, pin_check(KINDS[kind][0], fp))
    print(_dt.date.today())
