"""Roundtrip-harness over een corpus downloadpakketten.

Test de twee INVERTEERBARE roundtrips (compact->volledig bestaat niet: compact is
de lossy afvoerput), per as gediff't en gecategoriseerd:

  1. download <-> volledig        (verliesvrij; hergebruikt download_roundtrip.py)
       - verbatim tekstlaag, OW-objecten (sem_canon), GIO's
  2. compact  <-> integrated      (verliesvrij op de inherente n:1->1:1 na)
       - compact vs compact'  : structurele wId (byte-exact), tekst, activiteit-trio
       - integrated vs integrated' : marks + uId-stabiliteit

Forward-only tussenstap volledig->compact wordt op schema-validiteit gecheckt.

Gebruik:
  python roundtrip_harness.py [N] [--filter=substr] [--corpus=DIR]
  N        aantal pakketten (default 16, divers gekozen); 0 = alle
"""
import sys, re, zipfile, tempfile, shutil, traceback, copy
from collections import Counter
from pathlib import Path
from lxml import etree

# Elementtypes die compact<->integrated nu nog niet round-trippt (bekende gaten).
# De harness snoeit deze uit C weg vóór de wId/tekst-diff, zodat een resterend
# verschil een ECHTE afwijking is ("gaat de rest goed?"). Dit is tevens de TODO-lijst.
ACCEPTED_DROPS = {'Conditie', 'Kadertekst'}

import download_roundtrip as dr
import volledig_compact as vc
import compact_integrated as ci
import integrated_compact as ic

XSD_DIR = Path(r"C:\GIT\Storm\standaard\xsd")
SCHEMA = {n: etree.XMLSchema(etree.parse(str(XSD_DIR / f"storm-{n}.xsd")))
          for n in ("compact", "integrated")}
CORPUS = Path(r"C:\GIT\OCD\dso-loader\data\downloads\ow")

def L(t): return t.split('}')[-1] if isinstance(t, str) and '}' in t else t

# ---------- diverse steekproef ----------
def kies_pakketten(n, filt=None):
    zips = sorted(CORPUS.glob("*.zip"))
    if filt: zips = [z for z in zips if filt.lower() in z.name.lower()]
    if n == 0: return zips
    # divers: verdeel over documenttype-hints en bevoegd-gezag-prefix
    buckets = {"voorbereidingsbesluit": [], "programma": [], "visie": [],
               "omgevingsplan": [], "verordening": [], "overig": []}
    for z in zips:
        nm = z.name.lower()
        key = next((k for k in buckets if k in nm), "overig")
        buckets[key].append(z)
    uit, i = [], 0
    while len(uit) < n and any(buckets.values()):
        for k in list(buckets):
            if buckets[k]:
                uit.append(buckets[k].pop(0))
                if len(uit) >= n: break
        i += 1
        if i > n + 5: break
    return uit[:n]

# ---------- diff-assen ----------
def wids(root, struct_only=True):
    ws = set(e.get('wId') for e in root.iter() if isinstance(e.tag, str) and e.get('wId'))
    return {w for w in ws if not struct_only or not w.startswith('uid-')}

def tekst_van(root):
    # witruimte-ONgevoelig: STOP-content is de woorden; inter-element-witruimte
    # (bv. rond Kop-nummers) is incidenteel en verschilt onschuldig per serialisatie.
    tek = next((c for c in root.iter() if L(c.tag) == 'Tekst'), None)
    return re.sub(r'\s+', '', ''.join(tek.itertext())) if tek is not None else ''

def trio(root):
    d = {}
    for aa in root.iter():
        if L(aa.tag) != 'activiteitaanduiding': continue
        ident = next((c.text for c in aa if L(c.tag) == 'identificatie'), None)
        d[ident or etree.tostring(aa)] = re.sub(r'\s+', ' ', etree.tostring(aa, encoding='unicode'))
    return d

