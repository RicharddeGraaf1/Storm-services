"""Genereer een storm-volledig-pakket uit de echte Gemeentestad-bron.

Kiem van download2volledig: leest de STOP-besluit-tekst + de IMOW-deelbestanden
en spiegelt ze faithful naar de drie STORM-lagen (tekst/ow) + gecombineerd
manifest. Geometrie blijft extern (GML's meegekopieerd).
"""
from pathlib import Path
from copy import deepcopy
from lxml import etree

OPDRACHT = Path(r"C:\Testbestanden\GITHub\Gemeentestad\opdracht")
XSD = Path(r"C:\GIT\Storm\standaard\xsd\storm-volledig.xsd")
GIO_XSD = Path(r"C:\GIT\Storm\standaard\xsd\storm-gio.xsd")
OUT = Path(r"C:\GIT\Storm\standaard\voorbeelden\Gemeentestad-volledig")

STORM="urn:storm:1.0"; TEKST="urn:storm:tekst"; OW="urn:storm:ow"
DATA="urn:storm:data"; GIO="urn:storm:gio"
XLINK="http://www.w3.org/1999/xlink"
XSI="http://www.w3.org/2001/XMLSchema-instance"
XSD_URL=("https://raw.githubusercontent.com/RicharddeGraaf1/Storm/main/"
         "standaard/xsd/storm-volledig.xsd")

def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t
def href(e): return e.get(f"{{{XLINK}}}href")
def T(name,text=None,ns=OW):
    el=etree.Element(f"{{{ns}}}{name}")
    if text is not None: el.text=text
    return el

# ---------- tekstlaag: faithful verbatim spiegel ----------
REGELINGTYPE={'RegelingCompact':'compact','RegelingVrijetekst':'vrijetekst',
 'RegelingKlassiek':'klassiek','RegelingTijdelijkdeel':'tijdelijkdeel'}

def norm(s): return ' '.join((s or '').split()) or None

STOP_TEKST="https://standaarden.overheid.nl/stop/imop/tekst/"

def mirror_tekst(src):
    """Faithful verbatim spiegel van de STOP-tekst: deepcopy en hernoem alleen
    de STOP-tekst-namespace naar urn:storm:tekst. Alles blijft behouden —
    tabellen, inline-opmaak (i/b/IntRef/Noot/...), eId/wId, en de volledige
    Divisie/Groep/Toelichting-structuur. volledig doet zelf geen transformatie;
    storm-tekst.xsd valideert deze laag permissief (xs:any skip)."""
    out=deepcopy(src)
    old=f"{{{STOP_TEKST}}}"; new=f"{{{TEKST}}}"
    for e in out.iter():
        if isinstance(e.tag,str) and e.tag.startswith(old):
            e.tag=new+e.tag[len(old):]
    etree.cleanup_namespaces(out)
    return out

# ---------- objectlaag: IMOW-objecten spiegelen ----------
REF_WRAPPERS={'artikelOfLid','locatieaanduiding','gebiedsaanwijzing',
 'kaartaanduiding','omgevingsnormaanduiding','omgevingswaardeaanduiding',
 'gerelateerdeRegeltekst','gerelateerdeActiviteit','bovenliggendeActiviteit',
 'gerelateerdeHoofdlijn','hoofdlijnaanduiding','divisieaanduiding','groepselement',
 'normweergave','activiteitlocatieweergave','gebiedsaanwijzingweergave'}

def kids(e):
    return [c for c in e if isinstance(c.tag,str)]

def leaves(e):
    out=[]
    for c in kids(e):
        if kids(c): out.extend(leaves(c))
        else: out.append((L(c.tag),norm(''.join(c.itertext()))))
    return out

SKIP={'eigenSymbolisatie'}  # presentatie, geen inhoud

