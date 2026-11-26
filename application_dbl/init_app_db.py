#!/usr/bin/env python3
"""Build application_dbl/application.sqlite (the application-parts KiCad database library).

    python3 application_dbl/init_app_db.py [--db PATH] [--fetch-manual N] [--quiet]

Sources (all optional; the build is re-runnable and works on partial data):
  prefill/matches.json             {"Lib:Symbol": [slim DigiKey products]}  (daily prefill, tools/prefill_app.py)
  catalog.sqlite                   KiCad symbol catalog (footprint, fp_filters, description, datasheet)
  seed/generated/<Table>.json      spec-built rows (e.g. Connectors_USB, tools/build_commodity.py --lib application_dbl)
  manual_parts.json                manual additions (tools/app_part.py add)
  reviews.json                     {Part_ID: {Review_Status, Reviewed_By, Review_Date, Review_Notes[, Footprint]}}
  seed/locks/_prefill.json         Symbol -> chosen MPN (keeps Part_IDs stable between rebuilds; written here)

One row per prefilled symbol. Best DigiKey hit: lifecycle (Active > NRND/Last Time Buy >
Discontinued at DigiKey > Obsolete), then package matching the KiCad footprint, then packaging
(Cut Tape > Bulk > Tube > Tray > other; Tape & Reel / Digi-Reel never), then stock.
Symbols processed by the prefill without a DigiKey hit get a row with MPN "" and Lifecycle
"Not found at DigiKey" so the review list is complete.

Views per table:  <Table>_Active    (application_parts.kicad_dbl)
                  <Table>_Approved  (application_parts_approved.kicad_dbl)
plus All_Parts (UNION of all tables with a Table_Name column) for tools/app_part.py.
"""
import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import app_schema as S  # noqa: E402

DB = os.path.join(HERE, "application.sqlite")
CATALOG = os.path.join(HERE, "catalog.sqlite")
MATCHES = os.path.join(HERE, "prefill", "matches.json")
GENERATED = os.path.join(HERE, "seed", "generated")
PREFILL_LOCKS = os.path.join(HERE, "seed", "locks", "_prefill.json")
REVIEWS = os.path.join(HERE, "reviews.json")
MANUAL = os.path.join(HERE, "manual_parts.json")

NOT_FOUND = "Not found at DigiKey"
PACK_ORDER = ("Cut Tape", "Bulk", "Tube", "Tray")
NEVER = ("Tape & Reel", "Digi-Reel")
# DigiKey params that are not useful in Key_Params (packaging / admin / shown elsewhere)
SKIP_PARAMS = {"Packaging", "Part Status", "Product Status", "Base Product Number", "Supplier Device Package",
               "Package / Case", "Mounting Type", "Grade", "Qualification", "Series", "Moisture Sensitivity Level (MSL)",
               "ECCN", "HTSUS", "REACH Status", "RoHS Status", "Programmable", "Color", "Material Flammability Rating",
               "Ingress Protection", "Shell Finish", "Shell Size, MIL", "Cable Opening", "Mounting Feature"}


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def status_tier(status):
    s = (status or "").lower()
    if s == "active":
        return 0
    if "not for new" in s or "nrnd" in s or "last time" in s:
        return 1
    if "discontinued" in s:
        return 2
    if "obsolete" in s:
        return 3
    return 1  # unknown / preliminary


def pack_tier(pkg):
    if any(n in pkg for n in NEVER):
        return None
    for i, w in enumerate(PACK_ORDER):
        if w in pkg:
            return i
    return len(PACK_ORDER)  # Box, Bag, Strip, Retail Package ...


def best_variation(sp):
    """(variation, tier) of the preferred non-reel packaging, or (None, None)."""
    best = None
    for v in sp.get("variations") or []:
        t = pack_tier(v.get("pkg") or "")
        if t is None:
            continue
        k = (t, -(v.get("qty") or 0))
        if best is None or k < best[0]:
            best = (k, v)
    return (best[1], best[0][0]) if best else (None, None)


def _parts(s):
    return {p for p in re.split(r"[^A-Z0-9.]+", (s or "").upper()) if p}


def package_match(sp, footprint):
    """1 if a DigiKey package token (e.g. 'SOT-23-5', '8-SOIC') fits the KiCad footprint name."""
    if not footprint:
        return 0
    fp = _parts(footprint.split(":")[-1])
    for key in ("Supplier Device Package", "Package / Case"):
        for tok in re.split(r"[,(]", sp["params"].get(key) or ""):
            parts = _parts(tok) - {"MM", "METRIC"}
            if parts and len(parts) >= 2 and parts <= fp:
                return 1
    return 0


