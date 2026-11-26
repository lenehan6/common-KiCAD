# Company Parts Library (KiCad database library)

A KiCad [database library](https://docs.kicad.org/master/en/eeschema/eeschema.html#database-libraries)
backed by a single SQLite file. Each part row carries its KiCad symbol, footprint,
footprint filter, datasheet and DigiKey ordering info, so placed parts arrive with
MPN and supplier part number already filled in.

**Tables.** There are 27, and each one appears as its own library in the symbol chooser.
KiCad reads a `<Table>_Active` view of each table rather than the table itself (see
[Part status](#part-status)).

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
| `Diodes_Signal` | Diodes - Signal | Small-signal switching diodes, SOD-123 / SOD-323 / SOD-523 |
| `Diodes_Schottky` | Diodes - Schottky | Schottky rectifiers 0.2–3 A, 20–60 V, SOD-323 / SOD-123 / SMA |
| `Diodes_Zener` | Diodes - Zener | Zener E24 2.4–36 V, SOD-123 / SOD-323 |
| `Diodes_TVS` | Diodes - TVS | SMAJ / SMBJ TVS, unidirectional and bidirectional |
| `ESD_Protection` | ESD Protection | Low-capacitance ESD diodes and small USB/data-line arrays |
| `LEDs` | LEDs | Indicator LEDs, 0402 / 0603 / 0805 |
| `MOSFETs_SmallSignal` | Transistors - MOSFET Small Signal | SOT-23 N- and P-channel |
| `BJTs_SmallSignal` | Transistors - BJT Small Signal | SOT-23 NPN / PNP |
| `LDOs` | Regulators - LDO | 3.3 V and 1.8 V LDOs (TI preferred) |
| `Polyfuses` | Fuses - Resettable PTC | Resettable PTC fuses (Littelfuse preferred) |
| `Fuses_Chip` | Fuses - Chip | Fast-acting SMD chip fuses, 0402 / 0603 / 1206 |
| `Switches_Tactile` | Switches - Tactile | SMD tactile switches |
| `Headers_2p54mm` | Headers - 2.54mm | 2.54 mm pin headers, 1xN / 2xN |
| `Headers_1p27mm` | Headers - 1.27mm | 1.27 mm pin headers, 1xN / 2xN |
| `Headers_IDC_Shrouded` | Headers - IDC Shrouded | Shrouded IDC box headers |
| `TestPoints` | Test Points | SMD / THT test points |

**Manufacturer policy:** Vishay (Dale, Vitramon, Sprague, BCcomponents) and Würth
Elektronik are preferred for passives. Each table's spec in `specs/` sets the preferred
makers for that category; other makers are used only to fill gaps. Supplier: DigiKey,
using **Cut Tape** part numbers (Bulk for loose or through-hole parts). Tape & Reel and
Digi-Reel part numbers are never used.

## Part status

Every row has a `Status` column. The chooser shows it as a column.

- **Active:** use it.
- **Deprecated:** still shown, so existing designs resolve, but don't use it in new
  designs. `Superseded_By` names the replacement Part_ID.
- **Obsolete:** hidden. Each `<Table>_Active` view (for example
  `Resistors_ThickFilm_Active`) leaves out Obsolete rows, and `company_parts.kicad_dbl`
  points KiCad at those views.

Rows are never deleted and Part_IDs are never renamed, because placed symbols reference
them.

## Symbols and footprints

All symbols and footprints come from KiCad's **standard libraries**, so you don't need
any custom libraries. You do need these **default symbol libraries enabled** in
*Preferences → Manage Symbol Libraries*:

`Device`, `Diode`, `Transistor_FET`, `Transistor_BJT`, `Regulator_Linear`,
`Connector_Generic`, `Switch`, `Connector`, `Power_Protection`

If one is disabled or missing, parts from that category are placed as **text only, with
no symbol body**. You also need the default footprint libraries (`Resistor_SMD`,
`Capacitor_SMD`, `Capacitor_Tantalum_SMD`, `Inductor_SMD`, `Diode_SMD`, `LED_SMD`,
`Fuse`, `Package_TO_SOT_SMD`, `Package_SON`, `Button_Switch_SMD`,
`Connector_PinHeader_2.54mm`, `Connector_PinHeader_1.27mm`, `Connector_IDC`,
`TestPoint`).

Transistors and regulators use **pin-order-specific symbols**: the part's own KiCad
symbol (for example `Transistor_FET:2N7002` or `Transistor_BJT:BC817`), or an explicit
variant such as `Transistor_FET:Q_NMOS_GSD`. The generic `Device:Q_*` symbols are **not
used**, because their pin order doesn't have to match the package. Each semiconductor
row records its physical `Pinout` (for example `1=G 2=S 3=D`), and `tools/validate.py`
checks it against the symbol.

## Files

| File | Purpose |
|---|---|
| `company_parts.kicad_dbl` | KiCad library definition (ODBC connection + view/field mapping) |
| `parts.sqlite` | The database. Keep it **next to** the `.kicad_dbl` |
| `init_db.py` | Rebuilds `parts.sqlite` (tables + `*_Active` views) from `seed/generated/*.json` |
| `seed/schema.py` | Column list, table names, view naming |
| `seed/generated/*.json` | Part data per table (generated by `tools/build_commodity.py`) |
| `seed/locks/*.json` | Part_ID -> MPN pins, so a rebuild keeps chosen parts |
| `specs/*.py` | Selection rules per table (queries, slots, ranking) |
| `reports/*.md` | Build reports: changes, gaps, cache misses |
| `../tools/build_commodity.py` | Spec-driven builder, using the DigiKey API and cache |
| `../tools/validate.py` | Offline validation, also run in CI |
| `digikey_enrich.py` | Legacy ad-hoc DigiKey spot check (see MAINTAINING.md) |
| `SETUP_DB.md` | Step-by-step setup guide for users |
| `MAINTAINING.md` | Maintainer guide: adding parts and tables, monthly refresh, rules |

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
4. Make sure the default symbol libraries listed [above](#symbols-and-footprints) are
   enabled.

On macOS and Linux, change the `Driver=` part of `connection_string` to the locally
registered driver name (`odbcinst -q -d`). See SETUP_DB.md for details.

## Maintaining

See **[MAINTAINING.md](MAINTAINING.md)** for how the build works, adding values and
tables, the monthly DigiKey refresh, retiring parts, and the Cut Tape and pinout rules.
In short, from the repository root:

```sh
python tools/build_commodity.py all --refresh   # needs DIGIKEY_CLIENT_ID / DIGIKEY_CLIENT_SECRET
python kicad_dbl_library/init_db.py
python tools/validate.py
```

Close KiCad (or reload the library) before rebuilding, so the file isn't locked.

## Troubleshooting

- **"Data source name not found and no default driver specified":** the driver name in
  `connection_string` doesn't match an installed driver. Check the Drivers tab, or
  `odbcinst -q -d`. Another cause is a 32-bit/64-bit mismatch: 64-bit KiCad needs the
  64-bit driver (`sqliteodbc_w64.exe`).
- **Libraries appear but are empty:** KiCad can't find `parts.sqlite`. Make sure it
  sits next to the `.kicad_dbl` (that's where `${CWD}` points), and that `init_db.py`
  has been run. If the path still fails, replace `${CWD}` with an absolute path to test.
- **Placed part shows only text (Value/Reference) and no symbol body:** the symbol's
  library (`Device`, `Transistor_FET`, ...) is disabled or missing in your symbol library
  table. Enable it under *Manage Symbol Libraries*, using its default nickname.
- **Footprint not found when placing a part:** the standard KiCad footprint libraries
  need to be in your footprint library table under their default nicknames.

For more cases, see the troubleshooting table in [SETUP_DB.md](SETUP_DB.md#12-troubleshooting).
