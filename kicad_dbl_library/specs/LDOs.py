"""Fixed 3.3V / 1.8V LDO regulators, Texas Instruments only (TI covers every slot).

Each slot is one TI family + package with an exact KiCad stock symbol from
Regulator_Linear (or, for TLV1117LV, the pin-compatible TLV1117 stock symbol).
Footprint = the symbol's default Footprint property (TLV1117 has none; SOT-223 TabPin2
matches its 1=GND 2=OUT 3=IN, tab=OUT pinout). Slot order per voltage:
ultra-low-Iq 200mA, general 300mA, 500mA, 1A (SOT-23-5 / SOT-223 / 16V-input WSON),
low-noise RF (LP5907, TPS7A20).

Pinouts verified 2026-11-22 against the TI datasheet pin-functions table for the exact package
(PIN_CHECK, keyed by datasheet + package) and against the KiCad stock symbol pin numbers
(kicad-symbols sources, extends resolved).
"""
import re

TABLE = "LDOs"
QUERIES = [dict(keywords=k) for k in (
    "TLV75533", "TLV75518", "TLV75733", "TLV75718", "TPS7A02", "TPS7A0233", "TPS7A0218",
    "LP5907 3.3", "LP5907 1.8", "LP5912", "TLV733P", "TLV70033", "TLV70018", "TPS7A2033", "TPS7A2018",
    "TLV76733", "TLV76718", "TPS73633", "TPS73618", "LDO 3.3V Texas Instruments", "LDO 1.8V Texas Instruments")]

TI = "https://www.ti.com/lit/ds/symlink/"
SOT5 = "Package_TO_SOT_SMD:SOT-23-5"
SOT3 = "Package_TO_SOT_SMD:SOT-23"
SOT223 = "Package_TO_SOT_SMD:SOT-223-3_TabPin2"
WSON6 = "Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm"
WSON6TV = "Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm_ThermalVias"
PIN_SOT5 = "1=IN 2=GND 3=EN 4=NC 5=OUT"

# (class, current label, family value, MPN regex (preference order = list order), symbol, footprint,
#  package, fp_filter, pinout, datasheet, note)
def _fam(v):  # v = "33" | "18"
    return [
        ("ULP", "200MA", f"TPS7A05{v}P", [rf"TPS7A05{v}PDB{'Z' if v == '33' else 'V'}[RT]$"],
         f"Regulator_Linear:TPS7A05{v}PDB{'Z' if v == '33' else 'V'}", SOT3 if v == "33" else SOT5,
         "SOT-23-3" if v == "33" else "SOT-23-5", "SOT?23*",
         "1=GND 2=OUT 3=IN" if v == "33" else PIN_SOT5, TI + "tps7a05.pdf",
         "SOT-23-5 DBV not stocked; SOT-23-3 DBZ, no EN" if v == "33" else ""),
        ("GP", "300MA", f"TLV733{v}P", [rf"TLV733{v}PDBV[RT]$"], f"Regulator_Linear:TLV733{v}PDBV", SOT5,
         "SOT-23-5", "SOT?23*", PIN_SOT5, TI + "tlv733p.pdf", "capacitor-free"),
        ("GP", "500MA", f"TLV755{v}P", [rf"TLV755{v}PDBV[RT]$", rf"TLV755{v}PDRV[RT]$"], None, None,
         None, None, None, TI + "tlv755p.pdf", ""),
        ("GP", "1A", f"TLV757{v}P", [rf"TLV757{v}PDYD[RT]$", rf"TLV757{v}PDBV[RT]$"],
         f"Regulator_Linear:TLV757{v}PDBV", SOT5, "SOT-23-5", "SOT?23*", PIN_SOT5, TI + "tlv757p.pdf",
         "DYD = SOT-23-5, DBV pinout"),
        ("GP", "1A", f"TLV1117LV{v}", [rf"TLV1117LV{v}DCY[RT]$"], f"Regulator_Linear:TLV1117-{v}", SOT223,
         "SOT-223", "SOT?223*", "1=GND 2=OUT 3=IN tab=OUT (footprint tab pad 2)", TI + "tlv1117lv.pdf",
         "TLV1117 stock symbol, pin-compatible"),
        ("HV", "1A", f"TLV767{v}", [rf"TLV767{v}DRV[RT]$"], f"Regulator_Linear:TLV767{v}DRVx", WSON6TV,
         "WSON-6", "*WSON*1EP*2x2mm*P0.65mm*", "1=OUT 2=SNS 3=GND 4=EN 5=GND 6=IN 7=EP", TI + "tlv767.pdf",
         ""),
        ("LN", "250MA", f"LP5907-{v[0]}.{v[1]}", [rf"LP5907MFX-{v[0]}\.{v[1]}/NOPB$", rf"LP5907QMFX-{v[0]}\.{v[1]}Q1$"],
         f"Regulator_Linear:LP5907MFX-{v[0]}.{v[1]}", SOT5, "SOT-23-5", "SOT?23*", PIN_SOT5, TI + "lp5907.pdf",
         "RF, 6.5uVrms"),
        ("LN", "300MA", f"TPS7A20{v}P", [rf"TPS7A20{v}PDBV[RT]$"], "Regulator_Linear:TPS7A20xxxDBV", SOT5,
         "SOT-23-5", "SOT?23*", PIN_SOT5, TI + "tps7a20.pdf", "7uVrms"),
    ]


