"""Indicator chip LEDs, one per colour x size (0402 / 0603 / 0805).

Standard-brightness chip LEDs tested at 20 mA (white: 5-20 mA), single-colour 'Standard'
configuration. Kingbright first (APHHS1005 / APT1608 / APT2012 families), then Würth, Lite-On,
OSRAM, Rohm; parts with <1000 pcs on DigiKey Cut Tape rank after well-stocked ones.
Amber only where a stocked part exists (0603/0805).

Symbol Device:LED (1=K 2=A); KiCad LED_SMD footprints have pad 1 = cathode, so Pinout is
"1=K 2=A". Pinout_Source = datasheet + cathode-mark note once the datasheet has been read
(VERIFIED below); otherwise it starts with "UNVERIFIED".
"""
from _common import pkg_is, mfr_rank, num
from dk_client import https

TABLE = "LEDs"
QUERIES = [dict(keywords=k) for k in (
    "Kingbright LED 0402", "Kingbright LED 0603", "Kingbright LED 0805", "Wurth LED 0603", "Wurth LED 0805",
    "Wurth LED 0402", "Lite-On LED 0603", "Lite-On LED 0805", "Lite-On LED 0402")]
PREFERRED = ["Kingbright", "Würth", "Lite-On", "OSRAM", "Rohm"]
SIZES = ["0402", "0603", "0805"]
FOOTPRINT = {"0402": "LED_SMD:LED_0402_1005Metric", "0603": "LED_SMD:LED_0603_1608Metric",
             "0805": "LED_SMD:LED_0805_2012Metric"}
COLOURS = [("RED", "Red"), ("GREEN", "Green"), ("YELLOW", "Yellow"), ("ORANGE", "Orange"),
           ("BLUE", "Blue"), ("WHITE", "White"), ("AMBER", "Amber")]
NO_AMBER = {"0402"}  # no stocked amber 0402 from the listed makers
# Preferred standard parts (first match wins over generic ranking).
PICK = {
    ("0402", "Red"): ["APHHS1005SURCK", "APG1005SEC/E-T"], ("0402", "Green"): ["APHHS1005CGCK"],
    ("0402", "Yellow"): ["APHHS1005SYCK"], ("0402", "Orange"): ["APHHS1005SECK"],
    ("0402", "Blue"): ["APHHS1005QBC/D"],
    ("0603", "Red"): ["APT1608SURCK"], ("0603", "Green"): ["APT1608CGCK"], ("0603", "Yellow"): ["APT1608SYCK"],
    ("0603", "Orange"): ["APT1608SECK"], ("0603", "Blue"): ["APT1608QBC/D"], ("0603", "White"): ["APT1608QWF/D"],
    ("0805", "Red"): ["APT2012SURCK"], ("0805", "Green"): ["APT2012CGCK"], ("0805", "Yellow"): ["APT2012SYCK"],
    ("0805", "Orange"): ["APT2012SECK"], ("0805", "Blue"): ["APT2012QBC/D"],
    ("0603", "Amber"): ["150060AS75000"], ("0805", "Amber"): ["150080AS75000"],
}
PINOUT = "1=K 2=A"
VERIFIED = {}  # MPN -> "datasheet URL p.N: cathode mark ..." once read


def slots():
    return [dict(part_id=f"LED-{s}-{code}", size=s, colour=c) for s in SIZES for code, c in COLOURS
            if not (c == "Amber" and s in NO_AMBER)]


def accept(sp, slot):
    p = sp["params"]
    if not pkg_is(sp, slot["size"]) or (p.get("Color") or "") != slot["colour"]:
        return False
    if (p.get("Configuration") or "") != "Standard":
        return False
    it = num(p.get("Current - Test"), "A")
    lo = 0.005 if slot["colour"] == "White" else 0.02
    return it is not None and lo - 1e-9 <= it <= 0.02 + 1e-9


def _qty(sp):
    return max([v.get("qty") or 0 for v in sp["variations"] if "Cut Tape" in v["pkg"] or "Bulk" in v["pkg"]] or [0])


def rank(sp, slot):
    pick = PICK.get((slot["size"], slot["colour"]), [])
    idx = pick.index(sp["mpn"]) if sp["mpn"] in pick else len(pick)
    mcd = num(sp["params"].get("Millicandela Rating"), "cd") or 0
    # prefer moderate (standard) brightness: penalise very bright parts
    return (_qty(sp) < 1000, idx, mfr_rank(sp, PREFERRED), mcd > 0.5, abs(mcd - 0.1))


def make_row(sp, slot, var):
    p = sp["params"]
    it = (p.get("Current - Test") or "").replace(" ", "")
    vf = (p.get("Voltage - Forward (Vf) (Typ)") or "").replace(" ", "")
    wl = p.get("Wavelength - Dominant") or "-"
    mcd = (p.get("Millicandela Rating") or "").replace(" ", "")
    lens = p.get("Lens Transparency") or "-"
    tc = (f"λ {wl}, {mcd}" if wl not in ("-", "") else mcd)
    src = VERIFIED.get(sp["mpn"]) or ("UNVERIFIED (datasheet not readable from build env: "
                                      f"{https(sp.get('datasheet')) or 'n/a'}); cathode mark -> footprint pad 1 not checked")
    return dict(Symbol="Device:LED", Footprint=FOOTPRINT[slot["size"]], Value=slot["colour"], Package=slot["size"],
                Description=f"LED {slot['colour']} {slot['size']} {tc} Vf {vf}" + (f" ({lens.lower()} lens)" if lens != "-" else ""),
                Keywords=f"LED {slot['colour'].lower()} indicator chip SMD {slot['size']}",
                Rating=f"{it} {vf}", TC_Dielectric=tc, FP_Filter="LED*", Pinout=PINOUT, Pinout_Source=src)
