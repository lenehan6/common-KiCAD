"""Shared DigiKey Product Information API v4 client with a persistent cache.

* Credentials: env vars DIGIKEY_CLIENT_ID / DIGIKEY_CLIENT_SECRET only.
* Every response is stored in tools/cache/dk_cache.sqlite keyed by request, so
  re-running a harvest never spends quota twice (use max_age_days to refresh).
* Quota: DigiKey allows ~1000 calls/day. ``Budget`` stops cleanly when the
  per-run budget or the server-reported remaining quota is exhausted.
* stdlib only.
"""
import hashlib
import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.environ.get("DK_CACHE", os.path.join(HERE, "cache", "dk_cache.sqlite"))
TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"
KEYWORD_URL = "https://api.digikey.com/products/v4/search/keyword"
DETAILS_URL = "https://api.digikey.com/products/v4/search/{mpn}/productdetails"
MAX_WINDOW = 300  # DigiKey: Offset + Limit <= 300


class QuotaExhausted(Exception):
    pass


class Budget:
    def __init__(self, calls=900, reserve=20):
        self.calls, self.reserve, self.used, self.remaining = calls, reserve, 0, None

    def check(self):
        if self.used >= self.calls:
            raise QuotaExhausted(f"run budget of {self.calls} calls used")
        if self.remaining is not None and self.remaining <= self.reserve:
            raise QuotaExhausted(f"DigiKey daily quota low ({self.remaining} left)")


class DigiKey:
    def __init__(self, budget=None, cache_path=CACHE_PATH, offline=False):
        self.budget = budget or Budget()
        self.offline = offline  # True: serve from cache only, never call the API
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        self.db = sqlite3.connect(cache_path)
        self.db.execute("CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, req TEXT, ts REAL, body TEXT)")
        self._tok, self._exp = None, 0
        self.cid = os.environ.get("DIGIKEY_CLIENT_ID", "")
        self.sec = os.environ.get("DIGIKEY_CLIENT_SECRET", "")

    # ---------------- cache ----------------
    @staticmethod
    def _key(req):
        return hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()

    def _get_cached(self, req, max_age_days):
        row = self.db.execute("SELECT ts, body FROM cache WHERE k=?", (self._key(req),)).fetchone()
        if row and (max_age_days is None or time.time() - row[0] < max_age_days * 86400):
            return _unpack(row[1])
        return None

    def _put(self, req, body):
        self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)",
                        (self._key(req), json.dumps(req, sort_keys=True), time.time(), _pack(body)))
        self.db.commit()

    # ---------------- http ----------------
    def _token(self):
        if self._tok and time.time() < self._exp:
            return self._tok
        if not (self.cid and self.sec):
            raise SystemExit("Set DIGIKEY_CLIENT_ID and DIGIKEY_CLIENT_SECRET")
        data = urllib.parse.urlencode({"client_id": self.cid, "client_secret": self.sec,
                                       "grant_type": "client_credentials"}).encode()
        t = json.load(urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data), timeout=30))
        self._tok, self._exp = t["access_token"], time.time() + t.get("expires_in", 600) - 60
        return self._tok

    def _call(self, method, url, body=None):
        self.budget.check()
        for attempt in range(5):
            hdr = {"Authorization": "Bearer " + self._token(), "X-DIGIKEY-Client-Id": self.cid,
                   "X-DIGIKEY-Locale-Site": "US", "X-DIGIKEY-Locale-Currency": "USD",
                   "Content-Type": "application/json"}
            req = urllib.request.Request(url, method=method, headers=hdr,
                                         data=json.dumps(body).encode() if body is not None else None)
            try:
                r = urllib.request.urlopen(req, timeout=60)
                self.budget.used += 1
                rem = r.headers.get("x-ratelimit-remaining")
                if rem is not None:
                    self.budget.remaining = int(rem)
                return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    self._tok = None
                    continue
                if e.code == 429:
                    self.budget.used += 1
                    ra = e.headers.get("Retry-After")
                    if ra and int(ra) > 120:
                        raise QuotaExhausted("DigiKey 429: daily quota exhausted")
                    time.sleep(int(ra or 5 * (attempt + 1)))
                    continue
                if e.code == 404:
                    self.budget.used += 1
                    return None
                if e.code >= 500:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise RuntimeError(f"DigiKey HTTP {e.code}: {e.read()[:300]!r}")
        raise RuntimeError("DigiKey: retries exhausted")

    # ---------------- public API ----------------
    def keyword(self, keywords, offset=0, limit=50, mfr_ids=None, in_stock=True, max_age_days=30):
        fo = {"SearchOptions": ["InStock", "NormallyStocking"]} if in_stock else {}
        if mfr_ids:
            fo["ManufacturerFilter"] = [{"Id": str(m)} for m in mfr_ids]
        body = {"Keywords": keywords, "Limit": limit, "Offset": offset, "FilterOptionsRequest": fo}
        req = {"kind": "keyword", **body}
        hit = self._get_cached(req, max_age_days)
        if hit is not None:
            return hit
        if self.offline:
            return {"Products": [], "ProductsCount": 0, "_offline_miss": True}
        res = self._call("POST", KEYWORD_URL, body) or {}
        self._put(req, res)
        return res

    def keyword_all(self, keywords, mfr_ids=None, in_stock=True, max_age_days=30):
        """All products for a query (up to DigiKey's 300-result window)."""
        out, off = [], 0
        while True:
            d = self.keyword(keywords, off, 50, mfr_ids, in_stock, max_age_days)
            prods = (d.get("Products") or []) + (d.get("ExactMatches") or [])
            out += prods
            total = d.get("ProductsCount") or 0
            off += 50
            if off >= min(total, MAX_WINDOW) or not d.get("Products"):
                return out, total

    def keyword_split(self, prefix, mfr_ids=None, in_stock=True, alphabet="0123456789RKM", depth=3,
                      max_age_days=30, accept=None):
        """Harvest an MPN prefix, recursively splitting queries that exceed 300 results."""
        found = {}

        def rec(q, d):
            prods, total = self.keyword_all(q, mfr_ids, in_stock, max_age_days)
            if total > MAX_WINDOW and d < depth:
                for ch in alphabet:
                    rec(q + ch, d + 1)
                return
            for p in prods:
                m = p["ManufacturerProductNumber"]
                if accept is None or accept(m):
                    found[m] = p

        rec(prefix, 0)
        return list(found.values())

    def details(self, mpn, max_age_days=30):
        req = {"kind": "details", "mpn": mpn}
        hit = self._get_cached(req, max_age_days)
        if hit is not None:
            return hit
        if self.offline:
            return None
        res = self._call("GET", DETAILS_URL.format(mpn=urllib.parse.quote(mpn, safe="")))
        self._put(req, res)
        return res


