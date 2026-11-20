"""SMD polarized capacitors (50V) for the Capacitors_Tantalum and
Capacitors_Electrolytic tables.

Source: DigiKey stocked-only search dumps (harvested DK_CHECKED). One part per
E6 value 1uF..1000uF, all rated exactly 50V. Selection: Active, Cut Tape in
stock; Vishay (Sprague / BC Components) and Wuerth Elektronik first, then
KEMET / KYOCERA AVX (tantalum) or Panasonic / Nichicon / Chemi-Con / Rubycon
(electrolytic); then normally stocking, highest CT stock, smaller case.
Footprints are exact KiCad library matches (EIA code + seated height for
tantalum, can D x L for electrolytic) verified against kicad-footprints master.

Tantalum: standard molded MnO2 preferred; 33uF and 47uF are polymer only
(MnO2 at 50V exists there only as conformal-coated 7361/7660 cases with no
KiCad footprint). 47uF is the maximum 50V molded tantalum stocked; 68uF and
above do not exist in SMD molded form.
Electrolytic: 1.5uF does not exist at 50V SMD in the dumps.
"""
from .schema import SYMBOLS, FOOTPRINTS_EXTRA, SUPPLIER, DK_CHECKED


def _tant(pid, value, tol, pkg, case, mfr, mpn, dkpn, stock, status, ds, tc):
    esr = tc.split("ESR ")[1]
    return {
        "Part_ID": pid,
        "Symbol": SYMBOLS["CP"],
        "Footprint": FOOTPRINTS_EXTRA[("CP_TANT", pkg)],
        "FP_Filter": "CP_EIA*",
        "Value": value,
        "Tolerance": tol,
        "Rating": "50V",
        "TC_Dielectric": tc,
        "Package": pkg,
        "Manufacturer": mfr,
        "MPN": mpn,
        "Supplier": SUPPLIER,
        "Supplier_PN": dkpn,
        "DK_Stock": stock,
        "DK_Status": status,
        "DK_Checked": DK_CHECKED,
        "Datasheet": ds,
        "Description": f"Tantalum capacitor {value}F 50V {tol} {pkg} ({case} case) ESR {esr}",
        "Keywords": f"CP capacitor tantalum polarized 50V {value}",
    }


def _elec(pid, value, tol, can, mfr, mpn, dkpn, stock, status, ds, tc):
    return {
        "Part_ID": pid,
        "Symbol": SYMBOLS["CP"],
        "Footprint": FOOTPRINTS_EXTRA[("CP_ELEC", can)],
        "FP_Filter": "CP_Elec*",
        "Value": value,
        "Tolerance": tol,
        "Rating": "50V",
        "TC_Dielectric": tc,
        "Package": can,
        "Manufacturer": mfr,
        "MPN": mpn,
        "Supplier": SUPPLIER,
        "Supplier_PN": dkpn,
        "DK_Stock": stock,
        "DK_Status": status,
        "DK_Checked": DK_CHECKED,
        "Datasheet": ds,
        "Description": f"Aluminium electrolytic capacitor {value}F 50V {tol} SMD can {can}mm (D x L)",
        "Keywords": f"CP capacitor electrolytic aluminium polarized 50V {value}",
    }


