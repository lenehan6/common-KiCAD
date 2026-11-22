# Maintaining the Company Parts database

This is the maintainer guide. For installing the library in KiCad, see
[SETUP_DB.md](SETUP_DB.md). For an overview, see [README.md](README.md).

All commands run from the repository root (`common-KiCAD/`) and need Python 3.9+
(stdlib only).

## 1. How it works

```
specs/<Table>.py ─┐
                  ├─> tools/build_commodity.py ─> seed/generated/<Table>.json ─┐
DigiKey API ──────┤        │                      seed/locks/<Table>.json      │
(tools/cache/     │        └─> reports/<Table>.md                              │
 dk_cache.sqlite) ┘                                                            v
                         kicad_dbl_library/init_db.py ─> parts.sqlite (27 tables + 27 <Table>_Active views)
                                                                               │
                                     company_parts.kicad_dbl (one library per *_Active view) ─> KiCad
                                     tools/validate.py checks all of the above (also in CI)
```

| Piece | Role |
|---|---|
| `seed/schema.py` | The contract: `COLUMNS` (incl. `Status`, `Superseded_By`, `Pinout`, `Pinout_Source`), `TABLES` (27), `view_name()` |
| `specs/<Table>.py` | Selection rules for one table: DigiKey `QUERIES`, `slots()` (one per Part_ID), `accept()`, `rank()`, `make_row()`. `specs/Ferrite_Beads.py` is a short example; shared helpers are in `specs/_common.py`. |
| `tools/build_commodity.py` | Fills every slot with the best eligible DigiKey part and writes `seed/generated/<Table>.json`, `seed/locks/<Table>.json` and `reports/<Table>.md` |
| `tools/dk_client.py` | DigiKey Product Information v4 client with a persistent response cache and a call budget |
| `seed/generated/<Table>.json` | The row data that `init_db.py` loads. Committed. |
| `seed/locks/<Table>.json` | `Part_ID -> MPN` pins. A slot keeps its part until that part stops being eligible. Committed. |
| `init_db.py` | Rebuilds `parts.sqlite` from scratch: every schema table, plus a `<Table>_Active` view that hides `Status = 'Obsolete'` rows |
| `company_parts.kicad_dbl` | KiCad's mapping. Every library points at a **`*_Active` view**, never at a raw table |
| `tools/validate.py` | Offline consistency checks (sections 7, 8, 10, 11) |
| `tools/kicad_names.json` | Offline list of KiCad footprint names (for each referenced library) and of the referenced symbols with their pin number -> name maps |

The 10 passive tables (resistors, capacitors, inductors) have no spec yet. Their
`seed/generated/*.json` came from an earlier harvest, and `build_commodity.py` skips
them ("no spec, skipped"). Edit their JSON by hand, following the same rules, or write a
spec for them.

Build rules, enforced by `build_commodity.py`:

- A part is eligible only when DigiKey lists it as **Active** with a **Cut Tape or Bulk**
  variation in stock.
- Ranking: the spec's `rank()` comes first, then Cut Tape before Bulk, then higher stock,
  then the MPN.
- An MPN is used by at most one Active row in a table.

## 2. Everyday commands

```sh
python tools/build_commodity.py LEDs --offline     # rebuild one table from the cache only (no API calls)
python tools/build_commodity.py all --offline      # all tables with a spec
python kicad_dbl_library/init_db.py                # rebuild parts.sqlite
python tools/validate.py                           # check everything (exit 1 on errors)
python tools/validate.py --strict --verbose        # also fail on UNVERIFIED pinouts, list every warning
```

Commit the spec, `seed/generated/*.json`, `seed/locks/*.json`, `reports/*.md`,
`tools/cache/dk_cache.sqlite` and `parts.sqlite` together.

## 3. Adding a value or slot to an existing table

1. Edit `specs/<Table>.py` and add the value to the list that `slots()` iterates over
   (for example a new impedance in `IMPEDANCES` for ferrite beads). The new slot needs a
   **new, unique `part_id`**. Never reuse a retired Part_ID.
2. If the new value is outside the current `QUERIES`, extend `QUERIES`.
3. Build. Locked slots are left alone, and only the new slot is filled:
   ```sh
   python tools/build_commodity.py <Table>           # online; uses the cache for queries it already has
   ```
