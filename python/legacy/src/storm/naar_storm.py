"""Conversie: STOP-tekst + IMOW-deelbestanden [+ IMTR/STTR] -> één STORM-document.

Gebruik:
    python naar_storm.py <bronmap> <doel.xml> [imtr-map]

De bronmap is een consolidatie-/leveringsmap met daarin:
  - een XML met de STOP-regelingtekst (RegelingCompact of RegelingVrijetekst)
  - de IMOW-deelbestanden (ow*.xml met sl:standBestand/owObject)

De optionele imtr-map bevat STTR-bestanden (*.dmn of *.xml met
dmn:definitions als root; STTR v1.0 en 3.0.0 worden beide herkend).
De STTR-kern (activiteit, regelgroepen, vragen) wordt STORM-native;
de DMN-beslislogica wordt verbatim ingebed.

Presentatiegegevens (Kaart, SymbolisatieItem e.d.) worden bewust
overgeslagen: presentatie is geen inhoud (specificatie §7).
"""

from __future__ import annotations

import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from .storm_common import (
    BASISGEO, IDEALISATIE_VAN_URI, IMOW_DEELBESTAND, REGELSOORT_VAN_IMOW,
    STOP_DATA, STOP_GEO, STOP_TEKST, STORM, XLINK_HREF, hernoem_boom,
    lokale_naam, schrijf_xml, waarschuw,
)

S = f"{{{STORM}}}"

# owObject-typen die presentatie zijn en geen inhoud
PRESENTATIE_TYPEN = {"Kaart", "Kaartlaag", "SymbolisatieItem"}


# ---------------------------------------------------------------------------
# Inlezen
# ---------------------------------------------------------------------------

def vind_stop_tekst(bronmap: Path, meldingen):
    """Zoek de RegelingCompact/RegelingVrijetekst + identificatie.

    Returns ook het brondocument (wortel + pad): een AanleveringBesluit
    wordt door de aanroeper verbatim als Envelop bewaard.
    """
    for pad in sorted(bronmap.glob("*.xml")):
        try:
            wortel = ET.parse(pad).getroot()
        except ET.ParseError:
            continue
        for wortelnaam, structuur in (("RegelingCompact", "compact"),
                                      ("RegelingVrijetekst", "vrijetekst")):
            tekst = wortel.find(f".//{{{STOP_TEKST}}}{wortelnaam}")
            if tekst is None and lokale_naam(wortel.tag) == wortelnaam:
                tekst = wortel
            if tekst is not None:
                # bij een besluit-bron staan er meerdere identificaties in;
                # de régeling (soortWork /act/) is de STORM-identiteit
                idents = wortel.findall(
                    f".//{{{STOP_DATA}}}ExpressionIdentificatie")
                ident = next(
                    (i for i in idents
                     if "/act/" in (i.findtext(f"{{{STOP_DATA}}}FRBRWork")
                                    or "")),
                    idents[0] if idents else None)
                versie = wortel.find(f".//{{{STOP_DATA}}}versienummer")
                print(f"  STOP-tekst ({wortelnaam}) gevonden in {pad.name}")
                return tekst, structuur, ident, versie, wortel, pad
    raise SystemExit(f"Geen RegelingCompact/RegelingVrijetekst in {bronmap}")


def bouw_envelop(regeling, bron_wortel, bron_pad, bronmap: Path, meldingen):
    """Bewaar de LVBB-aanleveradministratie verbatim in een Envelop.

    Het AanleveringBesluit gaat er zonder de regelingtekst in (op die plek
    komt een Tekstinvoegpunt); de publicatieOpdracht gaat verbatim mee.
    """
    import copy
    if lokale_naam(bron_wortel.tag) != "AanleveringBesluit":
        return False
    envelop = _sub(regeling, "Envelop")

    besluit = copy.deepcopy(bron_wortel)
    for ouder in besluit.iter():
        for i, kind in enumerate(list(ouder)):
            if isinstance(kind.tag, str) and lokale_naam(kind.tag) in (
                    "RegelingCompact", "RegelingVrijetekst"):
                invoegpunt = ET.Element(f"{S}Tekstinvoegpunt")
                invoegpunt.tail = kind.tail
                ouder.remove(kind)
                ouder.insert(i, invoegpunt)
    deel = _sub(envelop, "Envelopdeel", bestand=bron_pad.name)
    deel.append(besluit)

    opdracht_pad = bronmap / "opdracht.xml"
    if opdracht_pad.is_file():
        try:
            deel = _sub(envelop, "Envelopdeel", bestand="opdracht.xml")
            deel.append(ET.parse(opdracht_pad).getroot())
        except ET.ParseError:
            waarschuw(meldingen, "opdracht.xml niet leesbaar; overgeslagen")
    return True


def _hrefs(el, naam):
    """Alle xlink:href's van descendant-elementen met deze lokale naam."""
    return [k.get(XLINK_HREF) for k in el.iter()
            if isinstance(k.tag, str) and lokale_naam(k.tag) == naam]


def _kindtekst(el, naam):
    for k in el.iter():
        if isinstance(k.tag, str) and lokale_naam(k.tag) == naam:
            return (k.text or "").strip()
    return None


def lees_ow_objecten(bronmap: Path, meldingen):
    """Verzamel alle IMOW-objecten uit de ow-deelbestanden, per soort."""
    ow = {
        "regelteksten": {},      # identificatie -> wId
        "regels": [],            # juridische regels
        "divisies": {},          # identificatie -> wId (Divisie/Divisietekst)
        "tekstdelen": [],        # vrijetekst-annotaties
        "activiteiten": [],
        "normen": [],            # omgevingsnorm + omgevingswaarde
        "gebiedsaanwijzingen": [],
        "gebieden": [],
        "gebiedengroepen": [],
        "ambtsgebieden": [],
        "ponsen": [],
        "regelingsgebieden": [],
        "hoofdlijnen": [],
    }
    for pad in sorted(bronmap.glob("*.xml")):
        try:
            wortel = ET.parse(pad).getroot()
        except ET.ParseError:
            continue
        for obj_wrapper in wortel.iter(f"{{{IMOW_DEELBESTAND}}}owObject"):
            for obj in obj_wrapper:
                if not isinstance(obj.tag, str):
                    continue
                _verwerk_ow_object(obj, ow, meldingen)
    return ow


