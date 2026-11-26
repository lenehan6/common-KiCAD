# Application parts database library

A KiCad **database library** for application parts: ICs, power, interface, MCUs, sensors, RF,
connectors, and so on. Each KiCad stock symbol gets one real, orderable DigiKey part.

It is **separate from the commodity library** in `../kicad_dbl_library/`, which holds
resistors, capacitors, small-signal diodes and transistors, headers, LEDs, and similar parts.
The two libraries share the ODBC setup, the DigiKey client and cache (`tools/dk_client.py`,
`tools/cache/`), and the spec engine (`tools/build_commodity.py`). They do not share tables,
files, or approval state.

| file | what it is |
|---|---|
| `application.sqlite` | the database. It's generated, so don't edit it; rebuild it with `init_app_db.py` |
| `application_parts.kicad_dbl` | KiCad library pointing at the `<Table>_Active` views: every usable part, reviewed or not |
| `application_parts_approved.kicad_dbl` | KiCad library pointing at the `<Table>_Approved` views: engineering-approved parts only |
| `app_schema.py` | columns, 26 tables, and the mapping from each KiCad library to a table (`LIBRARY_TO_TABLE`) |
| `init_app_db.py` | builds `application.sqlite` from all the sources below |
| `catalog.sqlite`, `TRIAGE.md` | KiCad symbol catalog and triage (`tools/scan_kicad_symbols.py`) |
| `prefill/matches.json` | daily DigiKey prefill output: `{"Lib:Symbol": [DigiKey products]}` |
| `specs/*.py`, `seed/generated/`, `seed/locks/` | spec-built tables (currently `Connectors_USB`) and their locks; `seed/locks/_prefill.json` pins the MPN chosen for each prefilled symbol |
| `reviews.json` | engineering reviews `{Part_ID: {Review_Status, Reviewed_By, Review_Date, Review_Notes[, Footprint]}}` |
| `manual_parts.json` | parts added by hand (`tools/app_part.py add`) |
| `REVIEW_CHECKLIST.md` | what to check before approving a part |

## How the data gets in

1. **Daily prefill.** `tools/prefill_app.py` works through the application-group symbols in
   `catalog.sqlite` in priority order. It uses about 900 DigiKey calls per day and is
   resumable. It harvests MPN prefixes and matches every symbol's name pattern against the
   results, then writes them to `prefill/matches.json`. Full coverage of about 19,000 symbols
   takes a few weeks, and you can rebuild the database at any point along the way.
