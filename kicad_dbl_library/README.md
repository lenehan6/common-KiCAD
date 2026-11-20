# Company Parts Library (KiCad database library)

A KiCad [database library](https://docs.kicad.org/master/en/eeschema/eeschema.html#database-libraries)
backed by a single SQLite file. Each part row carries its KiCad symbol, footprint,
footprint filter, datasheet and DigiKey ordering info, so placed parts arrive with
MPN and supplier part number already filled in.

**Tables** (each appears as its own library in the symbol chooser):

| Table | Library name | Contents |
|---|---|---|
| `Resistors_ThinFilm` | Resistors - Thin Film 0.1% | Vishay Dale TNPW, 0.1%, E96, 0402 / 0805 |
| `Resistors_ThickFilm` | Resistors - Thick Film 5% | Vishay Dale CRCW, 5%, E12 (+0R), 0402 / 0805 |
| `Capacitors` | Capacitors | MLCC, E12, >=50 V, C0G / X7R, 0402 / 0805 |
| `Capacitors_RF` | Capacitors - RF 0402 C0G | 0402 C0G/NP0 fine-step values, >=50 V |
| `Capacitors_Bulk` | Capacitors - Bulk | MLCC >=10 uF, >=50 V, X7R+, 1210 / 1812 / 2220 |
| `Inductors` | Inductors | E12, 0402 / 0805 |
| `Inductors_RF` | Inductors - RF 0402 | 0402 fine-step RF inductors |
| `Ferrite_Beads` | Ferrite Beads | 22 / 100 / 220 / 330 / 1k ohm @ 100 MHz, 0402 / 0805 |

Manufacturers: Vishay Dale, Vishay Vitramon, Würth Elektronik. Supplier: DigiKey
(Cut Tape part numbers).

The thin-film table is 0.1% rather than 1% because DigiKey doesn't stock TNPW at 1%
across the full E96 series. The 0.1% parts are stocked.

Symbols and footprints come from KiCad's standard libraries (`Device:R`, `Device:C`,
`Device:L`, `Device:FerriteBead`, plus `Resistor_SMD`, `Capacitor_SMD` and `Inductor_SMD`),
so you don't need any custom libraries.

## Files

| File | Purpose |
|---|---|
| `company_parts.kicad_dbl` | KiCad library definition (ODBC connection + table/field mapping) |
| `parts.sqlite` | The database. Keep it **next to** the `.kicad_dbl` |
| `init_db.py` | Rebuilds `parts.sqlite` from `seed/*.py` |
| `seed/schema.py` | Column list, table names, symbol/footprint mapping |
| `seed/*.py` | Part data per category |
| `digikey_enrich.py` | Refreshes DigiKey part numbers, stock, status and datasheets |

## Setup: Windows

1. Install the SQLite ODBC driver from <http://www.ch-werner.de/sqliteodbc/>.
   Use **`sqliteodbc_w64.exe`** for 64-bit KiCad, which is the normal install.
2. Open **ODBC Data Sources (64-bit)** and check the **Drivers** tab. It should list
   **`SQLite3 ODBC Driver`**. That name must match the `Driver={...}` part of
   `connection_string` in `company_parts.kicad_dbl`.
3. In KiCad, go to **Preferences → Manage Symbol Libraries → Global Libraries** (or
   **Project Specific Libraries**). Add `company_parts.kicad_dbl` and set the Library
   Format to **Database**.
4. Keep `parts.sqlite` in the same folder as `company_parts.kicad_dbl`. The
   connection string uses `Database=${CWD}/parts.sqlite`, and KiCad replaces `${CWD}`
   with the folder that holds the `.kicad_dbl` file.

No DSN is needed. The driver is selected directly in `connection_string`.

## Setup: macOS / Linux

**macOS:** run `brew install sqliteodbc`, then register the driver in `odbcinst.ini`
(`brew --prefix` gives you the path to `libsqlite3odbc.dylib`). Check the driver name
with `odbcinst -q -d` and use that exact name in `Driver={...}`.

**Linux (Debian/Ubuntu):** run `sudo apt install libsqliteodbc`. The driver name in
`/etc/odbcinst.ini` is usually `SQLite3`, so change `connection_string` to
`Driver={SQLite3};Database=${CWD}/parts.sqlite;`.

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
- `--tables Capacitors Inductors`: check only those tables.
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
  (`Resistor_SMD`, `Capacitor_SMD`, `Inductor_SMD`) need to be in your footprint
  library table under their default nicknames.