# (datasheet, package code) -> "p.N <table>: <pin numbers>" read from the TI pin-functions table.
PIN_CHECK = {
    ("tps7a05.pdf", "DBZ"): "p.5 Pin Functions, DBZ column: IN 3, GND 1, OUT 2",
    ("tps7a05.pdf", "DBV"): "p.5 Pin Functions, DBV column: IN 1, GND 2, EN 3, NC 4, OUT 5",
    ("tlv733p.pdf", "DBV"): "p.4 Pin Functions, DBV column: IN 1, GND 2, EN 3, NC 4, OUT 5",
    ("tlv755p.pdf", "DBV"): "p.3 Table 4-1, DBV column: IN 1, GND 2, EN 3, NC 4, OUT 5",
    ("tlv755p.pdf", "DRV"): "p.3 Table 4-1, DRV column: OUT 1, NC 2/5, GND 3, EN 4, IN 6, "
                            "thermal pad 'internally connected to GND'",
    ("tlv757p.pdf", "DYD"): "p.3 Table 4-1, DYD column: IN 1, GND 2, EN 3, NC 4, OUT 5",
    ("tlv1117lv.pdf", "DCY"): "p.3 Table 5-1 (DCY SOT-223): GND 1, OUT 2 and Tab, IN 3",
    ("tlv767.pdf", "DRV"): "p.4 Table 5-1, DRV (Fixed) column: OUT 1, SNS 2, GND 3/5, EN 4, IN 6, thermal pad",
    ("lp5907.pdf", "DBV"): "p.3 Table 4-2, SOT-23 column: IN 1, GND 2, EN 3, N/C 4, OUT 5",
    ("tps7a20.pdf", "DBV"): "p.4 Pin Functions X2SON/SOT-23, SOT-23 column: IN 1, GND 2, EN 3, N/C 4, OUT 5",
}
_PKGCODE = {"SOT-23-3": "DBZ", "SOT-223": "DCY", "WSON-6": "DRV", "SOT-23-5": "DBV"}


def _pin_check(slot):
    code = _PKGCODE[slot["pkg"]]
    ds = slot["ds"].rsplit("/", 1)[-1]
    if ds == "tlv757p.pdf":
        code = "DYD"
    return ds, PIN_CHECK[(ds, code)]


VARIANT_500 = {  # TLV755P: DBV preferred, WSON-6 DRV fallback (DBV not stocked for 3.3V at harvest time)
    "DBV": (SOT5, "SOT-23-5", "SOT?23*", PIN_SOT5),
    "DRV": (WSON6, "WSON-6", "*WSON*1EP*2x2mm*P0.65mm*", "1=OUT 2=NC 3=GND 4=EN 5=NC 6=IN 7=EP(GND)"),
}


def slots():
    out = []
    for v, vlabel, vout in (("33", "3V3", 3.3), ("18", "1V8", 1.8)):
        for cls, cur, value, pats, sym, fp, pkg, flt, pin, ds, note in _fam(v):
            if value.startswith("TLV755"):
                pkgcode = "DBV" if v == "18" else "DRV"
                pats = [rf"TLV755{v}P{pkgcode}[RT]$"] + ([rf"TLV755{v}PDYD[RT]$"] if pkgcode == "DBV" else [])
                fp, pkg, flt, pin = VARIANT_500[pkgcode]
                sym = f"Regulator_Linear:TLV755{v}P{pkgcode}"
                note = "" if pkgcode == "DBV" else "SOT-23-5 DBV not stocked; WSON-6 DRV"
            code = re.sub(r"[^A-Z0-9]", "", pats[0].split("[")[0].split("$")[0].replace("\\", ""))
            code = code.replace("NOPB", "").replace("LP5907MFX" + v, "LP5907MFX")
            out.append(dict(part_id=f"LDO-{vlabel}-{cur}-{code}", vout=vout, vlabel=vlabel, cls=cls, cur=cur,
                            value=value, pats=pats, sym=sym, fp=fp, pkg=pkg, flt=flt, pin=pin, ds=ds, note=note))
    return out


def accept(sp, slot):
    return sp["mfr"] == "Texas Instruments" and any(re.match(p, sp["mpn"]) for p in slot["pats"]) \
        and sp["params"].get("Voltage - Output (Min/Fixed)") == f"{slot['vout']}V"


def rank(sp, slot):
    return (next(i for i, p in enumerate(slot["pats"]) if re.match(p, sp["mpn"])),)


def _clean(s):
    return (s or "").replace("µ", "u").replace(" ", "")


def make_row(sp, slot, var):
    p = sp["params"]
    iq = _clean(p.get("Current - Quiescent (Iq)"))
    vdo = _clean((p.get("Voltage Dropout (Max)") or "").split("@")[0])
    vin = _clean(p.get("Voltage - Input (Max)"))
    cur = (p.get("Current - Output") or slot["cur"]).replace(" ", "")
    vtxt = f"{slot['vout']}V"
    cls = {"ULP": "ultra-low-Iq", "GP": "", "HV": "16V-input", "LN": "low-noise"}[slot["cls"]]
    desc = " ".join(x for x in (f"LDO {vtxt} {cur}", cls, slot["value"], slot["pkg"],
                                f"({slot['note']})" if slot["note"] else "") if x)
    return dict(Symbol=slot["sym"], Footprint=slot["fp"], Value=slot["value"], Package=slot["pkg"],
                Description=desc, Keywords=f"LDO regulator linear {vtxt} {cur} {slot['value']} {slot['pkg']} TI",
                Rating=f"{vtxt} {cur}", TC_Dielectric=f"Iq {iq}, Vdo {vdo}, Vin max {vin}",
                Datasheet=slot["ds"], FP_Filter=slot["flt"], Manufacturer="Texas Instruments",
                Pinout=slot["pin"],
                Pinout_Source=f"{slot['ds']} {_pin_check(slot)[1]}; matches KiCad symbol {slot['sym']} "
                              f"pin numbers")
