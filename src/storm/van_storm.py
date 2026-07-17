"""Conversie: één STORM-document -> STOP-tekst + IMOW-deelbestanden + STTR.

Gebruik:
    python van_storm.py <storm.xml> <doelmap>

Schrijft:
    <doelmap>/stop/regeling.xml        STOP RegelingCompact (annotaties gestript)
    <doelmap>/ow/ow<Type>.xml          IMOW-deelbestanden per objecttype
    <doelmap>/imtr/<naam>.dmn          STTR-bestanden (uit Beslislogica)

De IMOW-objecten worden gereconstrueerd uit de inline annotaties; de
oorspronkelijke identificaties komen uit de owId-attributen. Ontbreekt een
owId (nieuw geschreven STORM-content), dan wordt een deterministische
identificatie gegenereerd uit het bevoegd gezag en een volgnummer.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from .storm_common import (
    IDEALISATIE_URI, IMOW_DEELBESTAND, IMOW_GA, IMOW_LOCATIE, IMOW_PONS,
    IMOW_REGELINGSGEBIED, IMOW_REGELS, IMOW_ROL, IMOW_STANDLEVERING,
    IMOW_VAN_REGELSOORT, IMOW_VRIJETEKST, STOP_TEKST, STORM,
    STORM_ANNOTATIE_ATTRS, STORM_ANNOTATIE_ELEMENTEN, XLINK, XLINK_HREF,
    lokale_naam, schrijf_xml, waarschuw,
)

S = f"{{{STORM}}}"

for prefix, uri in [("r", IMOW_REGELS), ("l", IMOW_LOCATIE), ("rol", IMOW_ROL),
                    ("ga", IMOW_GA), ("p", IMOW_PONS),
                    ("rg", IMOW_REGELINGSGEBIED), ("vt", IMOW_VRIJETEKST),
                    ("sl", IMOW_STANDLEVERING), ("ow-dc", IMOW_DEELBESTAND),
                    ("xlink", XLINK)]:
    ET.register_namespace(prefix, uri)


# ---------------------------------------------------------------------------
# STORM -> STOP-tekst
# ---------------------------------------------------------------------------

def strip_annotaties(bron: ET.Element, naar_ns: str) -> ET.Element:
    """Herbouw de boom in de STOP-tekst-namespace zonder STORM-annotaties."""
    attrs = {k: v for k, v in bron.attrib.items()
             if k not in STORM_ANNOTATIE_ATTRS}
    nieuw = ET.Element(f"{{{naar_ns}}}{lokale_naam(bron.tag)}", attrs)
    nieuw.text = bron.text
    nieuw.tail = bron.tail
    for kind in bron:
        if not isinstance(kind.tag, str):
            continue
        if lokale_naam(kind.tag) in STORM_ANNOTATIE_ELEMENTEN:
            continue
        nieuw.append(strip_annotaties(kind, naar_ns))
    return nieuw


# ---------------------------------------------------------------------------
# STORM -> IMOW-deelbestanden
# ---------------------------------------------------------------------------

def _el(ns, naam, ouder=None, tekst=None, **attrs):
    tag = f"{{{ns}}}{naam}"
    el = ET.Element(tag, attrs) if ouder is None else ET.SubElement(ouder, tag, attrs)
    if tekst is not None:
        el.text = tekst
    return el


def _ref(ouder, ns, naam, href):
    return _el(ns, naam, ouder, **{XLINK_HREF: href})


def _locatieaanduiding(ouder, ns, gio_refs):
    la = _el(ns, "locatieaanduiding", ouder)
    for ref in gio_refs:
        _ref(la, IMOW_LOCATIE, "LocatieRef", ref)


def _gio_refs(storm_el):
    """GioRef-refs binnen de (directe) Locatieaanduiding van dit element."""
    la = storm_el.find(f"{S}Locatieaanduiding")
    if la is None:
        return []
    return [g.get("ref") for g in la.findall(f"{S}GioRef")]


class IdGenerator:
    """Deterministische identificaties voor content zonder owId."""

    def __init__(self, bevoegd_gezag):
        self.bg = bevoegd_gezag or "storm"
        self.tellers = {}

    def volgende(self, objecttype):
        n = self.tellers.get(objecttype, 0) + 1
        self.tellers[objecttype] = n
        return f"nl.imow-{self.bg}.{objecttype}.storm{n:07d}"


# tekst-elementen die drager van een Regeltekst-annotatie kunnen zijn;
# Divisie/Divisietekst zijn dragers van vrijetekst-annotaties (vt:)
REGELTEKST_DRAGERS = {"Artikel", "Lid"}
VRIJETEKST_DRAGERS = {"Divisie", "Divisietekst"}


def maak_destillatie_context(storm_tekst, exportregels, geo):
    """Context om regel-locaties te destilleren uit IntIoRefs (v0.2)."""
    extio = {}
    for e in storm_tekst.iter(f"{S}ExtIoRef"):
        if e.get("wId"):
            extio[e.get("wId")] = (e.get("ref") or "").strip()
        if e.get("eId"):
            extio[e.get("eId")] = (e.get("ref") or "").strip()
    werk_locatie = {}
    if exportregels is not None:
        for loc in exportregels.findall(f"{S}ImowLocatie"):
            if loc.get("gioWork"):
                werk_locatie[loc.get("gioWork")] = loc.get("owId")
    if geo is not None:
        # ook de expressie-id's van de Gio's op de locatie laten wijzen
        for gio in geo.findall(f"{S}Gio"):
            owid = werk_locatie.get(gio.get("work"))
            if owid and gio.get("expressie"):
                werk_locatie[gio.get("expressie")] = owid
    ambtsgebieden = ([a.get("id") for a in geo.findall(f"{S}Ambtsgebied")]
                     if geo is not None else [])
    return {"extio": extio, "werk_locatie": werk_locatie,
            "ambtsgebied": ambtsgebieden[0] if len(ambtsgebieden) == 1
            else None}


def _destilleer(el, ctx, meldingen):
    refs = [i.get("ref") for i in el.iter(f"{S}IntIoRef")]
    if not refs:
        if ctx["ambtsgebied"]:
            return [ctx["ambtsgebied"]]
        return []
    locs = []
    for ref in refs:
        join = ctx["extio"].get(ref)
        loc = ctx["werk_locatie"].get(join) if join else None
        if loc and loc not in locs:
            locs.append(loc)
        elif not loc:
            waarschuw(meldingen, f"IntIoRef '{ref}' niet herleidbaar naar "
                                 f"een IMOW-locatie")
    return locs


def bouw_regels(storm_tekst, norm_soorten, ctx, idgen, meldingen):
    """Regeltekst-objecten + juridische regels uit de inline annotaties."""
    objecten = []
    for el in storm_tekst.iter():
        if not isinstance(el.tag, str):
            continue
        if lokale_naam(el.tag) not in REGELTEKST_DRAGERS:
            continue
        regels = [k for k in el if k.tag == f"{S}Regel"]
        regeltekst_id = el.get("owId")
        if not regels and not regeltekst_id:
            continue
        if not regeltekst_id:
            regeltekst_id = idgen.volgende("regeltekst")
        rt = _el(IMOW_REGELS, "Regeltekst", wId=el.get("wId") or "")
        _el(IMOW_REGELS, "identificatie", rt, regeltekst_id)
        for rel in el.findall(f"{S}GerelateerdRef"):
            houder = _el(IMOW_REGELS, "gerelateerdeRegeltekst", rt)
            _ref(houder, IMOW_REGELS, "RegeltekstRef", rel.get("ref"))
        objecten.append(rt)
        for regel in regels:
            objecten.append(_bouw_regel(regel, el, regeltekst_id, norm_soorten,
                                        ctx, idgen, meldingen))
    return objecten


def _bouw_regel(regel, tekst_el, regeltekst_id, norm_soorten, ctx, idgen,
                meldingen):
    imow_naam = IMOW_VAN_REGELSOORT[regel.get("soort")]
    obj = _el(IMOW_REGELS, imow_naam)
    _el(IMOW_REGELS, "identificatie", obj,
        regel.get("owId") or idgen.volgende("juridischeregel"))
    _el(IMOW_REGELS, "idealisatie", obj,
        IDEALISATIE_URI[regel.get("idealisatie")])
    aol = _el(IMOW_REGELS, "artikelOfLid", obj)
    _ref(aol, IMOW_REGELS, "RegeltekstRef", regeltekst_id)
    # v0.2: expliciete locatie wint; anders destilleren uit de tekst
    locatie_refs = _gio_refs(regel) or _destilleer(tekst_el, ctx, meldingen)
    if not locatie_refs:
        waarschuw(meldingen, f"regel {regel.get('owId')}: geen locatie "
                             f"(expliciet noch destilleerbaar)")
    _locatieaanduiding(obj, IMOW_REGELS, locatie_refs)
    for gar in regel.findall(f"{S}GebiedsaanwijzingRef"):
        gaw = _el(IMOW_REGELS, "gebiedsaanwijzing", obj)
        _ref(gaw, IMOW_GA, "GebiedsaanwijzingRef", gar.get("ref"))
    for nr in regel.findall(f"{S}NormRef"):
        soort = norm_soorten.get(nr.get("ref"))
        if soort == "omgevingswaarde":
            houder = _el(IMOW_REGELS, "omgevingswaardeaanduiding", obj)
            _ref(houder, IMOW_ROL, "OmgevingswaardeRef", nr.get("ref"))
        elif soort == "omgevingsnorm":
            houder = _el(IMOW_REGELS, "omgevingsnormaanduiding", obj)
            _ref(houder, IMOW_ROL, "OmgevingsnormRef", nr.get("ref"))
        else:
            waarschuw(meldingen, f"NormRef naar onbekende norm {nr.get('ref')}")
    for veld in ("instrument", "taakuitoefening"):
        if regel.get(veld):
            _el(IMOW_REGELS, veld, obj, regel.get(veld))
    # één activiteitaanduiding per toedeling (zo levert de praktijk ze aan,
    # ook bij meerdere kwalificaties op dezelfde activiteit)
    for toe in regel.findall(f"{S}ActiviteitToedeling"):
        aand = _el(IMOW_REGELS, "activiteitaanduiding", obj)
        _ref(aand, IMOW_ROL, "ActiviteitRef", toe.get("activiteitRef"))
        ala = _el(IMOW_REGELS, "ActiviteitLocatieaanduiding", aand)
        _el(IMOW_REGELS, "identificatie", ala,
            toe.get("owId") or idgen.volgende("activiteitlocatieaanduiding"))
        _el(IMOW_REGELS, "activiteitregelkwalificatie", ala,
            toe.get("kwalificatie"))
        _locatieaanduiding(ala, IMOW_REGELS, _gio_refs(toe))
    return obj


def bouw_vrijetekst(storm_tekst, idgen, meldingen):
    """vt:Divisie/vt:Divisietekst/vt:Tekstdeel uit de inline annotaties."""
    objecten, typen = [], set()
    for el in storm_tekst.iter():
        if not isinstance(el.tag, str):
            continue
        naam = lokale_naam(el.tag)
        if naam not in VRIJETEKST_DRAGERS:
            continue
        tekstdelen = el.findall(f"{S}Tekstdeel")
        divisie_id = el.get("owId")
        if not tekstdelen and not divisie_id:
            continue
        if not divisie_id:
            divisie_id = idgen.volgende(naam.lower())
        obj = _el(IMOW_VRIJETEKST, naam, wId=el.get("wId") or "")
        _el(IMOW_VRIJETEKST, "identificatie", obj, divisie_id)
        objecten.append(obj)
        typen.add(naam)
        for td in tekstdelen:
            typen.add("Tekstdeel")
            td_obj = _el(IMOW_VRIJETEKST, "Tekstdeel")
            _el(IMOW_VRIJETEKST, "identificatie", td_obj,
                td.get("owId") or idgen.volgende("tekstdeel"))
            if td.get("idealisatie"):
                _el(IMOW_VRIJETEKST, "idealisatie", td_obj,
                    IDEALISATIE_URI[td.get("idealisatie")])
            if td.get("thema"):
                _el(IMOW_VRIJETEKST, "thema", td_obj, td.get("thema"))
            aand = _el(IMOW_VRIJETEKST, "divisieaanduiding", td_obj)
            _ref(aand, IMOW_VRIJETEKST, f"{naam}Ref", divisie_id)
            if _gio_refs(td):
                _locatieaanduiding(td_obj, IMOW_VRIJETEKST, _gio_refs(td))
            for gar in td.findall(f"{S}GebiedsaanwijzingRef"):
                gaw = _el(IMOW_VRIJETEKST, "gebiedsaanwijzing", td_obj)
                _ref(gaw, IMOW_GA, "GebiedsaanwijzingRef", gar.get("ref"))
            for hl in td.findall(f"{S}HoofdlijnRef"):
                haand = _el(IMOW_VRIJETEKST, "hoofdlijnaanduiding", td_obj)
                _ref(haand, IMOW_VRIJETEKST, "HoofdlijnRef", hl.get("ref"))
            objecten.append(td_obj)
    return objecten, typen


def bouw_activiteiten(ow_objecten):
    objecten = []
    for act in ow_objecten.findall(f"{S}Activiteit"):
        obj = _el(IMOW_ROL, "Activiteit")
        _el(IMOW_ROL, "identificatie", obj, act.get("id"))
        _el(IMOW_ROL, "naam", obj, act.findtext(f"{S}naam"))
        if act.findtext(f"{S}groep"):
            _el(IMOW_ROL, "groep", obj, act.findtext(f"{S}groep"))
        boven = act.find(f"{S}bovenliggendeActiviteitRef")
        if boven is not None:
            houder = _el(IMOW_ROL, "bovenliggendeActiviteit", obj)
            _ref(houder, IMOW_ROL, "ActiviteitRef", boven.get("ref"))
        for rel in act.findall(f"{S}gerelateerdeActiviteitRef"):
            houder = _el(IMOW_ROL, "gerelateerdeActiviteit", obj)
            _ref(houder, IMOW_ROL, "ActiviteitRef", rel.get("ref"))
        objecten.append(obj)
    return objecten


def lees_pakket_gios(geo, basis_map, meldingen):
    """Parse de GML-bestanden van het pakket: work -> gio-info."""
    from .naar_storm import _lees_gio_versie
    from .storm_common import BASISGEO
    gios = {}
    if geo is None:
        return gios
    for gio_el in geo.findall(f"{S}Gio"):
        pad = basis_map / (gio_el.get("bestand") or "")
        info = {"work": gio_el.get("work"), "norm": None, "waarden": {},
                "basisgeo_ids": frozenset()}
        if pad.is_file():
            try:
                wortel = ET.parse(pad).getroot()
                if lokale_naam(wortel.tag) == "GeoInformatieObjectVaststelling":
                    info = _lees_gio_versie(wortel, pad)
                else:
                    info["basisgeo_ids"] = frozenset(
                        e.text.strip() for e in wortel.iter(f"{{{BASISGEO}}}id"))
            except ET.ParseError:
                waarschuw(meldingen, f"GML '{pad.name}' niet leesbaar")
        else:
            waarschuw(meldingen, f"GML-bestand ontbreekt: {gio_el.get('bestand')}")
        gios[gio_el.get("work")] = info
    return gios


def bouw_normen(exportregels, pakket_gios, basisgeo_van_loc, idgen, meldingen):
    """Omgevingsnorm/-waarde afleiden uit de GIO-GML + exportregels (v0.2)."""
    objecten, typen = [], set()
    if exportregels is None:
        return objecten, typen
    for norm in exportregels.findall(f"{S}ImowNorm"):
        imow_naam = ("Omgevingswaarde" if norm.get("soort") == "omgevingswaarde"
                     else "Omgevingsnorm")
        typen.add(imow_naam)
        gio = pakket_gios.get(norm.get("gioWork")) if norm.get("gioWork") else None
        gio_norm = (gio or {}).get("norm") or {}
        obj = _el(IMOW_ROL, imow_naam)
        _el(IMOW_ROL, "identificatie", obj, norm.get("owId"))
        _el(IMOW_ROL, "naam", obj, norm.get("naam") or gio_norm.get("naam"))
        if norm.get("type") or gio_norm.get("type"):
            _el(IMOW_ROL, "type", obj, norm.get("type") or gio_norm.get("type"))
        if norm.get("eenheid") or gio_norm.get("eenheid"):
            _el(IMOW_ROL, "eenheid", obj,
                norm.get("eenheid") or gio_norm.get("eenheid"))
        waarden = norm.findall(f"{S}Normwaarde")
        houder = _el(IMOW_ROL, "normwaarde", obj) if waarden else None
        for w in waarden:
            nw = _el(IMOW_ROL, "Normwaarde", houder)
            _el(IMOW_ROL, "identificatie", nw,
                w.get("owId") or idgen.volgende("normwaarde"))
            refs = [r.get("ref") for r in w.findall(f"{S}LocatieRef")]
            geschreven = False
            for veld in ("kwantitatieveWaarde", "kwalitatieveWaarde",
                         "waardeInRegeltekst"):
                if w.get(veld) is not None:
                    _el(IMOW_ROL, veld, nw, w.get(veld))
                    geschreven = True
            if not geschreven and gio:
                # waarde uit de GML halen via de eerste locatie
                bids = basisgeo_van_loc.get(refs[0]) if refs else None
                waarde = None
                for bid in bids or []:
                    soort_w, waarde = gio["waarden"].get(bid, (None, None))
                    if waarde is not None:
                        _el(IMOW_ROL, "kwantitatieveWaarde", nw, waarde)
                        break
                if waarde is None:
                    waarschuw(meldingen, f"normwaarde {w.get('owId')}: geen "
                                         f"waarde in GML gevonden")
            _locatieaanduiding(nw, IMOW_ROL, refs)
        if norm.get("groep"):
            _el(IMOW_ROL, "groep", obj, norm.get("groep"))
        objecten.append(obj)
    return objecten, typen


def bouw_geo(geo, exportregels, idgen, meldingen):
    """Locaties + gebiedsaanwijzingen terug uit exportregels en Gio's."""
    locaties, aanwijzingen = [], []
    basisgeo_van_loc = {}

    if exportregels is not None:
        imow_locs = exportregels.findall(f"{S}ImowLocatie")
        groep_ids = {l.get("owId") for l in imow_locs
                     if l.get("soort") == "Gebiedengroep"}
        for loc in imow_locs:
            owid = loc.get("owId")
            if loc.get("soort") == "Gebiedengroep":
                obj = _el(IMOW_LOCATIE, "Gebiedengroep")
                _el(IMOW_LOCATIE, "identificatie", obj, owid)
                if loc.get("noemer"):
                    _el(IMOW_LOCATIE, "noemer", obj, loc.get("noemer"))
                for lid in loc.findall(f"{S}LidRef"):
                    houder = _el(IMOW_LOCATIE, "groepselement", obj)
                    naam = ("GebiedengroepRef" if lid.get("ref") in groep_ids
                            else "GebiedRef")
                    _ref(houder, IMOW_LOCATIE, naam, lid.get("ref"))
            else:
                obj = _el(IMOW_LOCATIE, "Gebied")
                _el(IMOW_LOCATIE, "identificatie", obj, owid)
                if loc.get("noemer"):
                    _el(IMOW_LOCATIE, "noemer", obj, loc.get("noemer"))
                geom = _el(IMOW_LOCATIE, "geometrie", obj)
                _ref(geom, IMOW_LOCATIE, "GeometrieRef", loc.get("basisgeoId"))
                if loc.get("basisgeoId"):
                    basisgeo_van_loc[owid] = frozenset([loc.get("basisgeoId")])
            locaties.append(obj)

        def _groep_basisgeo(owid, bezocht=frozenset()):
            if owid in basisgeo_van_loc or owid in bezocht:
                return basisgeo_van_loc.get(owid, frozenset())
            for loc in imow_locs:
                if loc.get("owId") == owid:
                    s = set()
                    for lid in loc.findall(f"{S}LidRef"):
                        s |= _groep_basisgeo(lid.get("ref"), bezocht | {owid})
                    basisgeo_van_loc[owid] = frozenset(s)
                    return basisgeo_van_loc[owid]
            return frozenset()

        for loc in imow_locs:
            _groep_basisgeo(loc.get("owId"))

        for ga_el in exportregels.findall(f"{S}ImowGebiedsaanwijzing"):
            aanwijzingen.append(_bouw_aanwijzing(
                ga_el, [r.get("ref") for r in ga_el.findall(f"{S}LocatieRef")],
                idgen))

    if geo is not None:
        for gio_el in geo.findall(f"{S}Gio"):
            ga_el = gio_el.find(f"{S}Gebiedsaanwijzing")
            if ga_el is not None:
                aanwijzingen.append(_bouw_aanwijzing(
                    ga_el, [ga_el.get("locatieRef")], idgen))
        for ag in geo.findall(f"{S}Ambtsgebied"):
            obj = _el(IMOW_LOCATIE, "Ambtsgebied")
            _el(IMOW_LOCATIE, "identificatie", obj, ag.get("id"))
            if ag.findtext(f"{S}noemer"):
                _el(IMOW_LOCATIE, "noemer", obj, ag.findtext(f"{S}noemer"))
            grens = ag.find(f"{S}BestuurlijkeGrenzen")
            houder = _el(IMOW_LOCATIE, "bestuurlijkeGrenzenVerwijzing", obj)
            bgv = _el(IMOW_LOCATIE, "BestuurlijkeGrenzenVerwijzing", houder)
            _el(IMOW_LOCATIE, "bestuurlijkeGrenzenID", bgv, grens.get("id"))
            _el(IMOW_LOCATIE, "domein", bgv, grens.get("domein"))
            if grens.get("geldigOp"):
                _el(IMOW_LOCATIE, "geldigOp", bgv, grens.get("geldigOp"))
            locaties.append(obj)
    return locaties, aanwijzingen, basisgeo_van_loc


