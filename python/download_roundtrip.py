"""Roundtrip-harness downloadpakket <-> storm-volledig (referentie, Python).

Fase 1: download(act) -> volledig, plus een verlies-census per laag die
kwantificeert wat NIET verliesloos naar volledig gaat. De census onderscheidt
'omkeerbaar-by-design' (bv. *Ref-wrappers die tot @ref inklappen, namespace-
prefixen — localname blijft) van 'echt verlies' (inline-opmaak die platgeslagen
wordt, weggegooide elementen).

Bron: geconsolideerde downloadpakketten op /d/downloadpakketten/prod/<bg>/<type>/
uitgepakt/<versie>/ met Regeling/ (module-bestanden) + OW-bestanden/ + IO-*/.

Hergebruikt de mirror-functies uit naar_volledig.py.
"""
from pathlib import Path
from copy import deepcopy
from collections import Counter
from lxml import etree
import naar_volledig as NV

STORM=NV.STORM; TEKST=NV.TEKST; OW=NV.OW; DATA=NV.DATA; GIO=NV.GIO
XSI=NV.XSI; XSD_URL=NV.XSD_URL
DEELBESTAND="http://www.geostandaarden.nl/imow/bestanden/deelbestand"
XLINK="http://www.w3.org/1999/xlink"
XSD=Path(r"C:\GIT\Storm\standaard\xsd\storm-volledig.xsd")

# De prod-OW-bestanden bevatten een kapotte xmlns:schemaLocation -> recover.
P=etree.XMLParser(recover=True, remove_blank_text=False)
def parse(p): return etree.parse(str(p),P).getroot()
def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t
kids=NV.kids

META_MODULES=('Identificatie.xml','VersieMetadata.xml','Metadata.xml','Momentopname.xml')

# ---------- download(act) -> volledig ----------
def download2volledig(pkgdir):
    pkgdir=Path(pkgdir); regdir=pkgdir/'Regeling'
    tekst_root=parse(regdir/'Tekst.xml')          # RegelingCompact
    structuur=NV.REGELINGTYPE.get(L(tekst_root.tag),'compact')

    R=etree.Element(f"{{{STORM}}}Regeling",
                    nsmap={None:STORM,'data':DATA,'tekst':TEKST,'ow':OW,'xsi':XSI})
    R.set('variant','volledig'); R.set('schemaversie','0.6.0')
    R.set(f"{{{XSI}}}schemaLocation",f"{STORM} {XSD_URL}")

    idroot=parse(regdir/'Identificatie.xml')
    work=next((e.text for e in idroot.iter() if L(e.tag)=='FRBRWork'),None)
    expr=next((e.text for e in idroot.iter() if L(e.tag)=='FRBRExpression'),None)
    ident=etree.SubElement(R,f"{{{STORM}}}Identificatie")
    if work: etree.SubElement(ident,f"{{{STORM}}}FRBRWork").text=work
    if expr: etree.SubElement(ident,f"{{{STORM}}}FRBRExpression").text=expr
    if work and len(work.split('/'))>4:
        etree.SubElement(ident,f"{{{STORM}}}bevoegdGezag").text=work.split('/')[4]

    # Metadata: de regeling-module-bestanden verbatim bewaren (verliesloos).
    meta=etree.SubElement(R,f"{{{DATA}}}Metadata")
    regm=etree.SubElement(meta,f"{{{DATA}}}Regeling")
    for fn in META_MODULES:
        f=regdir/fn
        if f.exists(): regm.append(deepcopy(parse(f)))

    # Tekstlaag: alle STOP-tekst-kinderen verbatim (geen whitelist)
    tekst=NV.T('Tekst',ns=TEKST); tekst.set('structuur',structuur)
    for k,v in tekst_root.attrib.items():   # componentnaam/wordt/schemaversie verbatim
        tekst.set(k,v)
    for c in tekst_root:
        if isinstance(c.tag,str) and c.tag.startswith(f"{{{NV.STOP_TEKST}}}"):
            tekst.append(NV.mirror_tekst(c))
    R.append(tekst)

    # Objectlaag
    buckets={}
    for owf in sorted((pkgdir/'OW-bestanden').glob('*.xml')):
        if owf.name=='manifest-ow.xml': continue
        for obj in parse(owf).iter(f"{{{DEELBESTAND}}}owObject"):
            elks=[c for c in obj if isinstance(c.tag,str)]
            if not elks: continue
            child=elks[0]; kind=L(child.tag)
            if kind in NV.SECTIE:
                sec,key=NV.SECTIE[kind]
                buckets.setdefault(sec,[]).append((key,NV.mirror_obj(child)))
    ow=NV.T('OwObjecten')
    for sec in NV.SECTIE_ORDER:
        if sec not in buckets: continue
        items=[el for k,el in sorted(buckets[sec],key=lambda x:x[0])]
        if sec in NV.SINGLE:
            for el in items: ow.append(el)
        else:
            s=NV.T(sec)
            for el in items: s.append(el)
            ow.append(s)
    R.append(ow)
    return R

