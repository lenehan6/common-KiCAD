# Setting up the Company Parts database library

This guide covers installing, connecting and maintaining the KiCad database library
in this folder (`company_parts.kicad_dbl` + `parts.sqlite`). It covers **Windows** first,
because that's the target OS, followed by short sections for [macOS](#macos) and
[Linux](#linux).

**Contents**

1. [Prerequisites](#1-prerequisites)
2. [Install the SQLite ODBC driver](#2-install-the-sqlite-odbc-driver)
3. [Verify the driver name](#3-verify-the-driver-name)
4. [Test the driver (optional)](#4-test-the-driver-optional)
5. [Place the library folder](#5-place-the-library-folder)
6. [Add the library in KiCad](#6-add-the-library-in-kicad)
7. [Confirm it works](#7-confirm-it-works)
8. [BOM tips](#8-bom-tips)
9. [Rebuilding the database](#9-rebuilding-the-database)
10. [Refreshing DigiKey data](#10-refreshing-digikey-data)
11. [Updating KiCad after database changes](#11-updating-kicad-after-database-changes)
12. [Troubleshooting](#12-troubleshooting)
13. [macOS](#macos)
14. [Linux](#linux)

---

## Windows

### 1. Prerequisites

| Item | Needed for | Notes |
|---|---|---|
| **KiCad 8 or 9, 64-bit** | Using the library | The standard Windows installer is 64-bit. |
| **SQLite ODBC driver, 64-bit** | Using the library | See step 2. Its bitness must match KiCad's. |
| **Python 3.9+** | Only for rebuilding or refreshing the DB | Not needed just to *use* the parts. `parts.sqlite` ships ready-made. |

The library uses only KiCad's standard symbol libraries (`Device`) and footprint
libraries (`Resistor_SMD`, `Capacitor_SMD`, `Inductor_SMD`, ...), so you don't need any
custom libraries.

### 2. Install the SQLite ODBC driver

1. Go to <http://www.ch-werner.de/sqliteodbc/>.
2. Download **`sqliteodbc_w64.exe`**. This is the 64-bit build. The `sqliteodbc.exe`
   build without `_w64` is 32-bit and **won't work** with 64-bit KiCad.
3. Run the installer with the default options. Administrator rights are required.

### 3. Verify the driver name

1. Open the Start menu and search for **"ODBC Data Sources (64-bit)"**. Make sure you
   open the 64-bit version, not the 32-bit one.
2. Open the **Drivers** tab.
3. Find the entry that reads exactly **`SQLite3 ODBC Driver`**.

That name must match the `Driver={...}` part of `connection_string` in
`company_parts.kicad_dbl`:

```json
"connection_string": "Driver={SQLite3 ODBC Driver};Database=${CWD}/parts.sqlite;"
```

If the Drivers tab shows a different name (for example a localized or older one), copy it
exactly, including spaces and capitalization, into the braces of `Driver={...}`. You
don't need to create a DSN, because the driver is named directly in the connection string.

### 4. Test the driver (optional)

PowerShell:

```powershell
Get-OdbcDriver -Name "SQLite3*" -Platform 64-bit
```

You should see a `SQLite3 ODBC Driver` entry with `Platform : 64-bit`. If nothing is
listed, the 64-bit driver isn't installed (repeat step 2).

To confirm that the database file itself is readable, you can run this optional check
(it needs Python):

```powershell
python -c "import sqlite3; c=sqlite3.connect('parts.sqlite'); print(c.execute('select count(*) from Capacitors_Ceramic').fetchone())"
```

### 5. Place the library folder

- **Keep `parts.sqlite` in the same folder as `company_parts.kicad_dbl`.** The connection
  string uses `${CWD}`, and KiCad replaces it with the folder that contains the
  `.kicad_dbl` file.
- Use a **stable path** that won't move, for example `C:\KiCad\common-KiCAD\kicad_dbl_library`.
  The best choice is a **git clone of this repository**, because you can then get
  updates with `git pull`.
- Avoid folders that sync aggressively (OneDrive/Dropbox "online-only" files) or that are
  read-only. KiCad needs to open the file directly.
- *Optional:* define a KiCad path variable under **Preferences → Configure Paths**, for
  example `COMPANY_PARTS = C:\KiCad\common-KiCAD\kicad_dbl_library`, and add the library
  as `${COMPANY_PARTS}/company_parts.kicad_dbl`. If the folder moves later, you then only
  change the variable.

### 6. Add the library in KiCad

1. Open KiCad and go to **Preferences → Manage Symbol Libraries**.
2. Select the **Global Libraries** tab. Use **Project Specific Libraries** instead if you
   only want the library in one project.
3. Click the **folder icon** (*Add existing library to table*), then select
   `company_parts.kicad_dbl`.
4. KiCad detects the file and sets **Library Format** to **Database**. If it doesn't,
   select *Database* from the drop-down.
5. Set the **Nickname** to **`Company_Parts`** (suggested).
6. Click **OK**.

### 7. Confirm it works

1. Open the Schematic Editor and press **A** (*Add Symbol*) to open the Symbol Chooser.
2. Expand **Company_Parts**. It should list these 11 categories:

   | Library (in KiCad) | Table |
   |---|---|
   | Resistors - Thin Film 0.1% Precision | `Resistors_ThinFilm_Precision` |
   | Resistors - Thin Film 1% | `Resistors_ThinFilm_1pct` |
   | Resistors - Thick Film 5% | `Resistors_ThickFilm` |
   | Capacitors - Ceramic | `Capacitors_Ceramic` |
   | Capacitors - RF 0402 C0G | `Capacitors_RF` |
   | Capacitors - Bulk | `Capacitors_Bulk` |
   | Capacitors - Tantalum 50V | `Capacitors_Tantalum` |
   | Capacitors - Electrolytic 50V | `Capacitors_Electrolytic` |
   | Inductors | `Inductors` |
   | Inductors - RF 0402 | `Inductors_RF` |
   | Ferrite Beads | `Ferrite_Beads` |

3. Place any part, then open its properties (**E**). Check that:
   - **Value**, **MPN**, **Manufacturer**, **Supplier** and **Supplier PN** are filled in.
   - A **footprint** is assigned, for example `Resistor_SMD:R_0402_1005Metric`.
   - The datasheet link opens.

### 8. BOM tips

Each placed part carries the fields **MPN**, **Manufacturer**, **Supplier** (always
`DigiKey`) and **Supplier PN** (the DigiKey Cut Tape part number). The BOM exporter
(**Tools → Generate Bill of Materials** in KiCad 8/9) can show all of them as columns.
Group by *Value + Footprint + MPN* to get a BOM you can order from directly, and use
the DigiKey part number column for the DigiKey BOM upload.

### 9. Rebuilding the database

Only needed after you edit the part data in `seed/*.py`:

```powershell
cd C:\KiCad\common-KiCAD\kicad_dbl_library
python init_db.py
```

This deletes and regenerates `parts.sqlite`. Close KiCad first, or at least close the
Symbol Chooser, so the file isn't locked.

### 10. Refreshing DigiKey data

`digikey_enrich.py` refreshes DigiKey part numbers, stock, product status and
datasheet links. You need a DigiKey API application (developer.digikey.com,
*Product Information v4*, production) that uses client credentials. The script reads
the credentials **only from environment variables**.

```powershell
$env:DIGIKEY_CLIENT_ID="..."
$env:DIGIKEY_CLIENT_SECRET="..."

python digikey_enrich.py --dry-run                  # query only; the DB isn't changed
python digikey_enrich.py                            # update rows in place
python digikey_enrich.py --prune --dry-run          # preview which parts would be removed
python digikey_enrich.py --prune                    # also delete dead / out-of-stock parts
python digikey_enrich.py --only-unchecked           # continue where a previous run stopped
python digikey_enrich.py --tables Capacitors_Tantalum Capacitors_Electrolytic
```

- **Rate limit:** about **1000 API calls per day**, one call per part. The script stops
  when the remaining quota drops below `--reserve` (default 20). Continue the next day
  with `--only-unchecked` or `--older-than DAYS`.
- `--prune` deletes rows whose MPN is unknown to DigiKey, Obsolete/Discontinued, or out
  of stock everywhere. `init_db.py` brings seeded rows back, so to keep a part removed,
  delete it from (or fix it in) `seed/*.py` too.
- **Never commit credentials.** Don't put them in scripts, `.kicad_dbl` files or the
  repository. Set them per session as shown above, or as user environment variables.

### 11. Updating KiCad after database changes

KiCad caches database libraries and keeps the ODBC connection open. After you rebuild
or refresh `parts.sqlite`:

- **Restart KiCad** (the most reliable option), or
- at minimum, close and re-open the Symbol Chooser. Changing the `.kicad_dbl` file
  itself (connection string, field mapping) always needs a restart.

Symbols already placed in a schematic keep their old field values. To pull in new data,
use **Tools → Update Symbols from Library**.

### 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| *"Data source name not found and no default driver specified"* / driver not found | Driver name mismatch, or 32-bit driver with 64-bit KiCad | Check the **ODBC Data Sources (64-bit)** Drivers tab (step 3). Install `sqliteodbc_w64.exe`. Make `Driver={...}` match the installed name exactly. |
| Library loads but the categories are empty | KiCad can't find or open `parts.sqlite` | Keep it next to the `.kicad_dbl` (that's what `${CWD}` resolves to). Check that the file exists (run `init_db.py`), isn't locked by another program or in an online-only sync folder. To test, replace `${CWD}` with an absolute path such as `Database=C:/KiCad/.../parts.sqlite;`. |
| Library missing or shown with an error icon | Wrong format or path in the library table | Check that **Library Format** is *Database* and the path or path variable is correct. |
| Some fields are missing or blank on placed parts | A `column` in the `.kicad_dbl` doesn't match a column in the DB, or the value is empty | Column names are case-sensitive and must match `seed/schema.py`. Rebuild the DB if you've changed the schema. |
| Footprint "not found" when placing | Standard footprint libraries aren't in your footprint table under their default nicknames | Add `Resistor_SMD`, `Capacitor_SMD`, `Inductor_SMD` (and `Capacitor_Tantalum_SMD` for polarized caps) through **Manage Footprint Libraries**. |
| Slow loading or timeouts | Slow network drive | Copy the folder to a local disk, or increase `"timeout_seconds"` in the `source` section of the `.kicad_dbl`. |
| Changes not visible | KiCad cache | Restart KiCad (step 11). |

---

## macOS

1. Install KiCad 8/9 (Apple Silicon or Intel build matching your Mac).
2. Install the driver and driver manager:
   ```sh
   brew install sqliteodbc unixodbc
   ```
3. Find the registered driver name:
   ```sh
   odbcinst -q -d
   ```
   If it isn't listed, register it in `$(brew --prefix)/etc/odbcinst.ini`:
   ```ini
   [SQLite3]
   Description = SQLite3 ODBC Driver
   Driver      = /opt/homebrew/lib/libsqlite3odbc.dylib
   ```
   (Intel Macs use `/usr/local/lib/...`. Check the path with `ls $(brew --prefix)/lib/libsqlite3odbc*`.)
4. Edit `connection_string` in `company_parts.kicad_dbl` to use that name, or the
   full path to the `.dylib`:
   ```json
   "connection_string": "Driver={SQLite3};Database=${CWD}/parts.sqlite;"
   ```
   ```json
   "connection_string": "Driver=/opt/homebrew/lib/libsqlite3odbc.dylib;Database=${CWD}/parts.sqlite;"
   ```
5. Continue with [steps 5–12](#5-place-the-library-folder). For DigiKey credentials use
   `export DIGIKEY_CLIENT_ID=...` and `export DIGIKEY_CLIENT_SECRET=...`.

> Don't commit a platform-specific `connection_string` back to the repository, because
> Windows is the target. Keep local edits uncommitted, or use a local copy of the file.

## Linux

1. Install KiCad 8/9 from your distribution or the KiCad PPA/Flatpak.
2. Install the driver:
   ```sh
   sudo apt install libsqliteodbc unixodbc     # Debian / Ubuntu
   sudo dnf install sqliteodbc unixODBC        # Fedora
   ```
3. Check the driver name (usually **`SQLite3`**, defined in `/etc/odbcinst.ini`):
   ```sh
   odbcinst -q -d
   ```
4. Edit `connection_string` in `company_parts.kicad_dbl`:
   ```json
   "connection_string": "Driver={SQLite3};Database=${CWD}/parts.sqlite;"
   ```
5. Continue with [steps 5–12](#5-place-the-library-folder), using `export` for the
   DigiKey environment variables.

> **Flatpak KiCad:** the sandbox can't see the host's ODBC drivers by default. Use
> the distribution package or PPA build of KiCad for database libraries.
