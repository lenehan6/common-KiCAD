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
    "Resistors_ThinFilm",   # Vishay Dale TNPW 0.1% E96, 0402 + 0805
    "Resistors_ThickFilm",  # Vishay Dale CRCW 5% E12, 0402 + 0805 (+0R)
    "Capacitors",           # MLCC E12 >=50V, C0G/X7R or better, 0402 + 0805
    "Capacitors_RF",        # MLCC 0402 C0G/NP0 fine-step values, >=50V
    "Capacitors_Bulk",      # MLCC >=10uF, >=50V, X7R or better, 1210/1812/2220
    "Inductors",            # E12 0402 + 0805
    "Inductors_RF",         # 0402 fine-step RF inductors
    "Ferrite_Beads",        # 22/100/220/330/1k ohm @100MHz, 0402 + 0805
]

SYMBOLS = {"R": "Device:R", "C": "Device:C", "L": "Device:L", "FB": "Device:FerriteBead"}

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

SUPPLIER = "DigiKey"
DK_CHECKED = "2026-11-20"
