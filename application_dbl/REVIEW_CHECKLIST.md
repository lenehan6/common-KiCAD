# Application parts: engineering review checklist

Use this before you set a part to `Approved` with
`python3 tools/app_part.py review <Part_ID> --status Approved --by NAME --notes "..."`.
Each row was prefilled automatically from DigiKey against a KiCad stock symbol, so assume
nothing has been checked yet. The prefill only matched the MPN to the symbol name.

Put what you checked and anything unusual in `--notes`, for example "pinout vs DS rev C p.3 OK; 2nd source TPS2042B".
Set `Rejected` for parts that must not be used (the row then leaves the `*_Active` views) and
`Obsolete` for parts that reached end of life. Re-review approved parts when `Lifecycle` changes.

## 1. General (all categories)

**Lifecycle and sourcing**
- [ ] `Lifecycle` is `Active`. Parts marked NRND, Last Time Buy, or Discontinued at DigiKey need a written reason in the notes.
- [ ] There is a second source: a pin-compatible part from another maker, or an approved alternative listed in the notes. Use `Candidates` as a starting point.
- [ ] The part is in stock at DigiKey (`DK_Stock`) and at least one other distributor. Check lead time, MOQ, and price at the expected volume.
- [ ] `Packaging` is Cut Tape, Bulk, Tube, or Tray. A row marked "Tape & Reel only" can't be ordered in prototype quantities.
- [ ] The MPN suffix is the one you want: temperature grade, packaging suffix (`R`/`T`/`TR` means reel), automotive `-Q1`, lead-free `#PBF`/`+`.

**Ratings**
- [ ] Absolute maximum ratings (voltage, current, temperature, ESD) have margin over the worst case of the application.
- [ ] Derating follows company rules: about 80% of rated voltage and 70% of rated current/power at the maximum ambient temperature.
- [ ] The operating temperature range covers the product's range.

**Package, footprint and pinout**
- [ ] `Footprint` matches the datasheet's package drawing: body size, pitch, exposed pad size and paste, and the pin 1 location.
- [ ] Every symbol pin number maps to the right footprint pad. Check the exposed pad and the NC/DNC pins.
- [ ] The symbol pin functions match the datasheet pinout for this exact package variant. Multi-package parts often differ between packages.
- [ ] Fill `Pinout_Source` with the datasheet revision and page (ask the DB maintainer, or record it in the notes).
- [ ] The part is assembly-compatible with our process: reflow profile, MSL, and no hand-solder-only packages unless planned.

**Thermal**
- [ ] Power dissipation at worst case × θJA (with the actual copper area) stays below Tj(max) with margin.
- [ ] The datasheet's thermal pad and via recommendations are noted for layout.

**ESD and robustness**
- [ ] The ESD rating (HBM/CDM) is adequate. Pins exposed to the outside world need external protection or an IEC 61000-4-2 rating.
- [ ] The latch-up, power-sequencing, and back-powering behaviour is understood.

**Compliance**
- [ ] RoHS and REACH compliant. Halogen-free if the product requires it.
- [ ] Export classification (ECCN) is acceptable. This matters for RF, crypto, and FPGA/MCU parts.
- [ ] Automotive and medical products need the AEC-Q grade or other qualification they require.

## 2. Category specifics

### Connectors (Connectors, Connectors_USB)
- [ ] The mating part or cable is identified and available. Check mating cycles against the product's use.
- [ ] The current rating per contact and in total covers the worst case. USB-C VBUS needs 3 A or 5 A capability for PD.
- [ ] The voltage rating fits the application. USB PD EPR runs up to 48 V.
- [ ] Mechanical retention is suitable: through-hole shell legs or hold-downs, board lock, and a panel cutout if needed. Check the pull-out and insertion forces.
- [ ] The mounting style matches the board stack: top mount, mid-mount, or board cutout, plus the PCB thickness the shell legs need (for example GCT USB4125 `-0190` for thick boards).
- [ ] The shield/SH pad connection strategy is decided (direct, RC, or ferrite to GND).
- [ ] USB-C: the CC1 and CC2 resistors are separate, and the symbol variant matches the contact count (16P vs 24P vs 6P power-only).
- [ ] The footprint keep-outs and the board edge position match the enclosure.
- [ ] Gold flash thickness and plating suit the environment.
- [ ] Environmental sealing (IP rating) is checked if the product needs it.