# ---------------- cache compaction ----------------
def trim_product(p):
    """Keep only the fields slim() and the selectors use (keeps the cache small)."""
    return {
        "ManufacturerProductNumber": p.get("ManufacturerProductNumber"),
        "Manufacturer": {"Name": (p.get("Manufacturer") or {}).get("Name")},
        "Series": {"Name": (p.get("Series") or {}).get("Name")},
        "Description": p.get("Description"), "ProductStatus": p.get("ProductStatus"),
        "NormallyStocking": p.get("NormallyStocking"), "DatasheetUrl": p.get("DatasheetUrl"),
        "ProductUrl": p.get("ProductUrl"), "Category": {"Name": (p.get("Category") or {}).get("Name")},
        "Parameters": [{"ParameterText": x.get("ParameterText"), "ValueText": x.get("ValueText")}
                       for x in p.get("Parameters", [])],
        "ProductVariations": [{"DigiKeyProductNumber": v.get("DigiKeyProductNumber"),
                               "PackageType": {"Name": (v.get("PackageType") or {}).get("Name")},
                               "QuantityAvailableforPackageType": v.get("QuantityAvailableforPackageType"),
                               "MinimumOrderQuantity": v.get("MinimumOrderQuantity")}
                              for v in p.get("ProductVariations", [])],
    }


def trim_response(body):
    if not isinstance(body, dict):
        return body
    if "Product" in body:  # productdetails
        return {"Product": trim_product(body["Product"])}
    out = {"ProductsCount": body.get("ProductsCount")}
    for k in ("Products", "ExactMatches"):
        out[k] = [trim_product(p) for p in (body.get(k) or [])]
    return out


def _pack(body):
    return zlib.compress(json.dumps(trim_response(body), separators=(",", ":")).encode(), 9)


def _unpack(blob):
    if isinstance(blob, str):  # legacy uncompressed row
        return json.loads(blob)
    return json.loads(zlib.decompress(blob))


# ---------------- helpers shared by selectors ----------------
ORDERABLE = ("Cut Tape", "Bulk")


def slim(p):
    """Flatten a DigiKey v4 product into the dict shape used by specs/selectors."""
    return {
        "mpn": p["ManufacturerProductNumber"], "mfr": p["Manufacturer"]["Name"],
        "series": (p.get("Series") or {}).get("Name"),
        "desc": p["Description"]["ProductDescription"], "detail": p["Description"]["DetailedDescription"],
        "status": p["ProductStatus"]["Status"], "normally_stocking": p.get("NormallyStocking"),
        "datasheet": p.get("DatasheetUrl"), "url": p.get("ProductUrl"),
        "category": ((p.get("Category") or {}).get("Name")),
        "params": {x["ParameterText"]: x["ValueText"] for x in p.get("Parameters", [])},
        "variations": [{"dkpn": v["DigiKeyProductNumber"], "pkg": v["PackageType"]["Name"],
                        "qty": v.get("QuantityAvailableforPackageType", 0), "moq": v.get("MinimumOrderQuantity")}
                       for v in p.get("ProductVariations", [])],
    }


def orderable_variation(sp):
    """Cut Tape first, then Bulk. Never Tape & Reel / Digi-Reel. Returns variation dict or None."""
    for want in ORDERABLE:
        hits = [v for v in sp["variations"] if want in (v["pkg"] or "")]
        if hits:
            stocked = [v for v in hits if (v.get("qty") or 0) > 0]
            return max(stocked, key=lambda v: v.get("qty") or 0) if stocked else hits[0]
    return None


def https(url):
    if not url:
        return url
    if url.startswith("//"):
        return "https:" + url
    return url.replace("http://", "https://", 1)
