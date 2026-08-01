"""storm-integrated (XML) <-> SimplicIT Project-JSON (wire-vorm), bidirectioneel.

integrated is 1-op-1 gemodelleerd op SimplicIT.Domain.Project, dus dit is een
model-bewuste mapping (geen generieke XML<->JSON): camelCase-sleutels,
discriminatoren documentComponentType/contentBlokType/kind, en groeperen van de
platte XML-kinderen in de JSON-arrays van het Project (documentComponenten/
leden/contentBlokken/activiteitAanduidingen/themas/normwaarden/...).

Roundtrip: integrated.xml -> json -> integrated.xml (canoniek identiek).
"""
import json
from lxml import etree

NS = "urn:storm:integrated"
Q = f"{{{NS}}}"

def L(t): return t.split('}')[-1] if isinstance(t, str) and '}' in t else t
def kids(e): return [c for c in e if isinstance(c.tag, str)]
def camel(s): return s[0].lower() + s[1:]
def pascal(s): return s[0].upper() + s[1:]

POLY_DOC = {'Boek','Deel','Hoofdstuk','Afdeling','Paragraaf','Subparagraaf',
            'Subsubparagraaf','Divisie','Bijlage','Artikel','Lid','Divisietekst'}
POLY_CB  = {'Alinea','Lijst','Tabel','Figuur','Begrippenlijst','Kadertekst','Citaat'}
BOOL_ATTRS = {'geordend','kop'}
INT_ATTRS  = {'colspan','rowspan','breedte','hoogte','dpi','grootteBytes'}
SKIP_ATTRS = {'variant','schemaversie'}          # storm-envelop, niet in Project-json

STR_ARR = {'Thema':'themas','LocatieRef':'locatieRefs',
           'JuridischeRegelRef':'juridischeRegelRefs',
           'GerelateerdeHoofdlijn':'gerelateerdeHoofdlijnen','DivisieRef':'divisieRefs'}
TOELICHTING = ['AlgemeneToelichting','ArtikelsgewijzeToelichting','Motivering','Aanhef','Sluiting']
# container -> singular kind; volgorde = XSD-sequence van Regeling
CONTAINERS = {'Gebiedsaanwijzingen':'Gebiedsaanwijzing','Omgevingsnormen':'Omgevingsnorm',
              'Ponsen':'Pons','Hoofdlijnen':'Hoofdlijn','Activiteiten':'Activiteit',
              'Bestanden':'Bestand'}
TEKST_WRAP = {'Opschrift','Titel','Bron','Bijschrift','Aanhef','Sluiting','Term'}

# ================= XML -> JSON =================
def attrs(el):
    o = {}
    for a in el.attrib:
        if '}' in a: continue          # namespaced attrs (xsi:schemaLocation) overslaan
        n = L(a)
        if n in SKIP_ATTRS: continue
        v = el.get(a)
        o[n] = (v == 'true') if n in BOOL_ATTRS else (int(v) if n in INT_ATTRS else v)
    return o

def tekst(el):        # lijst TekstRun onder een Tekst-getypeerd element
    return [tekstrun(x) for x in kids(el) if L(x.tag) == 'TekstRun']

def tekstrun(el):
    o = {'tekst': el.get('tekst')}
    if el.get('soort') and el.get('soort') != 'Tekst': o['soort'] = el.get('soort')
    marks = [attrs(m) for m in kids(el) if L(m.tag) == 'Mark']
    if marks: o['marks'] = marks
    noot = next((n for n in kids(el) if L(n.tag) == 'Noot'), None)
    if noot is not None:
        o['noot'] = {**attrs(noot), 'inhoud': tekst(noot)}
    return o

def kop(el):
    o = attrs(el)
    op = next((c for c in kids(el) if L(c.tag) == 'Opschrift'), None)
    if op is not None: o['opschrift'] = tekst(op)
    return o

def contentblok(el):
    t = L(el.tag); o = {'contentBlokType': t, **attrs(el)}
    if t == 'Alinea':
        o['content'] = tekst(el)
    elif t in ('Kadertekst', 'Citaat'):
        o['contentBlokken'] = [contentblok(c) for c in kids(el) if L(c.tag) in POLY_CB]
    elif t == 'Begrippenlijst':
        o['begrippen'] = [begrip(b) for b in kids(el) if L(b.tag) == 'Begrip']
    elif t == 'Lijst':
        for c in kids(el):
            ct = L(c.tag)
            if ct == 'Aanhef': o['aanhef'] = tekst(c)
            elif ct == 'Sluiting': o['sluiting'] = tekst(c)
            elif ct == 'Item':
                o.setdefault('items', []).append(
                    {**attrs(c), 'contentBlokken': [contentblok(x) for x in kids(c) if L(x.tag) in POLY_CB]})
    elif t == 'Tabel':
        for c in kids(el):
            ct = L(c.tag)
            if ct in ('Titel', 'Bron'): o[camel(ct)] = tekst(c)
            elif ct == 'Kolom': o.setdefault('kolommen', []).append(attrs(c))
            elif ct == 'Rij':
                rij = {**attrs(c), 'cellen': [
                    {**attrs(cel), 'contentBlokken': [contentblok(x) for x in kids(cel) if L(x.tag) in POLY_CB]}
                    for cel in kids(c) if L(cel.tag) == 'Cel']}
                o.setdefault('koprijen' if rij.pop('kop', False) else 'rijen', []).append(rij)
    elif t == 'Figuur':
        for c in kids(el):
            if L(c.tag) in ('Titel', 'Bijschrift', 'Bron'): o[camel(L(c.tag))] = tekst(c)
    return o

