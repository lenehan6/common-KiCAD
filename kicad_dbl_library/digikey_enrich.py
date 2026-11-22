#!/usr/bin/env python3
"""Refresh DigiKey ordering data in parts.sqlite (stdlib only).

For every row in every table (seed.schema.TABLES) the MPN is looked up with the
DigiKey Product Information API v4 ("productdetails"). Supplier_PN (Cut Tape
DigiKey part number), DK_Status, DK_Stock and DK_Checked are updated, and
Datasheet is filled in when empty. With --prune, rows whose MPN is unknown,
obsolete/discontinued, or out of stock everywhere are marked Status='Obsolete'
(rows are never deleted).

NOTE: this is an ad-hoc spot check that edits parts.sqlite in place; the next
init_db.py run rebuilds the file from seed/generated/*.json and discards those
edits. The maintained refresh path is ``tools/build_commodity.py all --refresh``
(see MAINTAINING.md).

Credentials are read ONLY from the environment:
    DIGIKEY_CLIENT_ID, DIGIKEY_CLIENT_SECRET

The DigiKey API allows ~1000 calls/day; the script stops when the remaining
quota (x-ratelimit-remaining) drops below --reserve. Use --only-unchecked or
--older-than DAYS to resume the next day.
"""

import argparse
import datetime as _dt
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from seed.schema import TABLES  # noqa: E402

TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"
DETAILS_URL = "https://api.digikey.com/products/v4/search/{mpn}/productdetails"
USER_AGENT = "kicad-dbl-digikey-enrich/1.0"
DEAD_STATUSES = ("obsolete", "discontinued")


class QuotaExhausted(Exception):
    pass


class ApiError(Exception):
    pass


# --------------------------------------------------------------------------
# HTTP layer: the single function tests replace.
# --------------------------------------------------------------------------
def http_request(method, url, headers=None, data=None, timeout=30):
    """Perform one HTTP request. Returns (status, headers_dict_lowercase, body_bytes).

    Never raises for HTTP error statuses; network errors propagate.
    """
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read()


# --------------------------------------------------------------------------
# DigiKey client
# --------------------------------------------------------------------------
class DigiKey:
    def __init__(self, client_id, client_secret, delay=0.6, max_retries=5):
        self._id = client_id
        self._secret = client_secret
        self.delay = delay
        self.max_retries = max_retries
        self._token = None
        self._token_expiry = 0.0
        self.remaining = None   # last seen x-ratelimit-remaining
        self.calls = 0

    def _get_token(self):
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        body = urllib.parse.urlencode({
            "client_id": self._id,
            "client_secret": self._secret,
            "grant_type": "client_credentials",
        }).encode()
        status, _h, raw = http_request("POST", TOKEN_URL, {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        }, body)
        if status != 200:
            # Do not echo the body verbatim: keep output free of anything secret-ish.
            raise ApiError("OAuth token request failed (HTTP %d)" % status)
        tok = json.loads(raw.decode("utf-8"))
        self._token = tok["access_token"]
        self._token_expiry = time.time() + float(tok.get("expires_in", 600))
        return self._token

    def product_details(self, mpn):
        """Return the 'Product' dict, or None if DigiKey answers 404."""
        url = DETAILS_URL.format(mpn=urllib.parse.quote(mpn, safe=""))
        backoff = 2.0
        reauth = False
        for _attempt in range(self.max_retries + 1):
            headers = {
                "Authorization": "Bearer " + self._get_token(),
                "X-DIGIKEY-Client-Id": self._id,
                "X-DIGIKEY-Locale-Site": "US",
                "X-DIGIKEY-Locale-Currency": "USD",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            }
            status, rh, raw = http_request("GET", url, headers)
            self.calls += 1
            rem = rh.get("x-ratelimit-remaining")
            if rem is not None:
                try:
                    self.remaining = int(rem)
                except ValueError:
                    pass
            if self.delay:
                time.sleep(self.delay)
            if status == 200:
                return json.loads(raw.decode("utf-8")).get("Product")
            if status == 404:
                return None
            if status == 401 and not reauth:
                self._token = None
                reauth = True
                continue
            if status == 429 or status >= 500:
                if status == 429 and self.remaining == 0:
                    raise QuotaExhausted("daily rate limit reached")
                wait = backoff
                ra = rh.get("retry-after")
                if ra:
                    try:
                        wait = max(wait, float(ra))
                    except ValueError:
                        pass
                print("    HTTP %d, backing off %.0fs" % (status, wait))
                time.sleep(wait)
                backoff = min(backoff * 2, 120)
                continue
            raise ApiError("HTTP %d for %s" % (status, mpn))
        raise ApiError("giving up on %s after %d retries" % (mpn, self.max_retries))


