"""imtr-zip-rondreis: KV-TR-ZIPs -> STORM -> KV-TR-ZIPs.

Op de Gemeentestad-toepasbareRegels-ZIPs: de DMN's komen verbatim terug,
de geldigBegindatum uit de opdracht reist mee, en de gegenereerde ZIPs
bevatten manifest + opdracht + DMN.
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from storm import naar_storm
from storm.adapters.imtr import storm2imtr
from storm.canoniek import canon_tekst
from storm.storm_common import STORM

import corpora

S = f"{{{STORM}}}"
ZIPS = Path(r"C:\Testbestanden\GITHub\Gemeentestad\toepasbareRegels")


@pytest.fixture(scope="module")
def rondreis(tmp_path_factory):
    bron = corpora.CORPORA["gemeentestad_opdracht"]
    if not bron.is_dir() or not ZIPS.is_dir():
        pytest.skip("Gemeentestad-corpus niet aanwezig")
    tmp = tmp_path_factory.mktemp("imtr")
    naar_storm.converteer(bron, tmp / "storm.xml", ZIPS)
    storm2imtr(tmp / "storm.xml", tmp / "zips")
    return {"storm": tmp / "storm.xml", "zips": tmp / "zips"}


def _dmns_uit_zips(map_: Path) -> dict:
    dmns = {}
    for zip_pad in sorted(map_.glob("*.zip")):
        with zipfile.ZipFile(zip_pad) as zf:
            for lid in zf.namelist():
                if lid.lower().endswith(".dmn"):
                    wortel = ET.fromstring(zf.read(lid))
                    dmns[(wortel.get("namespace"), wortel.get("name"))] = \
                        canon_tekst(wortel)
    return dmns


def test_drie_regelbestanden_gelezen(rondreis):
    regeling = ET.parse(rondreis["storm"]).getroot()
    tas = regeling.findall(f".//{S}ToepasbareActiviteit")
    assert len(tas) == 3
    assert all(ta.get("geldigBegindatum") for ta in tas)


def test_dmn_verbatim_rondreis(rondreis):
    orig = _dmns_uit_zips(ZIPS)
    terug = _dmns_uit_zips(rondreis["zips"])
    assert orig == terug
    assert len(orig) == 3


def test_zip_bevat_manifest_en_opdracht(rondreis):
    zips = sorted(rondreis["zips"].glob("*.zip"))
    assert len(zips) == 3
    for zip_pad in zips:
        with zipfile.ZipFile(zip_pad) as zf:
            namen = set(zf.namelist())
            assert "manifest.xml" in namen
            assert "opdrachtAanleverenToepasbareRegels.xml" in namen
            opdracht = ET.fromstring(
                zf.read("opdrachtAanleverenToepasbareRegels.xml"))
            datums = [e.text for e in opdracht.iter()
                      if e.tag.endswith("geldigBegindatum")]
            assert datums and datums[0]