def begrip(el):
    o = attrs(el)
    for c in kids(el):
        if L(c.tag) == 'Term': o['term'] = tekst(c)
        elif L(c.tag) == 'Definitie':
            o['definitie'] = [contentblok(x) for x in kids(c) if L(x.tag) in POLY_CB]
    return o

def doccomp(el):
    o = {'documentComponentType': L(el.tag), **attrs(el)}
    for c in kids(el):
        ct = L(c.tag)
        if ct == 'Kop': o['kop'] = kop(c)
        elif ct in POLY_CB: o.setdefault('contentBlokken', []).append(contentblok(c))
        elif ct == 'Lid': o.setdefault('leden', []).append(doccomp(c))
        elif ct in POLY_DOC: o.setdefault('documentComponenten', []).append(doccomp(c))
        elif ct == 'ActiviteitAanduiding': o.setdefault('activiteitAanduidingen', []).append(attrs(c))
        elif ct == 'InformatieobjectAanduiding': o.setdefault('informatieobjectAanduidingen', []).append(attrs(c))
        elif ct == 'Thema': o.setdefault('themas', []).append(c.text)
    return o

def owobj(el):
    o = attrs(el)
    for c in kids(el):
        ct = L(c.tag)
        if ct == 'Normwaarde': o.setdefault('normwaarden', []).append(owobj(c))
        elif ct in STR_ARR: o.setdefault(STR_ARR[ct], []).append(c.text)
    return o

def to_project(root):
    p = attrs(root)
    reg = {'opschrift': [], 'documentComponenten': []}
    for c in kids(root):
        t = L(c.tag)
        if t == 'Opschrift': reg['opschrift'] = tekst(c)
        elif t in ('Lichaam', 'Bijlage'): reg['documentComponenten'].append(doccomp(c))
        elif t in TOELICHTING: p[camel(t)] = [doccomp(x) for x in kids(c)]
        elif t in CONTAINERS: p[camel(t)] = [owobj(x) for x in kids(c)]
        elif t in ('Ambtsgebied', 'Regelingsgebied'): p[camel(t)] = attrs(c)
    p['regeling'] = reg
    return p

# ================= JSON -> XML =================
def E(name, **at):
    el = etree.Element(Q + name)
    for k, v in at.items():
        if v is not None: el.set(k, str(v).lower() if isinstance(v, bool) else str(v))
    return el

def x_tekst(name, runs):
    el = E(name)
    for r in runs or []: el.append(x_tekstrun(r))
    return el

def x_tekstrun(r):
    el = E('TekstRun', tekst=r['tekst'], soort=r.get('soort'))
    for m in r.get('marks', []): el.append(E('Mark', **m))
    if 'noot' in r:
        n = {k: v for k, v in r['noot'].items() if k != 'inhoud'}
        noot = E('Noot', **n)
        for tr in r['noot'].get('inhoud', []): noot.append(x_tekstrun(tr))
        el.append(noot)
    return el

def x_kop(k):
    el = E('Kop', label=k.get('label'), nummer=k.get('nummer'))
    if 'opschrift' in k: el.append(x_tekst('Opschrift', k['opschrift']))
    return el

