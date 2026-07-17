"""Conversie complete → compact: degradatie met tekstbehoud.

De staart-fixtures zijn echte inhoud-fragmenten met elementen onder de
10%-knip (Tussenkop, Kadertekst, Groep, Lijstaanhef/-sluiting, Aanhef/
Sluiting-familie, InlineTekstAfbeelding, abbr, InleidendeTekst). Per
fixture: degradeer, en controleer (a) compact-conform, (b) genormaliseerde
tekstinhoud ongewijzigd, (c) nog steeds XSD-geldig.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from lxml import etree

from storm.compact import naar_compact
from storm.profielen import controleer_compact
from storm.paden import xsd_pad
from storm.storm_common import STORM, hernoem_boom

from corpora import MINI

FIXTURES = sorted((Path(__file__).parent / "fixtures" / "staart").glob("*.xml"))


def normtekst(el):
    return " ".join("".join(el.itertext()).split())


@pytest.fixture(scope="module")
def schema():
    return etree.XMLSchema(etree.parse(str(xsd_pad())))


@pytest.mark.parametrize("pad", FIXTURES, ids=lambda p: p.stem)
def test_degradatie(pad, schema):
    wortel = hernoem_boom(
        ET.fromstring(pad.read_text(encoding="utf-8")), STORM)
    # fragmenten met een blok-element als root (InleidendeTekst, Aanhef,
    # Sluiting) in een Inhoud wikkelen: de conversie degradeert kinderen
    if not wortel.tag.endswith("}Inhoud"):
        houder = ET.Element(f"{{{STORM}}}Inhoud")
        houder.append(wortel)
        wortel = houder
    tekst_voor = normtekst(wortel)

    meldingen = naar_compact(wortel)
    assert meldingen, f"{pad.name}: fixture bevat geen staart-element meer?"
    assert controleer_compact(wortel) == []
    assert normtekst(wortel) == tekst_voor, f"{pad.name}: tekst veranderd"

    doc = etree.fromstring(ET.tostring(wortel, encoding="unicode"))
    assert schema.validate(doc), \
        f"{pad.name}: {[str(f.message) for f in schema.error_log[:3]]}"


def test_mini_is_al_compact():
    regeling = ET.parse(MINI / "storm.xml").getroot()
    tekst = regeling.find(f"{{{STORM}}}Tekst")
    assert controleer_compact(tekst) == []
    assert naar_compact(tekst) == []
