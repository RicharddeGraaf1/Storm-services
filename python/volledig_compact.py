"""storm-volledig -> storm-compact: vocabulaire-projectie (éénrichting, lossy).

compact = integrated's vocabulaire (SimplicIT-support) in volledig's STOP-
structuur. Deze transform houdt de structuur (tekst-laag + object-secties,
losse regel-objecten met ref) en SNOEIT de vocabulaire:
  - regel-subtypes -> één JuridischeRegel; drop per-regel locatie/gebieds/kaart/
    norm-koppeling; ActiviteitLocatieaanduiding -> activiteitaanduiding zonder locatie
  - idealisatie behouden (STOP-verplicht); opschrift-marks NIET platslaan
  - Omgevingsnorm/Omgevingswaarde -> Omgevingsnorm; Normwaarde zonder waardeInRegeltekst
  - Locaties -> minimale Locatie (id + geometrieRef); Kaarten weg
  - metadata -> scalars; geometrie -> Bestand-verwijzing (uit de storm-gio's)
"""
from copy import deepcopy
from pathlib import Path
from lxml import etree

STORM="urn:storm:1.0"; DATA="urn:storm:data"; TEKST="urn:storm:tekst"; OW="urn:storm:ow"
COMPACT="urn:storm:compact"; XSI="http://www.w3.org/2001/XMLSchema-instance"
EXACT="http://standaarden.omgevingswet.overheid.nl/idealisatie/id/concept/Exact"
XSD=Path(r"C:\GIT\Storm\standaard\xsd\storm-compact.xsd")
XSD_URL=("https://raw.githubusercontent.com/RicharddeGraaf1/Storm/main/"
         "standaard/xsd/storm-compact.xsd")

def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t
def kids(e): return [c for c in e if isinstance(c.tag,str)]
def C(name,text=None):
    el=etree.Element(f"{{{COMPACT}}}{name}")
    if text is not None: el.text=text
    return el
def Cref(name,refval):
    el=C(name); el.set('ref',refval); return el
def child(e,name): return next((c for c in kids(e) if L(c.tag)==name),None)
def childtext(e,name):
    c=child(e,name); return c.text if c is not None else None
def refval(e):  # element met een @ref of een child *Ref met @ref
    if e.get('ref'): return e.get('ref')
    return None

TEKST_SECTIES={'RegelingOpschrift','Lichaam','Bijlage','ArtikelgewijzeToelichting'}
LOC_TYPES={'Gebied','Gebiedengroep','Punt','Puntengroep','Lijn','Lijnengroep'}
REGEL_TYPES={'RegelVoorIedereen','Instructieregel','Omgevingswaarderegel'}

# ---------- tekstlaag: verbatim overnemen (marks/opschrift behouden) ----------
def map_tekst(vol_tekst):
    t=C('Tekst'); t.set('structuur', vol_tekst.get('structuur','compact'))
    for c in kids(vol_tekst):
        ln=L(c.tag)
        if ln in TEKST_SECTIES:
            t.append(deepcopy(c))
        elif ln=='Toelichting':                     # act-wrapper -> ArtikelgewijzeToelichting eruit
            for g in kids(c):
                if L(g.tag)=='ArtikelgewijzeToelichting': t.append(deepcopy(g))
    return t

# ---------- objectlaag: snoeien ----------
def map_juridischeregel(src):
    jr=C('JuridischeRegel')
    jr.append(C('identificatie', childtext(src,'identificatie')))
    jr.append(C('idealisatie', childtext(src,'idealisatie') or EXACT))   # STOP-verplicht
    al=child(src,'artikelOfLid')
    jr.append(Cref('artikelOfLid', al.get('ref') if al is not None else ''))
    for aa in kids(src):
        if L(aa.tag)!='activiteitaanduiding': continue
        act=child(aa,'activiteit')
        ca=C('activiteitaanduiding')
        ca.append(Cref('activiteit', act.get('ref') if act is not None else ''))
        ala=child(aa,'ActiviteitLocatieaanduiding')
        rk=childtext(ala,'activiteitregelkwalificatie') if ala is not None else None
        if rk: ca.append(C('regelkwalificatie', rk))
        jr.append(ca)
    for th in kids(src):
        if L(th.tag)=='thema': jr.append(C('thema', th.text))
    return jr, [child(aa,'activiteit').get('ref')
                for aa in kids(src) if L(aa.tag)=='activiteitaanduiding'
                and child(aa,'activiteit') is not None]

def map_activiteit(src, regelrefs_by_act, ident):
    a=C('Activiteit')
    a.append(C('identificatie', ident))
    a.append(C('naam', childtext(src,'naam')))
    om=childtext(src,'omschrijving')
    if om: a.append(C('omschrijving', om))
    a.append(C('groep', childtext(src,'groep')))
    a.append(C('type', childtext(src,'type') or 'Activiteit'))
    bov=child(src,'bovenliggendeActiviteit')
    if bov is not None and bov.get('ref'): a.append(Cref('bovenliggendeActiviteit', bov.get('ref')))
    for jr in regelrefs_by_act.get(ident, []):
        a.append(Cref('juridischeRegelRef', jr))
    return a

