"""Welke elementen vallen weg in compact->integrated->compact'? Toont de
elementtypes achter de verloren wId's en de verloren tekst-fragmenten, zodat we
de accepted-drops-allowlist kunnen opstellen."""
import sys, re, zipfile, tempfile, shutil, difflib
from collections import Counter
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
def tekst_toks(root):
    tek=next((c for c in root.iter() if L(c.tag)=='Tekst'),None)
    return ''.join(tek.itertext()) if tek is not None else ''

n=int(sys.argv[1]) if len(sys.argv)>1 else 8
gezien_drop=Counter(); gezien_pkg=0
for z in sorted(CORPUS.glob("*.zip"))[:n]:
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
        # verloren wId's -> elementtype
        aw={e.get('wId'):L(e.tag) for e in C.iter() if isinstance(e.tag,str) and e.get('wId')}
        bw={e.get('wId') for e in Cx.iter() if isinstance(e.tag,str) and e.get('wId')}
        verloren=[aw[w] for w in aw if w not in bw and not w.startswith('uid-')]
        if not verloren: continue
        gezien_pkg+=1
        for t in verloren: gezien_drop[t]+=1
        if gezien_pkg<=2:
            print(f"\n[{z.name}]  verloren wId-elementtypes: {dict(Counter(verloren))}")
            # eerste verloren tekst-fragment
            a,b=tekst_toks(C),tekst_toks(Cx)
            sm=difflib.SequenceMatcher(None,re.sub(r'\s+',' ',a),re.sub(r'\s+',' ',b))
            for tag,i1,i2,j1,j2 in sm.get_opcodes():
                if tag in ('delete','replace') and (i2-i1)>3:
                    print(f"   verloren tekst: {re.sub(chr(92)+'s+',' ',a)[i1:i2][:140]!r}"); break
    finally:
        shutil.rmtree(work,ignore_errors=True)
print(f"\n== samen over {gezien_pkg} pakketten met drops: verloren elementtypes ==")
for t,c in gezien_drop.most_common(): print(f"  {c:>5}x  {t}")
