"""Verliesvrije rondreis op de externe corpora (skipt wat ontbreekt)."""

import pytest

from storm.rondreis import rondreis

from corpora import CORPORA

GEVALLEN = [
    ("gemeentestad_opdracht", None),          # vol v0.2-pad (GIO's met norm)
    ("gemeentestad_opdracht", "imtr_sttr3"),  # + officiële STTR 3.0.0-set
    ("consolidatie", "imtr_dordrecht"),       # fallback-pad + Dordrecht v1.0
    ("leiden", None),                         # vrijetekststructuur
]


@pytest.mark.parametrize("bron_naam,imtr_naam", GEVALLEN)
def test_rondreis(bron_naam, imtr_naam, tmp_path):
    bron = CORPORA[bron_naam]
    if not bron.is_dir():
        pytest.skip(f"corpus {bron_naam} niet aanwezig: {bron}")
    imtr = CORPORA[imtr_naam] if imtr_naam else None
    if imtr and not imtr.is_dir():
        pytest.skip(f"imtr-corpus {imtr_naam} niet aanwezig: {imtr}")
    fouten = rondreis(bron, tmp_path, imtr)
    assert fouten == []
