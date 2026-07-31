"""Het mini-voorbeeldpakket: XSD-geldig en exporteerbaar zonder waarschuwingen."""

from storm import van_storm
from storm.rondreis import valideer

from corpora import MINI


def test_mini_valideert_tegen_xsd():
    assert valideer(MINI / "storm.xml") == []


def test_mini_exporteert_naar_imow(tmp_path):
    meldingen = van_storm.converteer(MINI / "storm.xml", tmp_path)
    assert meldingen == []

    from storm.canoniek import verzamel_ow_feiten
    feiten = verzamel_ow_feiten(tmp_path / "ow")
    per_type = {}
    for (naam, *_rest), n in feiten.items():
        per_type[naam] = per_type.get(naam, 0) + n
    assert per_type == {
        "Regeltekst": 1,
        "RegelVoorIedereen": 1,
        "Activiteit": 1,
        "Gebied": 1,
        "Gebiedengroep": 1,
        "Ambtsgebied": 1,
        "Gebiedsaanwijzing": 1,
    }