def _verwerk_ow_object(obj, ow, meldingen):
    naam = lokale_naam(obj.tag)
    ident = _kindtekst(obj, "identificatie")

    if naam in PRESENTATIE_TYPEN:
        return
    if naam == "Regeltekst":
        ow["regelteksten"][ident] = {
            "wId": obj.get("wId"),
            "gerelateerd": _hrefs(obj, "RegeltekstRef"),
        }
    elif naam in REGELSOORT_VAN_IMOW:
        ow["regels"].append(_lees_regel(obj, naam, meldingen))
    elif naam in ("Divisie", "Divisietekst"):
        ow["divisies"][ident] = obj.get("wId")
    elif naam == "Tekstdeel":
        themas = [k.text.strip() for k in obj
                  if isinstance(k.tag, str) and lokale_naam(k.tag) == "thema"
                  and k.text]
        if len(themas) > 1:
            waarschuw(meldingen, f"Tekstdeel {ident} heeft {len(themas)} "
                                 f"thema's; alleen het eerste wordt bewaard")
        idealisatie_uri = _kindtekst(obj, "idealisatie")
        ow["tekstdelen"].append({
            "owId": ident,
            "idealisatie": IDEALISATIE_VAN_URI.get(idealisatie_uri),
            "thema": themas[0] if themas else None,
            "divisieRef": (_hrefs(obj, "DivisieRef")
                           + _hrefs(obj, "DivisietekstRef") + [None])[0],
            "hoofdlijnRefs": _hrefs(obj, "HoofdlijnRef"),
            "locatieRefs": _hrefs(obj, "LocatieRef"),
            "gebiedsaanwijzingRefs": _hrefs(obj, "GebiedsaanwijzingRef"),
        })
    elif naam == "Activiteit":
        # ActiviteitRefs per relatie-soort scopen (bovenliggend vs gerelateerd)
        bovenliggend, gerelateerd = None, []
        for kind in obj:
            if not isinstance(kind.tag, str):
                continue
            if lokale_naam(kind.tag) == "bovenliggendeActiviteit":
                bovenliggend = (_hrefs(kind, "ActiviteitRef") or [None])[0]
            elif lokale_naam(kind.tag) == "gerelateerdeActiviteit":
                gerelateerd += _hrefs(kind, "ActiviteitRef")
        ow["activiteiten"].append({
            "id": ident,
            "naam": _kindtekst(obj, "naam"),
            "groep": _kindtekst(obj, "groep"),
            "bovenliggend": bovenliggend,
            "gerelateerd": gerelateerd,
        })
    elif naam in ("Omgevingsnorm", "Omgevingswaarde"):
        ow["normen"].append(_lees_norm(obj, naam))
    elif naam == "Gebiedsaanwijzing":
        ow["gebiedsaanwijzingen"].append({
            "id": ident,
            "type": _kindtekst(obj, "type"),
            "naam": _kindtekst(obj, "naam"),
            "groep": _kindtekst(obj, "groep"),
            "locatieRefs": _hrefs(obj, "LocatieRef"),
        })
    elif naam == "Gebied":
        ow["gebieden"].append({
            "id": ident,
            "noemer": _kindtekst(obj, "noemer"),
            "geometrieRef": (_hrefs(obj, "GeometrieRef") or [None])[0],
        })
    elif naam == "Gebiedengroep":
        ow["gebiedengroepen"].append({
            "id": ident,
            "noemer": _kindtekst(obj, "noemer"),
            "leden": _hrefs(obj, "GebiedRef") + _hrefs(obj, "GebiedengroepRef"),
        })
    elif naam == "Ambtsgebied":
        ow["ambtsgebieden"].append({
            "id": ident,
            "noemer": _kindtekst(obj, "noemer"),
            "grensId": _kindtekst(obj, "bestuurlijkeGrenzenID"),
            "domein": _kindtekst(obj, "domein"),
            "geldigOp": _kindtekst(obj, "geldigOp"),
        })
    elif naam == "Pons":
        ow["ponsen"].append({"id": ident, "locatieRefs": _hrefs(obj, "LocatieRef")})
    elif naam == "Regelingsgebied":
        ow["regelingsgebieden"].append({"id": ident,
                                        "locatieRefs": _hrefs(obj, "LocatieRef")})
    elif naam == "Hoofdlijn":
        ow["hoofdlijnen"].append({"id": ident,
                                  "soort": _kindtekst(obj, "soort"),
                                  "naam": _kindtekst(obj, "naam")})
    else:
        waarschuw(meldingen, f"onbekend owObject-type '{naam}' overgeslagen")


