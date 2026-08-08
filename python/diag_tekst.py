"""Karakteriseer de tekst-FAIL: dump het eerste verschil tussen compact en
compact' (na de compact->integrated->compact roundtrip) op één klein pakket."""
import sys, re, zipfile, tempfile, shutil, difflib
from pathlib import Path
from lxml import etree
import download_roundtrip as dr, volledig_compact as vc, compact_integrated as ci, integrated_compact as ic
CORPUS = Path(r"C:\GIT\OCD\dso-loader\data\downloads\ow")
def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t
def tekst_van(root):
    tek=next((c for c in root.iter() if L(c.tag)=='Tekst'),None)
    return re.sub(r'\s+',' ',''.join(tek.itertext())).strip() if tek is not None else ''
def mk_vol(pkg,vol):
    R=dr.download2volledig(pkg)
    etree.ElementTree(R).write(str(vol/"storm-volledig.xml"),xml_declaration=True,encoding="UTF-8",pretty_print=True)
    for G in dr.download2gio(pkg):
        frbr=next((e.text for e in G.iter() if L(e.tag)=='FRBRWork'),None)
        nm=re.sub(r'[^\w.-]','_',(frbr.rstrip('/').split('/')[-1].split('@')[0] if frbr else G.get('map','gio')) or 'gio')
        etree.ElementTree(G).write(str(vol/f"{nm}.storm-gio.xml"),xml_declaration=True,encoding="UTF-8")

z=sorted(CORPUS.glob("*.zip"))[int(sys.argv[1]) if len(sys.argv)>1 else 1]
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
    import re as _re
    a=_re.sub(r'\s+','',tekst_van(C)); b=_re.sub(r'\s+','',tekst_van(Cx))   # als harness: witruimte weg
    print(f"pakket: {z.name}\nlen C={len(a)}  len C'={len(b)}  (witruimte verwijderd)\n")
    sm=difflib.SequenceMatcher(None,a,b)
    n=0
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag!='equal':
            print(f"[{tag}] C  ={a[i1:i2][:160]!r}")
            print(f"       C' ={b[j1:j2][:160]!r}\n")
            n+=1
            if n>=6: break
finally:
    shutil.rmtree(work,ignore_errors=True)
