"""2.54mm male pin headers, vertical, through-hole: 1x01..1x20 and 2x01..2x20.
Würth WR-PHD first, then Samtec, Amphenol, Sullins, Harwin.  Standard-height parts
(~6mm mating post, 2.54mm insulator, ~3mm solder tail) preferred.

Note: Würth WR-PHD THT headers are sold at DigiKey in "Bag" packaging only, which the
engine does not treat as orderable (Cut Tape / Bulk), so Samtec TSW fills most slots."""
import re
from _common import num, mfr_rank

TABLE = "Headers_2p54mm"
QUERIES = [dict(keywords=k) for k in (
    "Wurth pin header 2.54mm single row", "Wurth pin header 2.54mm dual row", "Wurth WR-PHD 2.54mm",
    "Samtec TSW pin header", "Amphenol pin header 2.54mm", "Sullins pin header 2.54mm")]
# targeted gap-fill queries (tools/harvest/requests_Headers_2p54mm.json)
QUERIES += [dict(keywords=k) for k in (
    'TSW-101-07-G-S',
    'TSW-113-07-G-S',
    'TSW-117-07-G-S',
    'TSW-118-07-G-S',
    'TSW-119-07-G-S',
    'TSW-101-07-G-D',
    'TSW-111-07-G-D',
    'TSW-119-07-G-D',
    'Sullins PRPC001SAAN-RC',
    'Sullins PREC013SAAN-RC',
    'Sullins PRPC019SAAN-RC',
    'Sullins PRPC011DAAN-RC',
    'Sullins PRPC019DAAN-RC',
)]
PREFERRED = ["Würth", "Samtec", "Amphenol", "Sullins", "Harwin"]
PITCH = "2.54"


def slots():
    return [dict(part_id=f"HDR-{PITCH}-{r}x{n:02d}-V", rows=r, cols=n) for r in (1, 2) for n in range(1, 21)]


def _vertical(sp):
    text = f"{sp['desc']} {sp['detail']}".upper()
    return not ("R/A" in text or "RIGHT ANGLE" in text or re.search(r"-R[AE]\b", sp["mpn"]))


def accept(sp, slot):
    p = sp["params"]
    try:
        rows, pos = int(p.get("Number of Rows")), int(p.get("Number of Positions"))
    except (TypeError, ValueError):
        return False
    ok = (p.get("Contact Type") == "Male Pin" and PITCH in (p.get("Pitch - Mating") or "")
          and rows == slot["rows"] and pos == slot["rows"] * slot["cols"]
          and p.get("Number of Positions Loaded") == "All"
          and (p.get("Shrouding") or "Unshrouded") == "Unshrouded"
          and p.get("Mounting Type") == "Through Hole" and p.get("Termination") == "Solder"
          and _vertical(sp))
    mate = _mm(p.get("Contact Length - Mating"))
    ok = ok and mate is not None and 5.0 <= mate <= 7.0   # standard mating post (sockets / jumpers)
    if ok and rows == 2:
        ok = PITCH in (p.get("Row Spacing - Mating") or "")
    return ok


def _mm(text):
    m = re.search(r"\(([\d.]+)mm\)", text or "")
    return float(m.group(1)) if m else None


def rank(sp, slot):
    p = sp["params"]
    mate, post, ins = _mm(p.get("Contact Length - Mating")), _mm(p.get("Contact Length - Post")), _mm(p.get("Insulation Height"))
    std = (0 if mate and 5.5 <= mate <= 6.2 else 1) + (0 if ins and abs(ins - 2.54) < 0.05 else 1) + \
          (0 if post and 2.5 <= post <= 3.5 else 1)
    gold = 0 if "Gold" in (p.get("Contact Finish - Mating") or "") else 1
    return (mfr_rank(sp, PREFERRED), std, gold)


def make_row(sp, slot, var):
    p = sp["params"]
    r, n = slot["rows"], slot["cols"]
    tag = f"{r}x{n:02d}"
    if r == 1:
        sym, pinout = f"Connector_Generic:Conn_01x{n:02d}", f"1..{n} (single row)"
    elif n == 1:
        sym, pinout = "Connector_Generic:Conn_02x01", "Odd_Even (pin 1, 2 across rows)"
    else:
        sym, pinout = f"Connector_Generic:Conn_02x{n:02d}_Odd_Even", "Odd_Even (odd row 1,3,5..; pin 2 opposite pin 1)"
    cur = p.get("Current Rating (Amps)")
    cur = "" if cur in (None, "-") else cur
    fin = p.get("Contact Finish - Mating") or ""
    return dict(
        Symbol=sym, Footprint=f"Connector_PinHeader_2.54mm:PinHeader_{tag}_P2.54mm_Vertical",
        Value=f"{tag} P2.54mm", Package=f"THT {tag} 2.54mm",
        Description=f"Pin header {tag} 2.54mm male vertical THT {fin}".strip(),
        Keywords=f"pin header connector male 2.54mm 0.1in {tag} vertical THT",
        Rating=cur, FP_Filter=f"PinHeader_{tag}*P2.54mm*", Pinout=pinout,
        Pinout_Source=("Standard header numbering " + ("pin 1..N along the row" if r == 1 else "pin 1,2 across rows (Odd_Even)")
                       + " = KiCad PinHeader footprint + Connector_Generic symbol; mfr datasheet " + (sp.get("datasheet") or "")))