def _lees_regel(obj, imow_naam, meldingen):
    regel = {
        "owId": _kindtekst(obj, "identificatie"),
        "soort": REGELSOORT_VAN_IMOW[imow_naam],
        "idealisatie": None,
        "regeltekstRef": None,
        "locatieRefs": [],
        "gebiedsaanwijzingRefs": [],
        "normRefs": [],
        "toedelingen": [],
        "instrument": None,
        "taakuitoefening": None,
    }
    for kind in obj:
        if not isinstance(kind.tag, str):
            continue
        naam = lokale_naam(kind.tag)
        if naam == "idealisatie":
            uri = (kind.text or "").strip()
            regel["idealisatie"] = IDEALISATIE_VAN_URI.get(uri)
            if regel["idealisatie"] is None:
                waarschuw(meldingen, f"onbekende idealisatie-URI '{uri}'")
        elif naam == "artikelOfLid":
            regel["regeltekstRef"] = (_hrefs(kind, "RegeltekstRef") or [None])[0]
        elif naam == "locatieaanduiding":
            regel["locatieRefs"] += _hrefs(kind, "LocatieRef")
        elif naam == "gebiedsaanwijzing":
            regel["gebiedsaanwijzingRefs"] += _hrefs(kind, "GebiedsaanwijzingRef")
        elif naam in ("omgevingswaardeaanduiding", "omgevingsnormaanduiding"):
            regel["normRefs"] += _hrefs(kind, "OmgevingswaardeRef")
            regel["normRefs"] += _hrefs(kind, "OmgevingsnormRef")
        elif naam == "activiteitaanduiding":
            act_ref = (_hrefs(kind, "ActiviteitRef") or [None])[0]
            alas = [k for k in kind.iter() if isinstance(k.tag, str)
                    and lokale_naam(k.tag) == "ActiviteitLocatieaanduiding"]
            if not alas:
                waarschuw(meldingen,
                          f"activiteitaanduiding zonder ActiviteitLocatie"
                          f"aanduiding bij regel {regel['owId']}")
            for ala in alas:
                regel["toedelingen"].append({
                    "activiteitRef": act_ref,
                    "owId": _kindtekst(ala, "identificatie"),
                    "kwalificatie": _kindtekst(ala, "activiteitregelkwalificatie"),
                    "locatieRefs": _hrefs(ala, "LocatieRef"),
                })
        elif naam in ("instrument", "taakuitoefening"):
            regel[naam] = (kind.text or "").strip()
        elif naam in ("identificatie", "kaartaanduiding"):
            pass  # kaartaanduiding is presentatie, geen inhoud (spec §7)
        else:
            waarschuw(meldingen,
                      f"onbekend regel-onderdeel '{naam}' bij {regel['owId']}")
    return regel


def _lees_norm(obj, imow_naam):
    waarden = []
    for nw in obj.iter():
        if isinstance(nw.tag, str) and lokale_naam(nw.tag) == "Normwaarde":
            soort_waarde, waarde = None, None
            for k in nw:
                n = lokale_naam(k.tag) if isinstance(k.tag, str) else ""
                if n in ("kwantitatieveWaarde", "kwalitatieveWaarde",
                         "waardeInRegeltekst"):
                    soort_waarde, waarde = n, (k.text or "").strip()
            waarden.append({
                "owId": _kindtekst(nw, "identificatie"),
                "soortWaarde": soort_waarde,
                "waarde": waarde,
                "locatieRefs": _hrefs(nw, "LocatieRef"),
            })
    return {
        "id": _kindtekst(obj, "identificatie"),
        "soort": imow_naam.lower(),  # omgevingsnorm | omgevingswaarde
        "naam": _kindtekst(obj, "naam"),
        "type": _kindtekst(obj, "type"),
        "eenheid": _kindtekst(obj, "eenheid"),
        "groep": _kindtekst(obj, "groep"),
        "waarden": waarden,
    }


# ---------------------------------------------------------------------------
# GIO's (GML-bestanden) — v0.2: de geo-bron van het STORM-pakket
# ---------------------------------------------------------------------------

def lees_gios(bronmap: Path, meldingen):
    """Lees GIO's in drie vormen:

    1. geo:GeoInformatieObjectVaststelling (.gml/.xml): work + norm-info +
       basisgeo-ids + eventuele normwaarden per locatie.
    2. AanleveringInformatieObject (.xml): work + bestandsnaam van een
       kale basisgeo-GML; de ids worden uit dat bestand gelezen.
    3. kale basisgeo-GML zonder wrapper: genegeerd (geen work-context).

    Resultaat: lijst dicts met work, expressie, bestand, basisgeo_ids,
    norm (naam/type/eenheid) en waarde-per-basisgeo-id.
    """
    gios = []
    io_bijlagen = []
    basisgeo_bestanden = {}  # bestandsnaam -> frozenset basisgeo-ids
    for pad in sorted(list(bronmap.glob("*.gml")) + list(bronmap.glob("*.xml"))):
        try:
            wortel = ET.parse(pad).getroot()
        except ET.ParseError:
            continue
        vaststelling = (wortel if lokale_naam(wortel.tag) ==
                        "GeoInformatieObjectVaststelling" else
                        wortel.find(f".//{{{STOP_GEO}}}GeoInformatieObjectVersie"))
        if lokale_naam(wortel.tag) == "FeatureCollectionGeometrie":
            basisgeo_bestanden[pad.name] = frozenset(
                e.text.strip() for e in wortel.iter(f"{{{BASISGEO}}}id"))
            continue
        if vaststelling is not None:
            gio = _lees_gio_versie(wortel, pad)
            if gio["work"]:
                gios.append(gio)
            continue
        # AanleveringInformatieObject: work + verwijzing naar kale GML
        if lokale_naam(wortel.tag) == "AanleveringInformatieObject":
            work = wortel.findtext(f".//{{{STOP_DATA}}}FRBRWork")
            expr = wortel.findtext(f".//{{{STOP_DATA}}}FRBRExpression")
            bestand = wortel.findtext(f".//{{{STOP_DATA}}}bestandsnaam")
            if work and bestand and bestand.lower().endswith(".gml"):
                gios.append({"work": work, "expressie": expr,
                             "bestand": bestand, "basisgeo_ids": None,
                             "norm": None, "waarden": {}, "bron_pad": pad,
                             "wrapper_pad": pad, "vorm": "aanlevering"})
            elif work and bestand:
                # niet-geo informatieobject (bv. PDF): wrapper + payload
                # reizen verbatim mee in het pakket (io/)
                io_bijlagen.append({"wrapper_pad": pad, "payload": bestand})
    # duplicaten (vaststelling + aanlever-wrapper voor dezelfde work):
    # de vaststellingsvorm wint (draagt norm en geometrie direct), maar de
    # wrapper wordt onthouden — die draagt de LVBB-metadata en de hash
    per_work = {}
    for gio in gios:
        bestaand = per_work.get(gio["work"])
        if bestaand is None:
            per_work[gio["work"]] = gio
        elif bestaand.get("vorm") == "aanlevering" \
                and gio.get("vorm") == "vaststelling":
            gio["wrapper_pad"] = bestaand["bron_pad"]
            per_work[gio["work"]] = gio
        elif bestaand.get("vorm") == "vaststelling" \
                and gio.get("vorm") == "aanlevering":
            bestaand["wrapper_pad"] = gio["bron_pad"]
    gios = list(per_work.values())

    # kale-GML-verwijzingen naresolven
    for gio in gios:
        if gio["basisgeo_ids"] is None:
            ids = basisgeo_bestanden.get(gio["bestand"])
            if ids is None and (bronmap / gio["bestand"]).exists():
                try:
                    w = ET.parse(bronmap / gio["bestand"]).getroot()
                    ids = frozenset(e.text.strip()
                                    for e in w.iter(f"{{{BASISGEO}}}id"))
                except ET.ParseError:
                    ids = None
            if ids is None:
                waarschuw(meldingen, f"GIO {gio['work']}: GML-bestand "
                                     f"'{gio['bestand']}' niet leesbaar")
                ids = frozenset()
            gio["basisgeo_ids"] = ids
    if gios:
        print(f"  GIO's gelezen: {len(gios)}"
              + (f" (+{len(io_bijlagen)} overige informatieobjecten)"
                 if io_bijlagen else ""))
    return gios, io_bijlagen