4. Read `reports/<Table>.md`. The new part shows under *Changes*. If it shows under
   *Gaps*, no stocked Cut Tape/Bulk part matched.
5. For semiconductors, verify the pinout (section 8).
6. Run `python kicad_dbl_library/init_db.py && python tools/validate.py`.

For a table without a spec, add the row to `seed/generated/<Table>.json` directly, with
every column the other rows have, `Status: "Active"` and a Cut Tape `Supplier_PN`.

## 4. Adding a new table

1. `seed/schema.py`: append the table name to `TABLES`, with a short comment. The order
   only affects listing order.
2. `specs/<Table>.py`: set `TABLE = "<Table>"` and define `QUERIES`, `slots()`, `accept()`,
   `rank()` and `make_row()`. Copy `specs/Ferrite_Beads.py` as a starting point.
   `make_row()` must set `Symbol`, `Footprint`, `Value`, `Package`, `Description`,
   `Keywords` and `FP_Filter`, plus `Pinout` and `Pinout_Source` for semiconductors.
   `Supplier`, `Supplier_PN`, `MPN`, `Manufacturer`, `Datasheet`, `DK_*` and `Status`
   are filled in by the builder.
3. `python tools/build_commodity.py <Table>`, then review `reports/<Table>.md`.
4. `company_parts.kicad_dbl`: add one library entry with `"table": "<Table>_Active"`.
   Copy the fields of a similar entry and include `Status`, plus `Pinout` for
   semiconductors. Give `Rating` and `TC_Dielectric` display names that make sense for
   the category.
5. If the table uses footprint libraries or symbols that weren't referenced before:
   `python tools/validate.py --refresh-kicad-names` (needs network access to gitlab.com).
6. Add the table to the lists in README.md and SETUP_DB.md.
7. `python kicad_dbl_library/init_db.py && python tools/validate.py`.

**Never rename an existing library `name` in the `.kicad_dbl`.** Schematics store it in
each placed symbol's library link. `validate.py` checks that the 11 original names are
still present.

## 5. Monthly refresh

```sh
export DIGIKEY_CLIENT_ID=...          # PowerShell: $env:DIGIKEY_CLIENT_ID="..."
export DIGIKEY_CLIENT_SECRET=...
python tools/build_commodity.py all --refresh
```

- Cached DigiKey responses are reused for 30 days, so a monthly run fetches fresh data.
  `--refresh` also writes the fresh `DK_Stock`, `DK_Status` and `DK_Checked` into
  locked rows. Without it, those rows keep their old values.
- If a locked part is no longer eligible (obsolete, NRND, no Cut Tape/Bulk stock), the
  builder sets its row to `Status: "Deprecated"`, adds a replacement row
  `<part_id>-R<n>`, and links the two with `Superseded_By`.
- Review every `reports/*.md`: *Changes* (replacements, additions), *Gaps* and *Cache
  misses*. If the run stopped on quota, run the same command again the next day; cached
  responses are not fetched twice.
- Then rebuild and validate:
  ```sh
  python kicad_dbl_library/init_db.py
  python tools/validate.py
  ```
- Commit `seed/`, `reports/`, `tools/cache/dk_cache.sqlite` and `parts.sqlite`.

`digikey_enrich.py` is an older ad-hoc stock check that edits `parts.sqlite` in place.
`init_db.py` discards those edits, so don't use it for maintenance.

## 6. Retiring a part

**Never delete a row and never rename or reuse a Part_ID.** Placed symbols reference the
Part_ID (the `.kicad_dbl` key). If you delete the row, those symbols lose their link.

| Status | Meaning | Visible in KiCad |
|---|---|---|
| `Active` | Use it | yes |
| `Deprecated` | Don't use it in new designs; existing designs still resolve. Set `Superseded_By` to the replacement Part_ID. | yes (the chooser shows the Status column) |
| `Obsolete` | Hidden from the `*_Active` views, so it no longer appears in the chooser | no |

