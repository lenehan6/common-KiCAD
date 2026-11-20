#!/usr/bin/env python3
"""Build parts.sqlite for the KiCad database library from the seed modules.

Usage:  python init_db.py [--db PATH]

Drops and recreates every table listed in seed/schema.py and loads the rows
exported by each seed module (``ROWS = {table: [row, ...]}``).
"""
import argparse
import importlib
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from seed.schema import COLUMNS, COLUMN_NAMES, TABLES  # noqa: E402

SEED_MODULES = [
    "seed.resistors_thin",
    "seed.resistors_thick",
    "seed.capacitors",
    "seed.capacitors_bulk",
    "seed.inductors",
]

REQUIRED = ("Part_ID", "Symbol", "Footprint", "Value")


def collect_rows():
    rows = {t: [] for t in TABLES}
    for modname in SEED_MODULES:
        mod = importlib.import_module(modname)
        for table, items in mod.ROWS.items():
            if table not in rows:
                raise SystemExit(f"{modname}: unknown table {table!r}")
            for r in items:
                extra = set(r) - set(COLUMN_NAMES)
                if extra:
                    raise SystemExit(f"{modname}: {r.get('Part_ID')}: unknown columns {sorted(extra)}")
                missing = [c for c in REQUIRED if not r.get(c)]
                if missing:
                    raise SystemExit(f"{modname}: {r.get('Part_ID')}: missing {missing}")
            rows[table].extend(items)
    return rows


def build(db_path):
    rows = collect_rows()
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    cols_sql = ",\n    ".join(f'"{n}" {t}' for n, t in COLUMNS)
    placeholders = ",".join("?" for _ in COLUMN_NAMES)
    collist = ",".join(f'"{c}"' for c in COLUMN_NAMES)
    total = 0
    for table in TABLES:
        con.execute(f'CREATE TABLE "{table}" (\n    {cols_sql}\n)')
        con.execute(f'CREATE INDEX "idx_{table}_MPN" ON "{table}"("MPN")')
        con.execute(f'CREATE INDEX "idx_{table}_Value" ON "{table}"("Value")')
        data = [tuple(r.get(c) for c in COLUMN_NAMES) for r in rows[table]]
        con.executemany(f'INSERT INTO "{table}" ({collist}) VALUES ({placeholders})', data)
        print(f"  {table:<22} {len(data):>5} rows")
        total += len(data)
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