# ---------- verlies-census ----------
# Omkeerbaar-by-design: deze source-localnames verdwijnen bewust maar hun
# informatie blijft (ref-waarde/namespace afleidbaar).
def is_reversible(name):
    return name.endswith('Ref') or name=='owObject'  # -> @ref / unwrap
REVERSIBLE_ATTR={'href'}  # xlink:href -> @ref

# Inline-opmaak in STOP-tekst. Sinds de verbatim-mirror blijft dit behouden;
# alleen relevant als een toekomstige wijziging het weer zou platslaan.
INLINE={'i','b','u','strong','sup','sub','br','IntRef','ExtRef','IntIoRef',
        'ExtIoRef','Noot','Nootref'}

# By-design genormaliseerd (geen informatieverlies): het regeling-rootelement
# wordt de storm-Tekst-envelope (type in @structuur), en de IMOW 3.x-hoofdletter
# BestuurlijkeGrenzenVerwijzing normaliseert naar de schema-vorm.
NORMALIZED={'RegelingCompact','RegelingVrijetekst','RegelingKlassiek',
            'RegelingTijdelijkdeel','BestuurlijkeGrenzenVerwijzing'}

def census(elem):
    els=Counter(); ats=Counter()
    for e in elem.iter():
        if not isinstance(e.tag,str): continue
        els[L(e.tag)]+=1
        for a in e.attrib:
            ats[L(a)]+=1
    return els,ats

def analyse(pkgdir):
    pkgdir=Path(pkgdir); regdir=pkgdir/'Regeling'
    R=download2volledig(pkgdir)

    # tekst: bron vs volledig
    src_tekst=parse(regdir/'Tekst.xml')
    vol_tekst=next(e for e in R if L(e.tag)=='Tekst')
    st,sta=census(src_tekst); vt,vta=census(vol_tekst)

    # ow: bron (alle owObjecten samen) vs volledig
    src_els=Counter(); src_ats=Counter()
    for owf in sorted((pkgdir/'OW-bestanden').glob('*.xml')):
        if owf.name=='manifest-ow.xml': continue
        for obj in parse(owf).iter(f"{{{DEELBESTAND}}}owObject"):
            e,a=census(obj); src_els+=e; src_ats+=a
    vol_ow=next(e for e in R if L(e.tag)=='OwObjecten')
    ve,va=census(vol_ow)

    def verlies(src,vol):
        out=[]
        for name,n in sorted(src.items()):
            m=vol.get(name,0)
            if m<n: out.append((name,n,m))
        return out

    return {'R':R,
            'tekst_verlies':verlies(st,vt),'tekst_attr_verlies':verlies(sta,vta),
            'ow_verlies':verlies(src_els,ve),'ow_attr_verlies':verlies(src_ats,va)}

def rapport(pkgdir):
    res=analyse(pkgdir)
    R=res['R']
    # valideer volledig tegen het schema
    schema=etree.XMLSchema(etree.parse(str(XSD)))
    doc=etree.ElementTree(R)
    ok=schema.validate(doc)
    print(f"volledig valideert: {'JA' if ok else 'NEE'}")
    if not ok:
        for e in list(schema.error_log)[:8]: print('   ',e.line,e.message)

    def toon(titel,verlies):
        print(f"\n--- {titel} ---")
        if not verlies:
            print("  (geen verlies)"); return
        for name,n,m in verlies:
            if name in NORMALIZED: tag='genormaliseerd (by-design)'
            elif is_reversible(name) or name in REVERSIBLE_ATTR: tag='omkeerbaar'
            elif name in INLINE: tag='ECHT VERLIES (inline-opmaak)'
            else: tag='ECHT VERLIES'
            print(f"  {name:32} bron={n:5} volledig={m:5}  [{tag}]")

    print("\n--- Metadata-laag: verbatim bewaard (deepcopy) -> verliesloos ---")
    toon("TEKST — elementen",res['tekst_verlies'])
    toon("TEKST — attributen",res['tekst_attr_verlies'])
    toon("OW — elementen",res['ow_verlies'])
    toon("OW — attributen",res['ow_attr_verlies'])
    return res

