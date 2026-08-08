"""Traceer 'Eerste lid' door C -> I -> Cx: in welk element zit het, en waar valt
het weg (forward of reverse)?"""
import sys, re, zipfile, tempfile, shutil
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

idx=int(sys.argv[1]) if len(sys.argv)>1 else 5
frag=sys.argv[2] if len(sys.argv)>2 else "Eerste lid"
z=sorted(CORPUS.glob("*.zip"))[idx]
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
    def zoek(tree,naam):
        pars={c:p for p in tree.iter() for c in p}
        for e in tree.iter():
            if isinstance(e.tag,str) and e.text and frag in e.text:
                chain=[]; cur=e
                for _ in range(6):
                    if cur is None: break
                    chain.append(L(cur.tag)+(f"[{cur.get('wId') or cur.get('uId') or ''}]" if (cur.get('wId') or cur.get('uId')) else ""))
                    cur=pars.get(cur)
                print(f"  {naam}: {' < '.join(chain)}")
                return True
        print(f"  {naam}: NIET gevonden"); return False
    print(f"pakket: {z.name}  zoekterm: {frag!r}\n")
    zoek(C,"C ")
    zoek(I,"I ")
    zoek(Cx,"Cx")
finally:
    shutil.rmtree(work,ignore_errors=True)
