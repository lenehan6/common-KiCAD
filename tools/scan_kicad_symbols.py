#!/usr/bin/env python3
"""Offline scan + triage of the stock KiCad 10 symbol libraries.

Reads the official kicad-symbols tree (an extracted directory or the
.tar.gz archive, read in place without extraction), parses every
``<Lib>.kicad_symdir/<Symbol>.kicad_sym`` file with a small S-expression
reader, resolves ``(extends ...)`` inheritance, classifies symbol names
(mpn / mpn_pattern / generic), assigns every library to a triage group and
priority, and writes:

  * a SQLite catalog (tables: meta, libraries, symbols, usb_symbols)
  * a human-readable TRIAGE.md

Stdlib only.  Input files are treated as untrusted data: they are only
tokenised and parsed, never executed.

Example:
  python3 tools/scan_kicad_symbols.py \
      --src kicad-symbols-10.0.8.tar.gz --ref 10.0.8 \
      --sym-lib-table ~/.config/kicad/10.0/sym-lib-table \
      --out application_dbl/catalog.sqlite \
      --triage application_dbl/TRIAGE.md \
      --overrides application_dbl/triage_overrides.json
"""

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
import tarfile
from collections import Counter, defaultdict
from urllib.parse import urlparse

# --------------------------------------------------------------------------
# S-expression reader
# --------------------------------------------------------------------------

_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)
_ESC = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def _unescape(s):
    if "\\" not in s:
        return s
    return re.sub(r"\\(.)", lambda m: _ESC.get(m.group(1), m.group(1)), s)


class Atom(str):
    """Unquoted symbol token (distinguishes `power` from "power")."""


def parse_sexpr(text):
    """Parse text into nested lists.  Strings -> str, bare atoms -> Atom."""
    stack = [[]]
    pos, n = 0, len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError("bad token at offset %d" % pos)
        pos = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            if len(stack) < 2:
                raise ValueError("unbalanced ')' at offset %d" % pos)
            node = stack.pop()
            stack[-1].append(node)
        elif m.group(3) is not None:
            stack[-1].append(_unescape(m.group(3)))
        elif m.group(4) is not None:
            stack[-1].append(Atom(m.group(4)))
    if len(stack) != 1:
        raise ValueError("unbalanced '(' (depth %d)" % (len(stack) - 1))
    return stack[0]


def head(node):
    return node[0] if isinstance(node, list) and node and isinstance(node[0], Atom) else None


def children(node, name):
    return [c for c in node[1:] if isinstance(c, list) and head(c) == name]


# --------------------------------------------------------------------------
# Symbol extraction
# --------------------------------------------------------------------------

INHERITED = ("Description", "ki_keywords", "Datasheet", "Footprint", "ki_fp_filters")


def extract_symbol(sym):
    """Return dict for a top-level (symbol "Name" ...) node."""
    name = sym[1]
    props = {}
    for p in children(sym, "property"):
        if len(p) >= 3 and isinstance(p[1], str) and isinstance(p[2], str):
            props[str(p[1])] = str(p[2])
    ext = children(sym, "extends")
    extends = str(ext[0][1]) if ext and len(ext[0]) > 1 else None
    is_power = bool(children(sym, "power"))
    pins = set()
    npins_raw = 0

    def walk(node):
        nonlocal npins_raw
        for c in node[1:]:
            if not isinstance(c, list):
                continue
            h = head(c)
            if h == "pin":
                npins_raw += 1
                num = children(c, "number")
                pins.add(str(num[0][1]) if num and len(num[0]) > 1 else "#%d" % npins_raw)
            elif h == "symbol":
                walk(c)

    walk(sym)
    return {"name": str(name), "props": props, "extends": extends,
            "is_power": is_power, "pins": pins}


def iter_symbol_files(src):
    """Yield (library, filename, text) for every *.kicad_sym in a symdir."""
    pat = re.compile(r"(?:^|/)([^/]+)\.kicad_symdir/([^/]+)\.kicad_sym$")
    if os.path.isfile(src) and tarfile.is_tarfile(src):
        with tarfile.open(src, "r:*") as tf:
            for m in tf:
                if not m.isfile():
                    continue
                mm = pat.search(m.name)
                if mm:
                    f = tf.extractfile(m)
                    yield mm.group(1), mm.group(2), f.read().decode("utf-8", "replace")
    else:
        for root, _dirs, files in os.walk(src):
            for fn in files:
                path = os.path.join(root, fn)
                mm = pat.search(path.replace(os.sep, "/"))
                if mm:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        yield mm.group(1), mm.group(2), fh.read()


def read_sym_lib_table(path):
    tree = parse_sexpr(open(path, encoding="utf-8").read())
    libs = []
    for top in tree:
        for lib in children(top, "lib"):
            nm = children(lib, "name")
            if nm and len(nm[0]) > 1:
                libs.append(str(nm[0][1]))
    return libs


# --------------------------------------------------------------------------
# Manufacturer hint
# --------------------------------------------------------------------------

