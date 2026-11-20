"""Shared schema contract for all seed modules.

Every seed module exposes ``ROWS: dict[str, list[dict]]`` mapping a table name
(from TABLES) to a list of row dicts whose keys are a subset of COLUMNS.
``Part_ID``, ``Symbol``, ``Footprint`` and ``Value`` are mandatory.
"""

COLUMNS = [
    # name,           SQL type / constraint
    ("Part_ID",       "TEXT PRIMARY KEY"),
    ("Symbol",        "TEXT NOT NULL"),
    ("Footprint",     "TEXT NOT NULL"),
    ("Value",         "TEXT NOT NULL"),
    ("Description",   "TEXT"),
    ("Keywords",      "TEXT"),
    ("Manufacturer",  "TEXT"),
    ("MPN",           "TEXT"),
    ("Supplier",      "TEXT"),          # always "DigiKey"
    ("Supplier_PN",   "TEXT"),          # DigiKey Cut Tape (CT) part number
    ("Package",       "TEXT"),          # e.g. 0402, 0805, 1210
    ("Tolerance",     "TEXT"),          # e.g. 0.1%, 5%, 10%, 0.25pF
    ("Rating",        "TEXT"),          # resistor power, cap voltage, inductor/bead rated current
    ("Datasheet",     "TEXT"),
    ("TC_Dielectric", "TEXT"),          # TCR (25ppm/K), dielectric (C0G/X7R), inductor DCR/SRF note
    ("FP_Filter",     "TEXT"),          # KiCad footprint filter glob, e.g. R_0402*
    ("DK_Status",     "TEXT"),          # DigiKey product status (Active, ...)
    ("DK_Stock",      "INTEGER"),       # DigiKey quantity available (CT) at harvest time
    ("DK_Checked",    "TEXT"),          # ISO date the DigiKey data was fetched
]
COLUMN_NAMES = [c for c, _ in COLUMNS]

TABLES = [
    "Resistors_ThinFilm_Precision",  # Vishay Dale TNPW 0.1% E96, 0402 + 0805
    "Resistors_ThinFilm_1pct",       # thin film 1% E96, 0402 + 0805 (Vishay first, Yageo fallback)
    "Resistors_ThickFilm",  # Vishay Dale CRCW 5% E12, 0402 + 0805 (+0R)
    "Capacitors_Ceramic",   # MLCC E12 >=50V, C0G/X7R or better, 0402 + 0805
    "Capacitors_RF",        # MLCC 0402 C0G/NP0 fine-step values, >=50V
    "Capacitors_Bulk",      # MLCC >=10uF, >=50V, X7R or better, 1210/1812/2220
    "Capacitors_Tantalum",  # SMD tantalum 50V, E6 1uF..max available
    "Capacitors_Electrolytic",  # SMD aluminium electrolytic 50V, E6 1uF..1000uF
    "Inductors",            # E12 0402 + 0805
    "Inductors_RF",         # 0402 fine-step RF inductors
    "Ferrite_Beads",        # 22/100/220/330/1k ohm @100MHz, 0402 + 0805
]

SYMBOLS = {"R": "Device:R", "C": "Device:C", "CP": "Device:C_Polarized", "L": "Device:L", "FB": "Device:FerriteBead"}

FOOTPRINTS = {
    ("R", "0402"): "Resistor_SMD:R_0402_1005Metric",
    ("R", "0805"): "Resistor_SMD:R_0805_2012Metric",
    ("C", "0402"): "Capacitor_SMD:C_0402_1005Metric",
    ("C", "0805"): "Capacitor_SMD:C_0805_2012Metric",
    ("C", "1210"): "Capacitor_SMD:C_1210_3225Metric",
    ("C", "1812"): "Capacitor_SMD:C_1812_4532Metric",
    ("C", "2220"): "Capacitor_SMD:C_2220_5750Metric",
    ("L", "0402"): "Inductor_SMD:L_0402_1005Metric",
    ("L", "0805"): "Inductor_SMD:L_0805_2012Metric",
}

FP_FILTERS = {
    ("R", "0402"): "R_0402*", ("R", "0805"): "R_0805*",
    ("C", "0402"): "C_0402*", ("C", "0805"): "C_0805*",
    ("C", "1210"): "C_1210*", ("C", "1812"): "C_1812*", ("C", "2220"): "C_2220*",
    ("L", "0402"): "L_0402*", ("L", "0805"): "L_0805*",
}

# Manufacturer policy: Vishay / Würth Elektronik preferred. Other makers are used
# only to fill values the preferred makers do not stock at DigiKey.
PREFERRED_MANUFACTURERS = ("Vishay", "Würth Elektronik")

# Extra footprints used by polarized capacitors (tantalum case codes / electrolytic
# can sizes). Filled in by the seed modules' authors after verifying each name
# against the official KiCad footprint library.
FOOTPRINTS_EXTRA = {
    ('CP_ELEC', '4x5.4'): 'Capacitor_SMD:CP_Elec_4x5.4',
    ('CP_ELEC', '4x5.8'): 'Capacitor_SMD:CP_Elec_4x5.8',
    ('CP_ELEC', '5x5.4'): 'Capacitor_SMD:CP_Elec_5x5.4',
    ('CP_ELEC', '5x5.8'): 'Capacitor_SMD:CP_Elec_5x5.8',
    ('CP_ELEC', '6.3x5.4'): 'Capacitor_SMD:CP_Elec_6.3x5.4',
    ('CP_ELEC', '6.3x5.8'): 'Capacitor_SMD:CP_Elec_6.3x5.8',
    ('CP_ELEC', '6.3x7.7'): 'Capacitor_SMD:CP_Elec_6.3x7.7',
    ('CP_ELEC', '8x10.5'): 'Capacitor_SMD:CP_Elec_8x10.5',
    ('CP_ELEC', '10x10.5'): 'Capacitor_SMD:CP_Elec_10x10.5',
    ('CP_ELEC', '16x17.5'): 'Capacitor_SMD:CP_Elec_16x17.5',
    ('CP_ELEC', '16x22'): 'Capacitor_SMD:CP_Elec_16x22',
    ('CP_TANT', '2012-12'): 'Capacitor_Tantalum_SMD:CP_EIA-2012-12_Kemet-R',
    ('CP_TANT', '3528-21'): 'Capacitor_Tantalum_SMD:CP_EIA-3528-21_Kemet-B',
    ('CP_TANT', '6032-28'): 'Capacitor_Tantalum_SMD:CP_EIA-6032-28_Kemet-C',
    ('CP_TANT', '7343-31'): 'Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D',
    ('CP_TANT', '7343-43'): 'Capacitor_Tantalum_SMD:CP_EIA-7343-43_Kemet-X',
}

SUPPLIER = "DigiKey"
DK_CHECKED = "2026-11-20"
