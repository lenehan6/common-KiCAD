"""Schema contract for the application-parts database (application_dbl/application.sqlite).

Separate from the commodity library (kicad_dbl_library/). Rows come from
  * the daily DigiKey prefill  (application_dbl/prefill/matches.json, one row per KiCad symbol),
  * spec-built tables          (application_dbl/seed/generated/<Table>.json, e.g. Connectors_USB,
                                built by ``tools/build_commodity.py <Table> --lib application_dbl``),
  * manual additions           (application_dbl/manual_parts.json, ``tools/app_part.py add``),
and engineering reviews are merged from application_dbl/reviews.json.

This module is also imported by tools/build_commodity.py (--lib application_dbl), which
needs COLUMN_NAMES, TABLES and (optionally) ORDERABLE.
"""

COLUMNS = [
    # --- commodity-style columns (same meaning as kicad_dbl_library/seed/schema.py) ---
    ("Part_ID",       "TEXT PRIMARY KEY"),  # "<prefix>-<MPN>", e.g. PWR-TPS2113APWR
    ("Symbol",        "TEXT NOT NULL"),     # "<KiCad lib>:<symbol>"
    ("Footprint",     "TEXT NOT NULL"),     # "" when the KiCad symbol has no default footprint (hidden from KiCad)
    ("Value",         "TEXT NOT NULL"),     # MPN (symbol name when no MPN yet)
    ("Description",   "TEXT"),
    ("Keywords",      "TEXT"),
    ("Manufacturer",  "TEXT"),
    ("MPN",           "TEXT"),              # "" = no DigiKey match yet
    ("Supplier",      "TEXT"),              # "DigiKey"
    ("Supplier_PN",   "TEXT"),              # DigiKey PN of the chosen variation (never T&R / Digi-Reel)
    ("Package",       "TEXT"),              # DigiKey Supplier Device Package / Package / Case
    ("Datasheet",     "TEXT"),
    ("FP_Filter",     "TEXT"),              # KiCad symbol ki_fp_filters
    ("DK_Status",     "TEXT"),
    ("DK_Stock",      "INTEGER"),
    ("DK_Checked",    "TEXT"),              # ISO date of the DigiKey data
    ("Status",        "TEXT"),              # Active | Deprecated | Obsolete (library row status, as commodity)
    ("Superseded_By", "TEXT"),              # used by spec-built tables (engine supersede chain)
    ("Pinout",        "TEXT"),
    ("Pinout_Source", "TEXT"),
    # --- application-specific columns ---
    ("KiCad_Library", "TEXT"),              # KiCad symbol library the row came from
    ("Lifecycle",     "TEXT"),              # DigiKey product status, or "Not found at DigiKey"
    ("Key_Params",    "TEXT"),              # "k=v; k=v" of the most relevant DigiKey parameters
    ("Candidates",    "TEXT"),              # other matching MPNs (<=10) with status
    ("Packaging",     "TEXT"),              # Cut Tape | Bulk | Tube | Tray | ... of Supplier_PN
    ("Review_Status", "TEXT"),              # Unreviewed | Approved | Rejected | Obsolete
    ("Reviewed_By",   "TEXT"),
    ("Review_Date",   "TEXT"),
    ("Review_Notes",  "TEXT"),
]
COLUMN_NAMES = [c for c, _ in COLUMNS]

REVIEW_STATES = ("Unreviewed", "Approved", "Rejected", "Obsolete")

# Packaging preference (engine eligibility + prefill choice). Tape & Reel / Digi-Reel never.
ORDERABLE = ("Cut Tape", "Bulk", "Tube", "Tray")

# table -> Part_ID prefix
TABLE_PREFIX = {
    "Amplifiers": "AMP",
    "Analog_ADC_DAC": "ADC",
    "Analog_Switch": "ASW",
    "Audio": "AUD",
    "Battery_Mgmt": "BAT",
    "Connectors": "CON",
    "Connectors_USB": "USB",
    "Converters_DCDC": "CNV",
    "Displays": "DSP",
    "Drivers": "DRV",
    "Interface": "IF",
    "Isolators": "ISO",
    "Logic": "LOG",
    "MCU": "MCU",
    "Memory": "MEM",
    "Oscillators_Timers": "OSC",
    "Power_Management": "PWR",
    "Power_Protection": "PROT",
    "Regulators_Linear": "LDO",
    "Regulators_Switching": "SMPS",
    "Relays": "RLY",
    "RF": "RF",
    "Sensors": "SEN",
    "Transformers": "XFMR",
    "Transistors_Discretes": "Q",
    "Misc": "MISC",
}
TABLES = list(TABLE_PREFIX)