def _bouw_aanwijzing(ga_el, locatie_refs, idgen):
    ga = _el(IMOW_GA, "Gebiedsaanwijzing")
    _el(IMOW_GA, "identificatie", ga,
        ga_el.get("owId") or idgen.volgende("gebiedsaanwijzing"))
    _el(IMOW_GA, "type", ga, ga_el.findtext(f"{S}type"))
    _el(IMOW_GA, "naam", ga, ga_el.findtext(f"{S}naam"))
    _el(IMOW_GA, "groep", ga, ga_el.findtext(f"{S}groep"))
    _locatieaanduiding(ga, IMOW_GA, [r for r in locatie_refs if r])
    return ga


def bouw_simpele_objecten(ow_objecten, storm_naam, ns, imow_naam):
    objecten = []
    for el in ow_objecten.findall(f"{S}{storm_naam}"):
        obj = _el(ns, imow_naam)
        _el(ns, "identificatie", obj, el.get("id"))
        _locatieaanduiding(obj, ns, _gio_refs(el))
        objecten.append(obj)
    return objecten


def bouw_hoofdlijnen(ow_objecten):
    objecten = []
    for hl in ow_objecten.findall(f"{S}Hoofdlijn"):
        obj = _el(IMOW_VRIJETEKST, "Hoofdlijn")
        _el(IMOW_VRIJETEKST, "identificatie", obj, hl.get("id"))
        _el(IMOW_VRIJETEKST, "soort", obj, hl.findtext(f"{S}soort"))
        _el(IMOW_VRIJETEKST, "naam", obj, hl.findtext(f"{S}naam"))
        objecten.append(obj)
    return objecten


