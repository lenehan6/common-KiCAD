# Company Parts Library (KiCad database library)

A KiCad [database library](https://docs.kicad.org/master/en/eeschema/eeschema.html#database-libraries)
backed by a single SQLite file. Each part row carries its KiCad symbol, footprint,
footprint filter, datasheet and DigiKey ordering info, so placed parts arrive with
MPN and supplier part number already filled in.

**Tables** (each appears as its own library in the symbol chooser):

| Table | Library name | Contents |
|---|---|---|
| `Resistors_ThinFilm_Precision` | Resistors - Thin Film 0.1% Precision | Thin film 0.1%, E96, 0402 / 0805 (Vishay Dale TNPW) |
| `Resistors_ThinFilm_1pct` | Resistors - Thin Film 1% | Thin film 1%, E96, 0402 / 0805 (Vishay first, YAGEO RT fallback) |
| `Resistors_ThickFilm` | Resistors - Thick Film 5% | Thick film 5%, E12 (+0R), 0402 / 0805 (Vishay Dale CRCW) |
| `Capacitors_Ceramic` | Capacitors - Ceramic | MLCC, E12, >=50 V, X7R or better (C0G/X7R), 0402 / 0805 |
| `Capacitors_RF` | Capacitors - RF 0402 C0G | 0402 C0G/NP0 fine-step RF values, >=50 V |
| `Capacitors_Bulk` | Capacitors - Bulk | Bulk MLCC >=10 uF, >=50 V, X7R or better, 1210 / 1812 / 2220 |
| `Capacitors_Tantalum` | Capacitors - Tantalum 50V | SMD tantalum, 50 V, E6 values |
| `Capacitors_Electrolytic` | Capacitors - Electrolytic 50V | SMD aluminium electrolytic, 50 V, E6 values |
| `Inductors` | Inductors | E12: 0402 (1n–470n), 0805 (2.2n–100u), 1210 (1u–100u) |
| `Inductors_RF` | Inductors - RF 0402 | 0402 fine-step RF inductors |
| `Ferrite_Beads` | Ferrite Beads | 22 / 100 / 220 / 330 / 1k ohm @ 100 MHz, 0402 / 0805 |

**Manufacturer policy:** Vishay (Dale, Vitramon, Sprague, BCcomponents) and Würth
Elektronik are preferred. Parts from other manufacturers (for example YAGEO) are only
used to fill values the preferred makers don't stock at DigiKey. Supplier: DigiKey
(Cut Tape part numbers).

There are two thin-film tables. The 0.1% precision table uses Vishay Dale TNPW, which
DigiKey stocks across the full E96 series. The 1% table uses Vishay where it's stocked
and falls back to YAGEO RT for the remaining values.

Symbols and footprints come from KiCad's standard libraries (`Device:R`, `Device:C`,
`Device:C_Polarized`, `Device:L`, `Device:FerriteBead`, plus `Resistor_SMD`, `Capacitor_SMD`,
`Capacitor_Tantalum_SMD` and `Inductor_SMD`), so you don't need any custom libraries.

## Files

| File | Purpose |
|---|---|
| `company_parts.kicad_dbl` | KiCad library definition (ODBC connection + table/field mapping) |
| `parts.sqlite` | The database. Keep it **next to** the `.kicad_dbl` |
| `init_db.py` | Rebuilds `parts.sqlite` from `seed/*.py` |
| `seed/schema.py` | Column list, table names, symbol/footprint mapping |
| `seed/*.py` | Part data per category |
| `digikey_enrich.py` | Refreshes DigiKey part numbers, stock, status and datasheets |
| `SETUP_DB.md` | Step-by-step setup and maintenance guide |

## Setup

For the full step-by-step guide (Windows first, plus macOS and Linux), with
verification steps and troubleshooting, see **[SETUP_DB.md](SETUP_DB.md)**.

In short:

1. Install the **64-bit** SQLite ODBC driver (`sqliteodbc_w64.exe` from
   <http://www.ch-werner.de/sqliteodbc/>). Check that it's listed as
   `SQLite3 ODBC Driver` in **ODBC Data Sources (64-bit) → Drivers**.
2. Keep `parts.sqlite` next to `company_parts.kicad_dbl`. KiCad replaces `${CWD}`
   with the folder that holds the `.kicad_dbl`.
3. In KiCad, go to **Preferences → Manage Symbol Libraries → Global Libraries** and add
   `company_parts.kicad_dbl` (Library Format: **Database**, nickname e.g. `Company_Parts`).

On macOS and Linux, change the `Driver=` part of `connection_string` to the locally
registered driver name (`odbcinst -q -d`). See SETUP_DB.md for details.

## Rebuilding the database

```
python init_db.py
```

This regenerates `parts.sqlite` from `seed/*.py`. Close KiCad (or reload the library)
first, so the file isn't locked.

## Refreshing DigiKey data

You need a DigiKey API app (developer.digikey.com, Product Information v4, production)
that uses client credentials. Credentials are read only from environment variables.

PowerShell:

```powershell
$env:DIGIKEY_CLIENT_ID="..."
$env:DIGIKEY_CLIENT_SECRET="..."
python digikey_enrich.py --dry-run          # query only; the database isn't changed
python digikey_enrich.py --prune            # update rows, and delete dead/out-of-stock parts
```

The API allows about **1000 calls per day**, and each part uses one call. The script
prints the remaining quota and stops when it drops below `--reserve` (default 20). To
continue the next day, run `--only-unchecked` or `--older-than DAYS`.

Other options:
- `--tables Capacitors_Ceramic Inductors`: check only those tables.
- `--limit N`: check at most N parts.
- `--delay S`: wait S seconds between calls.
- `--db PATH`: use a different database file.

See `--help` for the full list.

`--prune` deletes a row when its MPN is unknown to DigiKey, is Obsolete or
Discontinued, or has zero stock in every package. Every pruned row is listed in the
output. Run it with `--dry-run` first to preview. To keep a pruned part permanently,
remove it from the seed module or fix its MPN there, because `init_db.py` brings
seeded rows back.

## Adding parts

Edit the matching `seed/*.py` module. Each row needs at least `Part_ID`, `Symbol`,
`Footprint` and `Value`, and the columns are listed in `seed/schema.py`. Then run
`python init_db.py`, and optionally
`python digikey_enrich.py --only-unchecked` to fill in the DigiKey data.

## Troubleshooting

- **"Data source name not found and no default driver specified":** the driver name in
  `connection_string` doesn't match an installed driver. Check the Drivers tab, or
  `odbcinst -q -d`. Another cause is a 32-bit/64-bit mismatch: 64-bit KiCad needs the
  64-bit driver (`sqliteodbc_w64.exe`).
- **Libraries appear but are empty:** KiCad can't find `parts.sqlite`. Make sure it
  sits next to the `.kicad_dbl` (that's where `${CWD}` points), and that `init_db.py`
  has been run. If the path still fails, replace `${CWD}` with an absolute path to test.
- **Footprint not found when placing a part:** the standard KiCad footprint libraries
  (`Resistor_SMD`, `Capacitor_SMD`, `Capacitor_Tantalum_SMD`, `Inductor_SMD`) need to be
  in your footprint library table under their default nicknames.

For more cases, see the troubleshooting table in [SETUP_DB.md](SETUP_DB.md#12-troubleshooting).
