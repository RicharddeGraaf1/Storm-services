"""Toon hetzelfde element in C, I en Cx naast elkaar.

    python diag_dump.py <pakket|index> <wId|uId|eId> [kind1,kind2,...]

Zonder derde argument wordt het hele element geprint; met een lijst kindnamen
alleen die kinderen (handig bij een groot Artikel: `Kop,LidNummer,LiNummer`).

Waar diag_verlies zegt WELK elementtype verlies draagt, laat dit zien WAT er
precies anders is -- bijvoorbeeld dat een Figuur/Titel in C een <i> bevat en in
I alleen de witruimte ervoor overhield, of dat een Divisietekst in Cx zijn
<Inhoud> volledig kwijt is en alleen <Kop> + <Vervallen/> overhoudt.
"""
import sys
from lxml import etree
import diag_common as dc


def hoofd(z, C, I, Cx):
    print(f"pakket: {z.name}\nid: {ID}\n")
    for label, root in (("C  (compact, uit de bron)", C),
                        ("I  (integrated)", I),
                        ("Cx (compact, terug)", Cx)):
        el = next((e for e in root.iter()
                   if isinstance(e.tag, str) and ID in (e.get('wId'), e.get('uId'), e.get('eId'))), None)
        print(f"===== {label} =====")
        if el is None:
            print("  (niet gevonden)\n")
            continue
        if KINDEREN:
            attrs = {k: v for k, v in el.attrib.items()}
            print(f"  <{dc.L(el.tag)}> {attrs}")
            for c in el:
                if isinstance(c.tag, str) and dc.L(c.tag) in KINDEREN:
                    print("   ", etree.tostring(c, pretty_print=True, encoding='unicode').strip()[:500])
        else:
            print(etree.tostring(el, pretty_print=True, encoding='unicode'))
        print()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    ID = sys.argv[2]
    KINDEREN = set(sys.argv[3].split(',')) if len(sys.argv) > 3 else None
    dc.met_varianten(sys.argv[1], hoofd)