def mirror_obj(src):
    ln=L(src.tag); out=T(ln)
    if src.get('wId'): out.set('wId',src.get('wId'))
    for c in kids(src):
        lc=L(c.tag)
        if lc in SKIP:
            continue
        if lc in REF_WRAPPERS:
            for g in kids(c):
                if L(g.tag).endswith('Ref'):
                    r=T(lc); r.set('ref',href(g)); out.append(r)
        elif lc=='activiteitaanduiding':
            aa=T('activiteitaanduiding')
            for g in kids(c):
                lg=L(g.tag)
                if lg=='ActiviteitRef':
                    a=T('activiteit'); a.set('ref',href(g)); aa.append(a)
                elif lg=='ActiviteitLocatieaanduiding':
                    aa.append(mirror_obj(g))
            out.append(aa)
        elif lc=='normwaarde':
            nw=T('normwaarde')
            for g in kids(c):
                if L(g.tag)=='Normwaarde': nw.append(mirror_obj(g))
            out.append(nw)
        elif lc=='geometrie':
            g=T('geometrie'); gr=T('GeometrieRef')
            for gg in kids(c):
                if L(gg.tag)=='GeometrieRef': gr.set('ref',href(gg))
            g.append(gr); out.append(g)
        elif lc=='uitsnede':
            u=T('uitsnede')
            for g in kids(c):
                if L(g.tag)=='Kaartextent':
                    ke=T('Kaartextent')
                    for name,text in leaves(g): ke.append(T(name,text))
                    u.append(ke)
            out.append(u)
        elif lc=='kaartlagen':
            kl=T('kaartlagen')
            for g in kids(c):
                if L(g.tag)=='Kaartlaag': kl.append(mirror_obj(g))
            out.append(kl)
        elif lc in ('hoogte','bestuurlijkeGrenzenVerwijzing',
                    'BestuurlijkeGrenzenVerwijzing'):
            # IMOW 2.0 schreef kleine letter, 3.x een hoofdletter -> normaliseer
            name='bestuurlijkeGrenzenVerwijzing' if lc[0] in 'bB' and 'renzen' in lc else lc
            w=T(name)
            for nm,text in leaves(c):
                w.append(T(nm,text))
            out.append(w)
        else:
            out.append(T(lc,norm(''.join(c.itertext()))))
    return out

# objecttype -> (sectie, bucket-key voor volgorde binnen sectie)
SECTIE={'Regeltekst':('Regels',0),'RegelVoorIedereen':('Regels',1),
 'Instructieregel':('Regels',1),'Omgevingswaarderegel':('Regels',1),
 'Omgevingsnorm':('Normen',0),'Omgevingswaarde':('Normen',0),
 'Activiteit':('Activiteiten',0),
 'Gebied':('Locaties',0),'Gebiedengroep':('Locaties',0),'Ambtsgebied':('Locaties',0),
 'Punt':('Locaties',0),'Puntengroep':('Locaties',0),'Lijn':('Locaties',0),
 'Lijnengroep':('Locaties',0),
 'Gebiedsaanwijzing':('Gebiedsaanwijzingen',0),
 'Regelingsgebied':('Regelingsgebied',0),'Pons':('Pons',0),
 'Tekstdeel':('VrijeTekst',0),'Divisie':('VrijeTekst',1),
 'Divisietekst':('VrijeTekst',2),'Hoofdlijn':('VrijeTekst',3),
 'Kaart':('Kaarten',0)}
# Regelingsgebied/Pons zijn eigen secties direct onder OwObjecten (geen wrapper).
# VrijeTekst = de IMOW-objectkant van omgevingsvisie/programma (vrijetekst-
# structuur). SymbolisatieItem is in de laatste IMOW vervallen.
SECTIE_ORDER=['Regels','Normen','Activiteiten','Locaties','Gebiedsaanwijzingen',
 'Regelingsgebied','Pons','VrijeTekst','Kaarten']
SINGLE={'Regelingsgebied','Pons'}  # object is zelf de sectie, geen container

