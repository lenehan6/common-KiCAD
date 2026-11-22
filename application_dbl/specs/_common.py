"""Helpers shared by application_dbl spec modules (import with: from _common import ...).

Copied from kicad_dbl_library/specs/_common.py and extended for application parts."""
import re

E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]
E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1,
       5.6, 6.2, 6.8, 7.5, 8.2, 9.1]

PREFIX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}


def num(text, unit=""):
    """Parse '220 Ohms @ 100 MHz', '1.5A', '300mA', '10 kOhms' -> float in base units (first number)."""
    if not text:
        return None
    m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*([pnuµmkKMG]?)\s*" + re.escape(unit), text)
    if not m:
        return None
    return float(m.group(1)) * PREFIX.get(m.group(2), 1.0)


def close(a, b, rel=0.005):
    return a is not None and b is not None and abs(a - b) <= rel * max(abs(a), abs(b), 1e-30)


def pkg_is(sp, code):
    """True if DigiKey 'Package / Case' starts with the size code, e.g. '0402 (1005 Metric)'."""
    return (sp["params"].get("Package / Case") or "").startswith(code + " ") or \
        (sp["params"].get("Package / Case") or "") == code


def mfr_rank(sp, preferred):
    """Index of the first preferred-maker substring found in the manufacturer name (len() if none)."""
    for i, name in enumerate(preferred):
        if name.lower() in sp["mfr"].lower():
            return i
    return len(preferred)


def mfr_in(sp, *names):
    """True if any of the maker substrings occurs in the DigiKey manufacturer name (case-insensitive)."""
    m = sp["mfr"].lower()
    return any(n.lower() in m for n in names)


def param(sp, key, default=""):
    v = sp["params"].get(key)
    return default if v in (None, "-") else v


def key_params(sp, keys, limit=10):
    """Compact 'k=v; k=v' string of the given DigiKey parameters (skips '-' / missing)."""
    out = []
    for k in keys:
        v = param(sp, k)
        if v:
            out.append(f"{k}={v}")
        if len(out) >= limit:
            break
    return "; ".join(out)
