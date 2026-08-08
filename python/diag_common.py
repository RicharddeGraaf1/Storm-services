"""Gedeelde bouwstenen voor de diagnose-scripts rond de variant-transformaties.

De diag_*-scripts bouwen allemaal dezelfde keten op uit een downloadpakket:

    zip -> storm-volledig (V) -> compact (C) -> integrated (I) -> compact terug (Cx)

en vergelijken vervolgens C met Cx. Dit module bundelt dat, plus de twee
zoekhulpen die het verschil maken bij het lokaliseren van verlies.

LET OP bij het zelf schrijven van een diagnose: `root.iter()` levert
documentvolgorde, dus de EERSTE treffer op een tekstfragment is altijd de
buitenste container (Regeling) en zegt niets. Gebruik `diepste_element()`.
"""
import re, sys, zipfile, tempfile, shutil, difflib
from pathlib import Path
from lxml import etree

import download_roundtrip as dr, volledig_compact as vc
import compact_integrated as ci, integrated_compact as ic

CORPUS = Path(r"C:\GIT\OCD\dso-loader\data\downloads\ow")

# STOP-tekst bevat bullets/aanhalingstekens die op een cp1252-console klappen
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def L(t):
    """Localname van een (mogelijk namespaced) tag."""
    return t.split('}')[-1] if isinstance(t, str) and '}' in t else t


def kies_pakket(naam_of_index):
    """Pakket uit het corpus op index of op (deel van) de bestandsnaam."""
    alle = sorted(CORPUS.glob("*.zip"))
    s = str(naam_of_index)
    if s.isdigit():
        return alle[int(s)]
    return next(z for z in alle if s.lower() in z.name.lower())


def _pak_uit(z, work):
    pkg = work/"pkg"
    zipfile.ZipFile(z).extractall(pkg)
    if not any(pkg.glob("Regeling*")) and not any(pkg.glob("IO-*")):
        subs = [p for p in pkg.iterdir() if p.is_dir()]
        if len(subs) == 1:
            pkg = subs[0]
    return pkg


def bouw_varianten(z, work):
    """zip -> (C, I, Cx): compact, integrated, en compact-terug."""
    pkg = _pak_uit(z, work)
    vol = work/"vol"; vol.mkdir()
    R = dr.download2volledig(pkg)
    etree.ElementTree(R).write(str(vol/"storm-volledig.xml"),
                               xml_declaration=True, encoding="UTF-8", pretty_print=True)
    for G in dr.download2gio(pkg):
        frbr = next((e.text for e in G.iter() if L(e.tag) == 'FRBRWork'), None)
        stam = frbr.rstrip('/').split('/')[-1].split('@')[0] if frbr else G.get('map', 'gio')
        nm = re.sub(r'[^\w.-]', '_', stam or 'gio')
        etree.ElementTree(G).write(str(vol/f"{nm}.storm-gio.xml"),
                                   xml_declaration=True, encoding="UTF-8")
    C = vc.transform(vol)
    cpad = work/"c.xml"
    etree.ElementTree(C).write(str(cpad), xml_declaration=True, encoding="UTF-8", pretty_print=True)
    I = ci.transform(cpad)
    ipad = work/"i.xml"
    etree.ElementTree(I).write(str(ipad), xml_declaration=True, encoding="UTF-8", pretty_print=True)
    Cx = ic.transform(ipad)
    return C, I, Cx


def met_varianten(naam_of_index, fn):
    """Bouw de varianten in een tempdir en geef ze door aan fn(z, C, I, Cx)."""
    z = kies_pakket(naam_of_index)
    work = Path(tempfile.mkdtemp(prefix="diag_"))
    try:
        C, I, Cx = bouw_varianten(z, work)
        return fn(z, C, I, Cx)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def tekst(root):
    """Alle tekst onder <Tekst>, zoals de harness hem vergelijkt."""
    tek = next((c for c in root.iter() if L(c.tag) == 'Tekst'), None)
    return ''.join(tek.itertext()) if tek is not None else ''


def norm(s):
    """Witruimte-ongevoelige normalisatie (idem harness)."""
    return re.sub(r'\s+', '', s)


def opcodes(a, b):
    return difflib.SequenceMatcher(None, a, b).get_opcodes()


def diepste_element(root, fragment, index=None):
    """Het KLEINSTE element waarvan de genormaliseerde tekst het fragment bevat.

    Dit is de hele truc: de eerste treffer in documentvolgorde is altijd de
    buitenste container. Door op de kortste itertext te selecteren krijg je het
    element dat het verlies daadwerkelijk draagt.

    `index` is een optionele {element: genormaliseerde tekst}-map om herhaald
    itereren over een groot document te vermijden.
    """
    if index is None:
        index = {e: norm(''.join(e.itertext())) for e in root.iter() if isinstance(e.tag, str)}
    kand = [e for e, t in index.items() if fragment in t]
    return min(kand, key=lambda e: len(index[e])) if kand else None


def keten(el, parents, diepte=10):
    """Voorouder-keten als leesbare string, binnenste eerst, met wId waar aanwezig."""
    uit, cur = [], el
    for _ in range(diepte):
        if cur is None:
            break
        wid = cur.get('wId') or ''
        uit.append(f"{L(cur.tag)}{('[' + wid + ']') if wid else ''}")
        cur = parents.get(cur)
    return ' < '.join(uit)


def ouders(root):
    return {c: p for p in root.iter() for c in p}