DOMAIN_MAKERS = [
    ("st.com", "STMicroelectronics"), ("ti.com", "Texas Instruments"),
    ("analog.com", "Analog Devices"), ("linear.com", "Analog Devices"),
    ("maximintegrated.com", "Analog Devices"), ("maxim-ic.com", "Analog Devices"),
    ("microchip.com", "Microchip"), ("atmel.com", "Microchip"),
    ("microsemi.com", "Microchip"), ("supertex.com", "Microchip"),
    ("nxp.com", "NXP"), ("freescale.com", "NXP"),
    ("onsemi.com", "onsemi"), ("onsemi.cn", "onsemi"), ("fairchildsemi.com", "onsemi"),
    ("infineon.com", "Infineon"), ("irf.com", "Infineon"), ("cypress.com", "Infineon"),
    ("diodes.com", "Diodes Inc"), ("vishay.com", "Vishay"), ("nexperia.com", "Nexperia"),
    ("we-online", "Würth"), ("molex", "Molex"), ("te.com", "TE"), ("amphenol", "Amphenol"),
    ("hirose", "Hirose"), ("jst", "JST"), ("rohm", "ROHM"), ("toshiba", "Toshiba"),
    ("renesas.com", "Renesas"), ("intersil.com", "Renesas"), ("idt.com", "Renesas"),
    ("silabs.com", "Silicon Labs"), ("nordicsemi", "Nordic"), ("espressif", "Espressif"),
    ("mps.com", "Monolithic Power"), ("monolithicpower", "Monolithic Power"),
    ("richtek", "Richtek"), ("semtech", "Semtech"), ("littelfuse", "Littelfuse"),
    ("bourns", "Bourns"), ("murata", "Murata"), ("tdk", "TDK"), ("kemet", "KEMET"),
    ("panasonic", "Panasonic"), ("omron", "Omron"), ("cui.com", "CUI"), ("cuidevices", "CUI"),
    ("recom", "RECOM"), ("tracopower", "Traco"), ("meanwell", "Mean Well"),
    ("xilinx.com", "AMD Xilinx"), ("amd.com", "AMD"), ("intel.com", "Intel"),
    ("altera.com", "Intel/Altera"), ("latticesemi", "Lattice"), ("efinix", "Efinix"),
    ("broadcom", "Broadcom"), ("avagotech", "Broadcom"), ("ftdichip", "FTDI"),
    ("wch.cn", "WCH"), ("wch-ic", "WCH"), ("sensirion", "Sensirion"), ("bosch", "Bosch"),
    ("allegromicro", "Allegro"), ("melexis", "Melexis"), ("ams.com", "ams OSRAM"),
    ("ams-osram", "ams OSRAM"), ("osram", "ams OSRAM"), ("lumileds", "Lumileds"),
    ("cree", "Cree"), ("kingbright", "Kingbright"), ("worldsemi", "Worldsemi"),
    ("everlight", "Everlight"), ("liteon", "Lite-On"), ("lite-on", "Lite-On"),
    ("sharp", "Sharp"), ("isocom", "Isocom"), ("skyworks", "Skyworks"), ("qorvo", "Qorvo"),
    ("minicircuits", "Mini-Circuits"), ("u-blox", "u-blox"), ("quectel", "Quectel"),
    ("simcom", "SIMCom"), ("winbond", "Winbond"), ("issi.com", "ISSI"),
    ("macronix", "Macronix"), ("micron.com", "Micron"), ("gigadevice", "GigaDevice"),
    ("adesto", "Renesas"), ("fujitsu", "Fujitsu"), ("ramxeed", "RAMXEED"),
    ("everspin", "Everspin"), ("ablic", "ABLIC"), ("sii.co.jp", "ABLIC"),
    ("torexsemi", "Torex"), ("torex", "Torex"), ("holtek", "Holtek"),
    ("silergy", "Silergy"), ("aosmd", "Alpha & Omega"), ("power.com", "Power Integrations"),
    ("powerint", "Power Integrations"), ("cmlmicro", "CML Micro"),
    ("raspberrypi", "Raspberry Pi"), ("sparkfun", "SparkFun"), ("adafruit", "Adafruit"),
    ("kycon", "Kycon"), ("cliff", "Cliff"), ("switchcraft", "Switchcraft"),
    ("neutrik", "Neutrik"), ("lumberg", "Lumberg"), ("samtec", "Samtec"),
    ("harting", "HARTING"), ("phoenixcontact", "Phoenix Contact"), ("wago", "WAGO"),
    ("ckswitches", "C&K"), ("e-switch", "E-Switch"), ("alps", "Alps Alpine"),
    ("knowles", "Knowles"), ("invensense", "TDK InvenSense"), ("hopeRF", "HopeRF"),
    ("hoperf", "HopeRF"), ("semikron", "Semikron"), ("ixys", "Littelfuse"),
    ("pulseelectronics", "Pulse"), ("coilcraft", "Coilcraft"), ("abracon", "Abracon"),
    ("ecsxtal", "ECS"), ("sitime", "SiTime"), ("epson", "Epson"), ("iqdfrequency", "IQD"),
    ("hamlin", "Littelfuse"), ("panjit", "Panjit"), ("mccsemi", "MCC"),
    ("sanken", "Sanken"), ("stmicro", "STMicroelectronics"), ("parallax", "Parallax"),
    ("zilog", "Zilog"), ("diotec", "Diotec"), ("comchip", "Comchip"),
    ("taiwansemi", "Taiwan Semiconductor"), ("smc-diodes", "SMC Diode"),
    ("goodark", "Goodark"), ("lrc", "LRC"), ("ubiq", "UBIQ"), ("3peak", "3PEAK"),
    ("awinic", "Awinic"), ("injoinic", "Injoinic"), ("puyasemi", "Puya"),
    ("stcmicro", "STC"), ("sifive", "SiFive"), ("dialog-semiconductor", "Renesas"),
    ("decawave", "Qorvo"), ("mouser", None), ("digikey", None), ("farnell", None),
    ("alldatasheet", None), ("lcsc", None), ("datasheetspdf", None),
]

