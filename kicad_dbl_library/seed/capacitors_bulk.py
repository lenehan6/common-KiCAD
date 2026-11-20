"""Bulk MLCCs (>=4.7uF, >=50V, X7R) for the Capacitors_Bulk table.

Source: DigiKey stocked-only search dumps (Wuerth Elektronik first, Vishay
Vitramon to fill gaps). No part >=10uF/50V X7R exists in 1210 or 1812 in the
dumps, so the largest qualifying values down to 4.7uF are included; 1812 has
nothing >=4.7uF at >=50V X7R (max 2.2uF) and is therefore absent. Vishay
Vitramon tops out at 1uF in 1210/1812/2220 and fills no gap.

Heights (Thickness Max): 885012209048 2.80mm, 885012214005 3.10mm,
885012214001 3.10mm, 885012214003 2.80mm.
"""
from .schema import SYMBOLS, FOOTPRINTS, FP_FILTERS, SUPPLIER, DK_CHECKED


def _row(pid, value, tol, volt, size, mpn, dkpn, stock, ds):
    return {
        "Part_ID": pid,
        "Symbol": SYMBOLS["C"],
        "Footprint": FOOTPRINTS[("C", size)],
        "FP_Filter": FP_FILTERS[("C", size)],
        "Value": value,
        "Tolerance": tol,
        "Rating": volt,
        "TC_Dielectric": "X7R",
        "Package": size,
        "Manufacturer": "Würth Elektronik",
        "MPN": mpn,
        "Supplier": SUPPLIER,
        "Supplier_PN": dkpn,
        "DK_Stock": stock,
        "DK_Status": "Active",
        "DK_Checked": DK_CHECKED,
        "Datasheet": ds,
        "Description": f"MLCC {value}F {volt} X7R {tol} {size} bulk",
        "Keywords": f"C capacitor MLCC ceramic bulk decoupling {size} X7R {value}",
    }


ROWS = {
    "Capacitors_Bulk": [
        # 1210: max available >=50V X7R is 4.7uF (no 10uF). Thickness 2.80mm.
        _row("CAPB-1210-4.7U-50V-X7R", "4.7u", "10%", "50V", "1210",
             "885012209048", "732-7386-1-ND", 3837,
             "https://www.we-online.com/components/products/datasheet/885012209048.pdf"),
        # 2220: 10uF achievable at 50V and 100V. Thickness 3.10mm.
        _row("CAPB-2220-10U-50V-X7R", "10u", "10%", "50V", "2220",
             "885012214005", "732-885012214005CT-ND", 719,
             "https://www.we-online.com/components/products/datasheet/885012214005.pdf"),
        _row("CAPB-2220-10U-100V-X7R", "10u", "20%", "100V", "2220",
             "885012214001", "732-885012214001CT-ND", 2219,
             "https://www.we-online.com/components/products/datasheet/885012214001.pdf"),
        # 2220 4.7uF 100V. Thickness 2.80mm.
        _row("CAPB-2220-4.7U-100V-X7R", "4.7u", "10%", "100V", "2220",
             "885012214003", "732-885012214003CT-ND", 1216,
             "https://www.we-online.com/components/products/datasheet/885012214003.pdf"),
    ],
}
