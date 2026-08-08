"""Vind het eerste pakket met een groot tekst-verlies (>2000) en toon het eerste
grote verloren fragment + zijn container-keten (welk elementtype zakt weg)."""
import sys, re, zipfile, tempfile, shutil, difflib
from pathlib import Path
from lxml import etree
import download_roundtrip as dr, volledig_compact as vc, compact_integrated as ci, integrated_compact as ic
CORPUS = Path(r"C:\GIT\OCD\dso-loader\data\downloads\ow")
def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t
def mk_vol(pkg,vol):
    R=dr.download2volledig(pkg)
    etree.ElementTree(R).write(str(vol/"storm-volledig.xml"),xml_declaration=True,encoding="UTF-8",pretty_print=True)
    for G in dr.download2gio(pkg):
        frbr=next((e.text for e in G.iter() if L(e.tag)=='FRBRWork'),None)
        nm=re.sub(r'[^\w.-]','_',(frbr.rstrip('/').split('/')[-1].split('@')[0] if frbr else G.get('map','gio')) or 'gio')
        etree.ElementTree(G).write(str(vol/f"{nm}.storm-gio.xml"),xml_declaration=True,encoding="UTF-8")
def tekst(root):
    tek=next((c for c in root.iter() if L(c.tag)=='Tekst'),None)
    return ''.join(tek.itertext()) if tek is not None else ''

import roundtrip_harness as rh
n=int(sys.argv[1]) if len(sys.argv)>1 else 20
for z in rh.kies_pakketten(n):   # zelfde diverse selectie als de harness
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
        a=re.sub(r'\s+','',tekst(C)); b=re.sub(r'\s+','',tekst(Cx))
        if abs(len(a)-len(b))<250: continue
        print(f"\n[groot verlies] {z.name}  (C={len(a)} Cx={len(b)} d={len(a)-len(b)})")
        # eerste grote verloren fragment
        frag=None
        for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(None,a,b).get_opcodes():
            if tag in('delete','replace') and (i2-i1)>40: frag=a[i1:i1+60]; break
        if not frag: print("  geen groot fragment gevonden"); break
        print(f"  verloren fragment: {frag!r}")
        # zoek dit fragment (met spaties) in C en toon de container-keten
        raw=re.sub(r'\s+',' ',tekst(C)); pos=raw.replace(' ','').find(frag)
        # simpeler: zoek een uniek woord uit het fragment in C-elementen
        woord=frag[:20]
        pars={c:p for p in C.iter() for c in p}
        hit=next((e for e in C.iter() if isinstance(e.tag,str) and woord in re.sub(r'\s+','',''.join(e.itertext()))),None)
        if hit is not None:
            chain=[]; cur=hit
            for _ in range(8):
                if cur is None: break
                wid=cur.get('wId') or ''
                chain.append(f"{L(cur.tag)}{('['+wid+']') if wid else ''}")
                cur=pars.get(cur)
            print("  container-keten:", ' < '.join(chain))
            cxwids={e.get('wId') for e in Cx.iter() if isinstance(e.tag,str) and e.get('wId')}
            for cur in [hit]:
                pass
            # dichtstbijzijnde wId-voorouder in Cx?
            cur=hit
            while cur is not None:
                if cur.get('wId'):
                    print(f"  dichtstbijzijnde wId-voorouder {L(cur.tag)}[{cur.get('wId')}] -> {'in Cx' if cur.get('wId') in cxwids else 'WEG uit Cx'}")
                    break
                cur=pars.get(cur)
        break
    finally:
        shutil.rmtree(work,ignore_errors=True)
