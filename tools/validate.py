#!/usr/bin/env python3
"""Validate kicad_dbl_library/parts.sqlite and company_parts.kicad_dbl (stdlib only).

    python tools/validate.py [--strict] [--verbose] [--db PATH] [--dbl PATH]
    python tools/validate.py --refresh-kicad-names      # needs network (gitlab.com)

Builds nothing: run ``python kicad_dbl_library/init_db.py`` first. Exit code 1
when any ERROR is found; WARNINGs never fail the run (except under --strict,
where UNVERIFIED pinouts / missing pinouts on Active rows become errors).

Checks
* every table in seed/schema.TABLES and its <Table>_Active view exist, and the
  table columns equal schema.COLUMN_NAMES; no table is empty
* Part_ID is unique across all tables; Status in Active/Deprecated/Obsolete;
  Superseded_By points at an existing Part_ID
* Active rows: Symbol, Footprint, Value, Manufacturer, MPN, Package, Datasheet
  non-empty; Supplier == "DigiKey"; Supplier_PN ends in "-ND"; no duplicate
  Active MPN inside a table
* Supplier_PN packaging (when tools/cache/dk_cache.sqlite exists): the DigiKey
  variation must not be Tape & Reel / Digi-Reel (Cut Tape or Bulk only)
* Symbol and Footprint names exist in the official KiCad libraries, checked
  offline against tools/kicad_names.json (refresh with --refresh-kicad-names)
* Pinout ("1=G 2=S 3=D", "1=K 2=A", ...) agrees with the KiCad symbol's pin
  number -> name map (case-insensitive, common aliases accepted)
* category rules (capacitor voltage/dielectric, resistor tolerances, sizes...)
* company_parts.kicad_dbl: one library per table, pointing at the *_Active
  view; every referenced column exists; legacy library names are kept
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "kicad_dbl_library")
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, LIB)
sys.path.insert(0, TOOLS)

from seed.schema import COLUMN_NAMES, TABLES, view_name  # noqa: E402

NAMES_PATH = os.path.join(TOOLS, "kicad_names.json")
CACHE_PATH = os.path.join(TOOLS, "cache", "dk_cache.sqlite")
FP_TREE = ("https://gitlab.com/api/v4/projects/kicad%2Flibraries%2Fkicad-footprints/repository/tree"
           "?path={lib}.pretty&per_page=100&page={page}")
SYM_RAW = "https://gitlab.com/kicad/libraries/kicad-symbols/-/raw/master/{lib}.kicad_symdir/{name}.kicad_sym"

# Library names users already reference in schematics: never rename these.
LEGACY_LIBRARY_NAMES = {
    "Resistors_ThinFilm_Precision": "Resistors - Thin Film 0.1% Precision",
    "Resistors_ThinFilm_1pct": "Resistors - Thin Film 1%",
    "Resistors_ThickFilm": "Resistors - Thick Film 5%",
    "Capacitors_Ceramic": "Capacitors - Ceramic",
    "Capacitors_RF": "Capacitors - RF 0402 C0G",
    "Capacitors_Bulk": "Capacitors - Bulk",
    "Capacitors_Tantalum": "Capacitors - Tantalum 50V",
    "Capacitors_Electrolytic": "Capacitors - Electrolytic 50V",
    "Inductors": "Inductors",
    "Inductors_RF": "Inductors - RF 0402",
    "Ferrite_Beads": "Ferrite Beads",
}
SEMI_TABLES = {"Diodes_Signal", "Diodes_Schottky", "Diodes_Zener", "Diodes_TVS", "ESD_Protection", "LEDs",
               "MOSFETs_SmallSignal", "BJTs_SmallSignal", "LDOs"}
STATUSES = ("Active", "Deprecated", "Obsolete")
REQUIRED_ACTIVE = ("Symbol", "Footprint", "Value", "Manufacturer", "MPN", "Supplier", "Supplier_PN",
                   "Datasheet", "Package")
BAD_PACKAGING = ("Tape & Reel", "Digi-Reel")
CERAMIC_DIELECTRICS = ("C0G", "NP0", "X7R", "X7S", "X8R", "X8L")
RES_TOL = {"Resistors_ThinFilm_Precision": "0.1%", "Resistors_ThinFilm_1pct": "1%", "Resistors_ThickFilm": "5%"}
SIZED_TABLES = {  # tables whose Package must be one of these and appear in the footprint name
    "Resistors_ThinFilm_Precision": ("0402", "0805"), "Resistors_ThinFilm_1pct": ("0402", "0805"),
    "Resistors_ThickFilm": ("0402", "0805"), "Capacitors_Ceramic": ("0402", "0805"),
    "Capacitors_RF": ("0402",), "Capacitors_Bulk": ("1210", "1812", "2220"),
    "Inductors": ("0402", "0805", "1210"), "Inductors_RF": ("0402",), "Ferrite_Beads": ("0402", "0805"),
}

# Pin-name aliases: each set is one canonical meaning.
_ALIASES = [  # first entry is the canonical name
    ("K", "CATHODE", "KATHODE"), ("A", "ANODE"),
    ("G", "GATE"), ("S", "SOURCE"), ("D", "DRAIN"),
    ("B", "BASE"), ("E", "EMITTER"), ("C", "COLLECTOR"),
    ("IN", "VIN", "VI", "INPUT"), ("OUT", "VOUT", "VO", "OUTPUT"),
    ("GND", "VSS", "EP", "PAD", "EPAD", "TAB", "THERMALPAD", "GNDPAD"),
    ("EN", "ENABLE", "CE"), ("NC", "DNC", "N.C."), ("SNS", "SENSE", "FB"),
]
ALIAS = {n: s[0] for s in _ALIASES for n in s}
# DigiKey part-number suffix convention, used when a PN is not in the cache.
DK_SUFFIX_PKG = (("DKR-ND", "Digi-Reel (from PN suffix)"), ("-6-ND", "Digi-Reel (from PN suffix)"),
                 ("TR-ND", "Tape & Reel (from PN suffix)"), ("-2-ND", "Tape & Reel (from PN suffix)"),
                 ("CT-ND", "Cut Tape (from PN suffix)"), ("-1-ND", "Cut Tape (from PN suffix)"))
PIN_TOKEN = re.compile(r"^(\d+)(\([^)]*\))?=(\S+)$")


# ----------------------------------------------------------------------------- helpers
class Report:
    def __init__(self, strict, verbose):
        self.strict, self.verbose = strict, verbose
        self.errors, self.warnings = [], []
        self.per_table = collections.defaultdict(lambda: [0, 0])  # table -> [errors, warnings]

    def err(self, table, msg):
        self.errors.append(f"{table}: {msg}" if table else msg)
        self.per_table[table][0] += 1

    def warn(self, table, msg, strict_error=False):
        if strict_error and self.strict:
            return self.err(table, msg + " [--strict]")
        self.warnings.append(f"{table}: {msg}" if table else msg)
        self.per_table[table][1] += 1


def norm_pin(name):
    n = (name or "").strip()
    m = re.match(r"^([^()]+)\(([^()]+)\)$", n)  # "EP(GND)" -> "GND"
    if m:
        n = m.group(2) if norm_pin(m.group(1)) in ("GND", "NC") else m.group(1)
    n = re.sub(r"~\{([^}]*)\}", r"\1", n)  # KiCad overbar ~{EN}
    n = n.replace("~", "").upper().replace(" ", "")
    return ALIAS.get(n, n)


def unnamed(name):
    """KiCad pins with no meaningful name ('~', '', or just a number)."""
    n = (name or "").strip()
    return n in ("", "~") or n.isdigit()


def parse_pinout(text):
    """'1=G 2=S 3=D' -> {'1': 'G', ...}; tokens that are not N=NAME are ignored."""
    out = {}
    for tok in (text or "").split():
        m = PIN_TOKEN.match(tok)
        if m:
            out[m.group(1)] = m.group(3)
    return out


def num(v):
    m = re.match(r"^\s*([0-9.]+)\s*([pnuµmkMR]?)", v or "")
    if not m:
        return None
    return float(m.group(1)) * {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1,
                                "k": 1e3, "M": 1e6, "R": 1}[m.group(2)]


# ----------------------------------------------------------------------------- s-expressions
def sexp(text):
    """Minimal KiCad s-expression parser -> nested lists of str."""
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+', text)
    stack, cur = [], []
    for t in tokens:
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
        elif t.startswith('"'):
            cur.append(re.sub(r"\\(.)", r"\1", t[1:-1]))
        else:
            cur.append(t)
    return cur


def _find(node, head):
    return [c for c in node if isinstance(c, list) and c and c[0] == head]


def symbol_info(text, name):
    """-> (extends or None, {pin number: pin name}) for symbol `name` in a .kicad_sym file."""
    lib = sexp(text)[0]
    for s in _find(lib, "symbol"):
        if s[1] != name:
            continue
        ext = _find(s, "extends")
        pins = {}

        def walk(n):
            for c in n:
                if isinstance(c, list) and c:
                    if c[0] == "pin":
                        nm, no = _find(c, "name"), _find(c, "number")
                        if no:
                            pins.setdefault(no[0][1], nm[0][1] if nm else "")
                    else:
                        walk(c)
        walk(s)
        return (ext[0][1] if ext else None), pins
    raise KeyError(name)


# ----------------------------------------------------------------------------- KiCad names refresh
def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kicad-dbl-validate"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def referenced_names(con):
    syms, fps = set(), set()
    for t in TABLES:
        try:
            for s, f in con.execute(f'SELECT Symbol, Footprint FROM "{t}"'):
                if s:
                    syms.add(s)
                if f:
                    fps.add(f)
        except sqlite3.OperationalError:
            pass
    return syms, fps


def refresh_kicad_names(con):
    syms, fps = referenced_names(con)
    out = {"_about": "Offline KiCad library name list for tools/validate.py. Regenerate with "
                     "`python tools/validate.py --refresh-kicad-names` (reads gitlab.com kicad-footprints / "
                     "kicad-symbols master).",
           "generated": dt.date.today().isoformat(), "footprints": {}, "symbols": {}, "missing_symbols": []}
    for lib in sorted({f.split(":", 1)[0] for f in fps if ":" in f}):
        names, page = [], 1
        while True:
            data = json.loads(_get(FP_TREE.format(lib=urllib.parse.quote(lib), page=page)))
            names += [e["name"][:-len(".kicad_mod")] for e in data
                      if e.get("type") == "blob" and e["name"].endswith(".kicad_mod")]
            if len(data) < 100:
                break
            page += 1
        out["footprints"][lib] = sorted(names)
        print(f"  footprints {lib}: {len(names)}")
    raw_cache = {}

    def fetch(lib, name):
        key = (lib, name)
        if key not in raw_cache:
            try:
                raw_cache[key] = symbol_info(_get(SYM_RAW.format(lib=urllib.parse.quote(lib),
                                                                 name=urllib.parse.quote(name))), name)
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
                raw_cache[key] = None
        return raw_cache[key]

    for full in sorted(syms):
        if ":" not in full:
            out["missing_symbols"].append(full)
            continue
        lib, name = full.split(":", 1)
        info = fetch(lib, name)
        if info is None:
            out["missing_symbols"].append(full)
            print(f"  symbol {full}: NOT FOUND")
            continue
        chain, ext, pins = [name], info[0], dict(info[1])
        while ext and not pins:  # derived symbols inherit the parent's pins
            chain.append(ext)
            parent = fetch(lib, ext)
            if parent is None:
                break
            ext, pins = parent[0], dict(parent[1])
        out["symbols"][full] = {"extends": chain[1:] or None,
                                "pins": dict(sorted(pins.items(), key=lambda kv: (len(kv[0]), kv[0])))}
        print(f"  symbol {full}: {len(pins)} pins" + (f" (extends {' -> '.join(chain[1:])})" if chain[1:] else ""))
    with open(NAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    print(f"Wrote {NAMES_PATH}: {sum(map(len, out['footprints'].values()))} footprints in "
          f"{len(out['footprints'])} libs, {len(out['symbols'])} symbols, {len(out['missing_symbols'])} missing")


# ----------------------------------------------------------------------------- DigiKey packaging
def load_dk_packaging():
    """{DigiKey PN: package type} from every cached keyword/details response, or None without a cache."""
    if not os.path.exists(CACHE_PATH):
        return None
    import dk_client
    dk = dk_client.DigiKey(offline=True, cache_path=CACHE_PATH)
    pkg = {}
    for (blob,) in dk.db.execute("SELECT body FROM cache"):
        try:
            body = dk_client._unpack(blob)
        except Exception:
            continue
        if not isinstance(body, dict):
            continue
        prods = list(body.get("Products") or []) + list(body.get("ExactMatches") or [])
        if body.get("Product"):
            prods.append(body["Product"])
        for p in prods:
            try:
                sp = dk_client.slim(p)
            except (KeyError, TypeError):
                continue
            for v in sp["variations"]:
                if v.get("dkpn"):
                    pkg[v["dkpn"]] = v.get("pkg") or ""
    dk.db.close()
    return pkg


# ----------------------------------------------------------------------------- checks
def check_tables(con, rep):
    rows_by_table, have = {}, {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    for t in TABLES:
        if t not in have:
            rep.err(t, "table missing (run kicad_dbl_library/init_db.py)")
            continue
        if view_name(t) not in have:
            rep.err(t, f"view {view_name(t)} missing")
        cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
        if cols != COLUMN_NAMES:
            rep.err(t, f"columns differ from schema.COLUMN_NAMES: {cols}")
            continue
        rows = [dict(zip(cols, r)) for r in con.execute(f'SELECT * FROM "{t}"')]
        if not rows:
            rep.err(t, "table is empty")
        rows_by_table[t] = rows
    return rows_by_table


def check_pinout(t, r, names, rep):
    pid, pin_text = r["Part_ID"], r.get("Pinout")
    active = (r.get("Status") or "Active") == "Active"
    if not pin_text:
        if t in SEMI_TABLES:
            rep.warn(t, f"{pid}: no Pinout recorded", strict_error=active)
        return
    if "UNVERIFIED" in (r.get("Pinout_Source") or "").upper():
        rep.warn(t, f"{pid}: Pinout '{pin_text}' is UNVERIFIED against the {r.get('MPN')} datasheet",
                 strict_error=active)
    claimed = parse_pinout(pin_text)
    sym = (names or {}).get("symbols", {}).get(r.get("Symbol"))
    if not claimed or not sym:
        return
    pins = sym["pins"]
    for no, want in claimed.items():
        if no not in pins:
            rep.warn(t, f"{pid}: Pinout pin {no}={want} has no pin {no} in symbol {r['Symbol']}")
            continue
        have = pins[no]
        if unnamed(have):
            continue
        if have.upper() in ("A1", "A2") and norm_pin(want) in ("K", "A"):
            # e.g. Diode:SMAJxxA is drawn unidirectional (bar on pin 1) but its pins are named A1/A2
            rep.warn(t, f"{pid}: symbol {r['Symbol']} names its pins A1/A2, so Pinout '{pin_text}' "
                        f"is not checkable by name (check the symbol graphic)")
            break
        if norm_pin(have) != norm_pin(want):
            rep.err(t, f"{pid}: Pinout says pin {no}={want} but symbol {r['Symbol']} has pin {no}={have} "
                       f"(symbol pins: {' '.join(f'{k}={v}' for k, v in pins.items())})")


def check_category(t, r, rep):
    pid, pkg, rating, tc = r["Part_ID"], r.get("Package") or "", r.get("Rating") or "", r.get("TC_Dielectric") or ""
    if t in SIZED_TABLES:
        if pkg not in SIZED_TABLES[t]:
            rep.err(t, f"{pid}: package {pkg} not in {SIZED_TABLES[t]}")
        if pkg and pkg not in (r.get("Footprint") or ""):
            rep.err(t, f"{pid}: package {pkg} does not match footprint {r.get('Footprint')}")
    if t in RES_TOL and r.get("Tolerance") != RES_TOL[t]:
        rep.err(t, f"{pid}: tolerance {r.get('Tolerance')} (expected {RES_TOL[t]})")
    if t in ("Capacitors_Tantalum", "Capacitors_Electrolytic"):
        if not re.match(r"(50|63)V", rating):
            rep.err(t, f"{pid}: polarized cap voltage {rating!r} (need 50/63V)")
        if r.get("Symbol") != "Device:C_Polarized":
            rep.err(t, f"{pid}: polarized cap symbol {r.get('Symbol')}")
    elif t.startswith("Capacitors"):
        v = re.match(r"(\d+)V", rating)
        if not v or int(v.group(1)) < 50:
            rep.err(t, f"{pid}: voltage {rating!r} (< 50V)")
        if tc not in CERAMIC_DIELECTRICS:
            rep.err(t, f"{pid}: dielectric {tc!r} not in {CERAMIC_DIELECTRICS}")
        if t == "Capacitors_RF" and tc not in ("C0G", "NP0"):
            rep.err(t, f"{pid}: RF cap must be C0G/NP0, got {tc}")
        if t == "Capacitors_Bulk" and (num(r.get("Value")) or 0) < 10e-6 * 0.999:
            rep.warn(t, f"{pid}: bulk cap value {r.get('Value')} < 10uF")
    if (r.get("Symbol") or "").startswith("Device:Q_"):
        rep.err(t, f"{pid}: generic {r['Symbol']} is not allowed; use a pin-order-specific symbol")


def check_rows(rows_by_table, names, dk_pkg, rep):
    seen_pid = {}
    for t, rows in rows_by_table.items():
        for r in rows:
            if r["Part_ID"] in seen_pid:
                rep.err(t, f"duplicate Part_ID {r['Part_ID']} (also in {seen_pid[r['Part_ID']]})")
            seen_pid[r["Part_ID"]] = t
    fp_libs = (names or {}).get("footprints", {})
    fp_sets = {k: set(v) for k, v in fp_libs.items()}
    symbols = (names or {}).get("symbols", {})
    for t, rows in rows_by_table.items():
        mpns = collections.defaultdict(list)
        for r in rows:
            pid, status = r["Part_ID"], r.get("Status") or "Active"
            if status not in STATUSES:
                rep.err(t, f"{pid}: Status {status!r} not in {STATUSES}")
            sup = r.get("Superseded_By")
            if sup and sup not in seen_pid:
                rep.err(t, f"{pid}: Superseded_By {sup} is not an existing Part_ID")
            if sup and sup == pid:
                rep.err(t, f"{pid}: supersedes itself")
            if status != "Active" and not sup:
                rep.warn(t, f"{pid}: {status} without Superseded_By (no replacement)")
            # symbol / footprint names (all non-obsolete rows: KiCad shows them)
            if status != "Obsolete" and names is not None:
                fp = r.get("Footprint") or ""
                lib, _, name = fp.partition(":")
                if lib not in fp_sets:
                    rep.err(t, f"{pid}: footprint library {lib!r} not in tools/kicad_names.json "
                               f"(run --refresh-kicad-names)")
                elif name not in fp_sets[lib]:
                    rep.err(t, f"{pid}: footprint {fp} does not exist in KiCad library {lib}")
                if r.get("Symbol") not in symbols:
                    extra = (" (not found in kicad-symbols)" if r.get("Symbol") in names.get("missing_symbols", [])
                             else " (not in tools/kicad_names.json; run --refresh-kicad-names)")
                    rep.err(t, f"{pid}: symbol {r.get('Symbol')}{extra}")
            if status != "Active":
                continue
            missing = [c for c in REQUIRED_ACTIVE if not r.get(c)]
            if missing:
                rep.err(t, f"{pid}: empty {', '.join(missing)}")
            if r.get("Supplier") and r["Supplier"] != "DigiKey":
                rep.err(t, f"{pid}: Supplier {r['Supplier']!r} (must be DigiKey)")
            spn = r.get("Supplier_PN") or ""
            if spn and not spn.endswith("-ND"):
                rep.err(t, f"{pid}: Supplier_PN {spn} does not end in -ND")
            if spn and dk_pkg is not None:
                pk = dk_pkg.get(spn)
                if pk is None:
                    pk = next((p for suf, p in DK_SUFFIX_PKG if spn.endswith(suf)), None)
                if pk is None:
                    rep.warn(t, f"{pid}: Supplier_PN {spn} not in DigiKey cache (packaging unknown)")
                elif any(b in pk for b in BAD_PACKAGING):
                    rep.err(t, f"{pid}: Supplier_PN {spn} is {pk}; use the Cut Tape or Bulk part number")
            dks = (r.get("DK_Status") or "").lower()
            if dks in ("obsolete", "discontinued at digi-key", "discontinued"):
                rep.err(t, f"{pid}: DigiKey status {r['DK_Status']} but Status is Active (retire it)")
            elif dks and dks != "active":
                rep.warn(t, f"{pid}: DigiKey status {r['DK_Status']}")
            if r.get("MPN"):
                mpns[r["MPN"]].append(pid)
            check_pinout(t, r, names, rep)
            check_category(t, r, rep)
        for mpn, pids in mpns.items():
            if len(pids) > 1:
                rep.err(t, f"MPN {mpn} used by several Active rows: {pids}")


def check_dbl(con, dbl_path, rep):
    try:
        dbl = json.load(open(dbl_path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        rep.err("kicad_dbl", f"cannot load {dbl_path}: {e}")
        return
    cs = (dbl.get("source") or {}).get("connection_string", "")
    if "${CWD}/parts.sqlite" not in cs:
        rep.err("kicad_dbl", f"connection_string should use ${{CWD}}/parts.sqlite: {cs}")
    libs = dbl.get("libraries") or []
    by_table = collections.defaultdict(list)
    names = collections.Counter(l.get("name") for l in libs)
    for n, c in names.items():
        if c > 1:
            rep.err("kicad_dbl", f"library name {n!r} used {c} times")
    for l in libs:
        by_table[l.get("table")].append(l)
    for t in TABLES:
        v = view_name(t)
        if t in by_table:
            rep.err("kicad_dbl", f"library {by_table[t][0]['name']!r} points at raw table {t}; use view {v}")
        if len(by_table.get(v, [])) != 1:
            rep.err("kicad_dbl", f"expected exactly one library for view {v}, found {len(by_table.get(v, []))}")
        if t in LEGACY_LIBRARY_NAMES and LEGACY_LIBRARY_NAMES[t] not in [l["name"] for l in by_table.get(v, [])]:
            rep.err("kicad_dbl", f"legacy library name {LEGACY_LIBRARY_NAMES[t]!r} for {t} must not change")
    known = {view_name(t) for t in TABLES}
    for l in libs:
        tbl = l.get("table")
        if tbl not in known:
            rep.err("kicad_dbl", f"library {l.get('name')!r}: table {tbl!r} is not a schema view")
            continue
        cols = {r[1] for r in con.execute(f'PRAGMA table_info("{tbl}")')}
        refs = [l.get("key"), l.get("symbols"), l.get("footprints")] + \
               [f.get("column") for f in l.get("fields", [])] + list((l.get("properties") or {}).values())
        for c in refs:
            if c not in cols:
                rep.err("kicad_dbl", f"library {l.get('name')!r}: column {c!r} not in {tbl}")
        if "Status" not in [f.get("column") for f in l.get("fields", [])]:
            rep.warn("kicad_dbl", f"library {l.get('name')!r}: no Status field")


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(LIB, "parts.sqlite"))
    ap.add_argument("--dbl", default=os.path.join(LIB, "company_parts.kicad_dbl"))
    ap.add_argument("--strict", action="store_true",
                    help="UNVERIFIED / missing pinouts on Active rows are errors")
    ap.add_argument("--verbose", "-v", action="store_true", help="print every warning")
    ap.add_argument("--refresh-kicad-names", action="store_true",
                    help=f"regenerate {os.path.relpath(NAMES_PATH, ROOT)} from gitlab.com, then validate")
    a = ap.parse_args()

    if not os.path.exists(a.db):
        sys.exit(f"{a.db} not found: run python kicad_dbl_library/init_db.py first")
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    if a.refresh_kicad_names:
        refresh_kicad_names(con)
    names = None
    if os.path.exists(NAMES_PATH):
        names = json.load(open(NAMES_PATH, encoding="utf-8"))
    rep = Report(a.strict, a.verbose)
    if names is None:
        rep.err(None, f"{os.path.relpath(NAMES_PATH, ROOT)} missing: run with --refresh-kicad-names")
    dk_pkg = load_dk_packaging()
    if dk_pkg is None:
        rep.warn(None, "tools/cache/dk_cache.sqlite not found: Supplier_PN packaging not checked")

    rows_by_table = check_tables(con, rep)
    check_rows(rows_by_table, names, dk_pkg, rep)
    check_dbl(con, a.dbl, rep)

    print(f"{'Table':<30} {'rows':>5} {'active':>6} {'depr':>5} {'obs':>4} {'err':>5} {'warn':>5}")
    for t in TABLES:
        rows = rows_by_table.get(t, [])
        st = collections.Counter(r.get("Status") or "Active" for r in rows)
        e, w = rep.per_table.get(t, [0, 0])
        print(f"{t:<30} {len(rows):>5} {st['Active']:>6} {st['Deprecated']:>5} {st['Obsolete']:>4} {e:>5} {w:>5}")
    total = sum(len(r) for r in rows_by_table.values())
    print(f"{'TOTAL':<30} {total:>5}")

    if rep.warnings:
        print(f"\n{len(rep.warnings)} warnings")
        if a.verbose:
            for w in rep.warnings:
                print("  WARN", w)
        else:  # group by kind, a few examples each
            kinds = collections.defaultdict(list)
            for w in rep.warnings:
                head, _, msg = w.partition(": ")
                msg = msg.split(": ", 1)[-1]
                kinds[(head, re.sub(r"'[^']*'|\S*\d\S*", "#", msg))].append(w)
            for _, ws in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
                for w in ws[:3]:
                    print("  WARN", w)
                if len(ws) > 3:
                    print(f"       ... and {len(ws) - 3} more like this (use --verbose)")
    print(f"\n{len(rep.errors)} errors")
    for e in rep.errors:
        print("  ERROR", e)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
