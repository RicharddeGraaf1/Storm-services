"""Diagnose: run download->volledig->compact op de eerste paar pakketten en dump
de storm-compact schema-fouten van het eerste INVALID-pakket (geclusterd)."""
import sys, re, zipfile, tempfile, shutil
from collections import Counter
from pathlib import Path
from lxml import etree
import download_roundtrip as dr, volledig_compact as vc

XSD = Path(r"C:\GIT\Storm\standaard\xsd")
SCH = etree.XMLSchema(etree.parse(str(XSD / "storm-compact.xsd")))
CORPUS = Path(r"C:\GIT\OCD\dso-loader\data\downloads\ow")
def L(t): return t.split('}')[-1] if isinstance(t, str) and '}' in t else t

def mk_vol(pkg, vol):
    R = dr.download2volledig(pkg)
    etree.ElementTree(R).write(str(vol/"storm-volledig.xml"), xml_declaration=True, encoding="UTF-8", pretty_print=True)
    for G in dr.download2gio(pkg):
        frbr = next((e.text for e in G.iter() if L(e.tag)=='FRBRWork'), None)
        nm = re.sub(r'[^\w.-]', '_', (frbr.rstrip('/').split('/')[-1].split('@')[0] if frbr else G.get('map','gio')) or 'gio')
        etree.ElementTree(G).write(str(vol/f"{nm}.storm-gio.xml"), xml_declaration=True, encoding="UTF-8")

def main():
    filt = next((a.split("=",1)[1] for a in sys.argv[1:] if a.startswith("--filter=")), None)
    n = next((int(a) for a in sys.argv[1:] if a.isdigit()), 8)
    zips = sorted(CORPUS.glob("*.zip"))
    if filt: zips = [z for z in zips if filt.lower() in z.name.lower()]
    for z in zips[:n]:
        work = Path(tempfile.mkdtemp(prefix="diag_"))
        try:
            pkg = work/"pkg"; zipfile.ZipFile(z).extractall(pkg)
            if not any(pkg.glob("Regeling*")) and not any(pkg.glob("IO-*")):
                subs=[p for p in pkg.iterdir() if p.is_dir()]
                if len(subs)==1: pkg=subs[0]
            vol = work/"vol"; vol.mkdir(); mk_vol(pkg, vol)
            C = vc.transform(vol)
            if SCH.validate(etree.ElementTree(C)):
                print(f"[valid ] {z.name[:50]}")
                continue
            print(f"\n[INVALID] {z.name}\n{'='*70}")
            # cluster de fouten op (element, kernboodschap)
            clust = Counter()
            for e in SCH.error_log:
                msg = re.sub(r"'[^']*'", "'X'", e.message)          # normaliseer waarden
                clust[msg] += 1
            for msg, c in clust.most_common(20):
                print(f"  {c:>4}x  {msg[:150]}")
            return
        finally:
            shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    main()