def _lees_gio_versie(wortel, pad):
    def t(naam):
        el = wortel.find(f".//{{{STOP_GEO}}}{naam}")
        return el.text.strip() if el is not None and el.text else None

    norm = {"naam": t("normlabel"), "type": t("normID"),
            "eenheid": t("eenheidID"), "eenheidlabel": t("eenheidlabel")}
    ids, waarden = set(), {}
    for loc in wortel.iter(f"{{{STOP_GEO}}}Locatie"):
        bid = next((e.text.strip() for e in loc.iter(f"{{{BASISGEO}}}id")), None)
        if not bid:
            continue
        ids.add(bid)
        for veld in ("kwantitatieveNormwaarde", "kwalitatieveNormwaarde"):
            w = loc.findtext(f".//{{{STOP_GEO}}}{veld}")
            if w is not None:
                waarden[bid] = (veld, w.strip())
    return {"work": t("FRBRWork"), "expressie": t("FRBRExpression"),
            "bestand": pad.name, "basisgeo_ids": frozenset(ids),
            "norm": norm if any(norm.values()) else None,
            "waarden": waarden, "bron_pad": pad, "vorm": "vaststelling"}


def bereken_locatie_mappings(ow, gios):
    """Bepaal welke IMOW-locatie 1-op-1 met welke GIO correspondeert.

    Basis voor de IntIoRef-destillatie: tekst -> work -> IMOW-locatie.
    Een Gebiedengroep wint van een los Gebied met dezelfde basisgeo-set
    (juridische regels verwijzen in de praktijk naar groepen).
    """
    loc_basisgeo = {g["id"]: frozenset([g["geometrieRef"]])
                    for g in ow["gebieden"] if g["geometrieRef"]}

    def groep_set(groep_id, bezocht=frozenset()):
        if groep_id in bezocht:
            return frozenset()
        for groep in ow["gebiedengroepen"]:
            if groep["id"] == groep_id:
                s = set()
                for lid in groep["leden"]:
                    s |= loc_basisgeo.get(lid) or groep_set(
                        lid, bezocht | {groep_id})
                return frozenset(s)
        return frozenset()

    for groep in ow["gebiedengroepen"]:
        loc_basisgeo[groep["id"]] = groep_set(groep["id"])

    werk_locatie, loc_giowork = {}, {}
    for gio in gios:
        if not gio["basisgeo_ids"]:
            continue
        kandidaten = ([g["id"] for g in ow["gebiedengroepen"]
                       if loc_basisgeo.get(g["id"]) == gio["basisgeo_ids"]]
                      + [g["id"] for g in ow["gebieden"]
                         if loc_basisgeo.get(g["id"]) == gio["basisgeo_ids"]])
        if kandidaten:
            werk_locatie[gio["work"]] = kandidaten[0]
            if gio["expressie"]:
                werk_locatie[gio["expressie"]] = kandidaten[0]
            loc_giowork[kandidaten[0]] = gio["work"]
    return loc_basisgeo, werk_locatie, loc_giowork


# ---------------------------------------------------------------------------
# IMTR / STTR
# ---------------------------------------------------------------------------

# bedr:functioneleStructuurRef-href bevat soort + IMOW-activiteit-id direct
# aan elkaar geplakt, bv. ".../id/concept/Conclusienl.imow-mnre1034.
# activiteit.BouwenDakkapel". De soort-prefix is vrij tekstueel en kan
# samengesteld zijn ("IndieningsvereistenVergunning"): alles vóór "nl.imow-".
FSR_PATROON = re.compile(
    r"([A-Za-z]*)"
    r"(nl\.imow-[A-Za-z0-9]+\.activiteit\.[A-Za-z0-9._-]+)")


def lees_toepasbare_regels(imtr_map: Path, meldingen):
    """Lees STTR-bestanden: losse DMN's én KV-TR-aanlever-ZIPs
    (manifest + opdracht + DMN, zoals het Omgevingsloket ze aanlevert)."""
    import zipfile

    resultaten = []
    paden = sorted(imtr_map.glob("*.dmn")) + sorted(imtr_map.glob("*.xml"))
    for pad in paden:
        try:
            wortel = ET.parse(pad).getroot()
        except ET.ParseError:
            continue
        if lokale_naam(wortel.tag) != "definitions":
            continue
        resultaten.append(_lees_sttr(wortel, pad.name, None, meldingen))
    for pad in sorted(imtr_map.glob("*.zip")):
        with zipfile.ZipFile(pad) as zf:
            begindatum = None
            for lid in zf.namelist():
                if lid.lower().endswith("opdrachtaanleverentoepasbareregels.xml"):
                    try:
                        opdracht = ET.fromstring(zf.read(lid))
                        begindatum = _kindtekst(opdracht, "geldigBegindatum")
                    except ET.ParseError:
                        pass
            for lid in zf.namelist():
                if not lid.lower().endswith(".dmn"):
                    continue
                try:
                    wortel = ET.fromstring(zf.read(lid))
                except ET.ParseError:
                    waarschuw(meldingen, f"{pad.name}:{lid} niet leesbaar")
                    continue
                if lokale_naam(wortel.tag) == "definitions":
                    resultaten.append(_lees_sttr(wortel, f"{pad.name}:{lid}",
                                                 begindatum, meldingen))
    return resultaten