ROWS = {
    "Capacitors_Tantalum": [
        # MICROTAN®, 298D, 0805 (2012 Metric), case P, H max 1.20mm, normally stocking=True
        _tant('CAPT-2012-1U-50V', '1u', '20%', '2012-12', 'P', 'Vishay Sprague', '298D105X0050P2T', '718-1720-1-ND', 12983, 'Active', 'https://www.vishay.com/docs/40065/298d298w.pdf', 'Tantalum MnO2, ESR 8R'),
        # TANTAMOUNT™, 293D, 2312 (6032 Metric), case C, H max 2.80mm, normally stocking=True
        _tant('CAPT-6032-1.5U-50V', '1.5u', '10%', '6032-28', 'C', 'Vishay Sprague', '293D155X9050C2TE3', '718-1811-1-ND', 696, 'Active', 'https://www.vishay.com/docs/40002/293d.pdf', 'Tantalum MnO2, ESR 3.4R'),
        # TANTAMOUNT™, TR3, 1411 (3528 Metric), case B, H max 2.11mm, normally stocking=True
        _tant('CAPT-3528-2.2U-50V', '2.2u', '10%', '3528-21', 'B', 'Vishay Sprague', 'TR3B225K050C2000', '718-1545-1-ND', 1607, 'Active', 'https://www.vishay.com/docs/40080/tr3.pdf', 'Tantalum MnO2, ESR 2R'),
        # TANTAMOUNT™, 293D, 2917 (7343 Metric), case D, H max 3.10mm, normally stocking=True
        _tant('CAPT-7343-3.3U-50V', '3.3u', '10%', '7343-31', 'D', 'Vishay Sprague', '293D335X9050D2TE3', '718-1822-1-ND', 4650, 'Active', 'https://www.vishay.com/docs/40002/293d.pdf', 'Tantalum MnO2, ESR 1.7R'),
        # TANTAMOUNT™, TR3, 2312 (6032 Metric), case C, H max 2.80mm, normally stocking=True
        _tant('CAPT-6032-4.7U-50V', '4.7u', '10%', '6032-28', 'C', 'Vishay Sprague', 'TR3C475K050C0500', '718-1548-1-ND', 6328, 'Active', 'https://www.vishay.com/docs/40080/tr3.pdf', 'Tantalum MnO2, ESR 0.5R'),
        # TANTAMOUNT™, 293D, 2917 (7343 Metric), case D, H max 3.10mm, normally stocking=True
        _tant('CAPT-7343-6.8U-50V', '6.8u', '20%', '7343-31', 'D', 'Vishay Sprague', '293D685X0050D2TE3', '718-293D685X0050D2TE3CT-ND', 510, 'Active', 'https://www.vishay.com/docs/40002/293d.pdf', 'Tantalum MnO2, ESR 0.9R'),
        # TANTAMOUNT™, 293D, 2917 (7343 Metric), case E, H max 4.32mm, normally stocking=True
        _tant('CAPT-7343-10U-50V', '10u', '10%', '7343-43', 'E', 'Vishay Sprague', '293D106X9050E2TE3', '718-1022-1-ND', 9600, 'Active', 'https://www.vishay.com/docs/40002/293d.pdf', 'Tantalum MnO2, ESR 0.8R'),
        # TANTAMOUNT™, 293D, 2917 (7343 Metric), case E, H max 4.32mm, normally stocking=True
        _tant('CAPT-7343-15U-50V', '15u', '20%', '7343-43', 'E', 'Vishay Sprague', '293D156X0050E2TE3', '718-1750-1-ND', 2481, 'Active', 'https://www.vishay.com/docs/40002/293d.pdf', 'Tantalum MnO2, ESR 0.8R'),
        # T491, 2917 (7343 Metric), case X, H max 4.30mm, normally stocking=True
        _tant('CAPT-7343-22U-50V', '22u', '20%', '7343-43', 'X', 'KEMET', 'T491X226M050AT', '399-9752-1-ND', 82536, 'Active', 'https://yageogroup.com/content/datasheet/asset/file/KEM_T2005_T491', 'Tantalum MnO2, ESR 0.6R'),
        # KO-CAP® T521, 2917 (7343 Metric), case X, H max 4.30mm, normally stocking=True
        _tant('CAPT-7343-33U-50V', '33u', '20%', '7343-43', 'X', 'KEMET', 'T521X336M050ATE075', '399-11721-1-ND', 39950, 'Active', 'https://yageogroup.com/content/datasheet/asset/file/KEM_T2076_T52X-530', 'Tantalum polymer, ESR 0.075R'),
        # vPolyTan™ T54, 2917 (7343 Metric), case EE, H max 4.30mm, normally stocking=True
        _tant('CAPT-7343-47U-50V', '47u', '20%', '7343-43', 'EE', 'Vishay Sprague', 'T54EE476M050ESA100', '718-T54EE476M050ESA100CT-ND', 2119, 'Active', 'https://www.vishay.com/docs/40212/t54.pdf', 'Tantalum polymer, ESR 0.1R'),
    ],
    "Capacitors_Electrolytic": [
        # UWT, D 0.157" Dia (4.00mm), H max 0.213" (5.40mm), normally stocking=True
        _elec('CAPE-4x5.4-1U-50V', '1u', '20%', '4x5.4', 'Nichicon', 'UWT1H010MCL1GB', '493-2216-1-ND', 48660, 'Active', 'https://www.nichicon.co.jp/english/series_items/catalog_pdf/e-uwt.pdf', 'Al electrolytic, 105C 1000h, ripple 6.3mA@120Hz'),
        # UWT, D 0.157" Dia (4.00mm), H max 0.213" (5.40mm), normally stocking=True
        _elec('CAPE-4x5.4-2.2U-50V', '2.2u', '20%', '4x5.4', 'Nichicon', 'UWT1H2R2MCL1GB', '493-2218-1-ND', 18456, 'Active', 'https://www.nichicon.co.jp/english/series_items/catalog_pdf/e-uwt.pdf', 'Al electrolytic, 105C 1000h, ripple 11mA@120Hz'),
        # UUA, D 0.157" Dia (4.00mm), H max 0.228" (5.80mm), normally stocking=True
        _elec('CAPE-4x5.8-3.3U-50V', '3.3u', '20%', '4x5.8', 'Nichicon', 'UUA1H3R3MCL1GS', '493-9461-1-ND', 5265, 'Active', 'https://www.nichicon.co.jp/english/series_items/catalog_pdf/e-uua.pdf', 'Al electrolytic, 105C 3000h, ripple 17mA@120Hz'),
        # UWT, D 0.197" Dia (5.00mm), H max 0.213" (5.40mm), normally stocking=True
        _elec('CAPE-5x5.4-4.7U-50V', '4.7u', '20%', '5x5.4', 'Nichicon', 'UWT1H4R7MCL1GB', '493-2220-1-ND', 66344, 'Active', 'https://www.nichicon.co.jp/english/series_items/catalog_pdf/e-uwt.pdf', 'Al electrolytic, 105C 1000h, ripple 19mA@120Hz'),
        # HB, D 0.197" Dia (5.00mm), H max 0.228" (5.80mm), normally stocking=True
        _elec('CAPE-5x5.8-6.8U-50V', '6.8u', '20%', '5x5.8', 'Panasonic Industry', 'EEE-HB1H6R8R', 'PCE4148CT-ND', 1320, 'Active', 'https://industrial.panasonic.com/cdbs/www-data/pdf/RDE0000/ABA0000C1157.pdf', 'Al electrolytic, 105C 2000h, ripple 23mA@120Hz'),
        # UWT, D 0.248" Dia (6.30mm), H max 0.213" (5.40mm), normally stocking=True
        _elec('CAPE-6.3x5.4-10U-50V', '10u', '20%', '6.3x5.4', 'Nichicon', 'UWT1H100MCL1GB', '493-2221-1-ND', 75695, 'Active', 'https://www.nichicon.co.jp/english/series_items/catalog_pdf/e-uwt.pdf', 'Al electrolytic, 105C 1000h, ripple 30mA@120Hz'),
        # UWD, D 0.248" Dia (6.30mm), H max 0.228" (5.80mm), normally stocking=True
        _elec('CAPE-6.3x5.8-15U-50V', '15u', '20%', '6.3x5.8', 'Nichicon', 'UWD1H150MCL1GS', '493-9674-1-ND', 1408, 'Active', 'https://www.nichicon.co.jp/english/series_items/catalog_pdf/e-uwd.pdf', 'Al electrolytic, 105C 2000h, ripple 82.5mA@120Hz'),
        # WCAP-AS5H, D 0.248" Dia (6.30mm), H max 0.303" (7.70mm), normally stocking=True
        _elec('CAPE-6.3x7.7-22U-50V', '22u', '20%', '6.3x7.7', 'Würth Elektronik', '865230645010', '732-8275-1-ND', 7130, 'Active', 'https://www.we-online.com/components/products/datasheet/865230645010.pdf', 'Al electrolytic, 105C 5000h, ripple 52mA@120Hz'),
        # WCAP-ASLI, D 0.248" Dia (6.30mm), H max 0.303" (7.70mm), normally stocking=True
        _elec('CAPE-6.3x7.7-33U-50V', '33u', '20%', '6.3x7.7', 'Würth Elektronik', '865080645010', '732-8455-1-ND', 14158, 'Active', 'https://www.we-online.com/components/products/datasheet/865080645010.pdf', 'Al electrolytic, 105C 2000h, ripple 123.5mA@120Hz'),
        # WCAP-ASLI, D 0.248" Dia (6.30mm), H max 0.303" (7.70mm), normally stocking=True
        _elec('CAPE-6.3x7.7-47U-50V', '47u', '20%', '6.3x7.7', 'Würth Elektronik', '865080645012', '732-8457-1-ND', 33917, 'Active', 'https://www.we-online.com/components/products/datasheet/865080645012.pdf', 'Al electrolytic, 105C 2000h, ripple 149.5mA@120Hz'),
        # WCAP-ASLL, D 0.315" Dia (8.00mm), H max 0.413" (10.50mm), normally stocking=True
        _elec('CAPE-8x10.5-68U-50V', '68u', '20%', '8x10.5', 'Würth Elektronik', '865060653009', '732-8549-1-ND', 2481, 'Active', 'https://www.we-online.com/components/products/datasheet/865060653009.pdf', 'Al electrolytic, 105C 5000h, ripple 195mA@120Hz'),
        # WCAP-ASLI, D 0.315" Dia (8.00mm), H max 0.413" (10.50mm), normally stocking=True
        _elec('CAPE-8x10.5-100U-50V', '100u', '20%', '8x10.5', 'Würth Elektronik', '865080653016', '732-8461-1-ND', 12804, 'Active', 'https://www.we-online.com/components/products/datasheet/865080653016.pdf', 'Al electrolytic, 105C 2000h, ripple 227.5mA@120Hz'),
        # WCAP-ASLI, D 0.394" Dia (10.00mm), H max 0.413" (10.50mm), normally stocking=True
        _elec('CAPE-10x10.5-150U-50V', '150u', '20%', '10x10.5', 'Würth Elektronik', '865080657017', '732-8462-1-ND', 1058, 'Active', 'https://www.we-online.com/components/products/datasheet/865080657017.pdf', 'Al electrolytic, 105C 2000h, ripple 390mA@120Hz'),
        # WCAP-ASLI, D 0.394" Dia (10.00mm), H max 0.413" (10.50mm), normally stocking=True
        _elec('CAPE-10x10.5-220U-50V', '220u', '20%', '10x10.5', 'Würth Elektronik', '865080657018', '732-8463-1-ND', 18439, 'Active', 'https://www.we-online.com/components/products/datasheet/865080657018.pdf', 'Al electrolytic, 105C 2000h, ripple 422.5mA@120Hz'),
        # WCAP-AS5H, D 0.394" Dia (10.00mm), H max 0.413" (10.50mm), normally stocking=True
        _elec('CAPE-10x10.5-330U-50V', '330u', '20%', '10x10.5', 'Würth Elektronik', '865230657014', '732-865230657014CT-ND', 1366, 'Active', 'https://www.we-online.com/components/products/datasheet/865230657014.pdf', 'Al electrolytic, 105C 2000h, ripple 585mA@120Hz'),
        # 146 CTI, D 0.630" Dia (16.00mm), H max 0.689" (17.50mm), normally stocking=True
        _elec('CAPE-16x17.5-470U-50V', '470u', '20%', '16x17.5', 'Vishay BC Components', 'MAL214699108E3', '4442PHCT-ND', 2458, 'Active', 'https://www.vishay.com/docs/28403/146cti.pdf', 'Al electrolytic, 125C 5000h, ripple 780mA@100Hz'),
        # 146 CTI, D 0.630" Dia (16.00mm), H max 0.689" (17.50mm), normally stocking=True
        _elec('CAPE-16x17.5-680U-50V', '680u', '20%', '16x17.5', 'Vishay BC Components', 'MAL214699109E3', '4443PHCT-ND', 1448, 'Active', 'https://www.vishay.com/docs/28403/146cti.pdf', 'Al electrolytic, 125C 5000h, ripple 780mA@100Hz'),
        # 146 CTI, D 0.630" Dia (16.00mm), H max 0.866" (22.00mm), normally stocking=True
        _elec('CAPE-16x22-1000U-50V', '1000u', '20%', '16x22', 'Vishay BC Components', 'MAL214699111E3', '4444PHCT-ND', 1780, 'Active', 'https://www.vishay.com/docs/28403/146cti.pdf', 'Al electrolytic, 125C 6000h, ripple 900mA@100Hz'),
    ],
}