DESC_MAKERS = [
    ("STMicroelectronics", "STMicroelectronics"), ("Texas Instruments", "Texas Instruments"),
    ("Analog Devices", "Analog Devices"), ("Linear Technology", "Analog Devices"),
    ("Maxim", "Analog Devices"), ("Microchip", "Microchip"), ("Atmel", "Microchip"),
    ("NXP", "NXP"), ("Freescale", "NXP"), ("Motorola", "Motorola/NXP"),
    ("onsemi", "onsemi"), ("ON Semi", "onsemi"), ("Fairchild", "onsemi"),
    ("Infineon", "Infineon"), ("Cypress", "Infineon"), ("Vishay", "Vishay"),
    ("Nexperia", "Nexperia"), ("Diodes Inc", "Diodes Inc"), ("Würth", "Würth"),
    ("Wurth", "Würth"), ("Molex", "Molex"), ("Amphenol", "Amphenol"), ("Hirose", "Hirose"),
    ("JST", "JST"), ("Espressif", "Espressif"), ("Nordic", "Nordic"), ("ROHM", "ROHM"),
    ("Toshiba", "Toshiba"), ("Renesas", "Renesas"), ("Silicon Labs", "Silicon Labs"),
    ("Xilinx", "AMD Xilinx"), ("Altera", "Intel/Altera"), ("Lattice", "Lattice"),
    ("Intel", "Intel"), ("Zilog", "Zilog"), ("Recom", "RECOM"), ("RECOM", "RECOM"),
    ("TRACO", "Traco"), ("Mean Well", "Mean Well"), ("MeanWell", "Mean Well"),
    ("Murata", "Murata"), ("CUI", "CUI"), ("Omron", "Omron"), ("Panasonic", "Panasonic"),
    ("Raspberry Pi", "Raspberry Pi"), ("Worldsemi", "Worldsemi"), ("u-blox", "u-blox"),
    ("Quectel", "Quectel"), ("FTDI", "FTDI"), ("WCH", "WCH"), ("Bosch", "Bosch"),
    ("Sensirion", "Sensirion"), ("Allegro", "Allegro"), ("Littelfuse", "Littelfuse"),
    ("Bourns", "Bourns"), ("Neutrik", "Neutrik"), ("Lumberg", "Lumberg"),
    ("Phoenix", "Phoenix Contact"), ("Samtec", "Samtec"), ("TE Connectivity", "TE"),
]

NAME_PREFIX_MAKERS = [
    (r"STM32|STM8|STM", "STMicroelectronics"), (r"ATmega|ATtiny|ATxmega|AT89|AT24|AT25|ATSAM|ATF|SAM[A-Z]\d|PIC|dsPIC|MCP|AVR\d", "Microchip"),
    (r"ESP32|ESP8266|ESP-", "Espressif"), (r"nRF", "Nordic"), (r"TPS|TLV|TLC|TL0|TL4|LM\d|LMR|LMZ|INA|OPA|DRV|SN74|CD4|MSP430|CC\d{4}|TMS|BQ\d|ADS\d|DAC\d|TXS|TXB|ISO\d|UCC|LP\d|LMV", "Texas Instruments"),
    (r"AD[A-Z]?\d|ADuM|ADuC|ADP\d|LT\d|LTC|LTM|MAX\d", "Analog Devices"),
    (r"MC\d|MK\d|LPC\d|KL\d|S9S|MCIMX|PCA\d|PCF\d|TJA", "NXP"),
    (r"WS28|SK68", "Worldsemi"), (r"CH\d{3}", "WCH"), (r"FT\d{3}|FT2", "FTDI"),
    (r"CY\d|CY8C", "Infineon"), (r"XC\d|XC[A-Z]", "AMD Xilinx"), (r"EFM|EFR|C8051|CP21", "Silicon Labs"),
    (r"RP20|RP23", "Raspberry Pi"), (r"MPM|MP\d", "Monolithic Power"),
]
_NAME_PREFIX_RE = [(re.compile(r"^(?:%s)" % p), m) for p, m in NAME_PREFIX_MAKERS]


def manufacturer_hint(datasheet, description, name):
    ds = (datasheet or "").strip()
    if ds and ds != "~":
        host = ""
        try:
            host = (urlparse(ds if "://" in ds else "http://" + ds).hostname or "").lower()
        except ValueError:
            host = ""
        if host:
            for key, maker in DOMAIN_MAKERS:
                k = key.lower()
                if "." in k:
                    ok = host == k or host.endswith("." + k)
                else:
                    ok = k in host
                if ok:
                    if maker:
                        return maker, "datasheet"
                    break  # distributor/aggregator domain: fall through
    desc = description or ""
    for word, maker in DESC_MAKERS:
        if re.search(r"(?<![A-Za-z])" + re.escape(word) + r"(?![a-z])", desc):
            return maker, "description"
    for rx, maker in _NAME_PREFIX_RE:
        if rx.match(name):
            return maker, "name"
    return None, None


# --------------------------------------------------------------------------
# Name classification
# --------------------------------------------------------------------------

