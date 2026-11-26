#!/usr/bin/env python3
"""Pre-fill the application-parts DB from the KiCad symbol catalog via DigiKey.

    python tools/prefill_app.py [--budget 900] [--max-priority 9] [--offline] [--report]

Strategy (quota-efficient "adaptive family harvest"):
  * Symbols come from application_dbl/catalog.sqlite (grp='application',
    name_kind in mpn/mpn_pattern), processed in priority order.
  * Their search stems are put in a trie. Starting from a coarse prefix (5 chars),
    one keyword call probes the prefix (and returns its first 50 hits). If DigiKey
    has <= 300 products for it, the prefix is harvested completely; otherwise only
    the child prefixes that actually lead to KiCad symbols are explored.
  * Every symbol's match_regex is then applied locally to the harvested MPNs.
  * Searches include non-stocked/obsolete parts so lifecycle is recorded.
  * All responses are cached (tools/cache/dk_cache.sqlite); progress is resumable;
    the run stops cleanly when --budget or the daily DigiKey quota is exhausted.

Output: application_dbl/prefill/matches.json  {"Lib:Symbol": [slim products...]}
        application_dbl/prefill/state.json    {"done_prefixes": [...], ...}
"""
import argparse
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import dk_client  # noqa: E402

APP = os.path.join(ROOT, "application_dbl")
OUT = os.path.join(APP, "prefill")
MIN_PREFIX = 5
WINDOW = dk_client.MAX_WINDOW


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def load_symbols(max_priority):
    con = sqlite3.connect(os.path.join(APP, "catalog.sqlite"))
    q = ("SELECT library, name, search_stem, match_regex, priority FROM symbols "
         "WHERE grp='application' AND name_kind IN ('mpn','mpn_pattern') AND search_stem IS NOT NULL "
         "AND priority <= ? ORDER BY priority, library, name")
    return [dict(lib=r[0], name=r[1], stem=r[2], rx=r[3], prio=r[4]) for r in con.execute(q, (max_priority,))]


def load_json(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--budget", type=int, default=900)
    ap.add_argument("--max-priority", type=int, default=9)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--report", action="store_true", help="only print progress")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    state_p, match_p = os.path.join(OUT, "state.json"), os.path.join(OUT, "matches.json")
    state = load_json(state_p, {"done_prefixes": [], "harvested_mpns": 0})
    matches = load_json(match_p, {})
    syms = load_symbols(a.max_priority)
    done = set(state["done_prefixes"])
    if a.report:
        found = sum(1 for s in syms if matches.get(f"{s['lib']}:{s['name']}"))
        print(f"{len(syms)} symbols, {len(matches)} processed, {found} with DigiKey matches, "
              f"{len(done)} prefixes harvested")
        return

    dk = dk_client.DigiKey(dk_client.Budget(a.budget), offline=a.offline)
    # group symbols by coarse prefix, keep priority order of first appearance
    groups = {}
    for s in syms:
        stem = s["stem"].strip()
        if len(norm(stem)) < 3:
            continue
        key = stem[:MIN_PREFIX].upper()
        groups.setdefault(key, []).append(s)

    def harvest_prefix(prefix, members):
        """Recursively harvest `prefix`; returns dict mpn->slim."""
        first = dk.keyword(prefix, 0, 50, None, False)
        total = first.get("ProductsCount") or 0
        if total > WINDOW:
            # descend only into child prefixes that lead to our symbols
            kids = {}
            for s in members:
                st = s["stem"].upper()
                if len(st) > len(prefix):
                    kids.setdefault(st[:len(prefix) + 1], []).append(s)
                else:
                    kids.setdefault(None, []).append(s)
            out = {}
            for p in (first.get("Products") or []) + (first.get("ExactMatches") or []):
                sp = dk_client.slim(p)
                out[sp["mpn"]] = sp
            for kp, ms in kids.items():
                if kp is None:  # stem fully consumed; take exact-ish matches already seen
                    continue
                if kp in done:
                    continue
                out.update(harvest_prefix(kp, ms))
            return out
        prods, _ = dk.keyword_all(prefix, None, False)
        return {dk_client.slim(p)["mpn"]: dk_client.slim(p) for p in prods}

    stopped = None
    try:
        for key, members in groups.items():
            pending = [s for s in members if f"{s['lib']}:{s['name']}" not in matches]
            if not pending:
                continue
            found = harvest_prefix(key, pending)
            for s in pending:
                rx = re.compile(s["rx"]) if s["rx"] else re.compile("(?i)^" + re.escape(s["stem"]))
                hits = [sp for m, sp in found.items() if rx.search(m)]
                matches[f"{s['lib']}:{s['name']}"] = hits[:25]
            done.add(key)
            state["harvested_mpns"] += len(found)
            if len(done) % 20 == 0:
                state["done_prefixes"] = sorted(done)
                json.dump(state, open(state_p, "w"))
                json.dump(matches, open(match_p, "w"))
    except dk_client.QuotaExhausted as e:
        stopped = str(e)
    state["done_prefixes"] = sorted(done)
    json.dump(state, open(state_p, "w"))
    json.dump(matches, open(match_p, "w"))
    hit = sum(1 for v in matches.values() if v)
    print(f"processed {len(matches)}/{len(syms)} symbols, {hit} with matches; calls {dk.budget.used}, "
          f"remaining {dk.budget.remaining}" + (f"; stopped: {stopped}" if stopped else "; complete"))


if __name__ == "__main__":
    main()