# KiCad library (catalog.sqlite libraries.grp='application') -> table.
LIBRARY_TO_TABLE = {
    # Amplifiers
    "Amplifier_Audio": "Amplifiers", "Amplifier_Buffer": "Amplifiers", "Amplifier_Current": "Amplifiers",
    "Amplifier_Difference": "Amplifiers", "Amplifier_Instrumentation": "Amplifiers",
    "Amplifier_Operational": "Amplifiers", "Amplifier_Video": "Amplifiers", "Comparator": "Amplifiers",
    # Analog
    "Analog": "Analog_ADC_DAC", "Analog_ADC": "Analog_ADC_DAC", "Analog_DAC": "Analog_ADC_DAC",
    "Potentiometer_Digital": "Analog_ADC_DAC",
    "Analog_Switch": "Analog_Switch",
    "Audio": "Audio",
    "Battery_Management": "Battery_Mgmt",
    # Connectors (USB receptacles are spec-built into Connectors_USB)
    "Connector": "Connectors", "Connector_Audio": "Connectors",
    # Converters
    "Converter_ACDC": "Converters_DCDC", "Converter_DCDC": "Converters_DCDC",
    "Converter_DCDC_Isolated": "Converters_DCDC",
    "Display_Character": "Displays", "Display_Graphic": "Displays",
    # Drivers
    "Driver": "Drivers", "Driver_Display": "Drivers", "Driver_FET": "Drivers", "Driver_LED": "Drivers",
    "Driver_Motor": "Drivers",
    # Interface
    "Interface": "Interface", "Interface_CAN_LIN": "Interface", "Interface_CurrentLoop": "Interface",
    "Interface_Ethernet": "Interface", "Interface_Expansion": "Interface", "Interface_HDMI": "Interface",
    "Interface_HID": "Interface", "Interface_LineDriver": "Interface", "Interface_Optical": "Interface",
    "Interface_UART": "Interface", "Interface_USB": "Interface", "Fiber_Optic": "Interface", "Video": "Interface",
    "Isolator": "Isolators", "Isolator_Analog": "Isolators",
    # Logic / programmable logic
    "74xGxx": "Logic", "74xx": "Logic", "Buffer": "Logic", "Logic_LevelTranslator": "Logic",
    "CPLD_Microchip": "Logic", "CPLD_Renesas": "Logic", "CPLD_Xilinx": "Logic",
    "FPGA_Altera_MAX10": "Logic", "FPGA_CologneChip_GateMate": "Logic", "FPGA_Efinix_Trion": "Logic",
    "FPGA_Lattice": "Logic", "FPGA_Microsemi": "Logic", "FPGA_Xilinx_Artix7": "Logic",
    "FPGA_Xilinx_Kintex7": "Logic", "FPGA_Xilinx_Virtex6": "Logic", "FPGA_Xilinx_Virtex7": "Logic",
    # Memory
    "Memory_EEPROM": "Memory", "Memory_Flash": "Memory", "Memory_NVRAM": "Memory", "Memory_RAM": "Memory",
    "Memory_UniqueID": "Memory",
    # Timing
    "Oscillator": "Oscillators_Timers", "Timer": "Oscillators_Timers", "Timer_PLL": "Oscillators_Timers",
    "Timer_RTC": "Oscillators_Timers",
    # Power
    "Power_Management": "Power_Management", "Power_Supervisor": "Power_Management",
    "Reference_Voltage": "Power_Management", "Reference_Current": "Power_Management",
    "Regulator_Current": "Power_Management",
    "Power_Protection": "Power_Protection",
    "Regulator_Linear": "Regulators_Linear",
    "Regulator_Switching": "Regulators_Switching", "Regulator_Controller": "Regulators_Switching",
    "Regulator_SwitchedCapacitor": "Regulators_Switching",
    "Relay": "Relays", "Relay_SolidState": "Relays",
    "Transformer": "Transformers",
    # Discretes
    "Transistor_Array": "Transistors_Discretes", "Transistor_BJT": "Transistors_Discretes",
    "Transistor_FET": "Transistors_Discretes", "Transistor_FET_Other": "Transistors_Discretes",
    "Transistor_IGBT": "Transistors_Discretes", "Transistor_Power_Module": "Transistors_Discretes",
    "Triac_Thyristor": "Transistors_Discretes", "Diode_Bridge": "Transistors_Discretes",
    "Diode_Laser": "Transistors_Discretes",
    # Misc
    "Filter": "Misc", "LED": "Misc", "Motor": "Misc", "Security": "Misc", "Switch": "Misc",
}
_RF = ["RF", "RF_AM_FM", "RF_Amplifier", "RF_Bluetooth", "RF_Filter", "RF_GPS", "RF_GSM", "RF_Mixer",
       "RF_Module", "RF_NFC", "RF_RFID", "RF_Switch", "RF_WiFi", "RF_ZigBee"]
