"""storm2bhkv: STORM-pakket -> LVBB-aanleverpakket (BHKV).

De platte aanlevermap/-ZIP bevat: opdracht.xml, manifest.xml, het
AanleveringBesluit (met de regelingtekst), de GIO-aanleveringen
(AanleveringInformatieObject + GML), overige informatieobjecten,
manifest-ow.xml en de OW-deelbestanden.

De besluit-envelop en de publicatieOpdracht komen verbatim uit het
Envelop-compartiment van het STORM-document (met de uit STORM
geregenereerde regelingtekst op het Tekstinvoegpunt); zonder envelop
wordt een minimaal sjabloon gegenereerd. GIO-wrappers en -GML's reizen
byte-verbatim mee, zodat de hashes in de wrappers geldig blijven.

De omgekeerde richting (bhkv2storm) is `naar_storm.converteer` op een
aanlevermap — de lezers herkennen de besluit-vorm en bewaren de envelop.
"""

from __future__ import annotations

import copy
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .. import van_storm
from ..storm_common import (IMOW_MANIFEST_OW, IMOW_STANDLEVERING,
                            LVBB_OPDRACHT, STORM, lokale_naam, schrijf_xml,
                            waarschuw)

S = f"{{{STORM}}}"

CONTENT_TYPES = {".xml": "application/xml", ".gml": "application/gml+xml",
                 ".pdf": "application/pdf"}


def storm2bhkv(storm_pad: Path, doelmap: Path, maak_zip: bool = False,
               id_levering: str | None = None,
               datum_bekendmaking: str | None = None) -> list[str]:
    """Schrijf een LVBB-aanleverpakket; returns meldingen."""
    meldingen: list[str] = []
    doelmap.mkdir(parents=True, exist_ok=True)
    regeling = ET.parse(storm_pad).getroot()
    pakket_map = storm_pad.parent

    # 1. regelingtekst + OW-deelbestanden via de bestaande exporter
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        van_storm.converteer(storm_pad, tmp)
        regelingtekst = ET.parse(tmp / "stop" / "regeling.xml").getroot()
        ow_bestanden = []
        if (tmp / "ow").is_dir():
            for ow_pad in sorted((tmp / "ow").glob("*.xml")):
                shutil.copy2(ow_pad, doelmap / ow_pad.name)
                ow_bestanden.append(ow_pad.name)

    # 2. besluit + opdracht uit de Envelop (of minimaal sjabloon)
    envelop = regeling.find(f"{S}Envelop")
    besluit_naam = None
    if envelop is not None:
        for deel in envelop.findall(f"{S}Envelopdeel"):
            inhoud = next((k for k in deel if isinstance(k.tag, str)), None)
            if inhoud is None:
                continue
            inhoud = copy.deepcopy(inhoud)
            if lokale_naam(inhoud.tag) == "AanleveringBesluit":
                _vul_tekst_in(inhoud, regelingtekst, meldingen)
                besluit_naam = deel.get("bestand")
            schrijf_xml(inhoud, doelmap / deel.get("bestand"))
    if besluit_naam is None:
        besluit_naam, opdracht = _sjabloon_envelop(
            regeling, regelingtekst, id_levering, datum_bekendmaking)
        schrijf_xml(opdracht[1], doelmap / "opdracht.xml")
        schrijf_xml(opdracht[0], doelmap / besluit_naam)
        waarschuw(meldingen, "geen Envelop in STORM-document; minimaal "
                             "besluit-sjabloon gegenereerd")

    # 3. GIO's + overige informatieobjecten: payloads byte-verbatim,
    #    wrappers met hergecontroleerde (zo nodig gecorrigeerde) hashes
    geo = regeling.find(f"{S}Geo")
    if geo is not None:
        for gio in geo.findall(f"{S}Gio"):
            rel = gio.get("bestand")
            if rel and (pakket_map / rel).is_file():
                shutil.copy2(pakket_map / rel, doelmap / Path(rel).name)
            rel = gio.get("wrapper")
            if rel and (pakket_map / rel).is_file():
                _schrijf_wrapper(pakket_map / rel, doelmap, meldingen)
    io_map = pakket_map / "io"
    if io_map.is_dir():
        for pad in sorted(io_map.iterdir()):
            shutil.copy2(pad, doelmap / pad.name)
        for pad in sorted(io_map.glob("*.xml")):
            _schrijf_wrapper(pad, doelmap, meldingen)

    # 4. manifest-ow + manifest
    if ow_bestanden:
        _schrijf_manifest_ow(regeling, envelop, ow_bestanden, doelmap)
    _schrijf_manifest(doelmap, besluit_naam)

    if maak_zip:
        zip_pad = doelmap.with_suffix(".zip")
        with zipfile.ZipFile(zip_pad, "w", zipfile.ZIP_DEFLATED) as zf:
            for pad in sorted(doelmap.iterdir()):
                zf.write(pad, pad.name)
        print(f"Geschreven: {zip_pad}")
    print(f"Aanleverpakket: {doelmap} ({len(list(doelmap.iterdir()))} "
          f"bestanden)")
    return meldingen