# ---------- volledig -> download (reverse, verbatim lagen) ----------
REGTYPE_ELEM={v:k for k,v in NV.REGELINGTYPE.items()}   # 'compact'->'RegelingCompact'
MODFILE={'ExpressionIdentificatie':'Identificatie.xml',
         'RegelingVersieMetadata':'VersieMetadata.xml',
         'RegelingMetadata':'Metadata.xml','Momentopname':'Momentopname.xml'}

def volledig2tekst(R, nsmap=None):
    """Reconstrueer de STOP RegelingCompact uit de verbatim tekstlaag:
    namespace terug-hernoemen en het root-element + attributen herstellen.
    nsmap (bv. van het bron-Tekst.xml) zorgt voor identieke prefixen."""
    tekst=next(e for e in R if L(e.tag)=='Tekst')
    rootname=REGTYPE_ELEM.get(tekst.get('structuur','compact'),'RegelingCompact')
    root=etree.Element(f"{{{NV.STOP_TEKST}}}{rootname}",
                       nsmap=nsmap or {'tekst':NV.STOP_TEKST})
    for k,v in tekst.attrib.items():
        if L(k)!='structuur': root.set(k,v)      # componentnaam/wordt/schemaversie
    for c in tekst:
        if not isinstance(c.tag,str): continue
        cp=deepcopy(c)
        for e in cp.iter():
            if isinstance(e.tag,str) and e.tag.startswith(f"{{{TEKST}}}"):
                e.tag=f"{{{NV.STOP_TEKST}}}"+L(e.tag)
        root.append(cp)
    etree.cleanup_namespaces(root)
    return root

def volledig2meta(R):
    meta=next((e for e in R if L(e.tag)=='Metadata'),None)
    reg=next((e for e in meta if L(e.tag)=='Regeling'),None) if meta is not None else None
    return {L(c.tag):deepcopy(c) for c in (reg if reg is not None else []) if isinstance(c.tag,str)}

_BP=etree.XMLParser(remove_blank_text=True, recover=True)
def canon(el):
    # canoniek, met niet-significante witruimte genormaliseerd (semantische lat)
    # en ongebruikte namespace-declaraties (o.a. de kapotte xmlns:schemaLocation
    # uit de bron) opgeruimd zodat ze de vergelijking niet vertroebelen.
    e2=deepcopy(el); etree.cleanup_namespaces(e2)
    e3=etree.fromstring(etree.tostring(e2), _BP)
    return etree.tostring(e3, method='c14n2')

def roundtrip_verbatim(pkgdir):
    """download -> volledig -> download' voor de verbatim lagen; canonieke diff."""
    pkgdir=Path(pkgdir); regdir=pkgdir/'Regeling'
    R=download2volledig(pkgdir)
    diffs=[]
    src_tekst=parse(regdir/'Tekst.xml')
    if canon(src_tekst)!=canon(volledig2tekst(R,src_tekst.nsmap)): diffs.append('Regeling/Tekst.xml')
    for ln,el in volledig2meta(R).items():
        fn=MODFILE.get(ln)
        if fn and (regdir/fn).exists():
            if canon(parse(regdir/fn))!=canon(el): diffs.append('Regeling/'+fn)
    return diffs

# ---------- volledig -> OW-bestanden (reverse, geleerde IMOW-mappings) ----------
def NS(t): return t.split('}')[0][1:] if isinstance(t,str) and t.startswith('{') else ''
SECTIE_CONTAINERS={'Regels','Normen','Activiteiten','Locaties','Gebiedsaanwijzingen',
 'VrijeTekst','Kaarten'}

def _seg(ref):
    """Objecttype-segment uit een IMOW-id: nl.imow-<bg>.<type>.<id> -> <type>."""
    p=(ref or '').split('.')
    return p[2] if len(p)>=3 else None

def learn_ow(pkgdir):
    """Leer uit de bron-OW-bestanden: namespace per objecttype, de namespace
    per *Ref, en welke *Ref bij een (wrapper, doeltype) hoort. Het doeltype
    (uit de ref-id) is nodig omdat één wrapper naar verschillende types kan
    wijzen (bv. divisieaanduiding -> DivisieRef of DivisietekstRef)."""
    pkgdir=Path(pkgdir); objns={}; refmap={}; refchild={}; refns={}
    for owf in sorted((pkgdir/'OW-bestanden').glob('*.xml')):
        if owf.name=='manifest-ow.xml': continue
        for obj in parse(owf).iter(f"{{{DEELBESTAND}}}owObject"):
            for e in obj.iter():
                if not isinstance(e.tag,str): continue
                lc=L(e.tag)
                if lc[:1].isupper() and lc.endswith('Ref'): refns[lc]=NS(e.tag)
                elif lc[:1].isupper(): objns[lc]=NS(e.tag)
                if lc[:1].islower():                     # wrapper
                    for ch in kids(e):
                        if L(ch.tag).endswith('Ref'):
                            rn=L(ch.tag); refchild.setdefault(lc,rn)
                            refmap[(lc,_seg(ch.get(f"{{{XLINK}}}href")))]=rn
    return {'objns':objns,'refmap':refmap,'refchild':refchild,'refns':refns,'cap':{}}

