#!/usr/bin/env python3
"""Spec-driven builder for the commodity database tables.

    python tools/build_commodity.py <Table|all> [--offline] [--refresh] [--budget N] [--lib DIR]

--lib DIR (default kicad_dbl_library) selects the library folder: specs are read from
DIR/specs, output goes to DIR/seed/{generated,locks} and DIR/reports, and the column
list / table list come from DIR/seed/schema.py, or else the single DIR/*_schema.py
(e.g. application_dbl/app_schema.py). That schema module may also define ORDERABLE,
the packaging preference used for eligibility (default: Cut Tape, then Bulk).

A spec is a Python module ``kicad_dbl_library/specs/<Table>.py`` that defines:

    TABLE    = "LEDs"
    QUERIES  = [dict(keywords="...", mfr_ids=[...], in_stock=True,
                     split=None | dict(prefix="...", alphabet="0123..."))]
    def slots():                 -> list of slot dicts; each has a unique "part_id"
    def accept(sp, slot):        -> bool   (sp = dk_client.slim(product))
    def rank(sp, slot):          -> tuple  (lower is better; build adds orderable/stock tie-breaks)
    def make_row(sp, slot, var): -> row dict (var = chosen Cut Tape/Bulk variation)

Behaviour
* Candidates come from the DigiKey cache (tools/cache/dk_cache.sqlite); with
  --offline nothing is fetched, cache misses are reported.
* Only Active parts with a Cut Tape or Bulk variation in stock are eligible.
* seed/locks/<Table>.json pins Part_ID -> MPN. A locked slot keeps its existing row unless
  fresh data shows the MPN is no longer eligible; then the old row is marked
  Deprecated (Superseded_By = new Part_ID "<part_id>-R<n>") and a replacement added.
  Rows are never deleted.
* --refresh updates DK_Stock / DK_Status / DK_Checked of locked rows from fresh data.
* Writes seed/generated/<Table>.json and reports/<Table>.md (gaps, changes).
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "kicad_dbl_library")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, LIB)
sys.path.insert(0, os.path.join(LIB, "specs"))

import dk_client  # noqa: E402
from seed.schema import COLUMN_NAMES, TABLES  # noqa: E402

GEN = os.path.join(LIB, "seed", "generated")
LOCKS = os.path.join(LIB, "seed", "locks")
SPECS = os.path.join(LIB, "specs")
REPORTS = os.path.join(LIB, "reports")
ORDERABLE = None  # None -> dk_client.orderable_variation (Cut Tape, Bulk)


def use_lib(lib_dir):
    """Point the engine at another library folder (see --lib). Default lib is untouched."""
    global LIB, GEN, LOCKS, SPECS, REPORTS, COLUMN_NAMES, TABLES, ORDERABLE
    LIB = os.path.abspath(lib_dir if os.path.isabs(lib_dir) else os.path.join(ROOT, lib_dir))
    if LIB == os.path.join(ROOT, "kicad_dbl_library"):
        return
    cands = [os.path.join(LIB, "seed", "schema.py")]
    if not os.path.exists(cands[0]):
        cands = sorted(os.path.join(LIB, f) for f in os.listdir(LIB) if f.endswith("_schema.py"))
    if len(cands) != 1:
        raise SystemExit(f"--lib {lib_dir}: need seed/schema.py or exactly one *_schema.py, found {cands}")
    spec = importlib.util.spec_from_file_location("lib_schema", cands[0])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    COLUMN_NAMES, TABLES = list(mod.COLUMN_NAMES), list(mod.TABLES)
    ORDERABLE = getattr(mod, "ORDERABLE", None)
    GEN, LOCKS = os.path.join(LIB, "seed", "generated"), os.path.join(LIB, "seed", "locks")
    SPECS, REPORTS = os.path.join(LIB, "specs"), os.path.join(LIB, "reports")
    sys.path.insert(0, SPECS)
    sys.modules.pop("_common", None)  # specs of this lib import their own _common


def orderable(sp):
    if ORDERABLE is None:
        return dk_client.orderable_variation(sp)
    for want in ORDERABLE:
        for v in sp["variations"]:
            if want in v["pkg"]:
                return v
    return None


def load_spec(table):
    path = os.path.join(SPECS, f"{table}.py")
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(f"spec_{table}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def harvest(dk, spec):
    cands, misses = {}, []
    for q in spec.QUERIES:
        mfr = q.get("mfr_ids")
        stock = q.get("in_stock", True)
        if q.get("split"):
            s = q["split"]
            prods = dk.keyword_split(s["prefix"], mfr, stock, s.get("alphabet", "0123456789RKM"),
                                     s.get("depth", 3))
            total = len(prods)
        else:
            prods, total = dk.keyword_all(q["keywords"], mfr, stock)
        if dk.offline and not prods:
            misses.append(q.get("keywords") or q["split"]["prefix"])
        for p in prods:
            sp = dk_client.slim(p)
            cands[sp["mpn"]] = sp
    return cands, misses


def eligible(sp):
    if sp["status"] != "Active":
        return None
    v = orderable(sp)
    if not v or (v.get("qty") or 0) <= 0:
        return None
    return v


def pick(spec, cands, slot, exclude=()):
    best = None
    for sp in cands.values():
        if sp["mpn"] in exclude or not spec.accept(sp, slot):
            continue
        v = eligible(sp)
        if not v:
            continue
        pk = "Cut Tape" not in v["pkg"] if ORDERABLE is None else \
            next(i for i, w in enumerate(ORDERABLE) if w in v["pkg"])
        key = (tuple(spec.rank(sp, slot)), pk, -(v.get("qty") or 0), sp["mpn"])
        if best is None or key < best[0]:
            best = (key, sp, v)
    return (best[1], best[2]) if best else (None, None)


def finish_row(row, sp, var):
    row.setdefault("Manufacturer", sp["mfr"])
    row.setdefault("MPN", sp["mpn"])
    row.setdefault("Datasheet", dk_client.https(sp.get("datasheet")))
    row.update(Supplier="DigiKey", Supplier_PN=var["dkpn"], DK_Status=sp["status"],
               DK_Stock=int(var.get("qty") or 0), DK_Checked=dt.date.today().isoformat())
    row.setdefault("Status", "Active")
    extra = set(row) - set(COLUMN_NAMES)
    if extra:
        raise SystemExit(f"{row.get('Part_ID')}: unknown columns {sorted(extra)}")
    return row


def build(table, dk, refresh=False):
    spec = load_spec(table)
    if spec is None:
        print(f"{table}: no spec, skipped")
        return
    lock_path = os.path.join(LOCKS, f"{table}.json")
    locks = json.load(open(lock_path)) if os.path.exists(lock_path) else {}
    gen_path = os.path.join(GEN, f"{table}.json")
    rows = {r["Part_ID"]: r for r in (json.load(open(gen_path, encoding="utf-8")) if os.path.exists(gen_path) else [])}
    cands, misses = harvest(dk, spec)
    used = {r["MPN"] for r in rows.values() if r.get("Status", "Active") == "Active"}
    log, gaps = [], []
    for slot in spec.slots():
        pid = slot["part_id"]
        cur = rows.get(pid)
        # follow the supersede chain to the current live row for this slot
        while cur and cur.get("Status") == "Deprecated" and cur.get("Superseded_By") in rows:
            cur = rows[cur["Superseded_By"]]
        if cur and cur.get("Status", "Active") == "Active":
            fresh = cands.get(cur["MPN"])
            if fresh is None:
                continue  # no fresh data -> keep as is
            var = eligible(fresh)
            if var and spec.accept(fresh, slot):
                if refresh:
                    cur.update(DK_Status=fresh["status"], DK_Stock=int(var.get("qty") or 0),
                               DK_Checked=dt.date.today().isoformat())
                continue
            # locked part no longer eligible -> deprecate and replace
            sp, var = pick(spec, cands, slot, exclude=used)
            n = 2
            while f"{pid}-R{n}" in rows:
                n += 1
            new_pid = f"{pid}-R{n}"
            cur["Status"] = "Deprecated"
            if sp:
                cur["Superseded_By"] = new_pid
                r = finish_row(spec.make_row(sp, slot, var), sp, var)
                r["Part_ID"] = new_pid
                rows[new_pid] = r
                locks[new_pid] = sp["mpn"]
                used.add(sp["mpn"])
                log.append(f"- {cur['Part_ID']} {cur['MPN']} no longer eligible -> {new_pid} {sp['mpn']}")
            else:
                log.append(f"- {cur['Part_ID']} {cur['MPN']} no longer eligible; no replacement found")
            continue
        sp, var = pick(spec, cands, slot, exclude=used)
        if not sp:
            gaps.append(pid)
            continue
        r = finish_row(spec.make_row(sp, slot, var), sp, var)
        r["Part_ID"] = pid
        rows[pid] = r
        locks[pid] = sp["mpn"]
        used.add(sp["mpn"])
        log.append(f"- added {pid} {sp['mpn']} ({sp['mfr']}) {var['dkpn']}")
    out = sorted(rows.values(), key=lambda r: r["Part_ID"])
    os.makedirs(GEN, exist_ok=True)
    json.dump(out, open(gen_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.makedirs(LOCKS, exist_ok=True)
    json.dump(locks, open(lock_path, "w"), indent=1, sort_keys=True)
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, f"{table}.md"), "w", encoding="utf-8") as f:
        f.write(f"# {table}\n\nBuilt {dt.date.today().isoformat()}: {len(out)} rows, "
                f"{len(cands)} candidates, {len(gaps)} gaps.\n\n")
        if misses:
            f.write("## Cache misses (run online)\n" + "\n".join(f"- `{m}`" for m in misses) + "\n\n")
        f.write("## Changes\n" + ("\n".join(log) or "- none") + "\n\n")
        f.write("## Gaps (no eligible stocked part)\n" + ("\n".join(f"- {g}" for g in gaps) or "- none") + "\n")
    print(f"{table}: {len(out)} rows, {len(log)} changes, {len(gaps)} gaps, {len(misses)} cache misses, "
          f"calls used {dk.budget.used}, remaining {dk.budget.remaining}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("table")
    ap.add_argument("--offline", action="store_true", help="cache only, no API calls")
    ap.add_argument("--refresh", action="store_true", help="update stock/status of locked rows")
    ap.add_argument("--budget", type=int, default=900)
    ap.add_argument("--lib", default="kicad_dbl_library",
                    help="library folder holding specs/, seed/ and reports/ (default kicad_dbl_library)")
    a = ap.parse_args()
    use_lib(a.lib)
    dk = dk_client.DigiKey(dk_client.Budget(a.budget), offline=a.offline)
    tables = TABLES if a.table == "all" else [a.table]
    for t in tables:
        try:
            build(t, dk, a.refresh)
        except dk_client.QuotaExhausted as e:
            print(f"Stopped: {e}")
            break


if __name__ == "__main__":
    main()
