"""Bulk MLCCs (>=10uF, >=50V, X7R or better) for the Capacitors_Bulk table.

Source: DigiKey stocked-only search dumps (DK_CHECKED). Criteria: >=10uF, >=50V,
X7R-class or better (no X5R/X6S/X7T/Y5V), Active, stocked (Cut Tape qty > 0),
standard termination preferred; sizes 1210/1812/2220. Every value available per
size is listed at 50V, plus a 100V option where one exists.

Manufacturer policy: Wuerth Elektronik / Vishay preferred; where they stock no
qualifying part, values are filled from other established MLCC makers (Murata,
TDK, Samsung Electro-Mechanics, KEMET, YAGEO, Taiyo Yuden, KYOCERA AVX) using the
best-stocked qualifying part. Vishay Vitramon tops out at 1uF in these sizes.

Coverage found: 1210 10uF/50V (no 22uF/47uF or 100V >=10uF); 2220 10uF/50V,
10uF/100V, 22uF/50V (no 47uF). 1812 has no stocked >=10uF part from the listed
makers (only stacked/leadframe or non-listed makers), so the largest qualifying
1812 value, 4.7uF/50V, is kept as a fallback row.

Thickness (max) is recorded in each Description.
"""
from .schema import SYMBOLS, FOOTPRINTS, FP_FILTERS, SUPPLIER, DK_CHECKED


def _row(pid, value, tol, volt, size, tc, mfr, mpn, dkpn, stock, thick, ds):
    return {
        "Part_ID": pid,
        "Symbol": SYMBOLS["C"],
        "Footprint": FOOTPRINTS[("C", size)],
        "FP_Filter": FP_FILTERS[("C", size)],
        "Value": value,
        "Tolerance": tol,
        "Rating": volt,
        "TC_Dielectric": tc,
        "Package": size,
        "Manufacturer": mfr,
        "MPN": mpn,
        "Supplier": SUPPLIER,
        "Supplier_PN": dkpn,
        "DK_Stock": stock,
        "DK_Status": "Active",
        "DK_Checked": DK_CHECKED,
        "Datasheet": ds,
        "Description": f"MLCC {value}F {volt} {tc} {tol} {size} {thick}",
        "Keywords": f"C capacitor MLCC ceramic bulk decoupling {size} {tc} {value}",
    }


ROWS = {
    "Capacitors_Bulk": [
        _row('CAPB-1210-10U-50V-X7R', '10u', '10%', '50V', '1210', 'X7R', 'Samsung Electro-Mechanics',
             'CL32B106KBJNNNE', '1276-3387-1-ND', 425415, "2.70mm",
             'https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/41/CL32B106KBJNNNE_Spec.pdf'),
        _row('CAPB-1812-4.7U-50V-X7R', '4.7u', '10%', '50V', '1812', 'X7R', 'TDK',
             'CGA8M3X7R1H475K200KB', '445-7906-1-ND', 34559, "2.20mm",
             'https://product.tdk.com/system/files/dam/doc/product/capacitor/ceramic/mlcc/catalog/mlcc_automotive_general_en.pdf'),
        _row('CAPB-2220-10U-50V-X7R', '10u', '10%', '50V', '2220', 'X7R', 'Würth Elektronik',
             '885012214005', '732-885012214005CT-ND', 719, "3.10mm",
             'https://www.we-online.com/components/products/datasheet/885012214005.pdf'),
        _row('CAPB-2220-10U-100V-X7R', '10u', '20%', '100V', '2220', 'X7R', 'Würth Elektronik',
             '885012214001', '732-885012214001CT-ND', 2219, "3.10mm",
             'https://www.we-online.com/components/products/datasheet/885012214001.pdf'),
        _row('CAPB-2220-22U-50V-X7R', '22u', '20%', '50V', '2220', 'X7R', 'TDK',
             'CGA9P3X7R1H226M250KB', '445-181650-1-ND', 438, "2.80mm",
             'https://product.tdk.com/system/files/dam/doc/product/capacitor/ceramic/mlcc/catalog/mlcc_automotive_general_en.pdf'),
    ],
}