The builder deprecates parts automatically (section 5). To retire a part by hand, edit
its row in `seed/generated/<Table>.json`: set `"Status": "Deprecated"` (or `"Obsolete"`)
and `"Superseded_By": "<new Part_ID>"`. If a builder-managed slot should not be refilled,
also remove the slot from the spec. `validate.py` checks that every `Superseded_By`
points at an existing Part_ID.

## 7. Supplier part number rule: Cut Tape or Bulk only

`Supplier_PN` must be the DigiKey **Cut Tape (CT)** part number, or **Bulk** for
through-hole and loose parts. It must never be **Tape & Reel** or **Digi-Reel**, because
those carry reel MOQs and re-reeling fees. `dk_client.orderable_variation()` applies the
rule during builds. `validate.py` checks it again:

- It looks each `Supplier_PN` up in the cached DigiKey responses.
- If the PN isn't cached, it falls back to DigiKey's suffix convention: `CT-ND`/`-1-ND`
  is Cut Tape, `TR-ND`/`-2-ND` is Tape & Reel, `DKR-ND`/`-6-ND` is Digi-Reel.
- A PN it can't classify either way is reported as a warning.

## 8. Pinout verification rule

Every semiconductor row records the physical pin order in `Pinout`, for example
`1=G 2=S 3=D`, `1=B 2=E 3=C` or `1=K 2=A`. It also records where that pin order was
verified in `Pinout_Source`: the datasheet URL and page, or "KiCad stock symbol X" when
the part has its own KiCad symbol.

- Use a **pin-order-specific symbol**: the part's own KiCad symbol (for example
  `Transistor_FET:2N7002`, `Transistor_BJT:BC817` or `Regulator_Linear:TLV75533PDBV`), or
  an explicit pin-order variant such as `Transistor_FET:Q_NMOS_GSD`. The generic
  `Device:Q_*` symbols are not used, and `validate.py` reports them as errors.
- `validate.py` compares `Pinout` with the symbol's pin number -> name map, which is
  stored in `tools/kicad_names.json` with `extends` resolved. Names are compared
  case-insensitively, and common aliases (K/Cathode, IN/VIN, GND/EP/PAD, EN/~{EN}, ...)
  count as equal. A mismatch is an **error**.
- If you couldn't check the datasheet, put `UNVERIFIED` in `Pinout_Source`. That's a
  **warning**, and an error under `--strict` for Active rows. Clear these before a part
  goes into a production design: read the MPN's datasheet package drawing, then replace
  `UNVERIFIED ...` with the URL and page.
- Some stock symbols (for example `Diode:SMAJ*A`) name their pins `A1`/`A2`, so their
  polarity can't be checked by name. Check the symbol graphic once (for SMAJ*A the
  cathode bar is on pin 1).

## 9. DigiKey quota and the cache

- The DigiKey API allows about **1000 calls per day**. `build_commodity.py --budget N`
  (default 900) caps one run. The client also stops when DigiKey reports fewer than 20
  calls remaining, or when it gets a 429 with a long `Retry-After`. The tables that were
  finished are saved; run again tomorrow to continue.
- Every response is stored, trimmed and compressed, in **`tools/cache/dk_cache.sqlite`**,
  keyed by request. **The cache is committed.** That lets anyone rebuild with
  `--offline`, and lets CI check packaging without credentials. Entries are reused for
  30 days. After that they are fetched again on the next online run.
- Credentials are read only from `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET`. Never
  commit them.

## 10. KiCad names list

`tools/kicad_names.json` makes the symbol and footprint checks work offline. Regenerate
it whenever a row references a new footprint library or symbol:

```sh
python tools/validate.py --refresh-kicad-names
```

This lists every referenced footprint library through the GitLab API (`kicad-footprints`)
and downloads each referenced symbol from `kicad-symbols` (master), resolving `extends`.
It then validates as usual. Commit the updated file.

## 11. CI

`.github/workflows/validate.yml` runs on every push and pull request (ubuntu-latest,
Python 3.12):

```sh
python kicad_dbl_library/init_db.py
python tools/validate.py
```

The job is fully offline: it uses the committed seed data, `tools/kicad_names.json` and
`tools/cache/dk_cache.sqlite`. Any error fails the job, and warnings don't. Run the same
two commands locally before pushing.