def map_norm(src):
    n=C('Omgevingsnorm')
    n.append(C('identificatie', childtext(src,'identificatie')))
    n.append(C('naam', childtext(src,'naam')))
    n.append(C('type', childtext(src,'type')))
    eh=childtext(src,'eenheid')
    if eh: n.append(C('eenheid', eh))
    n.append(C('groep', childtext(src,'groep')))
    nww=child(src,'normwaarde')
    for nw in (kids(nww) if nww is not None else []):
        if L(nw.tag)!='Normwaarde': continue
        w=C('Normwaarde')
        w.append(C('identificatie', childtext(nw,'identificatie')))
        for fld in ('kwantitatieveWaarde','kwalitatieveWaarde'):
            v=childtext(nw,fld)
            if v: w.append(C(fld, v))
        for la in kids(nw):
            if L(la.tag)=='locatieaanduiding' and la.get('ref'):
                w.append(Cref('locatieaanduiding', la.get('ref')))
        n.append(w)
    return n

def map_gebiedsaanwijzing(src):
    g=C('Gebiedsaanwijzing')
    g.append(C('identificatie', childtext(src,'identificatie')))
    g.append(C('naam', childtext(src,'naam')))
    g.append(C('type', childtext(src,'type')))
    g.append(C('groep', childtext(src,'groep')))
    la=child(src,'locatieaanduiding')     # compact: één (volledig kan er meer; eerste)
    g.append(Cref('locatieaanduiding', la.get('ref') if la is not None else ''))
    return g

def map_locatie(src):
    lo=C('Locatie')
    lo.append(C('identificatie', childtext(src,'identificatie')))
    nm=childtext(src,'noemer')
    if nm: lo.append(C('noemer', nm))
    geo=child(src,'geometrie')
    if geo is not None:
        gr=child(geo,'GeometrieRef')
        if gr is not None and gr.get('ref'): lo.append(Cref('geometrieRef', gr.get('ref')))
    return lo

def map_ambtsgebied(src):
    a=C('Ambtsgebied')
    a.append(C('identificatie', childtext(src,'identificatie')))
    a.append(C('naam', childtext(src,'noemer') or ''))
    bgv=child(src,'bestuurlijkeGrenzenVerwijzing')
    bgid=None
    if bgv is not None:
        inner=child(bgv,'BestuurlijkeGrenzenVerwijzing') or bgv
        bgid=childtext(inner,'bestuurlijkeGrenzenID')
    a.append(C('bestuurlijkeGrenzenId', bgid or ''))
    return a