_SENSORS = ["Sensor", "Sensor_Audio", "Sensor_Current", "Sensor_Distance", "Sensor_Energy", "Sensor_Gas",
            "Sensor_Humidity", "Sensor_Magnetic", "Sensor_Motion", "Sensor_Optical", "Sensor_Pressure",
            "Sensor_Proximity", "Sensor_Temperature", "Sensor_Touch", "Sensor_Voltage"]
_MCU = ["CPU_NXP_IMX", "DSP_AnalogDevices", "DSP_Microchip_DSPIC33", "DSP_Texas",
        "MCU_AnalogDevices", "MCU_Cypress", "MCU_Dialog", "MCU_Espressif", "MCU_Microchip_8051",
        "MCU_Microchip_ATmega", "MCU_Microchip_ATtiny", "MCU_Microchip_AVR", "MCU_Microchip_AVR_Dx",
        "MCU_Microchip_PIC10", "MCU_Microchip_PIC12", "MCU_Microchip_PIC16", "MCU_Microchip_PIC18",
        "MCU_Microchip_PIC24", "MCU_Microchip_PIC32", "MCU_Microchip_SAMA", "MCU_Microchip_SAMD",
        "MCU_Microchip_SAME", "MCU_Microchip_SAML", "MCU_Microchip_SAMV", "MCU_Module",
        "MCU_NXP_Kinetis", "MCU_NXP_LPC", "MCU_NXP_NTAG", "MCU_NXP_S08", "MCU_Nordic", "MCU_Puya",
        "MCU_RaspberryPi", "MCU_Renesas_Synergy_S1", "MCU_STC", "MCU_ST_STM32C0", "MCU_ST_STM32F0",
        "MCU_ST_STM32F1", "MCU_ST_STM32F2", "MCU_ST_STM32F3", "MCU_ST_STM32F4", "MCU_ST_STM32F7",
        "MCU_ST_STM32G0", "MCU_ST_STM32G4", "MCU_ST_STM32H5", "MCU_ST_STM32H7", "MCU_ST_STM32L0",
        "MCU_ST_STM32L1", "MCU_ST_STM32L4", "MCU_ST_STM32L5", "MCU_ST_STM32MP1", "MCU_ST_STM32U0",
        "MCU_ST_STM32U5", "MCU_ST_STM32WB", "MCU_ST_STM32WL", "MCU_ST_STM8", "MCU_SiFive",
        "MCU_SiliconLabs", "MCU_Texas", "MCU_Texas_MSP430", "MCU_Texas_SimpleLink", "MCU_Trident",
        "MCU_WCH_RiscV"]
LIBRARY_TO_TABLE.update({n: "RF" for n in _RF})
LIBRARY_TO_TABLE.update({n: "Sensors" for n in _SENSORS})
LIBRARY_TO_TABLE.update({n: "MCU" for n in _MCU})


def table_for_library(lib):
    """Table for a KiCad library. Raises KeyError when unmapped (add it to LIBRARY_TO_TABLE)."""
    return LIBRARY_TO_TABLE[lib]


def check_mapping(app_libraries):
    """Fail loudly if any application-group library has no table."""
    missing = []
    for lib in app_libraries:
        try:
            t = table_for_library(lib)
        except KeyError:
            missing.append(lib)
            continue
        if t not in TABLE_PREFIX:
            missing.append(f"{lib}->{t}")
    if missing:
        raise SystemExit("app_schema.LIBRARY_TO_TABLE: unmapped application libraries: " + ", ".join(missing))


def active_view(table):
    return f"{table}_Active"


def approved_view(table):
    return f"{table}_Approved"
