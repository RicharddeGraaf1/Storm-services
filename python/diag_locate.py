"""Lokaliseer verloren tekst in compact: welke container laat het vallen?
Zoekt een tekstfragment in C, toont de voorouder-keten (met eId/wId), en checkt
of dat element in Cx voorkomt."""
import sys, re, zipfile, tempfile, shutil
from pathlib import Path
from lxml import etree
import download_roundtrip as dr, volledig_compact as vc, compact_integrated as ci, integrated_compact as ic
CORPUS = Path(r"C:\GIT\OCD\dso-loader\data\downloads\ow")
def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t
def ch(e,n): return next((c for c in e if isinstance(c.tag,str) and L(c.tag)==n),None)
def mk_vol(pkg,vol):
    R=dr.download2volledig(pkg)
    etree.ElementTree(R).write(str(vol/"storm-volledig.xml"),xml_declaration=True,encoding="UTF-8",pretty_print=True)
    for G in dr.download2gio(pkg):
        frbr=next((e.text for e in G.iter() if L(e.tag)=='FRBRWork'),None)
        nm=re.sub(r'[^\w.-]','_',(frbr.rstrip('/').split('/')[-1].split('@')[0] if frbr else G.get('map','gio')) or 'gio')
        etree.ElementTree(G).write(str(vol/f"{nm}.storm-gio.xml"),xml_declaration=True,encoding="UTF-8")

arg1=sys.argv[1] if len(sys.argv)>1 else "5"
frag=sys.argv[2] if len(sys.argv)>2 else "begripsbepalingen"
allz=sorted(CORPUS.glob("*.zip"))
z=allz[int(arg1)] if arg1.isdigit() else next(x for x in allz if arg1.lower() in x.name.lower())
work=Path(tempfile.mkdtemp())
try:
    pkg=work/"pkg"; zipfile.ZipFile(z).extractall(pkg)
    if not any(pkg.glob("Regeling*")) and not any(pkg.glob("IO-*")):
        subs=[p for p in pkg.iterdir() if p.is_dir()]
        if len(subs)==1: pkg=subs[0]
    vol=work/"vol"; vol.mkdir(); mk_vol(pkg,vol)
    C=vc.transform(vol); cpad=work/"c.xml"; etree.ElementTree(C).write(str(cpad),xml_declaration=True,encoding="UTF-8",pretty_print=True)
    I=ci.transform(cpad); ipad=work/"i.xml"; etree.ElementTree(I).write(str(ipad),xml_declaration=True,encoding="UTF-8",pretty_print=True)
    Cx=ic.transform(ipad)
    print(f"pakket: {z.name}\nzoekterm: {frag!r}\n")
    # vind het element in C waarvan de tekst het fragment bevat
    parents={c:p for p in C.iter() for c in p}
    hit=None
    for e in C.iter():
        if isinstance(e.tag,str) and e.text and frag in e.text:
            hit=e; break
    if hit is None:
        # diepste element (kortste itertext) dat het fragment bevat
        best=None
        for e in C.iter():
            if isinstance(e.tag,str):
                it=''.join(e.itertext())
                if frag in it and (best is None or len(it)<len(''.join(best.itertext()))):
                    best=e
        hit=best
    if hit is None:
        print("fragment niet gevonden in C"); raise SystemExit
    # voorouder-keten
    chain=[]; cur=hit
    while cur is not None:
        chain.append((L(cur.tag), cur.get('eId'), cur.get('wId')))
        cur=parents.get(cur)
    print("voorouder-keten (binnenste eerst):")
    for tag,eid,wid in chain:
        print(f"  {tag:<16} eId={eid} wId={wid}")
    # zit de dichtstbijzijnde wId-voorouder in Cx?
    cxwids={e.get('wId') for e in Cx.iter() if isinstance(e.tag,str) and e.get('wId')}
    print("\nwId-voorouders en of ze in Cx staan:")
    for tag,eid,wid in chain:
        if wid: print(f"  {tag:<16} wId={wid}  -> {'in Cx' if wid in cxwids else 'WEG uit Cx'}")
finally:
    shutil.rmtree(work,ignore_errors=True)