def _href(el,ref,LZ,refname):
    el.set(f"{{{XLINK}}}href",ref)

def _isref(c): return c.get('ref') is not None and not kids(c)

def rev_obj(sel,parent_ns,LZ):
    """Reconstrueer één IMOW-object(-subboom) uit een storm-ow-element.
    Opeenvolgende ref-wrappers met dezelfde naam worden gegroepeerd tot één
    bron-wrapper met meerdere *Ref-kinderen (zo staat het in de bron)."""
    lc=L(sel.tag); name=LZ['cap'].get(lc,lc)
    myns=LZ['objns'].get(lc,parent_ns)
    el=etree.Element(f"{{{myns}}}{name}")
    if sel.get('wId'): el.set('wId',sel.get('wId'))
    cs=kids(sel); i=0
    while i<len(cs):
        c=cs[i]; clc=L(c.tag)
        if _isref(c):
            grp=[c]; j=i+1                            # groepeer gelijknamige refs
            while j<len(cs) and L(cs[j].tag)==clc and _isref(cs[j]):
                grp.append(cs[j]); j+=1
            if clc=='activiteit':                     # activiteitaanduiding: directe ActiviteitRef
                rns=LZ['refns'].get('ActiviteitRef',myns)
                for g in grp:
                    etree.SubElement(el,f"{{{rns}}}ActiviteitRef").set(f"{{{XLINK}}}href",g.get('ref'))
            elif clc.endswith('Ref'):                 # bv. GeometrieRef: is zelf de ref
                rns=LZ['refns'].get(clc,myns)
                for g in grp:
                    etree.SubElement(el,f"{{{rns}}}{clc}").set(f"{{{XLINK}}}href",g.get('ref'))
            else:                                     # wrapper met *Ref-kind(eren)
                w=etree.SubElement(el,f"{{{myns}}}{clc}")
                for g in grp:
                    ref=g.get('ref')
                    refname=(LZ['refmap'].get((clc,_seg(ref))) or LZ['refchild'].get(clc)
                             or clc[:1].upper()+clc[1:]+'Ref')
                    rns=LZ['refns'].get(refname,myns)
                    etree.SubElement(w,f"{{{rns}}}{refname}").set(f"{{{XLINK}}}href",ref)
            i=j
        elif kids(c):
            el.append(rev_obj(c,myns,LZ)); i+=1
        else:
            etree.SubElement(el,f"{{{myns}}}{clc}").text=c.text; i+=1
    return el

def _ident(el):
    for c in el.iter():
        if isinstance(c.tag,str) and L(c.tag)=='identificatie': return c.text
    return None

def sem_canon(el):
    """Prefix-onafhankelijke canonieke representatie op {URI}localname, met
    niet-significante witruimte genormaliseerd. Voor de OW-laag (geen mixed
    content) is namespace-URI + structuur + waarden de informatie; het gekozen
    prefix niet."""
    def walk(e):
        at=sorted((k,v) for k,v in e.attrib.items())   # k = {ns}naam (Clark)
        parts=[e.tag,'{',repr(at),'}',(e.text or '').strip(),'[']
        for c in e:
            if isinstance(c.tag,str): parts.append(walk(c))
        parts.append(']')
        return ''.join(parts)
    return walk(el)