def key_params(sp, limit=8):
    out = []
    for k, v in (sp.get("params") or {}).items():
        if k in SKIP_PARAMS or v in (None, "", "-"):
            continue
        out.append(f"{k}={v[:40]}")
        if len(out) >= limit:
            break
    return "; ".join(out)


def pkg_text(sp):
    p = sp.get("params") or {}
    for k in ("Supplier Device Package", "Package / Case"):
        if p.get(k) and p[k] != "-":
            return p[k]
    return ""


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def rank_key(sp, footprint, name=""):
    v, t = best_variation(sp)
    exact = 1 if name and norm(sp["mpn"]) == norm(name) else 0
    return (status_tier(sp["status"]), -exact, -package_match(sp, footprint), 9 if t is None else t,
            -((v or {}).get("qty") or 0), sp["mpn"])


def load_catalog():
    con = sqlite3.connect(CATALOG)
    con.row_factory = sqlite3.Row
    sym = {f"{r['library']}:{r['name']}": dict(r) for r in con.execute("SELECT * FROM symbols")}
    app_libs = [r[0] for r in con.execute("SELECT name FROM libraries WHERE grp='application'")]
    con.close()
    return sym, app_libs


def dk_fields(sp, var, checked):
    if sp is None:
        return dict(Supplier="", Supplier_PN="", DK_Status="", DK_Stock=None, DK_Checked="", Packaging="")
    if var is None:
        reel = max((v.get("qty") or 0 for v in sp.get("variations") or []), default=0)
        return dict(Supplier="DigiKey", Supplier_PN="", DK_Status=sp["status"], DK_Stock=reel, DK_Checked=checked,
                    Packaging="Tape & Reel only" if sp.get("variations") else "")
    return dict(Supplier="DigiKey", Supplier_PN=var["dkpn"], DK_Status=sp["status"], DK_Stock=int(var.get("qty") or 0),
                DK_Checked=checked, Packaging=re.sub(r"\s*\(.*\)$", "", var["pkg"]))


def https(url):
    if not url:
        return url or ""
    return ("https:" + url) if url.startswith("//") else url.replace("http://", "https://", 1)


def base_row(key, cat, table):
    lib, name = key.split(":", 1)
    return dict(Symbol=key, Footprint=cat.get("footprint") or "", Value=name, Description=cat.get("description") or "",
                Keywords=cat.get("keywords") or "", Manufacturer=cat.get("manufacturer_hint") or "", MPN="",
                Package="", Datasheet=https(cat.get("datasheet") if cat.get("datasheet") not in ("~", None) else ""),
                FP_Filter=cat.get("fp_filters") or "", Status="Active", Pinout="",
                Pinout_Source=f"KiCad symbol {key} (pin mapping not yet verified against datasheet)",
                KiCad_Library=lib, Lifecycle=NOT_FOUND, Key_Params="", Candidates="",
                Review_Status="Unreviewed", Reviewed_By="", Review_Date="", Review_Notes="", _auto=[], _table=table)


def fill_from_dk(row, sp, checked, others=()):
    var, _ = best_variation(sp)
    row.update(Value=sp["mpn"], MPN=sp["mpn"], Manufacturer=sp["mfr"], Package=pkg_text(sp),
               Datasheet=https(sp.get("datasheet")) or row["Datasheet"], Lifecycle=sp["status"],
               Key_Params=key_params(sp), **dk_fields(sp, var, checked))
    if not row["Description"]:
        row["Description"] = sp.get("detail") or sp.get("desc") or ""
    row["Candidates"] = "; ".join(f"{o['mpn']} ({o['status']})" for o in others[:10])
    if var is None:
        row["_auto"].append("no Cut Tape/Bulk/Tube/Tray variation at DigiKey (reel only)")
    if status_tier(sp["status"]) > 0:
        row["_auto"].append(f"lifecycle {sp['status']}")


