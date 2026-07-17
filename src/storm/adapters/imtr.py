"""storm2imtr: STORM -> KV-TR-aanlever-ZIPs (één per toepasbaar
regelbestand: manifest.xml + opdrachtAanleverenToepasbareRegels.xml +
het DMN-bestand, verbatim uit de Beslislogica).

De omgekeerde richting (imtr2storm) zit in `naar_storm.
lees_toepasbare_regels`, die zowel losse DMN's als deze ZIPs leest.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

from ..storm_common import STORM, lokale_naam, waarschuw

S = f"{{{STORM}}}"
MANIFEST_NS = "http://toepasbare-regels.omgevingswet.overheid.nl/v1/manifest.xsd"
OPDRACHT_NS = "http://toepasbare-regels.omgevingswet.overheid.nl/v1/opdracht.xsd"


def storm2imtr(storm_pad: Path, doelmap: Path,
               geldig_begindatum: str | None = None) -> list[str]:
    """Schrijf per ToepasbareActiviteit een KV-TR-ZIP; returns meldingen."""
    meldingen: list[str] = []
    regeling = ET.parse(storm_pad).getroot()
    toepasbaar = regeling.find(f"{S}ToepasbareRegels")
    if toepasbaar is None:
        waarschuw(meldingen, "geen ToepasbareRegels in dit STORM-document")
        return meldingen
    doelmap.mkdir(parents=True, exist_ok=True)

    for i, ta in enumerate(toepasbaar.findall(f"{S}ToepasbareActiviteit"), 1):
        logica = ta.find(f"{S}Beslislogica")
        dmn = next((k for k in logica if isinstance(k.tag, str)), None) \
            if logica is not None else None
        if dmn is None:
            waarschuw(meldingen, f"ToepasbareActiviteit {ta.get('naam')}: "
                                 f"geen Beslislogica")
            continue
        naam = ta.get("naam") or f"toepasbaar_{i}"
        veilig = re.sub(r"[^A-Za-z0-9 _-]+", "_", naam).strip("_ ")
        dmn_naam = f"{veilig}.dmn"
        datum = ta.get("geldigBegindatum") or geldig_begindatum

        dmn_bytes = BytesIO()
        # verbatim: geen herindenting van de DMN-inhoud
        ET.ElementTree(dmn).write(dmn_bytes, encoding="utf-8",
                                  xml_declaration=True)

        zip_pad = doelmap / f"{veilig}.zip"
        with zipfile.ZipFile(zip_pad, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.xml", _manifest(dmn_naam))
            zf.writestr("opdrachtAanleverenToepasbareRegels.xml",
                        _opdracht(dmn_naam, datum))
            zf.writestr(dmn_naam, dmn_bytes.getvalue())
        print(f"Geschreven: {zip_pad}")
    return meldingen


def _manifest(dmn_naam: str) -> str:
    M = f"{{{MANIFEST_NS}}}"
    wortel = ET.Element(f"{M}manifest")
    bestanden = ET.SubElement(wortel, f"{M}bestanden")
    for naam, soort in [("manifest.xml", "manifest"),
                        ("opdrachtAanleverenToepasbareRegels.xml", "opdracht"),
                        (dmn_naam, "toepasbareRegels")]:
        bestand = ET.SubElement(bestanden, f"{M}bestand")
        ET.SubElement(bestand, f"{M}naam").text = naam
        ET.SubElement(bestand, f"{M}type").text = soort
        ET.SubElement(bestand, f"{M}contenttype").text = "application/xml"
    ET.indent(wortel, space="  ")
    return ET.tostring(wortel, encoding="unicode",
                       default_namespace=None)


def _opdracht(dmn_naam: str, geldig_begindatum: str | None) -> str:
    O = f"{{{OPDRACHT_NS}}}"
    wortel = ET.Element(f"{O}opdrachten")
    opdracht = ET.SubElement(wortel, f"{O}opdracht")
    toevoegen = ET.SubElement(opdracht, f"{O}toevoegenToepasbareRegels")
    if geldig_begindatum:
        ET.SubElement(toevoegen, f"{O}geldigBegindatum").text = \
            geldig_begindatum
    ET.SubElement(toevoegen, f"{O}bestandsnaam").text = dmn_naam
    ET.indent(wortel, space="  ")
    return ET.tostring(wortel, encoding="unicode")