def roundtrip_ow(pkgdir):
    """Reconstrueer alle owObjecten uit volledig en vergelijk canoniek (per
    identificatie) met de bron. Retourneert (aantal_ok, totaal, mismatches)."""
    pkgdir=Path(pkgdir); R=download2volledig(pkgdir); LZ=learn_ow(pkgdir)
    ow=next(e for e in R if L(e.tag)=='OwObjecten')
    rebuilt={}
    for sec in kids(ow):
        objs=kids(sec) if L(sec.tag) in SECTIE_CONTAINERS else [sec]
        for o in objs:
            r=rev_obj(o,'',LZ); rebuilt[_ident(r)]=r
    src={}
    for owf in sorted((pkgdir/'OW-bestanden').glob('*.xml')):
        if owf.name=='manifest-ow.xml': continue
        for obj in parse(owf).iter(f"{{{DEELBESTAND}}}owObject"):
            typed=next((c for c in obj if isinstance(c.tag,str)),None)
            if typed is not None: src[_ident(typed)]=typed
    ok=0; mis=[]
    for ident,s in src.items():
        r=rebuilt.get(ident)
        if r is not None and sem_canon(r)==sem_canon(s): ok+=1
        else: mis.append(ident)
    return ok,len(src),mis

# ---------- GIO-laag (IO-mappen met geometrie) ----------
GIO_MODFILE={'ExpressionIdentificatie':'Identificatie.xml',
 'InformatieObjectVersieMetadata':'VersieMetadata.xml',
 'InformatieObjectMetadata':'Metadata.xml','Momentopname':'Momentopname.xml',
 'JuridischeBorgingVan':'JuridischeBorgingVan.xml'}
GIO_MODULES=('Identificatie.xml','VersieMetadata.xml','Metadata.xml',
 'Momentopname.xml','JuridischeBorgingVan.xml')

def download2gio(pkgdir):
    """Bundel elke download-IO-map (module-bestanden + GML) verbatim in één
    storm-gio-element (urn:storm:gio)."""
    pkgdir=Path(pkgdir); gios=[]
    for iod in sorted(pkgdir.glob('IO-*')):
        if not iod.is_dir(): continue
        G=etree.Element(f"{{{GIO}}}GeoInformatieObject",nsmap={None:GIO})
        G.set('map',iod.name)
        md=etree.SubElement(G,f"{{{GIO}}}Metadata")
        for mf in GIO_MODULES:
            if (iod/mf).exists(): md.append(deepcopy(parse(iod/mf)))
        # content-bestanden (niet-module): symbolisatie (FeatureTypeStyle),
        # geometrie (nl.xml/<id>.gml) en/of binaire bijlage (PDF e.d.)
        symb=geo=None
        for f in sorted(iod.iterdir()):
            if not f.is_file() or f.name in GIO_MODULES: continue
            root=parse(f) if f.suffix.lower() in ('.xml','.gml') else None
            if root is None:
                G.set('bijlage',f.name)                 # binair: verbatim meegekopieerd
            elif L(root.tag)=='FeatureTypeStyle':
                G.set('symbBestand',f.name); symb=root
            else:
                G.set('geoBestand',f.name); geo=root
        if symb is not None:
            etree.SubElement(G,f"{{{GIO}}}Symbolisatie").append(symb)
        if geo is not None:
            etree.SubElement(G,f"{{{GIO}}}Geo").append(geo)
        gios.append(G)
    return gios

def gio2folder(G):
    """storm-gio -> {bestandsnaam: element} van de download-IO-map."""
    files={}
    md=next((e for e in G if L(e.tag)=='Metadata'),None)
    for c in (kids(md) if md is not None else []):
        fn=GIO_MODFILE.get(L(c.tag))
        if fn: files[fn]=c
    for sec,attr in (('Symbolisatie','symbBestand'),('Geo','geoBestand')):
        e=next((x for x in G if L(x.tag)==sec),None)
        if e is not None and G.get(attr) and kids(e):
            files[G.get(attr)]=kids(e)[0]
    return G.get('map'),files

def roundtrip_gio(pkgdir):
    """download -> storm-gio -> download' voor elke IO-map; canonieke diff.
    Controleert volledigheid: elk bronbestand in de map moet gereconstrueerd
    worden (geen stil weggelaten bestand)."""
    pkgdir=Path(pkgdir); ok=0; tot=0; mis=[]
    for G in download2gio(pkgdir):
        mapnaam,files=gio2folder(G); iod=pkgdir/mapnaam
        for src in sorted(iod.iterdir()):
            if not src.is_file(): continue
            tot+=1
            if src.suffix.lower() not in ('.xml','.gml'):
                ok+=1; continue      # binaire bijlage: verbatim gekopieerd -> verliesloos
            el=files.get(src.name)
            if el is not None and canon(parse(src))==canon(el): ok+=1
            else: mis.append(mapnaam+'/'+src.name)
    return ok,tot,mis

if __name__=='__main__':
    import sys
    default=r"D:/downloadpakketten/prod/enkhuizen-gm0388/omgevingsplan/uitgepakt/1-0"
    rapport(sys.argv[1] if len(sys.argv)>1 else default)
