"""Karakteriseer de wId-diff: waar wijkt compact' af van compact na de
compact->integrated->compact roundtrip? Cluster de verschillen op patroon om
toelichting-gap vs echte uId<->wId-reassemblage-bug te scheiden."""
import sys, re, zipfile, tempfile, shutil
from collections import Counter
from pathlib import Path
from lxml import etree
import download_roundtrip as dr, volledig_compact as vc, compact_integrated as ci, integrated_compact as ic
CORPUS = Path(r"C:\GIT\OCD\dso-loader\data\downloads\ow")
def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t
def wids(root): return set(e.get('wId') for e in root.iter() if isinstance(e.tag,str) and e.get('wId'))
def mk_vol(pkg,vol):
    R=dr.download2volledig(pkg)
    etree.ElementTree(R).write(str(vol/"storm-volledig.xml"),xml_declaration=True,encoding="UTF-8",pretty_print=True)
    for G in dr.download2gio(pkg):
        frbr=next((e.text for e in G.iter() if L(e.tag)=='FRBRWork'),None)
        nm=re.sub(r'[^\w.-]','_',(frbr.rstrip('/').split('/')[-1].split('@')[0] if frbr else G.get('map','gio')) or 'gio')
        etree.ElementTree(G).write(str(vol/f"{nm}.storm-gio.xml"),xml_declaration=True,encoding="UTF-8")
def pat(w):
    if w.startswith('uid-'): return 'uid-NNNN (Alinea/Cel-ruis)'
    if '__' not in w: return 'top-level (geen prefix)'
    seg=w.split('__',1)[1].split('__')[0]
    return re.sub(r'\d+','N',seg.split('_')[0]) or seg   # eerste eId-segment, cijfers -> N

z=sorted(CORPUS.glob("*.zip"))[int(sys.argv[1]) if len(sys.argv)>1 else 2]
work=Path(tempfile.mkdtemp())
try:
    pkg=work/"pkg"; zipfile.ZipFile(z).extractall(pkg)
    if not any(pkg.glob("Regeling*")) and not any(pkg.glob("IO-*")):
        subs=[p for p in pkg.iterdir() if p.is_dir()]
        if len(subs)==1: pkg=subs[0]
    vol=work/"vol"; vol.mkdir(); mk_vol(pkg,vol)
    C=vc.transform(vol); cpad=work/"c.xml"
    etree.ElementTree(C).write(str(cpad),xml_declaration=True,encoding="UTF-8",pretty_print=True)
    I=ci.transform(cpad); ipad=work/"i.xml"
    etree.ElementTree(I).write(str(ipad),xml_declaration=True,encoding="UTF-8",pretty_print=True)
    Cx=ic.transform(ipad)
    a,b=wids(C),wids(Cx)
    print(f"pakket: {z.name}")
    print(f"wIds C={len(a)}  C'={len(b)}   alleen-in-C={len(a-b)}  alleen-in-C'={len(b-a)}\n")
    print("== alleen in origineel C (verloren/veranderd) — geclusterd ==")
    for p,c in Counter(pat(w) for w in (a-b)).most_common(12): print(f"  {c:>5}x  {p}")
    print("\n== alleen in roundtrip C' (nieuw/veranderd) — geclusterd ==")
    for p,c in Counter(pat(w) for w in (b-a)).most_common(12): print(f"  {c:>5}x  {p}")
    print("\n== voorbeelden (paar echte strings) ==")
    for w in sorted(a-b)[:4]: print("  C :", w)
    for w in sorted(b-a)[:4]: print("  C':", w)
finally:
    shutil.rmtree(work,ignore_errors=True)
