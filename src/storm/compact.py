"""Conversie complete → compact: degradeer elementen onder de 10%-knip.

Invariant: **tekstbehoud** — de genormaliseerde tekstinhoud van het
document is vóór en ná de conversie gelijk. Structuur- en
presentatie-informatie van de gedegradeerde elementen gaat (bewust)
verloren; dat is de aard van het compact-profiel.

Degradatieregels (empirisch onderbouwd, staart-inventaris 2026-07-17):

| element | regel |
|---|---|
| Titel (structuur)     | hernoem naar Hoofdstuk (recursieve structuur vangt het niveau) |
| Subsubparagraaf       | hernoem naar Subparagraaf |
| Tussenkop             | Al met b eromheen |
| Kadertekst / Groep / InleidendeTekst | unwrap naar hun kinderen; Kop erin → Al met b |
| Aanhef / Sluiting (+ kinderen) | unwrap naar Al's |
| Lijstaanhef / Lijstsluiting | Al vóór resp. ná de Lijst |
| abbr / Contact        | inline unwrap (tekst blijft) |
| InlineTekstAfbeelding / Nootref | verwijderen (dragen geen tekst) |
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .profielen import controleer_compact
from .storm_common import STORM, lokale_naam

S = f"{{{STORM}}}"

HERNOEM = {"Titel": "Hoofdstuk", "Subsubparagraaf": "Subparagraaf"}
UNWRAP_BLOK = {"Kadertekst", "Groep", "InleidendeTekst", "Aanhef", "Sluiting",
               "Considerans", "Afkondiging", "Ondertekening",
               "Slotformulering", "Dagtekening"}
UNWRAP_INLINE = {"abbr", "Contact"}
VERWIJDER_INLINE = {"InlineTekstAfbeelding", "Nootref"}


def _al_met_b(bron: ET.Element) -> ET.Element:
    """Maak van een kop-achtig mixed element een <Al><b>…</b></Al>."""
    al = ET.Element(f"{S}Al")
    b = ET.SubElement(al, f"{S}b")
    b.text = bron.text
    for kind in bron:
        b.append(kind)
    return al


def _unwrap_inline(ouder: ET.Element, idx: int) -> None:
    """Vervang kind idx door zijn eigen tekst + kinderen (mixed content)."""
    kind = ouder[idx]
    vorige = ouder[idx - 1] if idx > 0 else None
    subkinderen = list(kind)
    tekst, staart = kind.text or "", kind.tail or ""
    ouder.remove(kind)
    if vorige is None:
        ouder.text = (ouder.text or "") + tekst
    else:
        vorige.tail = (vorige.tail or "") + tekst
    for i, sub in enumerate(subkinderen):
        ouder.insert(idx + i, sub)
    laatste = ouder[idx + len(subkinderen) - 1] if subkinderen else vorige
    if laatste is None:
        ouder.text = (ouder.text or "") + staart
    else:
        laatste.tail = (laatste.tail or "") + staart


def _verwijder_inline(ouder: ET.Element, idx: int) -> None:
    kind = ouder[idx]
    staart = kind.tail or ""
    vorige = ouder[idx - 1] if idx > 0 else None
    ouder.remove(kind)
    if vorige is None:
        ouder.text = (ouder.text or "") + staart
    else:
        vorige.tail = (vorige.tail or "") + staart


def _degradeer_kinderen(el: ET.Element, meldingen: list[str]) -> None:
    """Bottom-up: eerst de kinderen, dan de directe kinderen van dit el."""
    for kind in list(el):
        _degradeer_kinderen(kind, meldingen)

    idx = 0
    while idx < len(el):
        kind = el[idx]
        naam = lokale_naam(kind.tag)

        if naam in HERNOEM and lokale_naam(el.tag) != "Figuur":
            kind.tag = f"{S}{HERNOEM[naam]}"
            meldingen.append(f"{naam} → {HERNOEM[naam]}")
            idx += 1
        elif naam == "Tussenkop":
            nieuw = _al_met_b(kind)
            nieuw.tail = kind.tail
            el.remove(kind)
            el.insert(idx, nieuw)
            meldingen.append("Tussenkop → Al/b")
            idx += 1
        elif naam == "Kop" and lokale_naam(el.tag) in ("Kadertekst",
                                                       "InleidendeTekst"):
            opschrift = kind.find(f"{S}Opschrift")
            nieuw = _al_met_b(opschrift if opschrift is not None else kind)
            nieuw.tail = kind.tail
            el.remove(kind)
            el.insert(idx, nieuw)
            meldingen.append("Kop (kader) → Al/b")
            idx += 1
        elif naam == "Lijstaanhef":
            kind.tag = f"{S}Al"
            el.remove(kind)
            # vóór de Lijst zelf plaatsen (el is de Lijst): kan niet als
            # sibling binnen deze functie — markeer voor de ouder-pass
            kind.set("__voor_lijst__", "1")
            el.insert(idx, kind)
            idx += 1
        elif naam == "Lijstsluiting":
            kind.tag = f"{S}Al"
            kind.set("__na_lijst__", "1")
            idx += 1
        elif naam in UNWRAP_BLOK:
            subkinderen = list(kind)
            staart = kind.tail
            el.remove(kind)
            for i, sub in enumerate(subkinderen):
                el.insert(idx + i, sub)
            if subkinderen and staart:
                subkinderen[-1].tail = (subkinderen[-1].tail or "") + staart
            meldingen.append(f"{naam} → inhoud")
        elif naam in UNWRAP_INLINE:
            _unwrap_inline(el, idx)
            meldingen.append(f"{naam} → tekst")
        elif naam in VERWIJDER_INLINE:
            _verwijder_inline(el, idx)
            meldingen.append(f"{naam} verwijderd")
        else:
            idx += 1

    # Lijstaanhef/-sluiting uit een kind-Lijst naar sibling-Al's tillen
    idx = 0
    while idx < len(el):
        kind = el[idx]
        if lokale_naam(kind.tag) == "Lijst":
            for al in list(kind):
                if al.get("__voor_lijst__"):
                    del al.attrib["__voor_lijst__"]
                    al.tail = None
                    kind.remove(al)
                    el.insert(idx, al)
                    meldingen.append("Lijstaanhef → Al vóór Lijst")
                    idx += 1
                elif al.get("__na_lijst__"):
                    del al.attrib["__na_lijst__"]
                    al.tail = kind.tail
                    kind.remove(al)
                    el.insert(idx + 1, al)
                    meldingen.append("Lijstsluiting → Al ná Lijst")
        idx += 1


def naar_compact(tekst_el: ET.Element) -> list[str]:
    """Degradeer een STORM-tekstboom in place naar profiel compact.

    Returns de degradatie-meldingen; gooit ValueError als het resultaat
    tóch nog compact-overtredingen bevat (bug-vangnet).
    """
    meldingen: list[str] = []
    _degradeer_kinderen(tekst_el, meldingen)
    rest = controleer_compact(tekst_el)
    if rest:
        raise ValueError(f"niet-gedegradeerde elementen: {rest[:5]}")
    return meldingen