# --------------------------------------------------------------------------
# Response interpretation
# --------------------------------------------------------------------------
def pick_variation(product):
    vars_ = product.get("ProductVariations") or []
    for v in vars_:
        if "cut tape" in ((v.get("PackageType") or {}).get("Name") or "").lower():
            return v
    for v in vars_:  # never Tape & Reel / Digi-Reel (see MAINTAINING.md, Cut Tape/Bulk rule)
        if "bulk" in ((v.get("PackageType") or {}).get("Name") or "").lower():
            return v
    return None


def total_stock(product):
    return sum(int(v.get("QuantityAvailableforPackageType") or 0)
               for v in (product.get("ProductVariations") or []))


def prune_reason(product):
    """Return a reason string if the row should be pruned, else None."""
    if product is None:
        return "not found at DigiKey (404)"
    status = ((product.get("ProductStatus") or {}).get("Status") or "")
    if any(s in status.lower() for s in DEAD_STATUSES):
        return "status '%s'" % status
    if product.get("Discontinued"):
        return "flagged Discontinued"
    if total_stock(product) <= 0:
        return "no stock in any package variation"
    return None


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------
def select_rows(conn, table, only_unchecked, older_than, today):
    sql = 'SELECT Part_ID, MPN, Datasheet, DK_Checked FROM "%s" WHERE MPN IS NOT NULL AND MPN != \'\'' % table
    params = []
    if only_unchecked:
        sql += " AND (DK_Checked IS NULL OR DK_Checked = '')"
    elif older_than is not None:
        cutoff = (today - _dt.timedelta(days=older_than)).isoformat()
        sql += " AND (DK_Checked IS NULL OR DK_Checked = '' OR DK_Checked < ?)"
        params.append(cutoff)
    sql += " ORDER BY Part_ID"
    return conn.execute(sql, params).fetchall()


