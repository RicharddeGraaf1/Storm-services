"""Rondreis: bron -> STORM -> terug, met XSD-validatie en vergelijking.

Bewijst per corpus dat de conversie verliesvrij is:
  1. naar_storm:  bronmap [+ imtr-map] -> <doelmap>/storm.xml (+ gio/)
  2. XSD-validatie tegen het schema uit de standaard-repo (zie paden.py)
  3. van_storm:   storm.xml -> <doelmap>/terug/
  4. Vergelijking: STOP-tekst (semantisch), IMOW-objectfeiten (multiset),
     STTR-DMN's (verbatim, per namespace+naam).
"""

from __future__ import annotations

from pathlib import Path

from . import naar_storm, van_storm
from .canoniek import (canon_tekst, eerste_verschil, laad_dmns,
                       verzamel_ow_feiten, vind_regelingtekst)
from .paden import xsd_pad


def valideer(storm_pad: Path) -> list[str]:
    """XSD-validatie; lege lijst = geldig."""
    from lxml import etree
    schema = etree.XMLSchema(etree.parse(str(xsd_pad())))
    doc = etree.parse(str(storm_pad))
    if schema.validate(doc):
        return []
    return [f"regel {f.line}: {f.message}" for f in schema.error_log]


def rondreis(bronmap: Path, doelmap: Path,
             imtr_map: Path | None = None) -> list[str]:
    """Volledige rondreis; lijst met FAIL-omschrijvingen (leeg = PASS)."""
    fouten: list[str] = []
    storm_pad = doelmap / "storm.xml"
    terug_map = doelmap / "terug"

    naar_storm.converteer(bronmap, storm_pad, imtr_map)

    schema_fouten = valideer(storm_pad)
    if schema_fouten:
        fouten.append("XSD: " + "; ".join(schema_fouten[:5]))

    van_storm.converteer(storm_pad, terug_map)

    origineel = canon_tekst(vind_regelingtekst(bronmap))
    terug = canon_tekst(vind_regelingtekst(terug_map / "stop"))
    verschil = eerste_verschil(origineel, terug, "Regeling")
    if verschil:
        fouten.append(f"STOP-tekst: {verschil}")

    orig_feiten = verzamel_ow_feiten(bronmap)
    terug_feiten = verzamel_ow_feiten(terug_map / "ow")
    if orig_feiten != terug_feiten:
        alleen_orig = orig_feiten - terug_feiten
        alleen_terug = terug_feiten - orig_feiten
        fouten.append(f"IMOW: {sum(alleen_orig.values())} alleen origineel, "
                      f"{sum(alleen_terug.values())} alleen terug; eerste: "
                      f"{str(next(iter(alleen_orig or alleen_terug)))[:200]}")

    if imtr_map:
        orig_dmns = laad_dmns(imtr_map)
        terug_dmns = laad_dmns(terug_map / "imtr")
        for sleutel, (naam, canon) in orig_dmns.items():
            if sleutel not in terug_dmns:
                fouten.append(f"IMTR: geen geregenereerde DMN voor {naam}")
                continue
            verschil = eerste_verschil(canon, terug_dmns[sleutel][1],
                                       "definitions")
            if verschil:
                fouten.append(f"IMTR {naam}: {verschil}")

    return fouten
