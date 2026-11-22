"""1.27mm male pin headers, vertical: 1x01..1x20 and 2x01..2x20.
THT preferred (Würth WR-PHD, then Samtec FTS/FTSH, then others); SMD only when no THT part is
stocked, and only Samtec FTSH-1xx-xx-x-DV dual-row SMD (its recommended land pattern -
0.74x2.4mm pads, 3.9mm row-to-row pad centres - is the one KiCad's PinHeader_2xNN_P1.27mm_Vertical_SMD
uses). Alignment-pin (-A) and locking-clip (-LC) options are excluded (need extra PCB holes).
Single-column parts carry no pitch at DigiKey; 2x01 is identified by its 1.27mm row spacing, 1x01 by
a known 1.27mm family MPN. Standard ~3mm mating posts rank ahead of long-post variants.
Single-row SMD headers are not used (KiCad's Pin1Left/Pin1Right land patterns not verified)."""
import re
from _common import mfr_rank

TABLE = "Headers_1p27mm"
QUERIES = [dict(keywords=k) for k in (
    "Wurth pin header 1.27mm", "Wurth WR-PHD 1.27mm", "Samtec FTSH", "Samtec FTS",
    "pin header 1.27mm dual row", "pin header 1.27mm single row")]
# targeted gap-fill queries (tools/harvest/requests_Headers_1p27mm.json)
QUERIES += [dict(keywords=k) for k in (
    'FTS-101-01-L-S',
    'FTS-105-01-L-S',
    'FTS-108-01-L-S',
    'FTS-110-01-L-S',
    'FTS-111-01-L-S',
    'FTS-112-01-L-S',
    'FTS-113-01-L-S',
    'FTS-114-01-L-S',
    'FTS-115-01-L-S',
    'FTS-116-01-L-S',
    'FTS-117-01-L-S',
    'FTS-118-01-L-S',
    'FTS-119-01-L-S',
    'FTS-120-01-L-S',
    'FTSH-101-01-L-D',
    'FTSH-109-01-L-D',
    'FTSH-111-01-L-D',
    'FTSH-114-01-L-D',
    'FTSH-118-01-L-D',
    'FTSH-119-01-L-D',
    'FTSH-109-01-L-DV',
    'FTSH-111-01-L-DV',
    'FTSH-114-01-L-DV',
    'FTSH-118-01-L-DV',
    'FTSH-119-01-L-DV',
    'FTS-109-01-L-D',
    'FTS-111-01-L-D',
    'FTS-114-01-L-D',
    'FTS-118-01-L-D',
    'FTS-119-01-L-D',
    'pin header 1.27mm 1 row through hole',
    'Harwin M50 pin header 1.27mm',
    'Sullins GRPB 1.27mm header',
)]
PREFERRED = ["Würth", "Samtec", "Sullins", "Harwin"]
PITCH = "1.27"
FAMILY_1P27 = re.compile(r"^(FTSH?-1\d\d-|GRPB\d|M50-)")
FTSH_DV = re.compile(r"^FTSH-1\d\d-\d\d-[A-Z]{1,2}-DV(-[A-Z]+)*$")


def slots():
    return [dict(part_id=f"HDR-{PITCH}-{r}x{n:02d}-V", rows=r, cols=n) for r in (1, 2) for n in range(1, 21)]


def _vertical(sp):
    text = f"{sp['desc']} {sp['detail']}".upper()
    return not ("R/A" in text or "RIGHT ANGLE" in text or "-DH" in sp["mpn"] or re.search(r"-R[AE]\b", sp["mpn"]))


def _smd_ok(sp, slot):
    mpn = sp["mpn"]
    toks = mpn.split("-")[5:]
    return slot["rows"] == 2 and bool(FTSH_DV.match(mpn)) and "A" not in toks and "LC" not in toks


def accept(sp, slot):
    p = sp["params"]
    try:
        rows, pos = int(p.get("Number of Rows")), int(p.get("Number of Positions"))
    except (TypeError, ValueError):
        return False
    mount = p.get("Mounting Type")
    pitch = p.get("Pitch - Mating") or "-"
    # single-column parts have no pitch on DigiKey ("-"): 2x01 is identified by the 1.27mm row spacing
    # below, 1x01 only when the MPN belongs to a known 1.27mm header family
    one_col = slot["cols"] == 1 and pitch == "-" and (slot["rows"] == 2 or bool(FAMILY_1P27.match(sp["mpn"])))
    ok = (p.get("Contact Type") == "Male Pin" and (PITCH in pitch or one_col)
          and rows == slot["rows"] and pos == slot["rows"] * slot["cols"]
          and p.get("Number of Positions Loaded") == "All"
          and (p.get("Shrouding") or "Unshrouded") == "Unshrouded" and _vertical(sp)
          and (mount == "Through Hole" or (mount == "Surface Mount" and _smd_ok(sp, slot))))
    if ok and rows == 2:
        ok = PITCH in (p.get("Row Spacing - Mating") or "")
    return ok


def rank(sp, slot):
    smd = sp["params"].get("Mounting Type") != "Through Hole"
    gold = 0 if "Gold" in (sp["params"].get("Contact Finish - Mating") or "") else 1
    std = 0 if re.search(r"-01-", sp["mpn"]) or "Samtec" not in sp["mfr"] else 1   # Samtec -01- = standard lead style
    m = re.search(r"\(([\d.]+)mm\)", sp["params"].get("Contact Length - Mating") or "")
    mate = 0 if m and 2.5 <= float(m.group(1)) <= 3.6 else 1   # standard ~3mm mating post (FTS/GRPB/M50)
    return (int(smd), mfr_rank(sp, PREFERRED), mate, std, gold)


def make_row(sp, slot, var):
    p = sp["params"]
    r, n = slot["rows"], slot["cols"]
    tag = f"{r}x{n:02d}"
    smd = p.get("Mounting Type") != "Through Hole"
    sfx = "_SMD" if smd else ""
    if r == 1:
        sym, pinout = f"Connector_Generic:Conn_01x{n:02d}", f"1..{n} (single row)"
    elif n == 1:
        sym, pinout = "Connector_Generic:Conn_02x01", "Odd_Even (pin 1, 2 across rows)"
    else:
        sym, pinout = f"Connector_Generic:Conn_02x{n:02d}_Odd_Even", "Odd_Even (odd row 1,3,5..; pin 2 opposite pin 1)"
    cur = p.get("Current Rating (Amps)")
    cur = "" if cur in (None, "-") else cur
    mnt = "SMD" if smd else "THT"
    return dict(
        Symbol=sym, Footprint=f"Connector_PinHeader_1.27mm:PinHeader_{tag}_P1.27mm_Vertical{sfx}",
        Value=f"{tag} P1.27mm", Package=f"{mnt} {tag} 1.27mm",
        Description=f"Pin header {tag} 1.27mm male vertical {mnt}",
        Keywords=f"pin header connector male 1.27mm 0.05in {tag} vertical {mnt}",
        Rating=cur, FP_Filter=f"PinHeader_{tag}*P1.27mm*", Pinout=pinout,
        Pinout_Source=("Standard header numbering " + ("pin 1..N along the row" if r == 1 else "pin 1,2 across rows (Odd_Even)")
                       + " = KiCad PinHeader footprint + Connector_Generic symbol"
                       + ("; SMD land pattern = Samtec FTSH-DV recommended footprint" if smd else "")
                       + "; mfr datasheet " + (sp.get("datasheet") or "")))
