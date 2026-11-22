#!/usr/bin/env python3
"""Review / inspect / add parts of the application-parts DB (application_dbl/).

    python3 tools/app_part.py review <Part_ID> --status Approved|Rejected|Obsolete|Unreviewed --by NAME [--notes TEXT]
                                    [--footprint Lib:Footprint] [--no-rebuild]
    python3 tools/app_part.py show <Part_ID>
    python3 tools/app_part.py list [--table X] [--status Unreviewed] [--lifecycle Active] [--lib KiCadLib]
                                    [--no-footprint] [--limit 50]
    python3 tools/app_part.py add <Lib:Symbol> <MPN> [--footprint Lib:Footprint] [--table X] [--by NAME]
                                    [--notes TEXT] [--no-rebuild]

* review  writes application_dbl/reviews.json ({Part_ID: {Review_Status, Reviewed_By, Review_Date,
          Review_Notes[, Footprint]}}) and rebuilds application.sqlite. Reviews survive rebuilds.
          --footprint assigns a footprint to a row whose KiCad symbol has none (e.g. generic symbols).
* add     stores a manual part in application_dbl/manual_parts.json (merged by init_app_db.py). DigiKey
          data is taken from the prefill matches or the DigiKey cache when present; otherwise the supplier
          fields stay blank until `init_app_db.py --fetch-manual N` (or a later prefill) finds it.
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "application_dbl")
sys.path.insert(0, APP)
import app_schema as S  # noqa: E402

DB = os.path.join(APP, "application.sqlite")
REVIEWS = os.path.join(APP, "reviews.json")
MANUAL = os.path.join(APP, "manual_parts.json")
CATALOG = os.path.join(APP, "catalog.sqlite")


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, sort_keys=isinstance(data, dict))
        f.write("\n")
    os.replace(tmp, path)


def db():
    if not os.path.exists(DB):
        rebuild()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def rebuild():
    r = subprocess.run([sys.executable, os.path.join(APP, "init_app_db.py"), "--quiet"], text=True)
    if r.returncode:
        raise SystemExit("init_app_db.py failed")


def get_row(pid):
    row = db().execute('SELECT * FROM "All_Parts" WHERE "Part_ID" = ?', (pid,)).fetchone()
    return dict(row) if row else None


def cmd_review(a):
    row = get_row(a.part_id)
    if row is None:
        raise SystemExit(f"{a.part_id}: not in {DB} (see `app_part.py list`)")
    if a.status == "Approved":
        problems = []
        if not row["MPN"]:
            problems.append("no MPN")
        if not (a.footprint or row["Footprint"]):
            problems.append("no footprint (use --footprint)")
        if row["Lifecycle"] == "Obsolete":
            problems.append("lifecycle Obsolete")
        if problems and not a.force:
            raise SystemExit(f"{a.part_id}: cannot approve: {', '.join(problems)} (use --force to override)")
    reviews = load(REVIEWS, {})
    entry = dict(Review_Status=a.status, Reviewed_By=a.by, Review_Date=dt.date.today().isoformat(),
                 Review_Notes=a.notes or "")
    if a.footprint:
        entry["Footprint"] = a.footprint
    elif reviews.get(a.part_id, {}).get("Footprint"):
        entry["Footprint"] = reviews[a.part_id]["Footprint"]
    reviews[a.part_id] = entry
    save(REVIEWS, reviews)
    print(f"{a.part_id}: {a.status} by {a.by} -> {os.path.relpath(REVIEWS, ROOT)}")
    if not a.no_rebuild:
        rebuild()
        r = get_row(a.part_id)
        print(f"rebuilt; {a.part_id} Review_Status={r['Review_Status'] if r else '?'}")


def cmd_show(a):
    row = get_row(a.part_id)
    if row is None:
        raise SystemExit(f"{a.part_id}: not found")
    w = max(len(k) for k in row)
    for k, v in row.items():
        if v not in (None, ""):
            print(f"{k:<{w}}  {v}")
    rv = load(REVIEWS, {}).get(a.part_id)
    if rv:
        print(f"{'reviews.json':<{w}}  {json.dumps(rv, ensure_ascii=False)}")


def cmd_list(a):
    where, args = [], []
    if a.table:
        if a.table not in S.TABLES:
            raise SystemExit(f"unknown table {a.table}; one of: {', '.join(S.TABLES)}")
        where.append('"Table_Name" = ?'); args.append(a.table)
    if a.status:
        where.append('COALESCE("Review_Status", \'Unreviewed\') = ?'); args.append(a.status)
    if a.lifecycle:
        where.append('"Lifecycle" = ?'); args.append(a.lifecycle)
    if a.lib:
        where.append('"KiCad_Library" = ?'); args.append(a.lib)
    if a.no_footprint:
        where.append('COALESCE("Footprint", \'\') = \'\'')
    sql = ('SELECT "Table_Name", "Part_ID", "Symbol", "MPN", "Lifecycle", "Packaging", "DK_Stock", "Review_Status" '
           'FROM "All_Parts"' + (" WHERE " + " AND ".join(where) if where else "") +
           ' ORDER BY "Table_Name", "Part_ID"')
    rows = db().execute(sql, args).fetchall()
    for r in rows[:a.limit]:
        print(f"{r['Part_ID']:<34} {r['Symbol']:<45} {r['MPN'] or '-':<24} {r['Lifecycle'] or '':<22} "
              f"{r['Packaging'] or '':<10} {r['DK_Stock'] if r['DK_Stock'] is not None else '':>8} {r['Review_Status']}")
    print(f"{len(rows)} rows" + (f" (showing {a.limit})" if len(rows) > a.limit else ""))


def cmd_add(a):
    if ":" not in a.symbol:
        raise SystemExit("symbol must be <Lib>:<Name>, e.g. Connector:USB_C_Receptacle_USB2.0_16P")
    lib, name = a.symbol.split(":", 1)
    con = sqlite3.connect(CATALOG)
    known = con.execute("SELECT footprint, is_usb FROM symbols WHERE library=? AND name=?", (lib, name)).fetchone()
    if known is None and not a.force:
        raise SystemExit(f"{a.symbol}: not in catalog.sqlite (KiCad stock symbols); use --force for custom symbols")
    table = a.table
    if not table and known and known[1]:
        table = "Connectors_USB"
    if not table:
        try:
            table = S.table_for_library(lib)
        except KeyError:
            raise SystemExit(f"{lib}: no table mapping; pass --table (one of {', '.join(S.TABLES)})")
    if table not in S.TABLES:
        raise SystemExit(f"unknown table {table}")
    manual = load(MANUAL, [])
    manual = [m for m in manual if not (m["Symbol"] == a.symbol and m["MPN"].upper() == a.mpn.upper())]
    entry = dict(Symbol=a.symbol, MPN=a.mpn, Table=table, Added_By=a.by or "", Added_Date=dt.date.today().isoformat())
    if a.footprint:
        entry["Footprint"] = a.footprint
    if a.notes:
        entry["Notes"] = a.notes
    manual.append(entry)
    save(MANUAL, manual)
    pid = f"{S.TABLE_PREFIX[table]}-{a.mpn}"
    print(f"added {a.symbol} {a.mpn} -> {os.path.relpath(MANUAL, ROOT)} (Part_ID {pid}, table {table})")
    if not a.footprint and not (known and known[0]):
        print("note: no footprint (symbol has no default); the part stays hidden from KiCad until one is set")
    if not a.no_rebuild:
        rebuild()
        r = get_row(pid) or get_row(f"{pid}@{name}")
        if r:
            print(f"rebuilt; {r['Part_ID']} Lifecycle={r['Lifecycle']} Supplier_PN={r['Supplier_PN'] or '-'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("review", help="record an engineering review")
    p.add_argument("part_id")
    p.add_argument("--status", required=True, choices=S.REVIEW_STATES)
    p.add_argument("--by", required=True)
    p.add_argument("--notes", default="")
    p.add_argument("--footprint", help="assign a footprint (Lib:Name) for this part")
    p.add_argument("--force", action="store_true", help="approve despite missing MPN/footprint/obsolete")
    p.add_argument("--no-rebuild", action="store_true")
    p.set_defaults(fn=cmd_review)
    p = sub.add_parser("show", help="show one part")
    p.add_argument("part_id")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("list", help="list parts")
    p.add_argument("--table")
    p.add_argument("--status", choices=S.REVIEW_STATES)
    p.add_argument("--lifecycle")
    p.add_argument("--lib", help="KiCad symbol library")
    p.add_argument("--no-footprint", action="store_true", help="only rows without footprint")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(fn=cmd_list)
    p = sub.add_parser("add", help="add a part manually")
    p.add_argument("symbol")
    p.add_argument("mpn")
    p.add_argument("--footprint")
    p.add_argument("--table")
    p.add_argument("--by", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--force", action="store_true", help="allow symbols not in the KiCad catalog")
    p.add_argument("--no-rebuild", action="store_true")
    p.set_defaults(fn=cmd_add)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