# ---------- montage ----------
def transform(vol_dir):
    vol_dir=Path(vol_dir)
    root=etree.parse(str(vol_dir/'storm-volledig.xml')).getroot()
    ident=child(root,'Identificatie')
    meta=child(root,'Metadata')
    regmeta=None
    if meta is not None:
        r=child(meta,'Regeling')
        if r is not None: regmeta=next((c for c in kids(r) if L(c.tag)=='RegelingMetadata'),None)

    R=etree.Element(f"{{{COMPACT}}}Regeling",
                    nsmap={None:COMPACT,'tekst':TEKST,'xsi':XSI})
    R.set('variant','compact'); R.set('schemaversie','0.6.0')
    R.set(f"{{{XSI}}}schemaLocation", f"{COMPACT} {XSD_URL}")
    work=childtext(ident,'FRBRWork') if ident is not None else None
    if work: R.set('frbrWork', work)
    expr=childtext(ident,'FRBRExpression') if ident is not None else None
    if expr: R.set('frbrExpression', expr)
    bg=childtext(ident,'bevoegdGezag') if ident is not None else None
    if not bg and work and len(work.split('/'))>4: bg=work.split('/')[4]
    R.set('bevoegdGezagCode', bg or 'onbekend')
    if regmeta is not None:
        naam=childtext(regmeta,'officieleTitel')
        if naam: R.set('naam', naam)
        sr=childtext(regmeta,'soortRegeling')
        if sr: R.set('soortRegeling', sr)
    R.set('type','omgevingsplan')

    # tekst
    vt=child(root,'Tekst')
    if vt is not None: R.append(map_tekst(vt))

    # objecten
    ow=child(root,'OwObjecten')
    co=C('CompactObjecten')
    regelrefs_by_act={}
    if ow is not None:
        # Regels
        regels_src=child(ow,'Regels')
        regels=C('Regels'); has_regel=False
        for o in (kids(regels_src) if regels_src is not None else []):
            ln=L(o.tag)
            if ln=='Regeltekst':
                rt=C('Regeltekst'); rt.set('wId', o.get('wId') or '')
                rt.append(C('identificatie', childtext(o,'identificatie')))
                regels.append(rt); has_regel=True
            elif ln in REGEL_TYPES:
                jr,acts=map_juridischeregel(o)
                for aref in acts:
                    regelrefs_by_act.setdefault(aref,[]).append(childtext(o,'identificatie'))
                regels.append(jr); has_regel=True
        if has_regel: co.append(regels)

        # Activiteiten
        acts_src=child(ow,'Activiteiten')
        if acts_src is not None and kids(acts_src):
            av=C('Activiteiten')
            for o in kids(acts_src):
                if L(o.tag)=='Activiteit':
                    av.append(map_activiteit(o, regelrefs_by_act, childtext(o,'identificatie')))
            co.append(av)

        # Normen
        norms_src=child(ow,'Normen')
        if norms_src is not None and kids(norms_src):
            nv=C('Normen')
            for o in kids(norms_src):
                if L(o.tag) in ('Omgevingsnorm','Omgevingswaarde'): nv.append(map_norm(o))
            co.append(nv)

        # Gebiedsaanwijzingen
        ga_src=child(ow,'Gebiedsaanwijzingen')
        if ga_src is not None and kids(ga_src):
            gv=C('Gebiedsaanwijzingen')
            for o in kids(ga_src):
                if L(o.tag)=='Gebiedsaanwijzing': gv.append(map_gebiedsaanwijzing(o))
            co.append(gv)

        # Locaties (+ Ambtsgebied)
        loc_src=child(ow,'Locaties')
        amb=None; locs=[]
        for o in (kids(loc_src) if loc_src is not None else []):
            if L(o.tag)=='Ambtsgebied': amb=map_ambtsgebied(o)
            elif L(o.tag) in LOC_TYPES: locs.append(map_locatie(o))
        if amb is not None or locs:
            lv=C('Locaties')
            if amb is not None: lv.append(amb)
            for lo in locs: lv.append(lo)
            co.append(lv)

        # Regelingsgebied
        rg=child(ow,'Regelingsgebied')
        if rg is not None:
            c=C('Regelingsgebied'); c.append(C('identificatie', childtext(rg,'identificatie')))
            la=child(rg,'locatieaanduiding')
            c.append(Cref('locatieaanduiding', la.get('ref') if la is not None else ''))
            co.append(c)

        # Ponsen
        pons=[o for o in kids(ow) if L(o.tag)=='Pons']
        if pons:
            pv=C('Ponsen')
            for o in pons:
                p=C('Pons'); p.append(C('identificatie', childtext(o,'identificatie')))
                la=child(o,'locatieaanduiding')
                p.append(Cref('locatieaanduiding', la.get('ref') if la is not None else ''))
                pv.append(p)
            co.append(pv)

        # Hoofdlijnen (uit VrijeTekst)
        vrij=child(ow,'VrijeTekst')
        hoofd=[o for o in (kids(vrij) if vrij is not None else []) if L(o.tag)=='Hoofdlijn']
        if hoofd:
            hv=C('Hoofdlijnen')
            for o in hoofd:
                h=C('Hoofdlijn')
                h.append(C('identificatie', childtext(o,'identificatie')))
                h.append(C('naam', childtext(o,'naam')))
                h.append(C('soort', childtext(o,'soort')))
                hv.append(h)
            co.append(hv)
        # Kaarten: bewust weg

    # Bestanden uit de storm-gio's
    gios=sorted(vol_dir.glob('*.storm-gio.xml'))
    if gios:
        bv=C('Bestanden')
        for gf in gios:
            g=etree.parse(str(gf)).getroot()
            idf=next((e for e in g.iter() if L(e.tag)=='Identificatie'),None)
            frbr=childtext(idf,'FRBRWork') if idf is not None else None
            b=C('Bestand'); b.set('type','gml')
            b.set('naam', gf.name.replace('.storm-gio.xml','.gml'))
            if frbr: b.set('frbrExpression', frbr)
            b.set('mimeType','application/gml+xml')
            bv.append(b)
        co.append(bv)

    if kids(co): R.append(co)
    return R

def rapport(vol_dir):
    R=transform(vol_dir)
    schema=etree.XMLSchema(etree.parse(str(XSD)))
    ok=schema.validate(etree.ElementTree(R))
    print('storm-compact valideert:', 'JA' if ok else 'NEE')
    for e in list(schema.error_log)[:10]: print('  ',e.line,e.message[:130])
    co=child(R,'CompactObjecten')
    if co is not None:
        for sec in kids(co):
            print(f'  {L(sec.tag):22} {len(kids(sec))}')
    return R

if __name__=='__main__':
    import sys
    d=sys.argv[1] if len(sys.argv)>1 else r"C:\GIT\Storm\standaard\voorbeelden\Gemeentestad-volledig"
    R=rapport(d)
    if len(sys.argv)>2:
        etree.ElementTree(R).write(sys.argv[2], xml_declaration=True,
                                   encoding='UTF-8', pretty_print=True)
        print('geschreven:', sys.argv[2])
