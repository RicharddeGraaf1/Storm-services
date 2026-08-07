"""Vind het pakket waar compact->integrated een ValueError gooit (regel-op-lid),
en toon de overtreding: staat er in de compact-data echt een JuridischeRegel op
een Artikel dat leden heeft?"""
import sys, re, zipfile, tempfile, shutil
from pathlib import Path
from lxml import etree
import download_roundtrip as dr, volledig_compact as vc, compact_integrated as ci
CORPUS = Path(r"C:\GIT\OCD\dso-loader\data\downloads\ow")
def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t
def ch(e,n): return next((c for c in e if isinstance(c.tag,str) and L(c.tag)==n),None)
def ct(e,n):
    c=ch(e,n); return c.text if c is not None else None
def mk_vol(pkg,vol):
    R=dr.download2volledig(pkg)
    etree.ElementTree(R).write(str(vol/"storm-volledig.xml"),xml_declaration=True,encoding="UTF-8",pretty_print=True)
    for G in dr.download2gio(pkg):
        frbr=next((e.text for e in G.iter() if L(e.tag)=='FRBRWork'),None)
        nm=re.sub(r'[^\w.-]','_',(frbr.rstrip('/').split('/')[-1].split('@')[0] if frbr else G.get('map','gio')) or 'gio')
        etree.ElementTree(G).write(str(vol/f"{nm}.storm-gio.xml"),xml_declaration=True,encoding="UTF-8")

n=int(sys.argv[1]) if len(sys.argv)>1 else 16
for z in sorted(CORPUS.glob("*.zip"))[:n]:
    work=Path(tempfile.mkdtemp())
    try:
        pkg=work/"pkg"; zipfile.ZipFile(z).extractall(pkg)
        if not any(pkg.glob("Regeling*")) and not any(pkg.glob("IO-*")):
            subs=[p for p in pkg.iterdir() if p.is_dir()]
            if len(subs)==1: pkg=subs[0]
        vol=work/"vol"; vol.mkdir(); mk_vol(pkg,vol)
        C=vc.transform(vol); cpad=work/"c.xml"
        etree.ElementTree(C).write(str(cpad),xml_declaration=True,encoding="UTF-8",pretty_print=True)
        try:
            ci.transform(cpad)
        except ValueError as e:
            print(f"\n[ValueError] {z.name}\n  {e}\n")
            # zoek in de compact-data: welke regeltekst-wId, en heeft dat artikel leden?
            m=re.search(r'Artikel (\S+)', str(e))
            wid=m.group(1) if m else None
            root=etree.parse(str(cpad)).getroot()
            # tel hoeveel JuridischeRegels op dezelfde artikelOfLid-ref hangen
            tekst=ch(root,'Tekst')
            # vind het artikel met die wId in de tekstlaag
            art=next((e for e in root.iter() if isinstance(e.tag,str) and L(e.tag)=='Artikel' and e.get('wId')==wid),None)
            if art is not None:
                leden=[c for c in art if isinstance(c.tag,str) and L(c.tag)=='Lid']
                alineas=[c for c in art if isinstance(c.tag,str) and L(c.tag) in ('Al','Inhoud')]
                print(f"  Artikel {wid}: {len(leden)} Lid-kinderen, {len(alineas)} eigen Al/Inhoud")
                print(f"  -> {'artikel MET leden dat OOK eigen inhoud+regel heeft' if leden and alineas else 'onduidelijk'}")
            # hoeveel JR's op deze regeltekst?
            rt=next((e for e in root.iter() if isinstance(e.tag,str) and L(e.tag)=='Regeltekst' and e.get('wId')==wid),None)
            rtid=ct(rt,'identificatie') if rt is not None else None
            jrs=[e for e in root.iter() if isinstance(e.tag,str) and L(e.tag)=='JuridischeRegel'
                 and (ch(e,'artikelOfLid') is not None and ch(e,'artikelOfLid').get('ref')==rtid)]
            print(f"  JuridischeRegels op regeltekst {rtid}: {len(jrs)}")
            break
    finally:
        shutil.rmtree(work,ignore_errors=True)