def x_contentblok(b):
    t = b['contentBlokType']
    at = {k: v for k, v in b.items() if k not in (
        'contentBlokType', 'content', 'contentBlokken', 'begrippen', 'items',
        'aanhef', 'sluiting', 'titel', 'bron', 'bijschrift', 'kolommen', 'rijen', 'koprijen')}
    el = E(t, **at)
    if t == 'Alinea':
        for r in b.get('content', []): el.append(x_tekstrun(r))
    elif t in ('Kadertekst', 'Citaat'):
        for c in b.get('contentBlokken', []): el.append(x_contentblok(c))
    elif t == 'Begrippenlijst':
        for g in b.get('begrippen', []): el.append(x_begrip(g))
    elif t == 'Lijst':
        if 'aanhef' in b: el.append(x_tekst('Aanhef', b['aanhef']))
        for it in b.get('items', []):
            iat = {k: v for k, v in it.items() if k != 'contentBlokken'}
            item = E('Item', **iat)
            for c in it.get('contentBlokken', []): item.append(x_contentblok(c))
            el.append(item)
        if 'sluiting' in b: el.append(x_tekst('Sluiting', b['sluiting']))
    elif t == 'Tabel':
        if 'titel' in b: el.append(x_tekst('Titel', b['titel']))
        for k in b.get('kolommen', []): el.append(E('Kolom', **k))
        for kop_flag, key in ((True, 'koprijen'), (False, 'rijen')):
            for rij in b.get(key, []):
                rat = {k: v for k, v in rij.items() if k != 'cellen'}
                r = E('Rij', kop=kop_flag if kop_flag else None, **rat)
                for cel in rij.get('cellen', []):
                    cat = {k: v for k, v in cel.items() if k != 'contentBlokken'}
                    ce = E('Cel', **cat)
                    for c in cel.get('contentBlokken', []): ce.append(x_contentblok(c))
                    r.append(ce)
                el.append(r)
        if 'bron' in b: el.append(x_tekst('Bron', b['bron']))
    elif t == 'Figuur':
        for key in ('titel', 'bijschrift', 'bron'):
            if key in b: el.append(x_tekst(pascal(key), b[key]))
    return el

def x_begrip(g):
    at = {k: v for k, v in g.items() if k not in ('term', 'definitie')}
    el = E('Begrip', **at)
    if 'term' in g: el.append(x_tekst('Term', g['term']))
    if 'definitie' in g:
        d = E('Definitie')
        for c in g['definitie']: d.append(x_contentblok(c))
        el.append(d)
    return el

DC_SKIP = {'documentComponentType', 'kop', 'contentBlokken', 'leden', 'documentComponenten',
           'activiteitAanduidingen', 'informatieobjectAanduidingen', 'themas'}

def x_doccomp(d):
    el = E(d['documentComponentType'], **{k: v for k, v in d.items() if k not in DC_SKIP})
    if 'kop' in d: el.append(x_kop(d['kop']))
    for c in d.get('contentBlokken', []): el.append(x_contentblok(c))
    for lid in d.get('leden', []): el.append(x_doccomp(lid))
    for dc in d.get('documentComponenten', []): el.append(x_doccomp(dc))
    for a in d.get('activiteitAanduidingen', []): el.append(E('ActiviteitAanduiding', **a))
    for a in d.get('informatieobjectAanduidingen', []): el.append(E('InformatieobjectAanduiding', **a))
    for th in d.get('themas', []): el.append(_txt('Thema', th))
    return el

def _txt(name, val):
    el = E(name); el.text = val; return el

OW_STR = {v: k for k, v in STR_ARR.items()}   # jsonKey -> element

def x_owobj(name, o):
    at = {k: v for k, v in o.items() if k not in ('normwaarden', *OW_STR)}
    el = E(name, **at)
    for nw in o.get('normwaarden', []): el.append(x_owobj('Normwaarde', nw))
    for key, elname in OW_STR.items():
        for v in o.get(key, []): el.append(_txt(elname, v))
    return el

def from_project(p):
    root = E('Regeling', variant='integrated', schemaversie='0.6.0',
             **{k: v for k, v in p.items() if k not in (
                 'regeling', 'ambtsgebied', 'regelingsgebied',
                 *[camel(t) for t in TOELICHTING], *[camel(c) for c in CONTAINERS])})
    reg = p.get('regeling', {})
    root.append(x_tekst('Opschrift', reg.get('opschrift', [])))
    for dc in reg.get('documentComponenten', []): root.append(x_doccomp(dc))
    for t in TOELICHTING:
        if camel(t) in p:
            wrap = E(t)
            for dc in p[camel(t)]: wrap.append(x_doccomp(dc))
            root.append(wrap)
    if 'ambtsgebied' in p: root.append(E('Ambtsgebied', **p['ambtsgebied']))
    if 'regelingsgebied' in p: root.append(E('Regelingsgebied', **p['regelingsgebied']))
    for cont, child in CONTAINERS.items():
        key = camel(cont)
        if key in p:
            wrap = E(cont)
            for o in p[key]: wrap.append(x_owobj(child, o))
            root.append(wrap)
    return root

# ================= CLI / roundtrip =================
if __name__ == '__main__':
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else \
        r"C:/GIT/Storm/standaard/voorbeelden/integrated-mini/storm-integrated.xml"
    root = etree.parse(src).getroot()
    proj = to_project(root)
    print(json.dumps(proj, indent=2, ensure_ascii=False))