def build_prefill(catalog, matches, locks, checked, used_ids):
    rows, skipped = [], []
    # Order in which symbols compete for an MPN (each MPN -> one Part_ID): locked symbols first
    # (stable Part_IDs), then symbols that have a hit equal to their own name, then the
    # most constrained (fewest hits) first, so a generic stem symbol does not grab a sibling's part.
    def order(k):
        name = k.split(":", 1)[1]
        hits = matches.get(k) or []
        exact = any(norm(h["mpn"]) == norm(name) for h in hits)
        return (k not in locks, not exact, len(hits), k)
    keys = sorted(matches, key=order)
    for key in keys:
        cat = catalog.get(key)
        if cat is None:
            skipped.append(key)
            continue
        lib = key.split(":", 1)[0]
        table = S.table_for_library(lib)
        prefix = S.TABLE_PREFIX[table]
        row = base_row(key, cat, table)
        if not row["Footprint"]:
            row["_auto"].append(f"KiCad symbol has no default footprint (fp_filters: {row['FP_Filter'] or '-'}); "
                                "hidden from KiCad until a Footprint is set (reviews.json 'Footprint')")
        hits = list({h["mpn"]: h for h in matches.get(key) or []}.values())
        if not hits:
            row["Part_ID"] = f"{prefix}-SYM-{key.split(':', 1)[1]}"
            used_ids.add(row["Part_ID"])
            rows.append(row)
            continue
        hits.sort(key=lambda h: rank_key(h, row["Footprint"], key.split(":", 1)[1]))
        chosen = None
        locked = locks.get(key)
        if locked:
            lh = next((h for h in hits if h["mpn"] == locked), None)
            if lh and status_tier(lh["status"]) <= status_tier(hits[0]["status"]):
                chosen = lh
            elif lh is None:
                row["_auto"].append(f"previous choice {locked} no longer in DigiKey matches")
            else:
                row["_auto"].append(f"previous choice {locked} ({lh['status']}) replaced by better lifecycle")
        if chosen is None:
            chosen = next((h for h in hits if f"{prefix}-{h['mpn']}" not in used_ids), None)
        pid = f"{prefix}-{(chosen or hits[0])['mpn']}"
        if chosen is None or pid in used_ids:  # every hit already used by another symbol
            chosen = chosen or hits[0]
            pid = f"{prefix}-{chosen['mpn']}@{key.split(':', 1)[1]}"
        row["Part_ID"] = pid
        used_ids.add(pid)
        locks[key] = chosen["mpn"]
        fill_from_dk(row, chosen, checked, [h for h in hits if h is not chosen])
        rows.append(row)
    return rows, skipped


def load_generated(table, used_ids):
    rows = []
    for r in load_json(os.path.join(GENERATED, f"{table}.json"), []):
        extra = set(r) - set(S.COLUMN_NAMES)
        if extra:
            raise SystemExit(f"{table}: {r.get('Part_ID')}: unknown columns {sorted(extra)}")
        r = {c: r.get(c) for c in S.COLUMN_NAMES} | {"_auto": [], "_table": table}
        r["Review_Status"] = r.get("Review_Status") or "Unreviewed"
        if r["Part_ID"] in used_ids:
            raise SystemExit(f"{table}: duplicate Part_ID {r['Part_ID']}")
        used_ids.add(r["Part_ID"])
        rows.append(r)
    return rows


def dk_index(matches):
    idx = {}
    for hits in matches.values():
        for h in hits or []:
            idx.setdefault(h["mpn"].upper(), h)
    return idx


_KW_INDEX = None


def cached_details(mpn):
    """slim product from the DigiKey cache (no API call): productdetails entry, else any cached
    keyword response containing the MPN. None when the cache does not know it."""
    global _KW_INDEX
    try:
        import dk_client
        dk = dk_client.DigiKey(offline=True)
        d = dk.details(mpn, max_age_days=None)
        if d and d.get("Product"):
            return dk_client.slim(d["Product"])
        if _KW_INDEX is None:
            _KW_INDEX = {}
            for req, body in dk.db.execute("SELECT req, body FROM cache"):
                if '"kind": "keyword"' not in req:
                    continue
                res = dk_client._unpack(body) or {}
                for p in (res.get("Products") or []) + (res.get("ExactMatches") or []):
                    _KW_INDEX.setdefault(p["ManufacturerProductNumber"].upper(), p)
        p = _KW_INDEX.get(mpn.upper())
        return dk_client.slim(p) if p else None
    except Exception:  # noqa: BLE001 - cache is optional
        return None


def fetch_details(mpns, budget):
    import dk_client
    dk = dk_client.DigiKey(dk_client.Budget(budget))
    for m in mpns:
        try:
            dk.details(m)
        except dk_client.QuotaExhausted as e:
            print(f"fetch-manual stopped: {e}")
            break