def marks(root):
    return sorted(etree.tostring(m, encoding='unicode').strip()
                  for m in root.iter() if L(m.tag) == 'Mark'
                  and m.get('kind') in ('activiteitRef', 'regelkwalificatie'))

def diff_keyed(a, b):
    ov = set(a) & set(b)
    gelijk = sum(a[k] == b[k] for k in ov)
    return len(a), len(b), len(ov), gelijk, sorted(set(a) - set(b))[:3]

def prune(root):
    """Verwijder de subtrees van de ACCEPTED_DROPS-types, zodat de vergelijking
    alleen de wél-gedragen elementen toetst."""
    r = copy.deepcopy(root)
    for parent in list(r.iter()):
        for c in [x for x in parent if isinstance(x.tag, str) and L(x.tag) in ACCEPTED_DROPS]:
            parent.remove(c)
    return r

# ---------- per pakket ----------
def verwerk(zippad, work):
    r = {"pakket": zippad.name}
    pkg = work / "pkg"
    with zipfile.ZipFile(zippad) as z: z.extractall(pkg)
    # sommige pakketten hebben een enkele submap
    if not any(pkg.glob("Regeling*")) and not any(pkg.glob("IO-*")):
        subs = [p for p in pkg.iterdir() if p.is_dir()]
        if len(subs) == 1: pkg = subs[0]

    # --- as 1: download <-> volledig ---
    try:
        vb = dr.roundtrip_verbatim(pkg)
        ok_ow, n_ow, mis_ow = dr.roundtrip_ow(pkg)
        ok_gio, n_gio, mis_gio = dr.roundtrip_gio(pkg)
        r["dl_verbatim"] = "OK" if not vb else f"FAIL({len(vb)})"
        r["dl_ow"] = f"{n_ow-len(mis_ow)}/{n_ow}"
        r["dl_gio"] = f"{n_gio-len(mis_gio)}/{n_gio}"
    except Exception as e:
        r["dl_verbatim"] = f"ERR:{type(e).__name__}"; return r

    # --- materialiseer volledig-dir (met gio's) voor volledig_compact ---
    vol = work / "vol"; vol.mkdir()
    R = dr.download2volledig(pkg)
    etree.ElementTree(R).write(str(vol / "storm-volledig.xml"), xml_declaration=True,
                               encoding="UTF-8", pretty_print=True)
    for G in dr.download2gio(pkg):
        frbr = next((e.text for e in G.iter() if L(e.tag) == 'FRBRWork'), None)
        naam = (frbr.rstrip('/').split('/')[-1].split('@')[0] if frbr else G.get('map', 'gio'))
        naam = re.sub(r'[^\w.-]', '_', naam or 'gio')
        etree.ElementTree(G).write(str(vol / f"{naam}.storm-gio.xml"),
                                   xml_declaration=True, encoding="UTF-8")

    # --- volledig -> compact (forward-only; validatie) ---
    try:
        C = vc.transform(vol)
    except Exception as e:
        r["v2c"] = f"ERR:{type(e).__name__}"; return r
    r["v2c"] = "valid" if SCHEMA["compact"].validate(etree.ElementTree(C)) else "INVALID"
    cpad = work / "compact.xml"
    etree.ElementTree(C).write(str(cpad), xml_declaration=True, encoding="UTF-8", pretty_print=True)

    # --- compact -> integrated -> compact' -> integrated' ---
    try:
        I = ci.transform(cpad)
    except Exception as e:
        r["c2i"] = f"ERR:{type(e).__name__}"; return r
    r["c2i"] = "valid" if SCHEMA["integrated"].validate(etree.ElementTree(I)) else "INVALID"
    if ci.regel_op_artikel:
        r["c2i"] += f"+{len(ci.regel_op_artikel)}roa"   # regel-op-artikel geflagd (geen crash)
    ipad = work / "integrated.xml"
    etree.ElementTree(I).write(str(ipad), xml_declaration=True, encoding="UTF-8", pretty_print=True)
    Cx = ic.transform(ipad)
    cxpad = work / "compact2.xml"
    etree.ElementTree(Cx).write(str(cxpad), xml_declaration=True, encoding="UTF-8", pretty_print=True)
    Ix = ci.transform(cxpad)

    # --- assen compact <-> integrated (snoei de accepted-drops uit BEIDE kanten:
    #     ze worden niet netjes gedropt maar soms gemangeld, dus uit C én Cx weg) ---
    Cp, Cxp = prune(C), prune(Cx)
    wa, wb = wids(Cp), wids(Cxp)
    r["wId"] = "OK" if wa == wb else f"d{len(wa ^ wb)}"
    r["tekst"] = "OK" if tekst_van(Cp) == tekst_van(Cxp) else "FAIL"
    drops = Counter(L(e.tag) for e in C.iter()
                    if isinstance(e.tag, str) and L(e.tag) in ACCEPTED_DROPS)
    r["drops"] = ",".join(f"{k[:3]}{v}" for k, v in drops.most_common(3)) or "-"
    ta, tb, tov, tgel, _ = diff_keyed(trio(C), trio(Cx))
    r["trio"] = f"{tgel}/{tov}" + (f" (n:1 {ta}->{tb})" if ta != tb else "")
    ma, mb = marks(I), marks(Ix)
    r["marks"] = "OK" if ma == mb else f"{len(ma)}!={len(mb)}"
    return r