# First-token patterns that are functional / connector-family names even
# though they contain digits.
GENERIC_FIRST = re.compile(
    r"^(?:USB\d?|RJ\d{2}[A-Z]?|D[ABCDE]\d{1,2}|XLR\d*|DIN-?\d*|Mini-DIN-?\d*|"
    r"\d+P\d+C|IEC[\d-]*|HDMI\d*|DVI\d*|SATA\d*|PCIe?\d*|TRRS\d*|TRS\d*|\d+x\d+)$")

# Lowercase runs that are part of real part numbers.
MPN_LOWER_PREFIX = re.compile(r"^(?:AT(?:x?mega|tiny)|dsPIC|nRF|iCE|ADuC|ADuM|Si|EFM|ispPAC)")

# Single-character alternatives (STM32 "STM32C031C_4-6_Tx").
CHOICE_TOKEN = re.compile(r"^[A-Z0-9](?:-[A-Z0-9])+$")


def mpn_core(name):
    """Return the literal MPN core (KiCad suffixes removed) as a list of
    parts: ('lit', s) | ('wild', n) | ('choice', chars)."""
    toks = name.split("_")
    parts = [toks[0]]
    i = 1
    # STM32-style choice tokens: core_CHOICE_rest
    while i + 1 < len(toks) and CHOICE_TOKEN.match(toks[i]):
        parts.append(("choice", toks[i].replace("-", "")))
        parts.append(toks[i + 1])
        i += 2
    out = []
    for p in parts:
        if isinstance(p, tuple):
            out.append(p)
            continue
        # split into literal / wildcard pieces; wildcard = run of only 'x'
        # (lower case) not adjacent to other lower-case letters, or '?'
        pos = 0
        for m in re.finditer(r"[a-z]+|\?+", p):
            run = m.group(0)
            if run[0] == "?" or set(run) == {"x"}:
                if m.start() > pos:
                    out.append(("lit", p[pos:m.start()]))
                out.append(("wild", len(run)))
                pos = m.end()
        if pos < len(p):
            out.append(("lit", p[pos:]))
    return out


# Leading maker words KiCad puts in front of an MPN (Relay:Panasonic_ALFG2PF09).
MAKER_PREFIX = {"Panasonic", "Wuerth", "Wurth", "COTO", "CK", "EA", "Fujitsu", "Omron", "SANYOU",
                "HONGFA", "TE", "Triad", "Samtec", "JAE", "LiteOn", "Inolux", "CUI", "Microchip",
                "Microsemi", "Ai-Thinker", "Jadak", "Olimex", "WSEN", "Hirose", "Molex", "JST",
                "Amphenol", "Bourns", "Murata", "Vishay", "Littelfuse", "Kycon", "Neutrik"}
# Traco/LEM style "TMR_1-2411SM" = MPN "TMR 1-2411SM" (space in MPN).
SPACED_SERIES = re.compile(r"^[A-Z]{2,5}$")
SPACED_REST = re.compile(r"^\d+(?:\.\d+)?-[0-9A-Z]")


def _is_mpn_token(first):
    if GENERIC_FIRST.match(first):
        return False
    if not re.search(r"\d", first):
        # no digits: only an MPN pattern like ABPxxxxxxxxxA / ACO-xxxMHz
        return bool(re.match(r"^[A-Z]{2,}[A-Z-]*x{2,}", first))
    if MPN_LOWER_PREFIX.match(first):
        return True
    for m in re.finditer(r"[a-z]{3,}", first):
        if set(m.group(0)) != {"x"}:
            return False  # lower-case word => functional name
    return True


def classify_name(name, library):
    """Return (name_kind, search_stem, match_regex)."""
    if library in GENERIC_LIBS:
        return "generic", None, None
    toks = name.split("_")
    prefix_rx = ""
    lit_join = ""
    if len(toks) > 1 and toks[0] in MAKER_PREFIX:
        prefix_rx = "(?:%s[ _-]?)?" % re.escape(toks[0])
        toks = toks[1:]
    elif len(toks) > 1 and SPACED_SERIES.match(toks[0]) and SPACED_REST.match(toks[1]):
        toks = [toks[0] + " " + toks[1]] + toks[2:]
    rest = "_".join(toks)
    if not _is_mpn_token(toks[0]):
        return "generic", None, None
    core = mpn_core(rest)
    kind = "mpn_pattern" if any(k != "lit" for k, _ in core) else "mpn"
    stem = ""
    for k, v in core:
        if k != "lit":
            break
        stem += v
    stem = stem.rstrip("-/., ")
    rx = "(?i)^" + prefix_rx
    for k, v in core:
        if k == "lit":
            rx += re.escape(v).replace("\\ ", "[ _-]?")
        elif k == "wild":
            rx += "[A-Z0-9]" if v == 1 else "[A-Z0-9]{%d}" % v
        else:
            rx += "[" + v + "]"
    return kind, stem or None, rx


# --------------------------------------------------------------------------
# Triage rules
# --------------------------------------------------------------------------

GENERIC_LIBS = {"Device", "Connector_Generic", "Connector_Generic_MountingPin",
                "Connector_Generic_Shielded", "Jumper", "power", "Graphic",
                "Simulation_SPICE", "Mechanical"}

COMMODITY = {
    "Device": "R/C/L/fuse/crystal/etc. generics - commodity DB",
    "Diode": "generic diodes (1N4148, Zener, Schottky, TVS) - commodity DB",
    "Jumper": "solder/pin jumpers - commodity DB",
    "Connector_Generic": "pin headers/terminal generics - commodity DB",
    "Connector_Generic_MountingPin": "pin header generics w/ mounting pin - commodity DB",
    "Connector_Generic_Shielded": "pin header generics w/ shield - commodity DB",
}

