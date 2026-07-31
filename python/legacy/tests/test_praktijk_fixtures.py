"""Praktijk-fixtures: echte inhoud-fragmenten uit DSO-regelingen (via de
OCD-dev-DB, 2026-07-17) die de v0.3-toevoegingen dekken — CALS-tabellen
(thead/title/morerows/namest/Bron), de Noot-familie, geneste opmaak,
Figuur met alt/Titel, Definitie met Lijst en vreemde-ns-attributen.

Elk fragment wordt naar de STORM-namespace hernoemd en tegen storm.xsd
gevalideerd; zo blijft de praktijk-dekking testbaar zonder databank.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from lxml import etree

from storm.storm_common import STORM, hernoem_boom
from storm.paden import xsd_pad

FIXTURES = sorted((Path(__file__).parent / "fixtures" / "praktijk").glob("*.xml"))


@pytest.fixture(scope="module")
def schema():
    return etree.XMLSchema(etree.parse(str(xsd_pad())))


@pytest.mark.parametrize("pad", FIXTURES, ids=lambda p: p.stem)
def test_fragment_valideert(pad, schema):
    wortel = ET.fromstring(pad.read_text(encoding="utf-8"))
    storm_el = hernoem_boom(wortel, STORM)
    doc = etree.fromstring(ET.tostring(storm_el, encoding="unicode"))
    assert schema.validate(doc), \
        f"{pad.name}: {[str(f.message) for f in schema.error_log[:3]]}"
