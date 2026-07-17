"""bhkv-rondreis: aanlevermap -> STORM -> LVBB-aanleverpakket.

Bewijst op de Gemeentestad-aanlevering dat storm2bhkv het besluit
envelop-verliesvrij reconstrueert (verbatim envelop + geregenereerde
regelingtekst), de opdracht verbatim teruggeeft, GML's byte-gelijk
meelevert, wrapper-hashes corrigeert en manifesten over de werkelijke
bestanden schrijft.
"""

import hashlib
import xml.etree.ElementTree as ET

import pytest

from storm import naar_storm
from storm.adapters.bhkv import storm2bhkv
from storm.canoniek import canon_tekst, verzamel_ow_feiten
from storm.storm_common import STORM, STORM_XSD_URL, XSI, lokale_naam

from corpora import CORPORA


@pytest.fixture(scope="module")
def pakket(tmp_path_factory):
    bron = CORPORA["gemeentestad_opdracht"]
    if not bron.is_dir():
        pytest.skip(f"corpus niet aanwezig: {bron}")
    tmp = tmp_path_factory.mktemp("bhkv")
    naar_storm.converteer(bron, tmp / "storm.xml")
    storm2bhkv(tmp / "storm.xml", tmp / "aanlevering")
    return {"bron": bron, "storm": tmp / "storm.xml",
            "uit": tmp / "aanlevering"}


def test_schemalocation_op_gegenereerd_document(pakket):
    regeling = ET.parse(pakket["storm"]).getroot()
    assert regeling.get(f"{{{XSI}}}schemaLocation") == \
        f"{STORM} {STORM_XSD_URL}"


def test_besluit_envelop_verliesvrij(pakket):
    orig = ET.parse(pakket["bron"] / "akn_nl_bill_gm0297-3520-01.xml").getroot()
    terug = ET.parse(pakket["uit"] / "akn_nl_bill_gm0297-3520-01.xml").getroot()
    assert canon_tekst(orig) == canon_tekst(terug)


def test_opdracht_verbatim(pakket):
    orig = ET.parse(pakket["bron"] / "opdracht.xml").getroot()
    terug = ET.parse(pakket["uit"] / "opdracht.xml").getroot()
    assert canon_tekst(orig) == canon_tekst(terug)


def test_gml_byte_gelijk(pakket):
    for naam in ("Bouwhoogte.gml", "Zuilichem.gml"):
        assert (pakket["bron"] / naam).read_bytes() == \
            (pakket["uit"] / naam).read_bytes()


def test_ow_feiten_gelijk(pakket):
    assert verzamel_ow_feiten(pakket["bron"]) == \
        verzamel_ow_feiten(pakket["uit"])


def test_wrapper_hashes_kloppen(pakket):
    """Elke hash in een uitgeleverde wrapper klopt met het payload-bestand
    (de bron-hashes van het oefenmateriaal waren deels onjuist)."""
    gecontroleerd = 0
    for pad in sorted(pakket["uit"].glob("*.xml")):
        try:
            wortel = ET.parse(pad).getroot()
        except ET.ParseError:
            continue
        if lokale_naam(wortel.tag) != "AanleveringInformatieObject":
            continue
        naam = hash_tekst = None
        for el in wortel.iter():
            if lokale_naam(el.tag) == "bestandsnaam":
                naam = el.text.strip()
            elif lokale_naam(el.tag) == "hash":
                hash_tekst = el.text.strip()
        payload = pakket["uit"] / naam
        if payload.is_file() and hash_tekst:
            assert hash_tekst == hashlib.sha512(
                payload.read_bytes()).hexdigest(), naam
            gecontroleerd += 1
    assert gecontroleerd >= 8


def test_manifest_dekt_bestanden(pakket):
    manifest = ET.parse(pakket["uit"] / "manifest.xml").getroot()
    genoemd = {el.text.strip() for el in manifest.iter()
               if lokale_naam(el.tag) == "bestandsnaam"}
    werkelijk = {p.name for p in pakket["uit"].iterdir()}
    assert genoemd == werkelijk


def test_manifest_ow_dekt_ow_bestanden(pakket):
    manifest = ET.parse(pakket["uit"] / "manifest-ow.xml").getroot()
    genoemd = {el.text.strip() for el in manifest.iter()
               if lokale_naam(el.tag) == "naam"}
    werkelijk = {p.name for p in pakket["uit"].glob("ow*.xml")}
    assert genoemd == werkelijk
    assert manifest.findtext(
        ".//{http://www.geostandaarden.nl/bestanden-ow/manifest-ow}"
        "WorkIDRegeling") == "/akn/nl/act/gm0297/2019/reg456"