def schrijf_deelbestand(pad, dataset, objecttypen, objecten):
    wortel = _el(IMOW_DEELBESTAND, "owBestand")
    stand = _el(IMOW_STANDLEVERING, "standBestand", wortel)
    _el(IMOW_STANDLEVERING, "dataset", stand, dataset)
    inhoud = _el(IMOW_STANDLEVERING, "inhoud", stand)
    _el(IMOW_STANDLEVERING, "gebied", inhoud, dataset)
    _el(IMOW_STANDLEVERING, "leveringsId", inhoud, "storm-export")
    typen = _el(IMOW_STANDLEVERING, "objectTypen", inhoud)
    for t in sorted(objecttypen):
        _el(IMOW_STANDLEVERING, "objectType", typen, t)
    for obj in objecten:
        s = _el(IMOW_STANDLEVERING, "stand", stand)
        houder = _el(IMOW_DEELBESTAND, "owObject", s)
        houder.append(obj)
    schrijf_xml(wortel, pad)


# ---------------------------------------------------------------------------
# Hoofdprogramma
# ---------------------------------------------------------------------------

def converteer(storm_pad: Path, doelmap: Path) -> list[str]:
    meldingen: list[str] = []
    regeling = ET.parse(storm_pad).getroot()
    tekst = regeling.find(f"{S}Tekst")
    ow_objecten = regeling.find(f"{S}OwObjecten")
    geo = regeling.find(f"{S}Geo")
    exportregels = regeling.find(f"{S}Exportregels")
    bevoegd_gezag = regeling.findtext(f"{S}Identificatie/{S}bevoegdGezag")
    dataset = bevoegd_gezag or "storm"
    idgen = IdGenerator(bevoegd_gezag)
    pakket_gios = lees_pakket_gios(geo, storm_pad.parent, meldingen)
    ctx = maak_destillatie_context(tekst, exportregels, geo)

    # 1. STOP-tekst
    stop_map = doelmap / "stop"
    stop_map.mkdir(parents=True, exist_ok=True)
    wortelnaam = ("RegelingVrijetekst"
                  if tekst.get("structuur") == "vrijetekst"
                  else "RegelingCompact")
    wortel_attrs = {k: v for k, v in tekst.attrib.items() if k != "structuur"}
    compact = ET.Element(f"{{{STOP_TEKST}}}{wortelnaam}", wortel_attrs)
    for kind in tekst:
        if isinstance(kind.tag, str):
            compact.append(strip_annotaties(kind, STOP_TEKST))
    schrijf_xml(compact, stop_map / "regeling.xml", default_ns=STOP_TEKST)
    print(f"Geschreven: {stop_map / 'regeling.xml'}")

    # 2. IMOW-deelbestanden
    ow_map = doelmap / "ow"
    ow_map.mkdir(parents=True, exist_ok=True)
    norm_soorten = {}
    if exportregels is not None:
        norm_soorten = {n.get("owId"): n.get("soort")
                        for n in exportregels.findall(f"{S}ImowNorm")}

    bestanden = []
    regels = bouw_regels(tekst, norm_soorten, ctx, idgen, meldingen)
    if regels:
        typen = {lokale_naam(o.tag) for o in regels}
        bestanden.append(("owRegelteksten.xml", typen, regels))
    vrijetekst, vt_typen = bouw_vrijetekst(tekst, idgen, meldingen)
    if vrijetekst:
        bestanden.append(("owDivisie.xml", vt_typen, vrijetekst))
    if ow_objecten is not None:
        acts = bouw_activiteiten(ow_objecten)
        if acts:
            bestanden.append(("owActiviteiten.xml", {"Activiteit"}, acts))
        hoofdlijnen = bouw_hoofdlijnen(ow_objecten)
        if hoofdlijnen:
            bestanden.append(("owHoofdlijnen.xml", {"Hoofdlijn"}, hoofdlijnen))
        ponsen = bouw_simpele_objecten(ow_objecten, "Pons", IMOW_PONS, "Pons")
        if ponsen:
            bestanden.append(("owPons.xml", {"Pons"}, ponsen))
        rgs = bouw_simpele_objecten(ow_objecten, "Regelingsgebied",
                                    IMOW_REGELINGSGEBIED, "Regelingsgebied")
        if rgs:
            bestanden.append(("owRegelingsgebied.xml", {"Regelingsgebied"}, rgs))
    locaties, aanwijzingen, basisgeo_van_loc = bouw_geo(geo, exportregels,
                                                        idgen, meldingen)
    if locaties:
        typen = {lokale_naam(o.tag) for o in locaties}
        bestanden.append(("owLocaties.xml", typen, locaties))
    if aanwijzingen:
        bestanden.append(("owGebiedsaanwijzingen.xml", {"Gebiedsaanwijzing"},
                          aanwijzingen))
    normen, norm_typen = bouw_normen(exportregels, pakket_gios,
                                     basisgeo_van_loc, idgen, meldingen)
    if normen:
        bestanden.append(("owNormen.xml", norm_typen, normen))

    for naam, typen, objecten in bestanden:
        schrijf_deelbestand(ow_map / naam, dataset, typen, objecten)
        print(f"Geschreven: {ow_map / naam}  ({len(objecten)} objecten)")

    # 3. STTR-bestanden: de ingebedde DMN-beslislogica verbatim terug
    toepasbaar = regeling.find(f"{S}ToepasbareRegels")
    if toepasbaar is not None:
        imtr_map = doelmap / "imtr"
        imtr_map.mkdir(parents=True, exist_ok=True)
        for i, ta in enumerate(toepasbaar.findall(f"{S}ToepasbareActiviteit"), 1):
            logica = ta.find(f"{S}Beslislogica")
            dmn = next((k for k in logica if isinstance(k.tag, str)), None) \
                if logica is not None else None
            if dmn is None:
                waarschuw(meldingen, f"ToepasbareActiviteit {ta.get('naam')}: "
                                     f"geen Beslislogica-inhoud")
                continue
            veilig = re.sub(r"[^A-Za-z0-9_-]+", "_",
                            ta.get("naam") or f"toepasbaar_{i}").strip("_")
            pad = imtr_map / f"{veilig}.dmn"
            # verbatim: geen inspringing toevoegen aan de DMN-inhoud
            schrijf_xml(dmn, pad, inspringen=False)
            print(f"Geschreven: {pad}")

    if meldingen:
        print(f"\n{len(meldingen)} waarschuwing(en)")
    return meldingen


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    converteer(Path(sys.argv[1]), Path(sys.argv[2]))