def build_manual(manual, catalog, matches, checked, used_ids, rows_by_id):
    idx = dk_index(matches)
    out = []
    for m in manual:
        key, mpn = m["Symbol"], m["MPN"].strip()
        lib = key.split(":", 1)[0]
        table = m.get("Table") or ("Connectors_USB" if (catalog.get(key) or {}).get("is_usb")
                                   else S.table_for_library(lib))
        if table not in S.TABLE_PREFIX:
            raise SystemExit(f"manual_parts.json: unknown table {table} for {key} {mpn}")
        cat = catalog.get(key, {})
        row = base_row(key, cat, table)
        if m.get("Footprint"):
            row["Footprint"] = m["Footprint"]
        sp = idx.get(mpn.upper()) or cached_details(mpn)
        if sp:
            fill_from_dk(row, sp, checked)
        else:
            row.update(Value=mpn, MPN=mpn, Manufacturer=m.get("Manufacturer") or row["Manufacturer"],
                       Lifecycle="Manual - not yet checked at DigiKey")
            row["_auto"].append("manual addition; no cached DigiKey data yet (init_app_db.py --fetch-manual N)")
        row["_auto"].append(f"manual addition by {m.get('Added_By') or '?'} {m.get('Added_Date') or ''}".strip())
        if m.get("Notes"):
            row["_auto"].append(m["Notes"])
        if not row["Footprint"]:
            row["_auto"].append("no footprint: set one with app_part.py add --footprint or reviews.json 'Footprint'")
        pid = f"{S.TABLE_PREFIX[table]}-{mpn}"
        if pid in rows_by_id and rows_by_id[pid]["Symbol"] == key:
            rows_by_id[pid]["_replaced"] = True  # manual entry overrides the prefill row of the same part
        elif pid in used_ids:
            pid = f"{pid}@{key.split(':', 1)[1]}"
        row["Part_ID"] = pid
        used_ids.add(pid)
        out.append(row)
    return out


def apply_reviews(rows, reviews):
    unknown = set(reviews) - {r["Part_ID"] for r in rows}
    for r in rows:
        rv = reviews.get(r["Part_ID"])
        if rv:
            st = rv.get("Review_Status", "Unreviewed")
            if st not in S.REVIEW_STATES:
                raise SystemExit(f"reviews.json {r['Part_ID']}: bad Review_Status {st!r}")
            r.update(Review_Status=st, Reviewed_By=rv.get("Reviewed_By", ""), Review_Date=rv.get("Review_Date", ""),
                     Review_Notes=rv.get("Review_Notes", ""))
            if rv.get("Footprint"):
                r["Footprint"] = rv["Footprint"]
                r["_auto"] = [a for a in r["_auto"] if "no default footprint" not in a and "no footprint" not in a]
        auto = "; ".join(r.pop("_auto", []))
        if auto:
            r["Review_Notes"] = (r["Review_Notes"] + " | " if r.get("Review_Notes") else "") + "[auto] " + auto
    return unknown