# ---------- main ----------
def main():
    n = 16; filt = None
    for a in sys.argv[1:]:
        if a.startswith("--filter="): filt = a.split("=", 1)[1]
        elif a.startswith("--corpus="): globals()["CORPUS"] = Path(a.split("=", 1)[1])
        elif a.isdigit(): n = int(a)
    pakketten = kies_pakketten(n, filt)
    print(f"corpus: {CORPUS}  |  steekproef: {len(pakketten)} pakketten\n")
    cols = ["pakket", "dl_verbatim", "dl_ow", "dl_gio", "v2c", "c2i", "wId", "tekst", "trio", "marks", "drops"]
    print("  ".join(f"{c:<14}" if c == "pakket" else f"{c:<11}" for c in cols))
    rijen = []
    for z in pakketten:
        work = Path(tempfile.mkdtemp(prefix="rt_"))
        try:
            r = verwerk(z, work)
        except Exception as e:
            r = {"pakket": z.name, "dl_verbatim": f"CRASH:{type(e).__name__}"}
            traceback.print_exc()
        finally:
            shutil.rmtree(work, ignore_errors=True)
        rijen.append(r)
        naam = r["pakket"][:14]
        print("  ".join(f"{naam:<14}" if c == "pakket" else f"{str(r.get(c,'-')):<11}" for c in cols))
    # samenvatting
    def telt(c, pred): return sum(1 for r in rijen if pred(r.get(c, "")))
    print(f"\n== samenvatting ({len(rijen)}) ==")
    print(f"  download<->volledig verbatim OK : {telt('dl_verbatim', lambda v: v=='OK')}")
    print(f"  volledig->compact valide        : {telt('v2c', lambda v: v=='valid')}")
    print(f"  compact->integrated valide      : {telt('c2i', lambda v: str(v).startswith('valid'))}")
    print(f"  wId byte-exact* (compact<->int) : {telt('wId', lambda v: v=='OK')}")
    print(f"  tekst verliesvrij*              : {telt('tekst', lambda v: v=='OK')}")
    print(f"  marks stabiel                   : {telt('marks', lambda v: v=='OK')}")
    print(f"  (* na snoei van de accepted-drops uit beide kanten: {sorted(ACCEPTED_DROPS)})")
    fouten = [r for r in rijen if any(str(r.get(c, '')).startswith(('ERR', 'CRASH', 'FAIL', 'INVALID'))
                                      for c in cols)]
    if fouten:
        print(f"\n  {len(fouten)} pakket(ten) met een afwijking (zie de tabel hierboven).")

if __name__ == "__main__":
    main()