def lees_objecten():
    buckets={}  # sectie -> list of (bucket-key, element)
    for f in sorted(OPDRACHT.glob('ow*.xml')):
        root=etree.parse(str(f)).getroot()
        for obj in root.iter(f"{{http://www.geostandaarden.nl/imow/bestanden/deelbestand}}owObject"):
            elks=[c for c in obj if isinstance(c.tag,str)]
            if not elks: continue
            child=elks[0]; kind=L(child.tag)
            if kind in SECTIE:
                sec,key=SECTIE[kind]
                buckets.setdefault(sec,[]).append((key,mirror_obj(child)))
    return buckets

# ---------- montage ----------
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    besluit=next(OPDRACHT.glob('akn_nl_bill*.xml'))
    broot=etree.parse(str(besluit)).getroot()
    reg=next(e for e in broot.iter() if L(e.tag) in REGELINGTYPE)
    structuur=REGELINGTYPE[L(reg.tag)]

    # manifest-ow: workid + doel + bestanden
    mow=etree.parse(str(OPDRACHT/'manifest-ow.xml')).getroot()
    work=next(e for e in mow.iter() if L(e.tag)=='WorkIDRegeling').text
    doel=next((e.text for e in mow.iter() if L(e.tag)=='DoelID'),None)

    # Regeling opbouwen
    R=etree.Element(f"{{{STORM}}}Regeling",
                    nsmap={None:STORM,'data':DATA,'tekst':TEKST,'ow':OW,'xsi':XSI})
    R.set('variant','volledig'); R.set('schemaversie','0.6.0')
    R.set(f"{{{XSI}}}schemaLocation",f"{STORM} {XSD_URL}")
    ident=etree.SubElement(R,f"{{{STORM}}}Identificatie")
    etree.SubElement(ident,f"{{{STORM}}}FRBRWork").text=work
    etree.SubElement(ident,f"{{{STORM}}}bevoegdGezag").text='gm0297'

    # Metadata (verbatim bewaard, roundtrip-veilig)
    meta=etree.SubElement(R,f"{{{DATA}}}Metadata")
    besl=etree.SubElement(meta,f"{{{DATA}}}Besluit")
    bv=next(e for e in broot.iter() if L(e.tag)=='BesluitVersie')
    for c in bv:
        if isinstance(c.tag,str) and L(c.tag) in (
                'ExpressionIdentificatie','BesluitMetadata','Procedureverloop',
                'ConsolidatieInformatie'):
            besl.append(deepcopy(c))
    regm=next((e for e in broot.iter() if L(e.tag)=='RegelingMetadata'),None)
    if regm is not None:
        etree.SubElement(meta,f"{{{DATA}}}Regeling").append(deepcopy(regm))

    # tekstlaag: alle STOP-tekst-kinderen van de regeling verbatim spiegelen
    # (RegelingOpschrift, Lichaam, Bijlage*, Toelichting/ArtikelgewijzeToelichting,
    # ...) — geen whitelist, zodat niets structureels wegvalt.
    tekst=T('Tekst',ns=TEKST); tekst.set('structuur',structuur)
    for k,v in reg.attrib.items():        # componentnaam/wordt/schemaversie verbatim
        tekst.set(k,v)
    for c in reg:
        if isinstance(c.tag,str) and c.tag.startswith(f"{{{STOP_TEKST}}}"):
            tekst.append(mirror_tekst(c))
    R.append(tekst)

    buckets=lees_objecten()
    ow=T('OwObjecten')
    for sec in SECTIE_ORDER:
        if sec not in buckets: continue
        items=[el for key,el in sorted(buckets[sec],key=lambda x:x[0])]
        if sec in SINGLE:
            for el in items: ow.append(el)      # direct kind van OwObjecten
        else:
            s=T(sec)
            for el in items: s.append(el)
            ow.append(s)
    R.append(ow)

    # storm-gio-bestanden: IO-metadata + symbolisatie + geometrie bundelen
    for old in OUT.glob('*.gml'): old.unlink()
    gio_files=[]
    for wf in sorted(OPDRACHT.glob('GIO*.xml'))+[OPDRACHT/'PonsGebied.xml']:
        if not wf.exists(): continue
        wr=etree.parse(str(wf)).getroot()
        bn=next((e.text for e in wr.iter() if isinstance(e.tag,str) and L(e.tag)=='bestandsnaam'),None)
        if not bn or not bn.endswith('.gml'): continue
        gml=OPDRACHT/bn
        if not gml.exists(): continue
        G=etree.Element(f"{{{GIO}}}GeoInformatieObject",nsmap={None:GIO})
        ids=next((e for e in wr.iter() if isinstance(e.tag,str) and L(e.tag)=='ExpressionIdentificatie'),None)
        gi=etree.SubElement(G,f"{{{GIO}}}Identificatie")
        for fld in ('FRBRWork','FRBRExpression','soortWork'):
            v=next((e.text for e in ids.iter() if isinstance(e.tag,str) and L(e.tag)==fld),None) if ids is not None else None
            if v: etree.SubElement(gi,f"{{{GIO}}}{fld}").text=v
        md=etree.SubElement(G,f"{{{GIO}}}Metadata")
        for c in wr.iter():
            if isinstance(c.tag,str) and L(c.tag) in ('InformatieObjectVersieMetadata','InformatieObjectMetadata'):
                md.append(deepcopy(c))
        fts=next((e for e in wr.iter() if isinstance(e.tag,str) and L(e.tag)=='FeatureTypeStyle'),None)
        if fts is not None:
            etree.SubElement(G,f"{{{GIO}}}Symbolisatie").append(deepcopy(fts))
        etree.SubElement(G,f"{{{GIO}}}Geo").append(deepcopy(etree.parse(str(gml)).getroot()))
        outname=gml.stem+'.storm-gio.xml'
        etree.ElementTree(G).write(str(OUT/outname),xml_declaration=True,encoding='UTF-8',pretty_print=True)
        w=next((e.text for e in ids.iter() if isinstance(e.tag,str) and L(e.tag)=='FRBRWork'),None) if ids is not None else None
        gio_files.append((outname,w))

    # Manifest
    M=etree.Element(f"{{{STORM}}}Manifest",nsmap={None:STORM,'xsi':XSI})
    M.set('schemaversie','0.6.0')
    M.set(f"{{{XSI}}}schemaLocation",f"{STORM} {XSD_URL}")
    etree.SubElement(M,f"{{{STORM}}}regeling").set('ref',work)
    if doel: etree.SubElement(M,f"{{{STORM}}}doel").text=doel
    b=etree.SubElement(M,f"{{{STORM}}}Bestand")
    b.set('naam','storm-volledig.xml'); b.set('rol','regeling'); b.set('contentType','application/xml')
    for outname,w in gio_files:
        bb=etree.SubElement(M,f"{{{STORM}}}Bestand")
        bb.set('naam',outname); bb.set('rol','gio'); bb.set('contentType','application/xml')
        if w: bb.set('work',w)

    for el,name in ((R,'storm-volledig.xml'),(M,'manifest.xml')):
        etree.ElementTree(el).write(str(OUT/name),xml_declaration=True,encoding='UTF-8',pretty_print=True)

    # validatie
    schema=etree.XMLSchema(etree.parse(str(XSD)))
    giosch=etree.XMLSchema(etree.parse(str(GIO_XSD)))
    for name in ('storm-volledig.xml','manifest.xml'):
        doc=etree.parse(str(OUT/name)); ok=schema.validate(doc)
        print(name,'->', 'VALIDE' if ok else 'FOUT')
        if not ok:
            for e in list(schema.error_log)[:12]: print('   ',e.line,e.message)
    giolist=sorted(OUT.glob('*.storm-gio.xml')); bad=0
    for gf in giolist:
        if not giosch.validate(etree.parse(str(gf))):
            bad+=1
            for e in list(giosch.error_log)[:4]: print('   ',gf.name,e.line,e.message)
    print(f"storm-gio: {len(giolist)} bestanden, {bad} fout")

if __name__=='__main__':
    main()