def write_db(db_path, rows):
    tmp = db_path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    cols_sql = ",\n    ".join(f'"{n}" {t}' for n, t in S.COLUMNS)
    collist = ",".join(f'"{c}"' for c in S.COLUMN_NAMES)
    ph = ",".join("?" for _ in S.COLUMN_NAMES)
    stats = {}
    for table in S.TABLES:
        trows = [r for r in rows if r["_table"] == table]
        con.execute(f'CREATE TABLE "{table}" (\n    {cols_sql}\n)')
        con.execute(f'CREATE INDEX "idx_{table}_MPN" ON "{table}"("MPN")')
        con.execute(f'CREATE INDEX "idx_{table}_Symbol" ON "{table}"("Symbol")')
        con.execute(
            f'CREATE VIEW "{S.active_view(table)}" AS SELECT * FROM "{table}" WHERE '
            f"COALESCE(\"Lifecycle\", '') <> 'Obsolete' AND COALESCE(\"MPN\", '') <> '' "
            f"AND COALESCE(\"Footprint\", '') <> '' "
            f"AND COALESCE(\"Review_Status\", 'Unreviewed') NOT IN ('Rejected', 'Obsolete') "
            f"AND COALESCE(\"Status\", 'Active') <> 'Obsolete'")
        con.execute(
            f'CREATE VIEW "{S.approved_view(table)}" AS SELECT * FROM "{table}" WHERE '
            f"\"Review_Status\" = 'Approved' AND COALESCE(\"Footprint\", '') <> '' "
            f"AND COALESCE(\"Status\", 'Active') <> 'Obsolete'")
        con.executemany(f'INSERT INTO "{table}" ({collist}) VALUES ({ph})',
                        [tuple(r.get(c) for c in S.COLUMN_NAMES) for r in trows])
        st = stats[table] = {}
        st["rows"] = len(trows)
        st["active"] = con.execute(f'SELECT COUNT(*) FROM "{S.active_view(table)}"').fetchone()[0]
        st["approved"] = con.execute(f'SELECT COUNT(*) FROM "{S.approved_view(table)}"').fetchone()[0]
        st["no_match"] = sum(1 for r in trows if not r.get("MPN"))
        st["no_fp"] = sum(1 for r in trows if not r.get("Footprint"))
        st["obsolete"] = sum(1 for r in trows if r.get("Lifecycle") == "Obsolete")
    union = " UNION ALL ".join(f"SELECT '{t}' AS Table_Name, * FROM \"{t}\"" for t in S.TABLES)
    con.execute(f'CREATE VIEW "All_Parts" AS {union}')
    con.execute('CREATE TABLE "_meta" (key TEXT PRIMARY KEY, value TEXT)')
    con.executemany('INSERT INTO "_meta" VALUES (?,?)',
                    [("built_utc", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")),
                     ("rows", str(len(rows)))])
    con.commit()
    con.execute("VACUUM")
    con.close()
    os.replace(tmp, db_path)
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DB)
    ap.add_argument("--fetch-manual", type=int, default=0, metavar="N",
                    help="spend up to N DigiKey calls fetching details of manual parts missing from the cache")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    catalog, app_libs = load_catalog()
    S.check_mapping(app_libs)  # fail loudly on an unmapped application library
    matches = load_json(MATCHES, {})
    checked = (dt.date.fromtimestamp(os.path.getmtime(MATCHES)).isoformat() if os.path.exists(MATCHES) else "")
    locks = load_json(PREFILL_LOCKS, {})
    reviews = load_json(REVIEWS, {})
    manual = load_json(MANUAL, [])

    if a.fetch_manual and manual:
        idx = dk_index(matches)
        todo = [m["MPN"] for m in manual if m["MPN"].upper() not in idx and not cached_details(m["MPN"])]
        if todo:
            fetch_details(todo, a.fetch_manual)

    used = set()
    gen_rows = []
    for table in S.TABLES:
        gen_rows += load_generated(table, used)
    pre_rows, skipped = build_prefill(catalog, matches, locks, checked, used)
    by_id = {r["Part_ID"]: r for r in pre_rows}
    man_rows = build_manual(manual, catalog, matches, checked, used, by_id)
    pre_rows = [r for r in pre_rows if not r.get("_replaced")]
    for r in pre_rows:
        r.pop("_replaced", None)
    rows = gen_rows + pre_rows + man_rows
    unknown = apply_reviews(rows, reviews)

    os.makedirs(os.path.dirname(PREFILL_LOCKS), exist_ok=True)
    with open(PREFILL_LOCKS, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(locks.items())), f, indent=1, ensure_ascii=False)
    stats = write_db(a.db, rows)

    if not a.quiet:
        print(f"{'table':<24}{'rows':>7}{'active':>8}{'approved':>9}{'no-DK':>7}{'no-FP':>7}{'obsol':>7}")
        for t, st in stats.items():
            print(f"{t:<24}{st['rows']:>7}{st['active']:>8}{st['approved']:>9}{st['no_match']:>7}"
                  f"{st['no_fp']:>7}{st['obsolete']:>7}")
    tot = {k: sum(st[k] for st in stats.values()) for k in ("rows", "active", "approved", "no_match", "no_fp")}
    print(f"Wrote {a.db}: {tot['rows']} rows ({len(pre_rows)} prefill, {len(gen_rows)} spec-built, "
          f"{len(man_rows)} manual); {tot['active']} in *_Active, {tot['approved']} approved, "
          f"{tot['no_match']} without DigiKey match, {tot['no_fp']} without footprint (hidden from KiCad)")
    if skipped:
        print(f"warning: {len(skipped)} prefill symbols not in catalog.sqlite (skipped), e.g. {skipped[:3]}")
    if unknown:
        print(f"warning: reviews.json has {len(unknown)} Part_IDs not in the DB (kept in the file): "
              f"{sorted(unknown)[:5]}")


if __name__ == "__main__":
    main()