def _lees_sttr(wortel, bron_naam, geldig_begindatum, meldingen):
    tr = {
        "naam": wortel.get("name"),
        "namespace": wortel.get("namespace"),
        "activiteitRef": None,
        "soort": None,
        "geldigBegindatum": geldig_begindatum,
        "regelgroepen": [],
        "uitvoeringsregels": [],
        "dmn": wortel,  # verbatim ingebed
        "bestand": bron_naam,
    }
    for el in wortel.iter():
        if not isinstance(el.tag, str):
            continue
        naam = lokale_naam(el.tag)
        if naam == "functioneleStructuurRef" and tr["activiteitRef"] is None:
            m = FSR_PATROON.search(el.get("href") or "")
            if m:
                tr["soort"] = (m.group(1) or "").lower() or None
                tr["activiteitRef"] = m.group(2)
        elif naam == "regelgroep":
            tr["regelgroepen"].append({
                "id": el.get("id"),
                "naam": _kindtekst(el, "naam"),
                "prioriteit": _kindtekst(el, "prioriteit"),
            })
        elif naam == "uitvoeringsregel":
            tr["uitvoeringsregels"].append(_lees_uitvoeringsregel(el))
    if tr["activiteitRef"] is None:
        waarschuw(meldingen, f"{bron_naam}: geen IMOW-activiteit gevonden "
                             f"in functioneleStructuurRef")
    print(f"  STTR gelezen: {bron_naam} "
          f"({len(tr['uitvoeringsregels'])} uitvoeringsregels)")
    return tr


def _lees_uitvoeringsregel(el):
    regel = {
        "id": el.get("id"),
        "regelgroepRef": None,
        "prioriteit": None,
        "gegevensType": None,
        "vraagTekst": None,
        "gioRef": None,
        "opties": [],
        "toelichting": None,
    }
    for kind in el.iter():
        if not isinstance(kind.tag, str):
            continue
        naam = lokale_naam(kind.tag)
        if naam == "regelgroepRef":
            regel["regelgroepRef"] = (kind.get("href") or "").lstrip("#")
        elif naam == "prioriteit" and regel["prioriteit"] is None:
            regel["prioriteit"] = (kind.text or "").strip()
        elif naam == "gegevensType":
            regel["gegevensType"] = (kind.text or "").strip()
        elif naam == "vraagTekst":
            regel["vraagTekst"] = (kind.text or "").strip()
        elif naam == "locatie" and kind.get("identificatie"):
            regel["gioRef"] = kind.get("identificatie")
        elif naam == "optie":
            regel["opties"].append({
                "sequenceId": _kindtekst(kind, "sequenceId"),
                "tekst": _kindtekst(kind, "optieText"),
            })
        elif naam == "toelichting" and regel["toelichting"] is None:
            regel["toelichting"] = (kind.text or "").strip()
    return regel


def bouw_toepasbare_regels(regeling, toepasbaar):
    wortel = _sub(regeling, "ToepasbareRegels")
    for tr in toepasbaar:
        el = _sub(wortel, "ToepasbareActiviteit",
                  activiteitRef=tr["activiteitRef"], soort=tr["soort"],
                  naam=tr["naam"], namespace=tr["namespace"],
                  geldigBegindatum=tr["geldigBegindatum"])
        for groep in tr["regelgroepen"]:
            _sub(el, "Regelgroep", groep["naam"], id=groep["id"],
                 prioriteit=groep["prioriteit"])
        for regel in tr["uitvoeringsregels"]:
            r = _sub(el, "Uitvoeringsregel", id=regel["id"],
                     regelgroepRef=regel["regelgroepRef"],
                     prioriteit=regel["prioriteit"],
                     gegevensType=regel["gegevensType"])
            if regel["vraagTekst"]:
                _sub(r, "VraagTekst", regel["vraagTekst"])
            if regel["gioRef"]:
                _sub(r, "GioRef", ref=regel["gioRef"])
            for optie in regel["opties"]:
                _sub(r, "Optie", optie["tekst"], sequenceId=optie["sequenceId"])
            if regel["toelichting"]:
                _sub(r, "Toelichting", regel["toelichting"])
        logica = _sub(el, "Beslislogica")
        logica.append(tr["dmn"])


# ---------------------------------------------------------------------------
# Opbouwen STORM-document
# ---------------------------------------------------------------------------

def _sub(_ouder, _naam, _tekst=None, **attrs):
    el = ET.SubElement(_ouder, f"{S}{_naam}", {k: v for k, v in attrs.items()
                                               if v is not None})
    if _tekst is not None:
        el.text = _tekst
    return el


def _locatieaanduiding(ouder, refs):
    la = _sub(ouder, "Locatieaanduiding")
    for ref in refs:
        _sub(la, "GioRef", ref=ref)
    return la


def bouw_identificatie(regeling, ident_el, versie_el):
    ident = _sub(regeling, "Identificatie")
    werk = None
    if ident_el is not None:
        for veld in ("FRBRWork", "FRBRExpression", "soortWork"):
            el = ident_el.find(f"{{{STOP_DATA}}}{veld}")
            if el is not None and el.text:
                _sub(ident, veld, el.text.strip())
                if veld == "FRBRWork":
                    werk = el.text.strip()
    if versie_el is not None and versie_el.text:
        _sub(ident, "versienummer", versie_el.text.strip())
    # /akn/nl/act/<bevoegdgezag>/... -> bevoegd gezag
    if werk:
        delen = werk.strip("/").split("/")
        if len(delen) >= 4:
            _sub(ident, "bevoegdGezag", delen[3])


