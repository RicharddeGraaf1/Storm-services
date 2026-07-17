"""Alle voorbeeldpakketten uit de standaard-repo valideren tegen het schema
en dragen de online xsi:schemaLocation (Oxygen-valideerbaar)."""

import xml.etree.ElementTree as ET

import pytest

from storm.paden import voorbeelden_map
from storm.rondreis import valideer
from storm.storm_common import STORM, STORM_XSD_URL, XSI

try:
    VOORBEELDEN = sorted(voorbeelden_map().glob("*/storm.xml"))
except FileNotFoundError:
    VOORBEELDEN = []


@pytest.mark.parametrize("pad", VOORBEELDEN, ids=lambda p: p.parent.name)
def test_voorbeeld_valideert(pad):
    assert valideer(pad) == []


@pytest.mark.parametrize("pad", VOORBEELDEN, ids=lambda p: p.parent.name)
def test_voorbeeld_heeft_online_schemalocation(pad):
    regeling = ET.parse(pad).getroot()
    locatie = regeling.get(f"{{{XSI}}}schemaLocation")
    assert locatie == f"{STORM} {STORM_XSD_URL}"


def test_er_zijn_voorbeelden():
    if not VOORBEELDEN:
        pytest.skip("standaard-repo niet gevonden (submodule/sibling)")
    assert len(VOORBEELDEN) >= 2  # mini + Gemeentestad
