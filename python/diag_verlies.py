"""Waar verliest compact -> integrated -> compact tekst, en welk element draagt het?

    python diag_verlies.py <pakket|index> [min_fragmentlengte]

Twee dingen in één beeld:

1. De delete/insert-BALANS. Een delete met een bijpassende insert elders is
   diff-uitlijning, geen verlies. Alleen het netto-verschil telt. (Bij gm0014
   leek de nummering 1..16 eerst ruis; 16 deletes en 0 inserts bewees dat een
   Begrippenlijst zijn LiNummers kwijtraakte.)

2. Per verloren fragment het DIEPSTE element dat het bevat, plus de
   voorouder-keten en of de dichtstbijzijnde wId-voorouder Cx nog haalt.
   Dat wijst het schuldige elementtype aan -- zie diag_common.diepste_element
   voor waarom de eerste treffer in documentvolgorde nutteloos is.
"""
import sys
from collections import Counter
import diag_common as dc


def hoofd(z, C, I, Cx):
    a, b = dc.norm(dc.tekst(C)), dc.norm(dc.tekst(Cx))
    print(f"{z.name}\nC={len(a)}  Cx={len(b)}  netto d={len(a)-len(b)}\n")

    dels, ins, frags = Counter(), Counter(), []
    for tag, i1, i2, j1, j2 in dc.opcodes(a, b):
        if tag in ('delete', 'replace') and i2 > i1:
            dels[a[i1:i2]] += 1
            if (i2 - i1) >= MINLEN:
                frags.append((tag, i2 - i1, a[i1:i2]))
        if tag in ('insert', 'replace') and j2 > j1:
            ins[b[j1:j2]] += 1

    d_tot = sum(len(k)*v for k, v in dels.items())
    i_tot = sum(len(k)*v for k, v in ins.items())
    print(f"balans: {sum(dels.values())} deletes / {d_tot} tekens  vs  "
          f"{sum(ins.values())} inserts / {i_tot} tekens")
    if i_tot and d_tot and abs(d_tot - i_tot) < min(d_tot, i_tot) * 0.1:
        print("  -> deletes en inserts lopen gelijk op: waarschijnlijk herordening, geen verlies")
    print()

    if not frags:
        print(f"geen verloren fragment >= {MINLEN} tekens")
        return
    parents = dc.ouders(C)
    index = {e: dc.norm(''.join(e.itertext())) for e in C.iter() if isinstance(e.tag, str)}
    cxwids = {e.get('wId') for e in Cx.iter() if isinstance(e.tag, str) and e.get('wId')}
    print(f"{len(frags)} verloren/gewijzigd fragment(en) >= {MINLEN} tekens\n")
    for k, (tag, n, frag) in enumerate(frags, 1):
        print(f"--- fragment {k} ({tag}, {n} tekens) ---")
        print(f"  {frag[:120]!r}")
        el = dc.diepste_element(C, frag[:80], index)
        if el is None:
            print("  niet terug te vinden in C\n")
            continue
        print(f"  diepste element: {dc.L(el.tag)} "
              f"(eId={el.get('eId')} wId={el.get('wId')} len={len(index[el])})")
        print(f"  keten: {dc.keten(el, parents)}")
        cur = el
        while cur is not None:
            if cur.get('wId'):
                staat = 'in Cx' if cur.get('wId') in cxwids else 'WEG uit Cx'
                print(f"  dichtstbijzijnde wId-voorouder {dc.L(cur.tag)}[{cur.get('wId')}] -> {staat}")
                break
            cur = parents.get(cur)
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    MINLEN = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    dc.met_varianten(sys.argv[1], hoofd)
