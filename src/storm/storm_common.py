"""Gedeelde constanten en helpers voor de STORM-converters."""

from __future__ import annotations

import xml.etree.ElementTree as ET

# --- Namespaces -------------------------------------------------------------

STORM = "urn:storm:1.0"

STOP_TEKST = "https://standaarden.overheid.nl/stop/imop/tekst/"
STOP_DATA = "https://standaarden.overheid.nl/stop/imop/data/"

IMOW_DEELBESTAND = "http://www.geostandaarden.nl/imow/bestanden/deelbestand"
IMOW_STANDLEVERING = "http://www.geostandaarden.nl/bestanden-ow/standlevering-generiek"
IMOW_REGELS = "http://www.geostandaarden.nl/imow/regels"
IMOW_LOCATIE = "http://www.geostandaarden.nl/imow/locatie"
IMOW_ROL = "http://www.geostandaarden.nl/imow/regelsoplocatie"
IMOW_GA = "http://www.geostandaarden.nl/imow/gebiedsaanwijzing"
IMOW_PONS = "http://www.geostandaarden.nl/imow/pons"
IMOW_REGELINGSGEBIED = "http://www.geostandaarden.nl/imow/regelingsgebied"
IMOW_VRIJETEKST = "http://www.geostandaarden.nl/imow/vrijetekst"

XLINK = "http://www.w3.org/1999/xlink"
XLINK_HREF = f"{{{XLINK}}}href"

STOP_GEO = "https://standaarden.overheid.nl/stop/imop/geo/"
BASISGEO = "http://www.geostandaarden.nl/basisgeometrie/1.0"

LVBB_AANLEVERING = "https://standaarden.overheid.nl/lvbb/stop/aanlevering/"
LVBB_OPDRACHT = "http://www.overheid.nl/2017/lvbb"
IMOW_MANIFEST_OW = "http://www.geostandaarden.nl/bestanden-ow/manifest-ow"

XSI = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("xsi", XSI)
# online schema-verwijzing zodat documenten in bv. Oxygen direct valideren
STORM_XSD_URL = ("https://raw.githubusercontent.com/RicharddeGraaf1/Storm/"
                 "main/standaard/xsd/storm.xsd")

# Idealisatie: IMOW-waardelijst-URI <-> STORM-enumeratie
IDEALISATIE_URI = {
    "exact": "http://standaarden.omgevingswet.overheid.nl/idealisatie/id/concept/Exact",
    "indicatief": "http://standaarden.omgevingswet.overheid.nl/idealisatie/id/concept/Indicatief",
}
IDEALISATIE_VAN_URI = {v: k for k, v in IDEALISATIE_URI.items()}

# IMOW juridische-regel-elementnaam <-> STORM regelsoort
REGELSOORT_VAN_IMOW = {
    "RegelVoorIedereen": "regelVoorIedereen",
    "Instructieregel": "instructieregel",
    "Omgevingswaarderegel": "omgevingswaarderegel",
}
IMOW_VAN_REGELSOORT = {v: k for k, v in REGELSOORT_VAN_IMOW.items()}

# STORM-specifieke attributen die bij STORM -> STOP gestript worden
STORM_ANNOTATIE_ATTRS = {"regelType", "idealisatie", "thema", "owId"}
# STORM-specifieke kindelementen die bij STORM -> STOP gestript worden
STORM_ANNOTATIE_ELEMENTEN = {"Regel", "Tekstdeel", "HoofdlijnRef",
                             "GerelateerdRef"}


def lokale_naam(tag: str) -> str:
    """'{ns}Naam' -> 'Naam'."""
    return tag.rsplit("}", 1)[-1]


def hernoem_boom(bron: ET.Element, naar_ns: str) -> ET.Element:
    """Kopieer een elementboom naar een andere namespace.

    Elementnamen behouden hun lokale naam; attributen (incl. eId/wId) en
    text/tail gaan ongewijzigd mee. Attributen in een namespace (zoals
    xlink:href) blijven zoals ze zijn.
    """
    nieuw = ET.Element(f"{{{naar_ns}}}{lokale_naam(bron.tag)}", dict(bron.attrib))
    nieuw.text = bron.text
    nieuw.tail = bron.tail
    for kind in bron:
        if not isinstance(kind.tag, str):  # comments / PI's overslaan
            continue
        nieuw.append(hernoem_boom(kind, naar_ns))
    return nieuw


def _indent(el: ET.Element, diepte: int, alleen_ns: str | None) -> None:
    """Als ET.indent, maar daalt niet af in elementen buiten alleen_ns.

    Nodig omdat ingebedde vreemde content (zoals DMN in Beslislogica)
    tekst direct tegen elementen aan kan hebben; whitespace toevoegen
    zou die inhoud veranderen.
    """
    kinderen = [k for k in el if isinstance(k.tag, str)]
    if not kinderen:
        return
    pad_kind = "\n" + "   " * (diepte + 1)
    pad_zelf = "\n" + "   " * diepte
    if not el.text or not el.text.strip():
        el.text = pad_kind
    for i, kind in enumerate(kinderen):
        if alleen_ns is None or kind.tag.startswith(f"{{{alleen_ns}}}"):
            _indent(kind, diepte + 1, alleen_ns)
        if not kind.tail or not kind.tail.strip():
            kind.tail = pad_kind if i < len(kinderen) - 1 else pad_zelf


def schrijf_xml(boom: ET.Element, pad, default_ns: str | None = None,
                inspringen: bool = True,
                alleen_ns: str | None = None) -> None:
    if default_ns:
        # tree.write(default_namespace=...) botst met ongekwalificeerde
        # attributen; registratie van het lege prefix geeft hetzelfde effect.
        ET.register_namespace("", default_ns)
    if inspringen:
        _indent(boom, 0, alleen_ns)
    boom.tail = None
    tree = ET.ElementTree(boom)
    tree.write(pad, encoding="utf-8", xml_declaration=True)


def waarschuw(meldingen: list[str], tekst: str) -> None:
    meldingen.append(tekst)
    print(f"  [waarschuwing] {tekst}")