def _voeg_annotatie_in(el, nieuw):
    """Voeg een annotatie-element in ná Kop/LidNummer/eerdere annotaties."""
    prefix = {f"{S}Kop", f"{S}LidNummer", f"{S}Regel", f"{S}Tekstdeel",
              f"{S}HoofdlijnRef", f"{S}GerelateerdRef"}
    idx = 0
    for kind in el:
        if kind.tag in prefix:
            idx += 1
        else:
            break
    el.insert(idx, nieuw)


def _destilleer_locaties(el, extio, werk_locatie):
    """Volg IntIoRef -> ExtIoRef -> GIO-work -> IMOW-locatie.

    Returns (locatie-set | None, geen_refs): None als een verwijzing niet
    naar een bekende locatie herleid kan worden; geen_refs=True als het
    tekst-element helemaal geen IntIoRefs bevat (ambtsgebied-kandidaat).
    """
    refs = [i.get("ref") for i in el.iter(f"{S}IntIoRef")]
    if not refs:
        return frozenset(), True
    locs = set()
    for ref in refs:
        join = extio.get(ref)
        loc = werk_locatie.get(join) if join else None
        if not loc:
            return None, False
        locs.add(loc)
    return frozenset(locs), False


def annoteer_tekst(tekst_el, ow, meldingen, werk_locatie=None):
    """Hang Regeltekst-owId's en Regel-annotaties inline aan de tekstboom.

    v0.2: een Regel krijgt alleen een expliciete Locatieaanduiding als de
    locatie NIET afleidbaar is uit de IntIoRefs van zijn artikel/lid
    (of uit de ambtsgebied-default voor artikelen zonder IntIoRefs).
    """
    werk_locatie = werk_locatie or {}
    op_wid = {el.get("wId"): el for el in tekst_el.iter()
              if isinstance(el.tag, str) and el.get("wId")}
    extio = {}
    for e in tekst_el.iter(f"{S}ExtIoRef"):
        if e.get("wId"):
            extio[e.get("wId")] = (e.get("ref") or "").strip()
        if e.get("eId"):
            extio[e.get("eId")] = (e.get("ref") or "").strip()
    ambtsgebied_ids = {a["id"] for a in ow["ambtsgebieden"]}

    # owId van het Regeltekst-object op het tekst-element (rondreisgarantie)
    gebonden = 0
    for regeltekst_id, info in ow["regelteksten"].items():
        el = op_wid.get(info["wId"])
        if el is None:
            waarschuw(meldingen, f"Regeltekst {regeltekst_id}: geen tekst-element"
                                 f" met wId '{info['wId']}' gevonden")
            continue
        el.set("owId", regeltekst_id)
        for ref in info["gerelateerd"]:
            _voeg_annotatie_in(el, ET.Element(f"{S}GerelateerdRef",
                                              {"ref": ref}))
        gebonden += 1

    # juridische regels inline
    for regel in ow["regels"]:
        info = ow["regelteksten"].get(regel["regeltekstRef"])
        el = op_wid.get(info["wId"]) if info else None
        if el is None:
            waarschuw(meldingen, f"regel {regel['owId']} verwijst naar onbekende"
                                 f" regeltekst {regel['regeltekstRef']}")
            continue
        regel_el = ET.Element(f"{S}Regel", {"soort": regel["soort"],
                                            "idealisatie": regel["idealisatie"] or "exact",
                                            "owId": regel["owId"]})
        if regel["instrument"]:
            regel_el.set("instrument", regel["instrument"])
        if regel["taakuitoefening"]:
            regel_el.set("taakuitoefening", regel["taakuitoefening"])
        # v0.2: locatie alleen expliciet als niet destilleerbaar
        doel, geen_refs = _destilleer_locaties(el, extio, werk_locatie)
        locs = set(regel["locatieRefs"])
        afleidbaar = (not geen_refs and doel is not None
                      and locs and doel == locs)
        ambts_default = (geen_refs and len(ambtsgebied_ids) == 1
                         and locs == ambtsgebied_ids)
        if not (afleidbaar or ambts_default):
            _locatieaanduiding(regel_el, regel["locatieRefs"])
        for ref in regel["gebiedsaanwijzingRefs"]:
            _sub(regel_el, "GebiedsaanwijzingRef", ref=ref)
        for ref in regel["normRefs"]:
            _sub(regel_el, "NormRef", ref=ref)
        for toe in regel["toedelingen"]:
            toe_el = _sub(regel_el, "ActiviteitToedeling",
                          activiteitRef=toe["activiteitRef"],
                          kwalificatie=toe["kwalificatie"], owId=toe["owId"])
            if toe["locatieRefs"]:
                _locatieaanduiding(toe_el, toe["locatieRefs"])
        _voeg_annotatie_in(el, regel_el)

    # vrijetekst: Divisie/Divisietekst-owId's binden + Tekstdelen inline
    for divisie_id, wid in ow["divisies"].items():
        el = op_wid.get(wid)
        if el is None:
            waarschuw(meldingen, f"Divisie(tekst) {divisie_id}: geen "
                                 f"tekst-element met wId '{wid}' gevonden")
            continue
        el.set("owId", divisie_id)
        gebonden += 1
    for td in ow["tekstdelen"]:
        wid = ow["divisies"].get(td["divisieRef"])
        el = op_wid.get(wid) if wid else None
        if el is None:
            waarschuw(meldingen, f"Tekstdeel {td['owId']} verwijst naar "
                                 f"onbekende divisie {td['divisieRef']}")
            continue
        td_el = ET.Element(f"{S}Tekstdeel", {"owId": td["owId"]})
        if td["idealisatie"]:
            td_el.set("idealisatie", td["idealisatie"])
        if td["thema"]:
            td_el.set("thema", td["thema"])
        if td["locatieRefs"]:
            _locatieaanduiding(td_el, td["locatieRefs"])
        for ref in td["gebiedsaanwijzingRefs"]:
            _sub(td_el, "GebiedsaanwijzingRef", ref=ref)
        for ref in td["hoofdlijnRefs"]:
            _sub(td_el, "HoofdlijnRef", ref=ref)
        _voeg_annotatie_in(el, td_el)

    # Rutopie-ideaalvorm: attributen op het tekst-element zelf wanneer
    # de annotatie eenduidig is (precies één Regel of Tekstdeel)
    for el in tekst_el.iter():
        if not isinstance(el.tag, str):
            continue
        regels = [k for k in el if k.tag == f"{S}Regel"]
        if len(regels) == 1:
            el.set("regelType", regels[0].get("soort"))
            el.set("idealisatie", regels[0].get("idealisatie"))
            if regels[0].get("thema"):
                el.set("thema", regels[0].get("thema"))
        tekstdelen = [k for k in el if k.tag == f"{S}Tekstdeel"]
        if len(tekstdelen) == 1:
            if tekstdelen[0].get("idealisatie"):
                el.set("idealisatie", tekstdelen[0].get("idealisatie"))
            if tekstdelen[0].get("thema"):
                el.set("thema", tekstdelen[0].get("thema"))
    return gebonden


