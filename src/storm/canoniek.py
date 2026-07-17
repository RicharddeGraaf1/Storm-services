"""Canonieke vormen voor vergelijking van STOP/IMOW/DMN-inhoud.

Gedeeld door de rondreis-tests én (straks) de diffkern van de
renvooiservice: wie kan zeggen "semantisch gelijk" kan ook zeggen
"dít is er veranderd".
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from .storm_common import IMOW_DEELBESTAND, STOP_TEKST, lokale_naam

XSI = "http://www.w3.org/2001/XMLSchema-instance"

# presentatie-objecttypen en -elementen: geen inhoud, tellen niet mee
PRESENTATIE_TYPEN = {"Kaart", "Kaartlaag", "SymbolisatieItem"}
PRESENTATIE_KINDEREN = {"kaartaanduiding", "eigenSymbolisatie"}


def canon_tekst(el):
    """Canonieke vorm van een tekst-element: naam, attributen, tekst, kinderen.

    itertext() vangt ook de tail-teksten van inline elementen, zodat mixed
    content (Al met IntIoRef etc.) volledig meetelt. Volgorde-gevoelig.
    """
    attrs = tuple(sorted((lokale_naam(k), v) for k, v in el.attrib.items()
                         if not k.startswith(f"{{{XSI}}}")))
    tekst = " ".join("".join(el.itertext()).split())
    kinderen = tuple(canon_tekst(k) for k in el if isinstance(k.tag, str))
    return (lokale_naam(el.tag), attrs, tekst, kinderen)


def canon_feit(el):
    """Canonieke, volgorde-ongevoelige vorm van een IMOW-object."""
    attrs = tuple(sorted((lokale_naam(k), v) for k, v in el.attrib.items()
                         if not k.startswith(f"{{{XSI}}}")))
    tekst = " ".join((el.text or "").split())
    kinderen = tuple(sorted(canon_feit(k) for k in el
                            if isinstance(k.tag, str)
                            and lokale_naam(k.tag) not in PRESENTATIE_KINDEREN))
    return (lokale_naam(el.tag), attrs, tekst, kinderen)


def verzamel_ow_feiten(map_: Path) -> Counter:
    """Alle IMOW-objecten in een map als multiset van canonieke feiten."""
    feiten = Counter()
    for pad in sorted(map_.glob("*.xml")):
        try:
            wortel = ET.parse(pad).getroot()
        except ET.ParseError:
            continue
        for houder in wortel.iter(f"{{{IMOW_DEELBESTAND}}}owObject"):
            for obj in houder:
                if not isinstance(obj.tag, str):
                    continue
                if lokale_naam(obj.tag) in PRESENTATIE_TYPEN:
                    continue
                feiten[canon_feit(obj)] += 1
    return feiten


def vind_regelingtekst(map_: Path):
    """De RegelingCompact/RegelingVrijetekst in een map met XML-bestanden."""
    for pad in sorted(map_.glob("*.xml")):
        try:
            wortel = ET.parse(pad).getroot()
        except ET.ParseError:
            continue
        for naam in ("RegelingCompact", "RegelingVrijetekst"):
            if lokale_naam(wortel.tag) == naam:
                return wortel
            el = wortel.find(f".//{{{STOP_TEKST}}}{naam}")
            if el is not None:
                return el
    raise FileNotFoundError(
        f"Geen RegelingCompact/RegelingVrijetekst in {map_}")


def laad_dmns(map_: Path) -> dict:
    """(namespace, naam) -> (bestandsnaam, canonieke vorm) per DMN.

    De namespace alleen is niet uniek: die is per aanleveraar/OIN,
    meerdere toepasbare-regelbestanden kunnen hem delen.
    """
    dmns = {}
    for pad in sorted(map_.glob("*.dmn")) + sorted(map_.glob("*.xml")):
        try:
            wortel = ET.parse(pad).getroot()
        except ET.ParseError:
            continue
        if lokale_naam(wortel.tag) == "definitions":
            sleutel = (wortel.get("namespace"), wortel.get("name"))
            dmns[sleutel] = (pad.name, canon_tekst(wortel))
    return dmns


def eerste_verschil(a, b, pad="wortel"):
    """Zoek recursief het eerste verschil tussen twee canonieke bomen."""
    if a[0] != b[0]:
        return f"{pad}: element {a[0]} != {b[0]}"
    if a[1] != b[1]:
        return f"{pad}/{a[0]}: attributen {a[1]} != {b[1]}"
    if a[2] != b[2]:
        return (f"{pad}/{a[0]}: tekst\n    a: {a[2][:200]}\n"
                f"    b: {b[2][:200]}")
    if len(a[3]) != len(b[3]):
        return f"{pad}/{a[0]}: {len(a[3])} vs {len(b[3])} kinderen"
    for i, (ka, kb) in enumerate(zip(a[3], b[3])):
        v = eerste_verschil(ka, kb, f"{pad}/{a[0]}[{i}]")
        if v:
            return v
    return None
