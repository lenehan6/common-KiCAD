#!/usr/bin/env python3
"""Build parts.sqlite for the KiCad commodity database library.

Usage:  python init_db.py [--db PATH]

Creates every table in seed/schema.py, loads seed/generated/<Table>.json and
creates a "<Table>_Active" view per table (Status != 'Obsolete'), which is what
company_parts.kicad_dbl points KiCad at. Tables without a generated file are
created empty so the .kicad_dbl always resolves.
"""
import argparse
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from seed.schema import COLUMNS, COLUMN_NAMES, TABLES, view_name  # noqa: E402

GENERATED = os.path.join(HERE, "seed", "generated")
REQUIRED = ("Part_ID", "Symbol", "Footprint", "Value")


def load_rows(table):
    path = os.path.join(GENERATED, f"{table}.json")
    if not os.path.exists(path):
        return []
    rows = json.load(open(path, encoding="utf-8"))
    for r in rows:
        extra = set(r) - set(COLUMN_NAMES)
        if extra:
            raise SystemExit(f"{table}: {r.get('Part_ID')}: unknown columns {sorted(extra)}")
        missing = [c for c in REQUIRED if not r.get(c)]
        if missing:
            raise SystemExit(f"{table}: {r.get('Part_ID')}: missing {missing}")
        r.setdefault("Status", "Active")
    return rows


def build(db_path):
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    cols_sql = ",\n    ".join(f'"{n}" {t}' for n, t in COLUMNS)
    placeholders = ",".join("?" for _ in COLUMN_NAMES)
    collist = ",".join(f'"{c}"' for c in COLUMN_NAMES)
    total = 0
    for table in TABLES:
        rows = load_rows(table)
        con.execute(f'CREATE TABLE "{table}" (\n    {cols_sql}\n)')
        con.execute(f'CREATE INDEX "idx_{table}_MPN" ON "{table}"("MPN")')
        con.execute(f'CREATE INDEX "idx_{table}_Value" ON "{table}"("Value")')
        con.execute(f'CREATE VIEW "{view_name(table)}" AS SELECT * FROM "{table}" '
                    f"WHERE COALESCE(\"Status\", 'Active') <> 'Obsolete'")
        con.executemany(f'INSERT INTO "{table}" ({collist}) VALUES ({placeholders})',
                        [tuple(r.get(c) for c in COLUMN_NAMES) for r in rows])
        print(f"  {table:<30} {len(rows):>5} rows")
        total += len(rows)
    con.commit()
    con.execute("VACUUM")
    con.close()
    print(f"Wrote {db_path}: {total} parts in {len(TABLES)} tables")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.path.join(HERE, "parts.sqlite"))
    build(ap.parse_args().db)


if __name__ == "__main__":
    main()