def bouw_ow_objecten(regeling, ow):
    wortel = _sub(regeling, "OwObjecten")
    for act in ow["activiteiten"]:
        el = _sub(wortel, "Activiteit", id=act["id"])
        _sub(el, "naam", act["naam"])
        if act["groep"]:
            _sub(el, "groep", act["groep"])
        if act["bovenliggend"]:
            _sub(el, "bovenliggendeActiviteitRef", ref=act["bovenliggend"])
        for ref in act["gerelateerd"]:
            _sub(el, "gerelateerdeActiviteitRef", ref=ref)
    for hl in ow["hoofdlijnen"]:
        el = _sub(wortel, "Hoofdlijn", id=hl["id"])
        _sub(el, "soort", hl["soort"])
        _sub(el, "naam", hl["naam"])
    for pons in ow["ponsen"]:
        el = _sub(wortel, "Pons", id=pons["id"])
        _locatieaanduiding(el, pons["locatieRefs"])
    for rg in ow["regelingsgebieden"]:
        el = _sub(wortel, "Regelingsgebied", id=rg["id"])
        _locatieaanduiding(el, rg["locatieRefs"])


def bouw_geo(regeling, ow, gios, loc_giowork, meldingen):
    """v0.2: Gio-verwijzingen naar de GML-bestanden + het ambtsgebied.

    Gebiedsaanwijzingen rusten op de Gio waarvan de work correspondeert
    met hun IMOW-locatie (P5); lukt dat niet, dan gaan ze als fallback
    naar de Exportregels (return-waarde).
    """
    geo = _sub(regeling, "Geo")
    aanwijzing_rest = []
    aanwijzing_per_work = {}
    for ga in ow["gebiedsaanwijzingen"]:
        doel = ga["locatieRefs"][0] if ga["locatieRefs"] else None
        work = loc_giowork.get(doel)
        if work and work not in aanwijzing_per_work \
                and len(ga["locatieRefs"]) == 1:
            aanwijzing_per_work[work] = ga
        else:
            aanwijzing_rest.append(ga)

    for gio in gios:
        wrapper = gio.get("wrapper_pad")
        el = _sub(geo, "Gio", work=gio["work"], expressie=gio["expressie"],
                  bestand=f"gio/{gio['bestand']}",
                  wrapper=f"gio/{wrapper.name}" if wrapper else None)
        ga = aanwijzing_per_work.get(gio["work"])
        if ga:
            ga_el = _sub(el, "Gebiedsaanwijzing", owId=ga["id"],
                         locatieRef=ga["locatieRefs"][0])
            _sub(ga_el, "type", ga["type"])
            _sub(ga_el, "naam", ga["naam"])
            _sub(ga_el, "groep", ga["groep"])
    for ag in ow["ambtsgebieden"]:
        el = _sub(geo, "Ambtsgebied", id=ag["id"])
        if ag["noemer"]:
            _sub(el, "noemer", ag["noemer"])
        _sub(el, "BestuurlijkeGrenzen", id=ag["grensId"], domein=ag["domein"],
             geldigOp=ag["geldigOp"])
    return aanwijzing_rest


def bouw_exportregels(regeling, ow, gios, loc_basisgeo, loc_giowork,
                      aanwijzing_rest, meldingen):
    """IMOW-export-administratie: locatie-identiteiten en norm-objecten."""
    wortel = _sub(regeling, "Exportregels")

    for gebied in ow["gebieden"]:
        _sub(wortel, "ImowLocatie", owId=gebied["id"], soort="Gebied",
             noemer=gebied["noemer"], basisgeoId=gebied["geometrieRef"],
             gioWork=loc_giowork.get(gebied["id"]))
    for groep in ow["gebiedengroepen"]:
        el = _sub(wortel, "ImowLocatie", owId=groep["id"],
                  soort="Gebiedengroep", noemer=groep["noemer"],
                  gioWork=loc_giowork.get(groep["id"]))
        for lid in groep["leden"]:
            _sub(el, "LidRef", ref=lid)

    for ga in aanwijzing_rest:
        el = _sub(wortel, "ImowGebiedsaanwijzing", owId=ga["id"])
        _sub(el, "type", ga["type"])
        _sub(el, "naam", ga["naam"])
        _sub(el, "groep", ga["groep"])
        for ref in ga["locatieRefs"]:
            _sub(el, "LocatieRef", ref=ref)

    for norm in ow["normen"]:
        gio = _vind_norm_gio(norm, gios, loc_basisgeo)
        attrs = {"owId": norm["id"], "soort": norm["soort"],
                 "groep": norm["groep"]}
        if gio:
            attrs["gioWork"] = gio["work"]
        else:
            attrs.update(naam=norm["naam"], type=norm["type"],
                         eenheid=norm["eenheid"])
        el = _sub(wortel, "ImowNorm", **attrs)
        for w in norm["waarden"]:
            w_attrs = {"owId": w["owId"]}
            # waarde alleen expliciet als niet uit de GML afleidbaar
            if not (gio and w["soortWaarde"] == "kwantitatieveWaarde"):
                w_attrs[w["soortWaarde"]] = w["waarde"]
            nw = _sub(el, "Normwaarde", **w_attrs)
            for ref in w["locatieRefs"]:
                _sub(nw, "LocatieRef", ref=ref)