def run(args, client, conn, today=None):
    today = today or _dt.date.today()
    tables = args.tables or TABLES
    unknown = [t for t in tables if t not in TABLES]
    if unknown:
        raise SystemExit("unknown table(s): %s (valid: %s)" % (", ".join(unknown), ", ".join(TABLES)))

    stats = {"checked": 0, "updated": 0, "not_found": 0, "errors": 0, "pruned": 0}
    pruned = []
    processed = 0
    stopped = None
    try:
        for table in tables:
            rows = select_rows(conn, table, args.only_unchecked, args.older_than, today)
            print("== %s: %d row(s) to check" % (table, len(rows)))
            for part_id, mpn, datasheet, _checked in rows:
                if args.limit is not None and processed >= args.limit:
                    stopped = "--limit %d reached" % args.limit
                    break
                if client.remaining is not None and client.remaining < args.reserve:
                    stopped = "API quota remaining %d < reserve %d" % (client.remaining, args.reserve)
                    break
                processed += 1
                try:
                    product = client.product_details(mpn)
                except QuotaExhausted as e:
                    stopped = str(e)
                    break
                except (ApiError, OSError, ValueError) as e:
                    stats["errors"] += 1
                    print("  %-28s %-24s ERROR %s" % (part_id, mpn, e))
                    continue
                stats["checked"] += 1
                rem = "" if client.remaining is None else " [remaining %d]" % client.remaining

                reason = prune_reason(product) if args.prune else None
                if product is None:
                    stats["not_found"] += 1
                if reason:
                    pruned.append((table, part_id, mpn, reason))
                    print("  %-28s %-24s PRUNE: %s%s" % (part_id, mpn, reason, rem))
                    if not args.dry_run:
                        conn.execute('UPDATE "%s" SET "Status" = \'Obsolete\' WHERE Part_ID = ?' % table,
                                     (part_id,))
                    stats["pruned"] += 1
                    continue
                if product is None:
                    print("  %-28s %-24s not found (404)%s" % (part_id, mpn, rem))
                    continue

                var = pick_variation(product) or {}
                dkpn = var.get("DigiKeyProductNumber")
                stock = var.get("QuantityAvailableforPackageType")
                status = (product.get("ProductStatus") or {}).get("Status")
                sets = {"DK_Status": status, "DK_Stock": int(stock) if stock is not None else None,
                        "DK_Checked": today.isoformat()}
                if dkpn:
                    sets["Supplier_PN"] = dkpn
                if not datasheet and product.get("DatasheetUrl"):
                    ds = product["DatasheetUrl"]
                    sets["Datasheet"] = "https:" + ds if ds.startswith("//") else ds
                print("  %-28s %-24s %-22s %-10s stock %s%s" % (
                    part_id, mpn, dkpn or "-", status or "-", sets["DK_Stock"], rem))
                if not args.dry_run:
                    cols = ", ".join('"%s" = ?' % c for c in sets)
                    conn.execute('UPDATE "%s" SET %s WHERE Part_ID = ?' % (table, cols),
                                 list(sets.values()) + [part_id])
                stats["updated"] += 1
                if not args.dry_run and processed % 25 == 0:
                    conn.commit()
            if stopped:
                break
    except KeyboardInterrupt:
        stopped = "interrupted"
    finally:
        if not args.dry_run:
            conn.commit()

    print()
    print("Summary%s:" % (" (DRY RUN - database not modified)" if args.dry_run else ""))
    print("  API calls made     : %d" % client.calls)
    print("  rows checked       : %d" % stats["checked"])
    print("  rows updated       : %d" % stats["updated"])
    print("  not found (404)    : %d" % stats["not_found"])
    print("  errors             : %d" % stats["errors"])
    print("  rows %s: %d" % ("to prune     " if args.dry_run else "pruned       ", stats["pruned"]))
    for t, pid, mpn, why in pruned:
        print("    - %s/%s (%s): %s" % (t, pid, mpn, why))
    if client.remaining is not None:
        print("  API quota remaining: %d" % client.remaining)
    if stopped:
        print("  stopped early      : %s (rerun with --only-unchecked or --older-than to resume)" % stopped)
    return stats


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="Credentials: set DIGIKEY_CLIENT_ID and DIGIKEY_CLIENT_SECRET.")
    p.add_argument("--db", default=os.path.join(SCRIPT_DIR, "parts.sqlite"),
                   help="SQLite database (default: parts.sqlite next to this script)")
    p.add_argument("--tables", nargs="+", metavar="TABLE", help="only these tables (default: all)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--only-unchecked", action="store_true", help="only rows with empty DK_Checked")
    g.add_argument("--older-than", type=int, metavar="DAYS",
                   help="only rows whose DK_Checked is empty or older than DAYS days")
    p.add_argument("--limit", type=int, metavar="N", help="check at most N rows")
    p.add_argument("--dry-run", action="store_true", help="query the API but do not write to the DB")
    p.add_argument("--prune", action="store_true",
                   help="mark rows Status=Obsolete that 404, are Obsolete/Discontinued, or have no stock anywhere")
    p.add_argument("--delay", type=float, default=0.6, help="seconds to sleep between calls (default 0.6)")
    p.add_argument("--reserve", type=int, default=20,
                   help="stop when API quota remaining drops below this (default 20)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    cid = os.environ.get("DIGIKEY_CLIENT_ID")
    secret = os.environ.get("DIGIKEY_CLIENT_SECRET")
    if not cid or not secret:
        raise SystemExit("Set DIGIKEY_CLIENT_ID and DIGIKEY_CLIENT_SECRET environment variables.")
    if not os.path.exists(args.db):
        raise SystemExit("Database not found: %s (run init_db.py first)" % args.db)
    conn = sqlite3.connect(args.db)
    try:
        run(args, DigiKey(cid, secret, delay=args.delay), conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
