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

STORM=NV.STORM; TEKST=NV.TEKST; OW=NV.OW; DATA=NV.DATA
XSI=NV.XSI; XSD_URL=NV.XSD_URL
DEELBESTAND="http://www.geostandaarden.nl/imow/bestanden/deelbestand"
XLINK="http://www.w3.org/1999/xlink"
XSD=Path(r"C:\GIT\Storm\standaard\xsd\storm-volledig.xsd")

# De prod-OW-bestanden bevatten een kapotte xmlns:schemaLocation -> recover.
P=etree.XMLParser(recover=True, remove_blank_text=False)
def parse(p): return etree.parse(str(p),P).getroot()
def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t

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

if __name__=='__main__':
    import sys
    default=r"/d/downloadpakketten/prod/enkhuizen-gm0388/omgevingsplan/uitgepakt/1-0"
    rapport(sys.argv[1] if len(sys.argv)>1 else default)