2. **Build.** `python3 application_dbl/init_app_db.py` turns each processed symbol into one row:
   - The best hit is chosen by lifecycle (Active, then NRND or Last Time Buy, then
     Discontinued at DigiKey, then Obsolete). Ties are broken by an MPN equal to the symbol
     name, then a package matching the KiCad footprint, then packaging (Cut Tape, Bulk, Tube,
     Tray, then other; never Tape & Reel or Digi-Reel), then stock.
   - `Part_ID` is `<prefix>-<MPN>`, for example `PWR-TPS2042DR`. It stays stable because the
     chosen MPN is locked in `seed/locks/_prefill.json`. The MPN only changes when it
     disappears from DigiKey or a better lifecycle tier appears.
   - The other matching MPNs go into `Candidates`.
   - Symbols with no DigiKey hit still get a row (`MPN` empty, `Lifecycle` "Not found at
     DigiKey") so the review list is complete. Their Part_ID is `<prefix>-SYM-<symbol>`.
   - Symbols without a default footprint get `Footprint` "" and an `[auto]` note. They stay out
     of the KiCad views until you assign a footprint, with `app_part.py review ... --footprint`
     or `add --footprint`.
   - Spec-built rows (`seed/generated/*.json`), manual parts, and reviews are merged in at the
     end. Reviews and manual parts survive every rebuild.
3. **Spec-built tables** use the commodity engine. For example:
   `python3 tools/build_commodity.py Connectors_USB --lib application_dbl --offline`
   (drop `--offline` to refresh from DigiKey). The USB spec only uses parts that have an exact
   KiCad `Connector_USB` footprint, and it records the symbol-pin vs footprint-pad check in
   `Pinout` / `Pinout_Source`.

A typical daily job:

```sh
python3 tools/prefill_app.py --budget 900
python3 tools/build_commodity.py Connectors_USB --lib application_dbl   # optional, refresh USB
python3 application_dbl/init_app_db.py
```

## Views

| view | content |
|---|---|
| `<Table>_Active` | MPN set, footprint set, `Lifecycle` not Obsolete, `Review_Status` not Rejected or Obsolete, `Status` not Obsolete |
| `<Table>_Approved` | `Review_Status` = Approved and footprint set |
| `All_Parts` | every row of every table, plus a `Table_Name` column. Used by `app_part.py` and for queries |

## Review and approve

```sh
python3 tools/app_part.py list --table Regulators_Linear --status Unreviewed
python3 tools/app_part.py show LDO-TLV75533PDBVR
python3 tools/app_part.py review LDO-TLV75533PDBVR --status Approved --by "J. Doe" \
        --notes "pinout vs DS rev F p.3 OK; 2nd source AP7343"
python3 tools/app_part.py review CON-SYM-XYZ --status Rejected --by "J. Doe" --notes "no longer made"
python3 tools/app_part.py add Connector:USB_C_Receptacle_USB2.0_16P USB4110-GF-A \
        --footprint Connector_USB:USB_C_Receptacle_GCT_USB4110 --by "J. Doe"
```

- `review` writes to `reviews.json` and then rebuilds the database. It refuses to approve a row
  that has no MPN or footprint, or whose lifecycle is Obsolete, unless you pass `--force`.
- `add` takes the DigiKey data from the prefill or the DigiKey cache when it is there.
  Otherwise the supplier fields stay blank until `init_app_db.py --fetch-manual N` fetches the
  details, using up to N DigiKey API calls.
- Work through `REVIEW_CHECKLIST.md` for every part you approve.
- Commit `reviews.json` and `manual_parts.json`. They are the only hand-maintained state.

## Add the library to KiCad

Install the 64-bit SQLite ODBC driver as described in `../kicad_dbl_library/SETUP_DB.md`
(steps 2-4). Then:

1. Keep `application.sqlite` next to the `.kicad_dbl` files. The connection string is
   `Driver={SQLite3 ODBC Driver};Database=${CWD}/application.sqlite;`.
2. In KiCad, go to **Preferences → Manage Symbol Libraries** and add
   `application_parts_approved.kicad_dbl`. Give it a nickname such as `AppParts_Approved`.
   This is the library to use for production designs.
3. Optionally add `application_parts.kicad_dbl` as well, for example as `AppParts_All`. It is
   useful for exploring parts and for early prototypes.
4. The chooser shows Value, Part ID, Review Status, Lifecycle, MPN, Manufacturer, Supplier PN,
   Packaging, Key Params, Package, and DK Stock.
5. The library uses KiCad stock symbols and footprints only, so the standard libraries must be
   in your symbol and footprint tables under their default nicknames.

After a rebuild, reopen the Symbol Chooser. Use **Tools → Update Symbols from Library** to
refresh fields on symbols already placed.

## Relation to the commodity library

| | commodity (`kicad_dbl_library`) | application (`application_dbl`) |
|---|---|---|
| content | passives, small discretes, headers, LEDs | ICs, modules, application connectors |
| selection | specs per value/size slot, fully automatic | one row per KiCad symbol, best DigiKey hit, then human review |
| KiCad file | `company_parts.kicad_dbl` → `parts.sqlite` | `application_parts*.kicad_dbl` → `application.sqlite` |
| approval | implicit (spec rules) | explicit `Review_Status` per part |

SOT-23-class small-signal transistors are flagged `commodity_overlap` in the catalog. Prefer
the commodity library for those parts.