### Regulators (Regulators_Linear, Regulators_Switching, Converters_DCDC, Power_Management)
- [ ] Vin(max), including transients and load dump, stays below the absolute maximum with margin.
- [ ] Dropout and headroom are met at minimum Vin and maximum load. For LDOs, check PSRR and noise if the rail is analog.
- [ ] The output capacitor type and ESR range are stable for the part. Ceramic-stable is required.
- [ ] Switchers: switching frequency vs EMI and audio band, inductor saturation current, soft start, and the compensation network.
- [ ] The light-load mode (PFM/PWM) fits the noise requirements.
- [ ] Protections are present: current limit, thermal shutdown, UVLO, OVP, and reverse current.
- [ ] Load switches and hot-swap parts: check the inrush, SOA, and fault response (latch or auto-retry).
- [ ] Isolated converters: check the isolation rating (working and test voltage), creepage and clearance, and the required safety approvals.

### MCUs (MCU, Logic/FPGA)
- [ ] Flash and RAM leave room for growth (at least 30%), and the peripheral count and pin mux fit the design.
- [ ] The toolchain, debugger, and programming interface (SWD/JTAG/UPDI) are supported by the company setup.
- [ ] The silicon errata sheet has been read, and its workarounds are noted.
- [ ] The clock source is decided: crystal load capacitance or the internal oscillator's accuracy.
- [ ] The boot and option pins and the reset circuit are defined.
- [ ] The supply rails, decoupling, VCAP/VDDCORE pins, and power sequencing follow the datasheet.
- [ ] The product longevity programme is noted if the maker offers one (ST, NXP, Microchip).

### Op amps and comparators (Amplifiers)
- [ ] The supply range and single- or dual-supply operation fit the design.
- [ ] Input and output rail-to-rail behaviour is right, and the common-mode range covers the signal.
- [ ] Vos, drift, Ib, and noise are acceptable for the gain and source impedance used.
- [ ] GBW and slew rate are sufficient. The part is stable at the configured gain and with the capacitive load.
- [ ] Input protection and the phase-reversal behaviour are understood.
- [ ] Unused channels are terminated as the datasheet recommends.

### Sensors (Sensors)
- [ ] The accuracy, resolution, and range over temperature have been checked, including the calibration need.
- [ ] The interface (I2C/SPI/analog), its address conflicts, and its logic levels are checked.
- [ ] Mounting constraints are met: thermal coupling, optical or acoustic port, venting, and no conformal coating over openings.
- [ ] Self-heating, warm-up, and long-term drift are acceptable.
- [ ] Current sensors: check the shunt or Hall isolation rating, bandwidth, and common-mode range.

### RF (RF)
- [ ] Frequency band, output power, and sensitivity meet the link budget.
- [ ] A reference layout exists: impedance-controlled traces, the matching network, the antenna keep-out, and shielding.
- [ ] The radio's regulatory certification (FCC, CE/RED, IC) is covered. A pre-certified module is preferred.
- [ ] The crystal or TCXO accuracy meets the radio specification.
- [ ] Export classification and encryption implications are checked.

### Interface, isolators and drivers
- [ ] The bus standard compliance and the bus-pin ESD rating are adequate (for example IEC ESD on CAN or RS-485 pins).
- [ ] Isolators: check the isolation voltage, working voltage, CMTI, and creepage on the PCB.
- [ ] Gate and motor drivers: check the drive current, propagation delay, dead time, and the protection features.

### Relays and transistors/discretes
- [ ] The coil voltage and power, contact rating (AC/DC, inductive load), and electrical life are adequate.
- [ ] Power semiconductors: check the SOA, Rds(on) or Vce(sat) at temperature, and the avalanche rating.
- [ ] Small-signal SOT-23 transistors belong in the commodity library (`kicad_dbl_library`), so use those.

## 3. After approval
- Place the part from the **Application Parts (Approved)** library in KiCad.
- On the first board, check the footprint against the physical part and record the result in the notes.
