"""Scan de harness-steekproef en toon het eerste pakket met een groot tekstverlies.

    python diag_bigloss.py [n] [drempel]

Verkenner: welk pakket moet ik hebben? Voor de diagnose zelf daarna
`diag_verlies.py <pakket>` draaien -- die geeft de balans en alle fragmenten.

Historie: dit script wees eerder het diepste element aan met de eerste treffer
in documentvolgorde, en dat is per definitie de buitenste container. Daardoor
rapporteerde het "container-keten: Regeling" op elk verlies, wat vier echte
gaten (Lijstsluiting, Bron, inline figuurtitel, Lijst-in-Noot) maandenlang als
ruis liet doorgaan. Het gebruikt nu diag_common.diepste_element.
"""
import sys, tempfile, shutil
from pathlib import Path
import diag_common as dc
import roundtrip_harness as rh

n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
drempel = int(sys.argv[2]) if len(sys.argv) > 2 else 250

for z in rh.kies_pakketten(n):
    work = Path(tempfile.mkdtemp(prefix="bigloss_"))
    try:
        C, I, Cx = dc.bouw_varianten(z, work)
        a, b = dc.norm(dc.tekst(C)), dc.norm(dc.tekst(Cx))
        if abs(len(a) - len(b)) < drempel:
            continue
        print(f"\n[groot verlies] {z.name}  (C={len(a)} Cx={len(b)} d={len(a)-len(b)})")
        frag = next((a[i1:i2] for tag, i1, i2, j1, j2 in dc.opcodes(a, b)
                     if tag in ('delete', 'replace') and (i2 - i1) > 40), None)
        if not frag:
            print("  geen groot fragment gevonden")
            break
        print(f"  verloren fragment: {frag[:60]!r}")
        el = dc.diepste_element(C, frag[:40])
        if el is not None:
            parents = dc.ouders(C)
            print(f"  diepste element: {dc.L(el.tag)}")
            print(f"  keten: {dc.keten(el, parents, 8)}")
        print(f"\n  vervolg: python diag_verlies.py {z.name}")
        break
    finally:
        shutil.rmtree(work, ignore_errors=True)
