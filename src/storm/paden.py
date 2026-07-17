"""Vind de STORM-standaard (XSD + voorbeelden).

De standaard leeft in een aparte repo (github.com/RicharddeGraaf1/Storm).
Deze services-repo heeft het schema nodig om te valideren en de
voorbeeldpakketten om op te toetsen. Zoekvolgorde:

  1. ``$STORM_STANDAARD``       expliciet pad — de standaard-map zelf óf een
                                Storm-repo-root die er een bevat.
  2. sibling ``../Storm``       jouw lokale working copy; edits aan de
                                standaard werken zo meteen door.
  3. submodule ``standaard-ref``  gepinde versie (reproduceerbaar op CI en
                                verse clones, waar geen sibling staat).

Sibling gaat bewust vóór de submodule: tijdens co-ontwikkeling wil je dat
wijzigingen aan de standaard direct doorwerken in de tests. Op een machine
zonder sibling wint de gepinde submodule. ``$STORM_STANDAARD`` overschrijft
altijd.
"""
from __future__ import annotations

import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]  # src/storm -> services-repo-root


def _normaliseer(basis: Path) -> Path | None:
    """Geef de standaard-map (die xsd/storm.xsd bevat), of None."""
    for kandidaat in (basis, basis / "standaard"):
        if (kandidaat / "xsd" / "storm.xsd").exists():
            return kandidaat
    return None


def vind_standaard() -> Path:
    kandidaten: list[Path] = []
    env = os.environ.get("STORM_STANDAARD")
    if env:
        kandidaten.append(Path(env))
    kandidaten.append(_REPO.parent / "Storm")     # sibling working copy
    kandidaten.append(_REPO / "standaard-ref")    # git-submodule
    for basis in kandidaten:
        gevonden = _normaliseer(basis)
        if gevonden:
            return gevonden
    raise FileNotFoundError(
        "STORM-standaard niet gevonden. Opties: zet $STORM_STANDAARD, check "
        "de Storm-repo als sibling (../Storm) uit, of init de submodule met "
        "`git submodule update --init`.")


_cache: Path | None = None


def standaard() -> Path:
    """De standaard-map, éénmalig geresolved en gecachet."""
    global _cache
    if _cache is None:
        _cache = vind_standaard()
    return _cache


def xsd_pad() -> Path:
    return standaard() / "xsd" / "storm.xsd"


def voorbeelden_map() -> Path:
    return standaard() / "voorbeelden"