def _vind_norm_gio(norm, gios, loc_basisgeo):
    """De GIO die deze norm volledig draagt (naam/type/eenheid/waarden)."""
    for gio in gios:
        g = gio["norm"]
        if not g or g["type"] != norm["type"] or g["naam"] != norm["naam"] \
                or g["eenheid"] != norm["eenheid"]:
            continue
        gedekt = True
        for w in norm["waarden"]:
            if w["soortWaarde"] != "kwantitatieveWaarde":
                gedekt = False
                break
            for loc in w["locatieRefs"]:
                for bid in loc_basisgeo.get(loc, frozenset()) or {None}:
                    if gio["waarden"].get(bid) != ("kwantitatieveNormwaarde",
                                                   w["waarde"]):
                        gedekt = False
            if not gedekt:
                break
        if gedekt and norm["waarden"]:
            return gio
    return None


# ---------------------------------------------------------------------------
# Hoofdprogramma
# ---------------------------------------------------------------------------

def converteer(bronmap: Path, doel: Path,
               imtr_map: Path | None = None) -> list[str]:
    from .storm_common import STORM_XSD_URL, XSI

    meldingen: list[str] = []
    print(f"Bron: {bronmap}")
    compact, structuur, ident_el, versie_el, bron_wortel, bron_pad = \
        vind_stop_tekst(bronmap, meldingen)
    ow = lees_ow_objecten(bronmap, meldingen)
    gios, io_bijlagen = lees_gios(bronmap, meldingen)
    loc_basisgeo, werk_locatie, loc_giowork = bereken_locatie_mappings(ow, gios)
    toepasbaar = (lees_toepasbare_regels(imtr_map, meldingen)
                  if imtr_map else [])

    regeling = ET.Element(f"{S}Regeling", {"schemaversie": "0.5.0"})
    regeling.set(f"{{{XSI}}}schemaLocation",
                 f"{STORM} {STORM_XSD_URL}")
    bouw_identificatie(regeling, ident_el, versie_el)

    tekst_el = ET.SubElement(regeling, f"{S}Tekst", {"structuur": structuur})
    for k, v in compact.attrib.items():  # bv. componentnaam/wordt (mutatie)
        tekst_el.set(k, v)
    for kind in compact:
        if isinstance(kind.tag, str):
            tekst_el.append(hernoem_boom(kind, STORM))
    gebonden = annoteer_tekst(tekst_el, ow, meldingen, werk_locatie)

    bouw_ow_objecten(regeling, ow)
    aanwijzing_rest = bouw_geo(regeling, ow, gios, loc_giowork, meldingen)
    bouw_exportregels(regeling, ow, gios, loc_basisgeo, loc_giowork,
                      aanwijzing_rest, meldingen)
    envelop = bouw_envelop(regeling, bron_wortel, bron_pad, bronmap, meldingen)
    if toepasbaar:
        bouw_toepasbare_regels(regeling, toepasbaar)

    doel.parent.mkdir(parents=True, exist_ok=True)
    # GML-pakket: GIO-bestanden + aanleverwrappers verbatim naast storm.xml
    if gios:
        gio_map = doel.parent / "gio"
        gio_map.mkdir(exist_ok=True)
        for gio in gios:
            bron_gml = bronmap / gio["bestand"]
            if bron_gml.exists():
                shutil.copy2(bron_gml, gio_map / gio["bestand"])
            wrapper = gio.get("wrapper_pad")
            if wrapper and wrapper.exists():
                shutil.copy2(wrapper, gio_map / wrapper.name)
    # overige informatieobjecten (bv. PDF-bijlagen) verbatim in io/
    if io_bijlagen:
        io_map = doel.parent / "io"
        io_map.mkdir(exist_ok=True)
        for io in io_bijlagen:
            shutil.copy2(io["wrapper_pad"], io_map / io["wrapper_pad"].name)
            payload = bronmap / io["payload"]
            if payload.exists():
                shutil.copy2(payload, io_map / io["payload"])
    # alleen_ns: niet inspringen binnen ingebedde DMN (Beslislogica)
    schrijf_xml(regeling, doel, default_ns=STORM, alleen_ns=STORM)

    print(f"\nGeschreven: {doel}")
    print(f"  tekst-ankers gebonden           : {gebonden}/"
          f"{len(ow['regelteksten']) + len(ow['divisies'])}")
    print(f"  juridische regels inline        : {len(ow['regels'])}")
    print(f"  tekstdelen inline               : {len(ow['tekstdelen'])}")
    print(f"  activiteiten                    : {len(ow['activiteiten'])}")
    print(f"  normen                          : {len(ow['normen'])}")
    print(f"  gebiedsaanwijzingen op Gio      : "
          f"{len(ow['gebiedsaanwijzingen']) - len(aanwijzing_rest)}"
          f" (+{len(aanwijzing_rest)} in exportregels)")
    print(f"  GIO-GML's in pakket             : {len(gios)}")
    print(f"  imow-locaties in exportregels   : "
          f"{len(ow['gebieden']) + len(ow['gebiedengroepen'])}")
    print(f"  normen in exportregels          : {len(ow['normen'])}")
    print(f"  envelop (LVBB-administratie)    : {'ja' if envelop else 'nee'}")
    print(f"  toepasbare-regelbestanden       : {len(toepasbaar)}")
    print(f"  waarschuwingen                  : {len(meldingen)}")
    return meldingen


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__)
    converteer(Path(sys.argv[1]), Path(sys.argv[2]),
               Path(sys.argv[3]) if len(sys.argv) == 4 else None)
