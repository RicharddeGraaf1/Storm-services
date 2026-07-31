"""Profielen op de STORM-standaard.

**complete** = het volledige tekst-vocabulaire van storm.xsd.
**compact** = het restrictieprofiel voor afnemers: alleen elementen met
≥10% spreiding over de vigerende regelingen (elementgebruik-analyse
2026-07-17, zie standaard/profiel-compact/elementgebruik.md). Elk
compact-document is per definitie een geldig STORM-document; de conversie
complete→compact zit in `storm.compact`.
"""

from __future__ import annotations

from .storm_common import lokale_naam

# Tekst-elementen toegestaan in profiel compact (≥10% spreiding).
COMPACT_TEKST_ELEMENTEN = frozenset({
    # structuur
    "RegelingOpschrift", "Lichaam", "Hoofdstuk", "Afdeling", "Paragraaf",
    "Subparagraaf", "Artikel", "Lid", "LidNummer", "Divisie", "Divisietekst",
    "Bijlage", "ArtikelgewijzeToelichting", "Kop", "Label", "Nummer",
    "Opschrift", "Inhoud", "Gereserveerd",
    # blok
    "Al", "Lijst", "Li", "LiNummer", "Begrippenlijst", "Begrip", "Term",
    "Definitie", "Figuur", "Illustratie", "Bijschrift", "Bron",
    # CALS-tabellen
    "table", "title", "tgroup", "colspec", "thead", "tbody", "row", "entry",
    # inline
    "IntRef", "ExtRef", "IntIoRef", "ExtIoRef", "IntOwRef", "ExtOwRef",
    "Nadruk", "i", "b", "u", "strong", "sup", "sub", "br",
    "Noot", "NootNummer",
})

# Alleen-complete: onder de 10%-knip; de conversie degradeert ze.
ALLEEN_COMPLETE = frozenset({
    "Titel", "Subsubparagraaf",                      # structuur (<2%)
    "Tussenkop", "Kadertekst", "Groep",              # blok (4–7%)
    "InleidendeTekst", "Lijstaanhef", "Lijstsluiting",
    "Aanhef", "Considerans", "Afkondiging",          # besluit-elementen
    "Sluiting", "Ondertekening", "Slotformulering", "Dagtekening",
    "Contact", "InlineTekstAfbeelding", "abbr", "Nootref",
})


def controleer_compact(tekst_el) -> list[str]:
    """Overtredingen van profiel compact in een STORM-tekstboom.

    Contextgevoelig detail: `Titel` is als figuur-titel (kind van Figuur)
    wél compact (19,8% spreiding), als structuurelement niet (1,4%).
    """
    overtredingen = []
    oudermap = {kind: el for el in tekst_el.iter() for kind in el}
    for el in tekst_el.iter():
        if not isinstance(el.tag, str):
            continue
        naam = lokale_naam(el.tag)
        if naam == "Titel":
            ouder = oudermap.get(el)
            if ouder is not None and lokale_naam(ouder.tag) == "Figuur":
                continue
        if naam in ALLEEN_COMPLETE:
            overtredingen.append(f"{naam} @ {el.get('wId') or el.get('eId') or '?'}")
    return overtredingen