def _schrijf_wrapper(wrapper_pad: Path, doelmap: Path, meldingen):
    """Kopieer een AanleveringInformatieObject; herbereken de sha512-hash
    van het bijbehorende bestand (LVBB keurt een foute hash af)."""
    import hashlib
    try:
        wortel = ET.parse(wrapper_pad).getroot()
    except ET.ParseError:
        shutil.copy2(wrapper_pad, doelmap / wrapper_pad.name)
        return
    if lokale_naam(wortel.tag) != "AanleveringInformatieObject":
        return  # geen wrapper (bv. een payload-xml in io/)
    gewijzigd = False
    for bestand_el in wortel.iter():
        if not isinstance(bestand_el.tag, str) \
                or lokale_naam(bestand_el.tag) != "Bestand":
            continue
        naam = hash_el = None
        for kind in bestand_el:
            if lokale_naam(kind.tag) == "bestandsnaam":
                naam = (kind.text or "").strip()
            elif lokale_naam(kind.tag) == "hash":
                hash_el = kind
        payload = doelmap / naam if naam else None
        if hash_el is not None and payload and payload.is_file():
            echte = hashlib.sha512(payload.read_bytes()).hexdigest()
            if (hash_el.text or "").strip() != echte:
                hash_el.text = echte
                gewijzigd = True
                waarschuw(meldingen, f"{wrapper_pad.name}: hash van {naam} "
                                     f"herberekend (bron was onjuist)")
    if gewijzigd:
        schrijf_xml(wortel, doelmap / wrapper_pad.name, inspringen=False)
    else:
        shutil.copy2(wrapper_pad, doelmap / wrapper_pad.name)


def _vul_tekst_in(besluit, regelingtekst, meldingen):
    """Vervang het Tekstinvoegpunt door de geregenereerde regelingtekst."""
    for ouder in besluit.iter():
        for i, kind in enumerate(list(ouder)):
            if isinstance(kind.tag, str) \
                    and lokale_naam(kind.tag) == "Tekstinvoegpunt":
                regelingtekst.tail = kind.tail
                ouder.remove(kind)
                ouder.insert(i, regelingtekst)
                return
    waarschuw(meldingen, "geen Tekstinvoegpunt in besluit-envelop; "
                         "regelingtekst niet ingevoegd")


def _sjabloon_envelop(regeling, regelingtekst, id_levering,
                      datum_bekendmaking):
    """Minimale envelop voor STORM-documenten zonder bewaarde aanlevering."""
    ident = regeling.find(f"{S}Identificatie")
    werk = ident.findtext(f"{S}FRBRWork") or "/akn/nl/act/onbekend"
    bg = ident.findtext(f"{S}bevoegdGezag") or "onbekend"

    from ..storm_common import LVBB_AANLEVERING, STOP_DATA
    L, D = f"{{{LVBB_AANLEVERING}}}", f"{{{STOP_DATA}}}"
    besluit = ET.Element(f"{L}AanleveringBesluit", {"schemaversie": "1.2.0"})
    versie = ET.SubElement(besluit, f"{L}BesluitVersie")
    idel = ET.SubElement(versie, f"{D}ExpressionIdentificatie")
    ET.SubElement(idel, f"{D}FRBRWork").text = werk.replace("/act/", "/bill/")
    ET.SubElement(idel, f"{D}soortWork").text = "/join/id/stop/work_003"
    versie.append(regelingtekst)

    O = f"{{{LVBB_OPDRACHT}}}"
    opdracht = ET.Element(f"{O}publicatieOpdracht")
    ET.SubElement(opdracht, f"{O}idLevering").text = \
        id_levering or f"storm-{bg}-001"
    ET.SubElement(opdracht, f"{O}idBevoegdGezag").text = bg
    ET.SubElement(opdracht, f"{O}publicatie").text = "besluit.xml"
    if datum_bekendmaking:
        ET.SubElement(opdracht, f"{O}datumBekendmaking").text = \
            datum_bekendmaking
    return "besluit.xml", (besluit, opdracht)


def _schrijf_manifest_ow(regeling, envelop, ow_bestanden, doelmap):
    werk = regeling.findtext(f"{S}Identificatie/{S}FRBRWork")
    doel = None
    if envelop is not None:
        for el in envelop.iter():
            if isinstance(el.tag, str) and lokale_naam(el.tag) == "doel":
                doel = (el.text or "").strip()
                break
    M = f"{{{IMOW_MANIFEST_OW}}}"
    wortel = ET.Element(f"{M}Aanleveringen")
    ET.SubElement(wortel, f"{M}domein").text = "omgevingswet"
    aanlevering = ET.SubElement(wortel, f"{M}Aanlevering")
    ET.SubElement(aanlevering, f"{M}WorkIDRegeling").text = werk
    if doel:
        ET.SubElement(aanlevering, f"{M}DoelID").text = doel
    SL = f"{{{IMOW_STANDLEVERING}}}"
    for naam in ow_bestanden:
        bestand = ET.SubElement(aanlevering, f"{M}Bestand")
        ET.SubElement(bestand, f"{M}naam").text = naam
        try:
            ow = ET.parse(doelmap / naam).getroot()
            for objecttype in ow.iter(f"{SL}objectType"):
                ET.SubElement(bestand, f"{M}objecttype").text = \
                    (objecttype.text or "").strip()
        except ET.ParseError:
            pass
    schrijf_xml(wortel, doelmap / "manifest-ow.xml")


def _schrijf_manifest(doelmap, besluit_naam):
    O = f"{{{LVBB_OPDRACHT}}}"
    wortel = ET.Element(f"{O}manifest")
    namen = sorted(p.name for p in doelmap.iterdir()
                   if p.name != "manifest.xml")
    for naam in [besluit_naam, "manifest.xml", "opdracht.xml"] + \
            [n for n in namen if n not in (besluit_naam, "opdracht.xml")]:
        bestand = ET.SubElement(wortel, f"{O}bestand")
        ET.SubElement(bestand, f"{O}bestandsnaam").text = naam
        ET.SubElement(bestand, f"{O}contentType").text = CONTENT_TYPES.get(
            Path(naam).suffix.lower(), "application/octet-stream")
    schrijf_xml(wortel, doelmap / "manifest.xml")
