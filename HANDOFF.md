# Handoff: KiCad component database libraries

Last updated 2026-11-26. Merged to `master` on `lenehan6/common-kicad`
(PR #2). Everything needed to continue is on `master`; nothing lives only in the
old Claude account.

## What this is
Two KiCad 10 **database libraries** (SQLite over ODBC, Windows `SQLite3 ODBC Driver`):

| Library | Folder | Contents | Status |
|---|---|---|---|
| Commodity parts | `kicad_dbl_library/` (`company_parts.kicad_dbl`, `parts.sqlite`) | 1,924 parts in 27 tables: R (thin film 0.1% & 1%, thick film 5%), C (ceramic ≥50V X7R+, RF C0G, bulk, tantalum 50V, electrolytic 50V), L (to 100µH, RF), ferrite beads, diodes (signal/Schottky/Zener/TVS), ESD, LEDs, small-signal MOSFET/BJT, TI LDOs, Littelfuse polyfuses & chip fuses, tactile switches, 2.54/1.27mm & IDC headers, test points | Complete; 0 validation errors |
| Application parts | `application_dbl/` (`application_parts.kicad_dbl`, `application_parts_approved.kicad_dbl`, `application.sqlite`) | KiCad stock symbols (op amps, MCUs, regulators, connectors…) mapped to DigiKey MPNs with lifecycle + review fields; 13 hand-picked USB connectors | **Pre-fill 24% done** (4,555 / 19,002 symbols; 3,448 matched); 0 parts reviewed |

Setup in KiCad: `kicad_dbl_library/SETUP_DB.md`. Maintenance: `kicad_dbl_library/MAINTAINING.md`.
Application DB usage/review: `application_dbl/README.md`, `application_dbl/REVIEW_CHECKLIST.md`.

## Rules the user set (keep these)
- Preferred makers: Vishay / Würth for passives; TI for LDOs; Littelfuse for fuses; Kingbright for LEDs; Nexperia/onsemi/Diodes/TSC for small-signal. Other makers only to fill gaps.
- Supplier is **DigiKey only**. Supplier_PN must be a **Cut Tape or Bulk** DigiKey PN (never Tape & Reel / Digi-Reel). Application DB also allows Tube/Tray (e.g. USB-A is tray-only).
- Capacitors ≥50V and X7R or better; thin film 0.1% / 1% E96; thick film 5% E12; resistors 0402/0805 only.
- Standard KiCad symbols only. **Never use `Device:Q_NMOS`/`Q_NPN` etc.** (KiCad 10 letter pin numbers); use the pin-order symbols in `Transistor_FET` / `Transistor_BJT`. Every semiconductor row's pinout must be verified against its datasheet (`Pinout`, `Pinout_Source`); `tools/validate.py` checks symbol pins vs `Pinout`.
- Part_IDs are permanent (schematics store them). Never delete or rename; retire with `Status` = Deprecated/Obsolete + `Superseded_By`. KiCad reads `<Table>_Active` views that hide Obsolete rows.
- In KiCad the default libraries `Device, Diode, Transistor_FET, Transistor_BJT, Regulator_Linear, Connector_Generic, Connector, Switch, Power_Protection` must be enabled (symbols show as text-only otherwise).

## How it works (one paragraph per tool)
- `tools/dk_client.py` — DigiKey Product Information API v4 client. Credentials ONLY from env `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET`. Every response cached (trimmed + zlib) in `tools/cache/dk_cache.sqlite` (committed) so re-runs spend no quota. Daily quota ≈1,000 calls.
- `tools/build_commodity.py <Table|all> [--offline] [--refresh] [--lib application_dbl]` — spec-driven selection. Specs in `kicad_dbl_library/specs/<Table>.py`; output `seed/generated/<Table>.json`, locks `seed/locks/<Table>.json`, reports `reports/<Table>.md`. Extra queries can be queued in `tools/harvest/requests*_<Table>.json` and are picked up automatically. The 10 original passive tables have no spec (hand-built data, locked).
- `kicad_dbl_library/init_db.py` — builds `parts.sqlite` + `*_Active` views from generated JSON.
- `tools/validate.py [--strict] [--refresh-kicad-names]` — offline checks (schema, pinouts, Cut Tape/Bulk, footprints/symbols exist via `tools/kicad_names.json`). CI: `.github/workflows/validate.yml`.
- `tools/scan_kicad_symbols.py` — scanned KiCad 10.0.8 symbols → `application_dbl/catalog.sqlite` + `TRIAGE.md` (priority order: USB/connectors, power, interface, analog/sensors, MCU/memory, RF/other, legacy last).
- `tools/prefill_app.py --budget 900` — resumable DigiKey harvest for the application DB (progress in `application_dbl/prefill/`). Stops cleanly at the budget/quota. `--report` prints progress.
- `application_dbl/init_app_db.py` — builds `application.sqlite` from prefill matches + USB spec + `reviews.json` + `manual_parts.json`.
- `tools/app_part.py review|show|list|add` — engineering review workflow (approvals persist in `application_dbl/reviews.json`).

## To continue from a new account (do this first)
1. **DigiKey credentials:** the old client secret was pasted into the old chat — **rotate it** at developer.digikey.com (or create a new app: Production, "Product Information v4"). Never commit it.
2. **Claude Code cloud environment** (new account): connect GitHub with access to `lenehan6/common-kicad`; create an environment with **limited network** + these allowed hosts:
   `api.digikey.com, www.vishay.com, www.we-online.com, www.ti.com, assets.nexperia.com, www.nexperia.com, www.onsemi.com, www.diodes.com, www.kingbrightusa.com, www.kingbright.com, www.littelfuse.com, www.st.com, aosmd.com, optoelectronics.liteon.com, mm.digikey.com` (gitlab.com is needed for KiCad library checks and is normally reachable).
3. Start a session on `master` (work on a new branch and open PRs) and paste this prompt:
   > Continue the KiCad database project described in HANDOFF.md. Read HANDOFF.md, kicad_dbl_library/MAINTAINING.md and application_dbl/README.md first. I will paste DigiKey credentials; export them as env vars only, never write them to files. Then each day run `python3 tools/prefill_app.py --budget 900`, rebuild with `python3 application_dbl/init_app_db.py` and `python3 kicad_dbl_library/init_db.py`, run `python3 tools/validate.py`, commit and push. Set up a daily scheduled task (≈01:23 UTC, after DigiKey's quota reset) into this session to do that until prefill reports complete, then delete the task.
4. Alternatively run it on your own PC (no Claude needed): `git pull`, set `DIGIKEY_CLIENT_ID`/`DIGIKEY_CLIENT_SECRET`, run the commands in step 3 daily, commit and push.

## Open items
- Application pre-fill: ~14,450 symbols left, ≈6–8 daily runs at the current ~2.4 symbols/call.
- Application DB: 0 parts reviewed; 1,107 symbols had no DigiKey match; 315 matched symbols have no KiCad default footprint (hidden until a reviewer assigns one via `app_part.py review --footprint`).
- Commodity gaps that DigiKey doesn't stock (see `kicad_dbl_library/reports/*.md`): 0402 22R ferrite bead; amber LEDs and 0805 white LED (datasheets unobtainable); PMBT2222A; 1.27mm 1x01, 2.54mm 1x17/1x19 headers; IDC 2x06/09/11/12; 3.3V SMA TVS; PRTR5V0U2X; many E96 values in the 1% thin film table.
- Decisions to confirm with the user: Part_ID `Q-P-AO3401A-SOT23` now holds Diodes DMP3056L-7 (rename while unreleased?); TVS-SMB-3V3-UNI uses Vishay SMBJ3V3 (non-"A" grade); 1812 4.7µF in the ≥10µF bulk table; 1.27mm 1x14–1x20 are long-post Fischer parts.