NONBOM = {
    "power": "power flags / net symbols, not placed parts",
    "Graphic": "graphic items, no BOM line",
    "Simulation_SPICE": "SPICE sources/models, no BOM line",
    "Mechanical": "mounting holes, fiducials, heatsinks (handled outside part DB)",
    "Auxiliary_Items": "auxiliary/annotation items",
}

LEGACY = {
    "CPU_NXP_6800": "Motorola 6800-family CPUs/peripherals, obsolete",
    "CPU_NXP_68000": "68000-family CPUs, obsolete",
    "CPU_PowerPC": "single legacy PowerPC part",
    "CPU": "checked: CDP1802, Z80 (Z0840004/Z84C00/TMPZ84C00), P4080 - vintage/EOL",
    "DSP_Motorola": "56k DSP, obsolete",
    "DSP_Freescale": "single legacy DSP",
    "MCU_NXP_HC11": "68HC11, obsolete",
    "MCU_NXP_HC12": "68HC12, obsolete",
    "MCU_NXP_HCS12": "HCS12, legacy",
    "MCU_NXP_MCore": "M-Core, obsolete",
    "MCU_NXP_MAC7100": "MAC7100, obsolete",
    "MCU_NXP_ColdFire": "ColdFire, legacy/NRND",
    "MCU_Parallax": "Propeller/BASIC Stamp era parts",
    "Memory_EPROM": "UV EPROMs (27xx), obsolete",
    "Valve": "vacuum tubes",
    "CPLD_Altera": "MAX 3000/7000 CPLDs, mostly obsolete",
    "FPGA_Xilinx_Virtex5": "Virtex-5, legacy",
    "FPGA_Xilinx_Spartan6": "Spartan-6, mature/legacy (still sold; reconsider via overrides)",
    "4xxx": "CD4000 CMOS logic; many still active but rarely new-design (override if needed)",
    "4xxx_IEEE": "IEEE-style duplicates of 4xxx",
    "74xx_IEEE": "IEEE-style duplicates of 74xx",
    # judged additionally
    "MCU_Intel": "judged legacy: 8080/8086/8048/8051-era Intel parts",
    "GPU": "judged legacy: MC6845 CRT controllers",
    "FPGA_Xilinx": "judged legacy: XC2000/3000/4000, Spartan-II/3 era FPGAs",
    "Logic_Programmable": "judged legacy: PAL/GAL/PEEL 16V8/22V10 era PLDs",
    "Memory_ROM": "judged legacy: XC18V/XCF Xilinx config PROMs (discontinued)",
    "Interface_Telecom": "judged legacy: DTMF/FSK telecom ICs (FX614, HT9170, Si3210)",
}

APP_NOTES = {
    "Connector": "USB symbols get priority 0; most names are generic -> manual MPN",
    "LED": "application: addressable LEDs (WS2812/APA102/SK6812); plain indicator LEDs are commodity",
    "Diode_Bridge": "decided application: bridges are power-path specific, not commodity",
    "Transistor_FET": "SOT-23 small-signal parts flagged commodity_overlap=1",
    "Transistor_BJT": "SOT-23 small-signal parts flagged commodity_overlap=1",
    "74xx": "kept application: many families still active",
    "74xGxx": "kept application: single-gate logic, active",
}


def app_priority(lib):
    if lib in ("Connector", "Connector_Audio"):
        return 1
    if lib in ("Regulator_Linear", "Regulator_Switching", "Regulator_Controller",
               "Power_Management", "Power_Protection", "Power_Supervisor",
               "Battery_Management", "Converter_DCDC", "Reference_Voltage"):
        return 2
    if lib == "Isolator_Analog":
        return 6
    if lib.startswith(("Interface", "Isolator")) or lib == "Logic_LevelTranslator":
        return 3
    if (lib.startswith(("Amplifier_", "Analog", "Sensor", "Driver", "Timer"))
            or lib in ("Comparator", "Filter", "Oscillator")):
        return 4
    if lib.startswith(("MCU_", "Memory_", "FPGA_", "CPLD_")):
        return 5
    return 6


def triage_library(lib):
    if lib in NONBOM:
        return "nonbom", None, NONBOM[lib]
    if lib in COMMODITY:
        return "commodity", None, COMMODITY[lib]
    if lib in LEGACY:
        return "legacy", 9, LEGACY[lib]
    return "application", app_priority(lib), APP_NOTES.get(lib, "")


FAMILY_RE = re.compile(r"^[^0-9]*[0-9]+(?:\.[0-9]+)?(?:[A-Z]{1,3}[0-9]+)?")
SOT23 = re.compile(r"SOT-?23(?![0-9])|SOT\?23|SOT\*23|SC-?70|SOT-?323|SOT-?523|SOT-?416", re.I)
USB_NAME = re.compile(r"^USB")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def scan(args):
    table_libs = read_sym_lib_table(args.sym_lib_table)
    wanted = set(table_libs)
    raw = defaultdict(dict)  # lib -> name -> parsed
    errors = []
    files_seen = 0
    for lib, fname, text in iter_symbol_files(args.src):
        if lib not in wanted:
            continue
        files_seen += 1
        try:
            tree = parse_sexpr(text)
        except ValueError as e:
            errors.append("%s/%s: %s" % (lib, fname, e))
            continue
        for top in tree:
            if head(top) != "kicad_symbol_lib":
                continue
            for sym in children(top, "symbol"):
                if len(sym) > 1 and isinstance(sym[1], str):
                    s = extract_symbol(sym)
                    raw[lib][s["name"]] = s
    return table_libs, raw, errors, files_seen


