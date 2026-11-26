"""Keystone test points: SMD 5015 (micro-mini) and 5019 (miniature), plus THT wire loops in
the Miniature (5000-5004), Compact (5005-5009) and Multipurpose (5010-5014) families, red/black
(plus white/yellow miniature). Only parts with a KiCad TestPoint_Keystone_* footprint
(5016/5017/5018 have none and are not used). Exact MPN per slot."""

TABLE = "TestPoints"
QUERIES = [dict(keywords=k) for k in (
    "Keystone test point SMD", "Keystone test point PC", "Keystone 5015", "Keystone 5019",
    "Keystone 5000", "Keystone 5001", "Keystone 5005", "test point SMD")]

FP = {"5015": "TestPoint_Keystone_5015_Micro_Mini", "5019": "TestPoint_Keystone_5019_Miniature",
      "mini": "TestPoint_Keystone_5000-5004_Miniature", "compact": "TestPoint_Keystone_5005-5009_Compact",
      "multi": "TestPoint_Keystone_5010-5014_Multipurpose"}
# part_id, MPN, footprint key, family text, colour
SLOTS = [
    ("TP-KEYSTONE-5015", "5015", "5015", "SMD micro-mini", None),
    ("TP-KEYSTONE-5019", "5019", "5019", "SMD miniature", None),
    ("TP-KEYSTONE-5000", "5000", "mini", "THT miniature loop", "Red"),
    ("TP-KEYSTONE-5001", "5001", "mini", "THT miniature loop", "Black"),
    ("TP-KEYSTONE-5002", "5002", "mini", "THT miniature loop", "White"),
    ("TP-KEYSTONE-5004", "5004", "mini", "THT miniature loop", "Yellow"),
    ("TP-KEYSTONE-5005", "5005", "compact", "THT compact loop", "Red"),
    ("TP-KEYSTONE-5006", "5006", "compact", "THT compact loop", "Black"),
    ("TP-KEYSTONE-5010", "5010", "multi", "THT multipurpose loop", "Red"),
    ("TP-KEYSTONE-5011", "5011", "multi", "THT multipurpose loop", "Black"),
]


def slots():
    return [dict(part_id=pid, mpn=m, fp=FP[k], fam=fam, colour=c) for pid, m, k, fam, c in SLOTS]


def accept(sp, slot):
    return sp["mpn"] == slot["mpn"] and "Keystone" in sp["mfr"]


def rank(sp, slot):
    return (0,)


def make_row(sp, slot, var):
    p = sp["params"]
    smd = "SMD" in slot["fam"]
    col = f" {slot['colour']}" if slot["colour"] else ""
    hole = p.get("Hole Diameter")
    return dict(
        Symbol="Connector:TestPoint", Footprint="TestPoint:" + slot["fp"], Value=f"TP {slot['mpn']}{col}",
        Package=("SMD " if smd else "THT ") + (p.get("Size / Dimension") or ""),
        Description=f"Keystone {slot['mpn']} test point, {slot['fam']}{col}",
        Keywords=f"test point testpoint TP Keystone {slot['mpn']} {'SMD' if smd else 'THT loop'}{col}",
        Rating=None if smd or not hole or hole == "-" else f"Hole {hole}",
        FP_Filter="TestPoint*Keystone*", Pinout="1=TP",
        Pinout_Source="Single-pin part; KiCad Connector:TestPoint pin 1 = footprint pad 1 (" + slot["fp"] + ")")