def resolve(lib_syms, name, depth=0):
    s = lib_syms[name]
    if not s["extends"] or depth > 10 or s["extends"] not in lib_syms:
        return dict(s["props"]), s["pins"], s["is_power"], s["extends"] and s["extends"] not in lib_syms
    pprops, ppins, ppower, broken = resolve(lib_syms, s["extends"], depth + 1)
    props = dict(pprops)
    for k, v in s["props"].items():
        if k in INHERITED and (v is None or v.strip() in ("", "~") and pprops.get(k)):
            continue
        props[k] = v
    pins = s["pins"] or ppins
    return props, pins, (s["is_power"] or ppower), broken


def build_rows(raw, overrides):
    lib_info = {}
    for lib in raw:
        grp, prio, note = triage_library(lib)
        ov = overrides.get(lib) or {}
        if ov:
            grp = ov.get("grp", grp)
            if "priority" in ov:
                prio = ov["priority"]
            elif "grp" in ov:
                prio = {"application": app_priority(lib), "legacy": 9}.get(grp)
            note = ov.get("note", (note + " [override]").strip())
        lib_info[lib] = [grp, prio, note]
    rows = []
    for lib in sorted(raw):
        lgrp, lprio, _ = lib_info[lib]
        for name in sorted(raw[lib]):
            s = raw[lib][name]
            props, pins, is_power, broken = resolve(raw[lib], name)
            desc = props.get("Description", "")
            ds = props.get("Datasheet", "")
            maker, maker_src = manufacturer_hint(ds, desc, name)
            kind, stem, rx = classify_name(name, lib)
            grp, prio = lgrp, lprio
            if is_power:
                grp, prio = "nonbom", None
            fp = props.get("Footprint", "")
            fpf = props.get("ki_fp_filters", "")
            is_usb = int(lib == "Connector" and bool(USB_NAME.match(name)))
            if is_usb and grp == "application":
                prio = 0
            overlap = int(lib in ("Transistor_FET", "Transistor_BJT")
                          and bool(SOT23.search(fp) or SOT23.search(fpf) or SOT23.search(name)))
            rows.append({
                "library": lib, "name": name, "extends": s["extends"],
                "description": desc, "keywords": props.get("ki_keywords", ""),
                "datasheet": ds, "footprint": fp, "fp_filters": fpf,
                "value": props.get("Value", ""), "reference": props.get("Reference", ""),
                "pin_count": len(pins), "is_power": int(is_power),
                "manufacturer_hint": maker, "manufacturer_hint_src": maker_src,
                "name_kind": kind, "search_stem": stem, "match_regex": rx,
                "grp": grp, "priority": prio,
                "needs_manual_mpn": int(grp == "application" and kind == "generic"),
                "commodity_overlap": overlap, "is_usb": is_usb,
                "broken_extends": int(bool(broken)),
            })
    return lib_info, rows


SYMBOL_COLS = ["library", "name", "extends", "description", "keywords", "datasheet",
               "footprint", "fp_filters", "value", "reference", "pin_count", "is_power",
               "manufacturer_hint", "manufacturer_hint_src", "name_kind", "search_stem",
               "match_regex", "grp", "priority", "needs_manual_mpn", "commodity_overlap",
               "is_usb", "broken_extends"]


def write_db(path, ref, table_libs, lib_info, rows, files_seen):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    c = db.cursor()
    c.executescript("""
    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE libraries (name TEXT PRIMARY KEY, symbols INTEGER, grp TEXT,
        priority INTEGER, note TEXT, n_mpn INTEGER, n_mpn_pattern INTEGER,
        n_generic INTEGER);
    CREATE TABLE symbols (
        library TEXT, name TEXT, extends TEXT, description TEXT, keywords TEXT,
        datasheet TEXT, footprint TEXT, fp_filters TEXT, value TEXT, reference TEXT,
        pin_count INTEGER, is_power INTEGER, manufacturer_hint TEXT,
        manufacturer_hint_src TEXT, name_kind TEXT, search_stem TEXT, match_regex TEXT,
        grp TEXT, priority INTEGER, needs_manual_mpn INTEGER, commodity_overlap INTEGER,
        is_usb INTEGER, broken_extends INTEGER,
        PRIMARY KEY (library, name));
    CREATE INDEX symbols_grp ON symbols(grp, priority);
    CREATE INDEX symbols_stem ON symbols(search_stem);
    CREATE TABLE usb_symbols (library TEXT, name TEXT, pin_count INTEGER,
        description TEXT, footprint TEXT, fp_filters TEXT, priority INTEGER,
        PRIMARY KEY (library, name));
    """)
    meta = {"source_ref": ref, "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "sym_lib_table_libraries": str(len(table_libs)), "symbol_files": str(files_seen),
            "symbols": str(len(rows))}
    c.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
    counts = defaultdict(Counter)
    for r in rows:
        counts[r["library"]][r["name_kind"]] += 1
        counts[r["library"]]["_"] += 1
    for lib, (grp, prio, note) in sorted(lib_info.items()):
        k = counts[lib]
        c.execute("INSERT INTO libraries VALUES (?,?,?,?,?,?,?,?)",
                  (lib, k["_"], grp, prio, note, k["mpn"], k["mpn_pattern"], k["generic"]))
    c.executemany("INSERT INTO symbols (%s) VALUES (%s)" % (",".join(SYMBOL_COLS), ",".join("?" * len(SYMBOL_COLS))),
                  [[r[k] for k in SYMBOL_COLS] for r in rows])
    c.executemany("INSERT INTO usb_symbols VALUES (?,?,?,?,?,?,?)",
                  [(r["library"], r["name"], r["pin_count"], r["description"], r["footprint"],
                    r["fp_filters"], r["priority"]) for r in rows if r["is_usb"]])
    db.commit()
    db.close()


def md_escape(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def write_triage(path, ref, table_libs, lib_info, rows, files_seen, errors, overrides_path):
    total = len(rows)
    by_grp = Counter(r["grp"] for r in rows)
    kinds = defaultdict(Counter)
    for r in rows:
        kinds[r["library"]][r["name_kind"]] += 1
        kinds[r["library"]]["_"] += 1
    power_moved = [r for r in rows if r["is_power"] and r["library"] not in NONBOM]
    L = []
    L.append("# Application-parts DB: KiCad symbol triage\n")
    L.append("Generated by `tools/scan_kicad_symbols.py`; full data in `application_dbl/catalog.sqlite` "
             "(tables `libraries`, `symbols`, `usb_symbols`, `meta`).\n")
    L.append("- **Source**: gitlab.com/kicad/libraries/kicad-symbols, ref `%s`" % ref)
    L.append("- **Libraries**: %d in sym-lib-table, %d scanned" % (len(table_libs), len(lib_info)))
    L.append("- **Symbols scanned**: %d (from %d `.kicad_sym` files; expected ~22,930 -> diff %+d, %.2f%%)"
             % (total, files_seen, total - 22930, 100.0 * (total - 22930) / 22930))
    if errors:
        L.append("- **Parse errors**: %d (see end)" % len(errors))
    L.append("")
    L.append("## Totals by group\n")
    L.append("| group | libraries | symbols |")
    L.append("|---|---:|---:|")
    lib_grp_count = Counter(g for g, _, _ in lib_info.values())
    for g in ("application", "commodity", "nonbom", "legacy"):
        L.append("| %s | %d | %d |" % (g, lib_grp_count[g], by_grp[g]))
    L.append("| **total** | %d | **%d** |" % (len(lib_info), sum(by_grp.values())))
    L.append("")
    if power_moved:
        L.append("Note: %d symbol(s) with the power flag outside nonbom libraries were moved to `nonbom` at symbol level: %s.\n"
                 % (len(power_moved), ", ".join("%s:%s" % (r["library"], r["name"]) for r in power_moved[:10])))
    app = [r for r in rows if r["grp"] == "application"]
    L.append("Application flags: %d `needs_manual_mpn` (generic names), %d `commodity_overlap` (SOT-23-class small-signal transistors), "
             "%d symbols with an MPN-like name.\n"
             % (sum(r["needs_manual_mpn"] for r in app), sum(r["commodity_overlap"] for r in app),
                sum(1 for r in app if r["name_kind"] != "generic")))

    # Prefill effort
    stem_prio = {}
    for r in app:
        if r["search_stem"]:
            p = r["priority"]
            st = r["search_stem"].upper()
            if st not in stem_prio or p < stem_prio[st]:
                stem_prio[st] = p
    per_p = Counter(stem_prio.values())
    syms_p = Counter(r["priority"] for r in app)
    gen_p = Counter(r["priority"] for r in app if r["name_kind"] == "generic")
    overlap_stems = {r["search_stem"].upper() for r in app if r["commodity_overlap"] and r["search_stem"]}
    L.append("## Estimated DigiKey prefill effort (application group)\n")
    L.append("| priority | symbols | generic (manual MPN) | distinct search_stems | cumulative stems |")
    L.append("|---:|---:|---:|---:|---:|")
    cum = 0
    for p in sorted(set(syms_p)):
        cum += per_p[p]
        L.append("| %s | %d | %d | %d | %d |" % (p, syms_p[p], gen_p[p], per_p[p], cum))
    L.append("| **total** | %d | %d | **%d** | |" % (len(app), sum(gen_p.values()), len(stem_prio)))
    L.append("")
    fam = {}
    for st, p in stem_prio.items():
        m = FAMILY_RE.match(st)
        f = m.group(0) if m else st
        fam[f] = min(p, fam.get(f, 99))
    fam_p = Counter(fam.values())
    L.append("Family-keyword alternative (stem cut after the first letter+digit groups, e.g. `STM32F405RGT`->`STM32F405`, "
             "`ATMEGA328P-PU`->`ATMEGA328`): **%d** keywords (%s). Fewer calls, but each returns more hits "
             "(DigiKey pages at 50 results), so paging eats part of the saving.\n"
             % (len(fam), ", ".join("p%s: %d" % (p, fam_p[p]) for p in sorted(fam_p))))
    L.append("Assumptions: one DigiKey KeywordSearch call per distinct stem (stems de-duplicated "
             "case-insensitively across libraries, credited to the lowest priority number); results are matched "
             "back to symbols with `match_regex` (prefix match, `x`/`?` -> `[A-Z0-9]`). "
             "Rough call estimate: ~%d calls, plus ~%d%% for paging/retry of stems with many hits "
             "-> **~%d calls**. Generic symbols (%d) need manual MPN selection and are not counted. "
             "%d stems come from `commodity_overlap` transistors and could be skipped (handled by the commodity DB). "
             "At DigiKey's ~1,000 calls/day (see tools/dk_client.py) that is ~%d day(s); priorities 1-2 alone fit in ~%d days.\n"
             % (len(stem_prio), 20, round(len(stem_prio) * 1.2), sum(gen_p.values()), len(overlap_stems),
                -(-round(len(stem_prio) * 1.2) // 1000),
                -(-round(sum(per_p[p] for p in per_p if p is not None and p <= 2) * 1.2) // 1000)))

    # USB list
    usb = [r for r in rows if r["is_usb"]]
    L.append("## USB connector symbols (Connector library, priority 0)\n")
    L.append("All generic -> `needs_manual_mpn=1`; table `usb_symbols`.\n")
    L.append("| symbol | pins | default footprint | fp_filters | description |")
    L.append("|---|---:|---|---|---|")
    for r in usb:
        L.append("| %s | %d | %s | %s | %s |" % (r["name"], r["pin_count"], md_escape(r["footprint"]) or "-",
                                                 md_escape(r["fp_filters"]) or "-", md_escape(r["description"])[:90]))
    L.append("")

    titles = {"application": "Application libraries (ordered by priority)",
              "commodity": "Commodity libraries (separate commodity DB)",
              "nonbom": "Non-BOM libraries", "legacy": "Legacy libraries (priority 9)"}
    for g in ("application", "commodity", "nonbom", "legacy"):
        libs = sorted((l for l, v in lib_info.items() if v[0] == g),
                      key=lambda l: (lib_info[l][1] if lib_info[l][1] is not None else 99, l))
        L.append("## %s\n" % titles[g])
        L.append("| library | symbols | mpn | mpn_pattern | generic | priority | note |")
        L.append("|---|---:|---:|---:|---:|---:|---|")
        for l in libs:
            k = kinds[l]
            pr = lib_info[l][1]
            L.append("| %s | %d | %d | %d | %d | %s | %s |" % (l, k["_"], k["mpn"], k["mpn_pattern"], k["generic"],
                                                             "-" if pr is None else pr, md_escape(lib_info[l][2])))
        L.append("")

    L.append("## How to change priorities / groups\n")
    L.append("- Quick: edit `libraries.priority` / `libraries.grp` in `catalog.sqlite` (and `symbols` for the same "
             "library: `UPDATE symbols SET priority=? WHERE library=?`). Lost on re-run.")
    L.append("- Durable: create `application_dbl/triage_overrides.json` and re-run with `--overrides`:")
    L.append("")
    L.append("```json")
    L.append('{"4xxx": {"grp": "application", "priority": 6},')
    L.append(' "FPGA_Xilinx_Spartan6": {"grp": "application", "priority": 5, "note": "still in use"}}')
    L.append("```")
    L.append("")
    L.append("```sh")
    L.append("python3 tools/scan_kicad_symbols.py --src kicad-symbols-%s.tar.gz --ref %s \\" % (ref, ref))
    L.append("  --sym-lib-table <path/to/sym-lib-table> --out application_dbl/catalog.sqlite \\")
    L.append("  --triage application_dbl/TRIAGE.md --overrides application_dbl/triage_overrides.json")
    L.append("```")
    L.append("")
    L.append("Overrides apply per library (`grp` one of application/commodity/nonbom/legacy, `priority` int, optional `note`); "
             "USB symbols in Connector keep priority 0 and power-flagged symbols stay nonbom.%s\n"
             % (" Overrides used this run: `%s`." % overrides_path if overrides_path else ""))
    if errors:
        L.append("## Parse errors\n")
        for e in errors:
            L.append("- " + e)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", required=True, help="extracted kicad-symbols dir or .tar.gz archive")
    ap.add_argument("--ref", default=None, help="source ref (tag/branch) recorded in outputs")
    ap.add_argument("--out", required=True, help="output SQLite path")
    ap.add_argument("--triage", required=True, help="output TRIAGE.md path")
    ap.add_argument("--sym-lib-table", required=True, help="user's sym-lib-table")
    ap.add_argument("--overrides", default=None, help='JSON {"Lib": {"grp":..., "priority":...}}')
    args = ap.parse_args(argv)
    ref = args.ref
    if not ref:
        m = re.search(r"kicad-symbols-([^/]+?)(?:\.tar\.gz|\.tgz)?/?$", os.path.abspath(args.src))
        ref = m.group(1) if m else "unknown"
    overrides = {}
    if args.overrides:
        if os.path.exists(args.overrides):
            with open(args.overrides, encoding="utf-8") as fh:
                overrides = json.load(fh)
        else:
            print("note: overrides file %s not found, using defaults" % args.overrides, file=sys.stderr)
    table_libs, raw, errors, files_seen = scan(args)
    missing = [l for l in table_libs if l not in raw]
    if missing:
        print("warning: %d sym-lib-table libraries not found in source: %s" % (len(missing), ", ".join(missing)),
              file=sys.stderr)
    lib_info, rows = build_rows(raw, overrides)
    write_db(args.out, ref, table_libs, lib_info, rows, files_seen)
    write_triage(args.triage, ref, table_libs, lib_info, rows, files_seen, errors,
                 args.overrides if overrides else None)
    by = Counter(r["grp"] for r in rows)
    print("ref=%s libraries=%d symbols=%d files=%d errors=%d %s" % (
        ref, len(lib_info), len(rows), files_seen, len(errors), dict(by)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
