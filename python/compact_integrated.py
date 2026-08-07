"""storm-compact -> storm-integrated: structuur-hervorming (zelfde vocabulaire).

Per het variantenprincipe (varianten.md): compact en integrated delen de
vocabulaire (SimplicIT-support); dit is de STRUCTUUR-as. Twee hervormingen:
  1. annotatie VOUWEN: losse Regeltekst/JuridischeRegel-objecten (met artikelOfLid-
     ref) -> owRegeltekst/JuridischeRegelId + ActiviteitAanduiding + Thema ÓP het
     Artikel/Lid. (n:1 -> 1:1: eerste JR per tekst-element wint.)
  2. STOP-tekst -> ContentBlok/TekstRun+Mark; Kop-child-elementen -> attributen.
Pools (Activiteit/Norm/...): compact child-elementen -> integrated attributen.
"""
import re
from pathlib import Path
from lxml import etree

COMPACT="urn:storm:compact"; TEKST="urn:storm:tekst"; INT="urn:storm:integrated"
XSI="http://www.w3.org/2001/XMLSchema-instance"
XSD=Path(r"C:\GIT\Storm\standaard\xsd\storm-integrated.xsd")
XSD_URL=("https://raw.githubusercontent.com/RicharddeGraaf1/Storm/main/"
         "standaard/xsd/storm-integrated.xsd")

def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t
def kids(e): return [c for c in e if isinstance(c.tag,str)]
def ch(e,n): return next((c for c in kids(e) if L(c.tag)==n),None)
def ct(e,n):
    c=ch(e,n); return c.text if c is not None else None
def I(name):
    return etree.Element(f"{{{INT}}}{name}")

STRUCTUUR={'Boek','Deel','Hoofdstuk','Titel','Afdeling','Paragraaf','Subparagraaf',
           'Subsubparagraaf','Divisie'}   # 'Titel'/'Subchp' -> map onbekende op Divisie? nee: skip
MARK={'i':'italic','b':'strong','strong':'strong','u':'underline','sup':'sup','sub':'sub',
      'IntRef':'intRef','ExtRef':'extRef','IntIoRef':'intIoRef','ExtIoRef':'extIoRef'}
_uid=[0]
def uid():
    _uid[0]+=1; return f"uid-{_uid[0]:04d}"

# ---------- tekst: STOP -> ContentBlok/TekstRun ----------
def runs(el, active=None):
    """Tekstregel (mixed) -> lijst integrated TekstRun-elementen."""
    active=active or []
    out=[]
    def emit(text):
        if text is None or text=='' : return
        r=I('TekstRun'); r.set('tekst',text)
        for m in active:
            mk=I('Mark')
            for k,v in m.items(): mk.set(k,v)
            r.append(mk)
        out.append(r)
    emit(el.text)
    for c in kids(el):
        ln=L(c.tag)
        if ln in MARK:
            m={'kind':MARK[ln]}
            for a in ('ref','soort','scope','eId','wId'):
                if c.get(a): m[a]=c.get(a)
            out.extend(runs(c, active+[m]))
        elif ln=='Noot':
            r=I('TekstRun'); r.set('tekst',''); r.set('soort','Noot')
            noot=I('Noot')
            for a in ('id','type'):
                if c.get(a): noot.set(a,c.get(a))
            nn=ct(c,'NootNummer')
            if nn: noot.set('nummer',nn)
            for al in kids(c):
                if L(al.tag)=='Al':
                    for rr in runs(al): noot.append(rr)
            r.append(noot); out.append(r)
        else:
            emit(''.join(c.itertext()))
        emit(c.tail)
    return out

def kop_to_int(stop_kop):
    k=I('Kop')
    lbl=ct(stop_kop,'Label'); num=ct(stop_kop,'Nummer')
    if lbl: k.set('label',lbl)
    if num: k.set('nummer',num)
    op=ch(stop_kop,'Opschrift')
    if op is not None:
        o=I('Opschrift')
        for r in runs(op): o.append(r)
        k.append(o)
    return k

def contentblok(el):
    ln=L(el.tag)
    if ln=='Al':
        a=I('Alinea'); a.set('uId', el.get('wId') or el.get('eId') or uid())
        for r in runs(el): a.append(r)
        return a
    if ln=='Lijst':
        lj=I('Lijst'); lj.set('eId',el.get('eId') or uid()); lj.set('wId',el.get('wId') or lj.get('eId'))
        aan=ch(el,'Lijstaanhef')
        if aan is not None:
            w=I('Aanhef')
            for r in runs(aan): w.append(r)
            lj.append(w)
        for li in kids(el):
            if L(li.tag)!='Li': continue
            it=I('Item'); it.set('eId',li.get('eId') or uid()); it.set('wId',li.get('wId') or it.get('eId'))
            num=ct(li,'LiNummer')
            if num: it.set('nummer',num)
            for c in kids(li):
                if L(c.tag) in ('Al','Lijst','Figuur','table'):
                    cb=contentblok(c)
                    if cb is not None: it.append(cb)
            lj.append(it)
        return lj
    if ln=='Begrippenlijst':
        bl=I('Begrippenlijst'); bl.set('eId',el.get('eId') or uid()); bl.set('wId',el.get('wId') or bl.get('eId'))
        for bg in kids(el):
            if L(bg.tag)!='Begrip': continue
            g=I('Begrip'); g.set('eId',bg.get('eId') or uid()); g.set('wId',bg.get('wId') or g.get('eId'))
            term=ch(bg,'Term')
            if term is not None:
                t=I('Term')
                for r in runs(term): t.append(r)
                g.append(t)
            defi=ch(bg,'Definitie')
            if defi is not None:
                d=I('Definitie')
                for c in kids(defi):
                    cb=contentblok(c)
                    if cb is not None: d.append(cb)
                g.append(d)
            bl.append(g)
        return bl
    if ln=='table':
        return table_to_int(el)
    if ln=='Kadertekst':
        kt=I('Kadertekst'); kt.set('eId',el.get('eId') or uid()); kt.set('wId',el.get('wId') or kt.get('eId'))
        for c in kids(el):
            if L(c.tag)=='Kop': continue
            cb=contentblok(c)
            if cb is not None: kt.append(cb)
        return kt
    return None   # Tussenkop/Figuur zonder id e.d. -> aanzet: overslaan

def table_to_int(el):
    tb=I('Tabel'); tb.set('eId',el.get('eId') or uid()); tb.set('wId',el.get('wId') or tb.get('eId'))
    tg=ch(el,'tgroup')
    if tg is None: return tb
    for cs in kids(tg):
        if L(cs.tag)=='colspec':
            k=I('Kolom')
            if cs.get('colname'): k.set('naam',cs.get('colname'))
            tb.append(k)
    for block,kop in (('thead',True),('tbody',False)):
        b=ch(tg,block)
        if b is None: continue
        for row in kids(b):
            if L(row.tag)!='row': continue
            r=I('Rij'); r.set('uId',uid())
            if kop: r.set('kop','true')
            for entry in kids(row):
                if L(entry.tag)!='entry': continue
                cel=I('Cel'); cel.set('uId',uid())
                al=I('Alinea'); al.set('uId',uid())
                for rr in runs(entry): al.append(rr)
                cel.append(al); r.append(cel)
            tb.append(r)
    return tb

# ---------- vorm A: inline span-anker-marks (activiteitRef + regelkwalificatie) ----------
# De marks wijzen met @ref naar ActiviteitAanduiding@identificatie; de waarheid staat
# op die aanduiding. De span is best-effort: gevonden via naam-/keyword-match op de tekst
# (spiegelt annotatie-detectie.md). Geen match -> geen mark, data blijft op de aanduiding.
RK_KEYWORDS=[
    ('Verbod',           ['niet toegestaan','niet is toegestaan','verboden']),
    ('Vergunningplicht', ['omgevingsvergunning','vergunningplichtig','vergunningplicht','vergunning']),
    ('Meldingsplicht',   ['meldingsplichtig','meldingsplicht','melding','melden']),
    ('Informatieplicht', ['informatieplicht','informeren']),
    ('Gebod',            ['verplicht','is gehouden','dient te','moet']),
    ('Toegestaan',       ['is toegestaan','toelaatbaar','toegestaan','mag']),
]
def _concept(uri): return uri.rstrip('/').split('/')[-1] if uri else None

def _eigen_tekstruns(comp):
    """TekstRuns in de eigen Alinea's van comp — niet in geneste Lid/Artikel/Divisietekst."""
    out=[]
    def walk(el):
        for c in kids(el):
            ln=L(c.tag)
            if ln in ('Lid','Artikel','Divisietekst'): continue
            if ln=='TekstRun': out.append(c)
            else: walk(c)
    walk(comp); return out

def _markeer_een(comp, zoek, kind, ref):
    """Splits het eerste ongemarkeerde run met een hele-woord-match op 'zoek' en zet
    er de mark op. Runs die al een Mark dragen (bv. intIoRef, of een eerdere anker-
    mark) worden overgeslagen — die zijn één span. Geeft True als er gemarkeerd is."""
    pat=re.compile(r'\b'+re.escape(zoek)+r'\b', re.IGNORECASE)
    for run in _eigen_tekstruns(comp):
        if any(L(m.tag)=='Mark' for m in kids(run)): continue
        tekst=run.get('tekst') or ''
        m=pat.search(tekst)
        if not m: continue
        parent=run.getparent(); idx=parent.index(run); parent.remove(run)
        for seg,ismark in ((tekst[:m.start()],False),(tekst[m.start():m.end()],True),
                           (tekst[m.end():],False)):
            if seg=='' and not ismark: continue
            r=I('TekstRun'); r.set('tekst',seg)
            if run.get('soort'): r.set('soort',run.get('soort'))
            if ismark:
                mk=I('Mark'); mk.set('kind',kind); mk.set('ref',ref); r.append(mk)
            parent.insert(idx,r); idx+=1
        return True
    return False

def _markeer_alle(comp, zoek, kind, ref):
    """Markeer ÁLLE heel-woord-voorkomens van 'zoek'. Geeft het aantal terug."""
    if not zoek: return 0
    n=0
    while _markeer_een(comp, zoek, kind, ref): n+=1
    return n

def plaats_ankermarks(comp, aanduidingen, act_naam):
    """Vorm A, exacte plaatsing (annotatie-detectie.md § plaatsingsregel):
      - activiteitRef: markeer élk heel-woord-voorkomen van de activiteitnaam (uit de pool).
      - regelkwalificatie: kies per aanduiding-concept het meest-specifieke (langste)
        keyword dat vóórkomt, en markeer álle voorkomens dáárvan; concept-keyed, dus
        de koppeling klopt ook in een lid met meerdere activiteiten."""
    for aa in aanduidingen:
        ident=aa.get('identificatie')
        if not ident: continue
        naam=act_naam.get(aa.get('activiteitIdentificatie'))   # naam uit de pool
        _markeer_alle(comp, naam, 'activiteitRef', ident)
        kws=next((k for c,k in RK_KEYWORDS if c==_concept(aa.get('regelkwalificatie'))), [])
        for kw in kws:   # langste eerst; eerste dat voorkomt wint, dan al zijn voorkomens
            if _markeer_alle(comp, kw, 'regelkwalificatie', ident)>0: break

def reshape_doccomp(el, ann, act_naam):
    ln=L(el.tag)
    if ln=='Lichaam':
        out=I('Lichaam'); out.set('eId',el.get('eId') or 'body'); out.set('wId',el.get('wId') or 'body')
        for c in kids(el):
            if L(c.tag) in STRUCTUUR|{'Artikel','Lid','Divisietekst','Bijlage'}:
                out.append(reshape_doccomp(c, ann, act_naam))
        return out
    if ln in STRUCTUUR or ln=='Bijlage':
        out=I(ln); out.set('eId',el.get('eId') or uid()); out.set('wId',el.get('wId') or out.get('eId'))
        st=ch(el,'Gereserveerd')
        if st is None: st=ch(el,'Vervallen')
        if st is not None: out.set('aantekening', L(st.tag))
        kop=ch(el,'Kop')
        if kop is not None: out.append(kop_to_int(kop))
        for c in kids(el):
            if L(c.tag) in STRUCTUUR|{'Artikel','Lid','Divisietekst','Bijlage'}:
                out.append(reshape_doccomp(c, ann, act_naam))
        return out
    if ln in ('Artikel','Lid','Divisietekst'):
        out=I(ln); out.set('eId',el.get('eId') or uid()); out.set('wId',el.get('wId') or out.get('eId'))
        st=ch(el,'Gereserveerd')
        if st is None: st=ch(el,'Vervallen')
        if st is not None: out.set('aantekening', L(st.tag))
        if ln=='Lid':
            num=ct(el,'LidNummer') or el.get('nummer') or '1'
            out.set('nummer',num)
        kop=ch(el,'Kop')
        if kop is not None and ln!='Lid': out.append(kop_to_int(kop))
        # inhoud -> contentBlokken
        inh=ch(el,'Inhoud')
        blokken=kids(inh) if inh is not None else [c for c in kids(el) if L(c.tag) in ('Al','Lijst','Begrippenlijst','table','Kadertekst')]
        for c in blokken:
            cb=contentblok(c)
            if cb is not None: out.append(cb)
        # leden
        for c in kids(el):
            if L(c.tag)=='Lid': out.append(reshape_doccomp(c, ann, act_naam))
        # annotatie vouwen — regel MOET op het lid als het artikel leden heeft
        a=ann.get(out.get('wId'))
        heeft_leden=any(L(c.tag)=='Lid' for c in kids(el))
        if a and ln=='Artikel' and heeft_leden:
            raise ValueError(
                f"Juridische regel {a.get('owJuridischeRegel')} staat op Artikel "
                f"{out.get('wId')} dat leden heeft; een regel moet dan op het lid staan.")
        if a:
            if a.get('owRegeltekst'): out.set('owRegeltekstIdentificatie',a['owRegeltekst'])
            if a.get('owJuridischeRegel'): out.set('owJuridischeRegelIdentificatie',a['owJuridischeRegel'])
            aanduidingen=[]
            for aa in a.get('activiteiten',[]):
                el2=I('ActiviteitAanduiding')
                if aa.get('identificatie'): el2.set('identificatie',aa['identificatie'])
                el2.set('activiteitIdentificatie',aa['ref'])   # naam: uit de Activiteit-pool
                if aa.get('regelkwalificatie'): el2.set('regelkwalificatie',aa['regelkwalificatie'])
                if aa.get('locatieRef'): el2.set('locatieRef',aa['locatieRef'])
                out.append(el2); aanduidingen.append(el2)
            plaats_ankermarks(out, aanduidingen, act_naam)   # vorm A: span-ankers inline
            for th in a.get('themas',[]):
                t=I('Thema'); t.text=th; out.append(t)
        return out
    return None

# ---------- pools ----------
def pool_obj(name, src, attr_fields, ref_children=(), str_children=()):
    o=I(name)
    for f in attr_fields:
        v=ct(src,f)
        if v is not None: o.set(f,v)
    return o

def transform(compact_path):
    root=etree.parse(str(compact_path)).getroot()
    R=etree.Element(f"{{{INT}}}Regeling", nsmap={None:INT,'xsi':XSI})
    R.set('variant','integrated'); R.set('schemaversie','0.6.0')
    R.set(f"{{{XSI}}}schemaLocation", f"{INT} {XSD_URL}")
    for a in ('naam','type','soortRegeling','bevoegdGezagCode','frbrWork','frbrExpression','versienummer','datum'):
        if root.get(a): R.set(a, root.get(a))

    co=ch(root,'CompactObjecten')
    # indexen
    act_naam={}; rt_wid={}; ann={}
    if co is not None:
        av=ch(co,'Activiteiten')
        for a in (kids(av) if av is not None else []):
            act_naam[ct(a,'identificatie')]=ct(a,'naam')
        regels=ch(co,'Regels')
        for o in (kids(regels) if regels is not None else []):
            if L(o.tag)=='Regeltekst': rt_wid[ct(o,'identificatie')]=o.get('wId')
        for o in (kids(regels) if regels is not None else []):
            if L(o.tag)!='JuridischeRegel': continue
            al=ch(o,'artikelOfLid'); rtid=al.get('ref') if al is not None else None
            wid=rt_wid.get(rtid)
            if not wid or wid in ann: continue   # 1:1: eerste JR wint
            acts=[]
            for aa in kids(o):
                if L(aa.tag)!='activiteitaanduiding': continue
                act=ch(aa,'activiteit')
                loc=ch(aa,'locatieaanduiding')
                acts.append({'ref':act.get('ref') if act is not None else '',
                             'regelkwalificatie':ct(aa,'regelkwalificatie'),
                             'identificatie':ct(aa,'identificatie'),
                             'locatieRef':loc.get('ref') if loc is not None else None})
            ann[wid]={'owRegeltekst':rtid,'owJuridischeRegel':ct(o,'identificatie'),
                      'activiteiten':acts,
                      'themas':[t.text for t in kids(o) if L(t.tag)=='thema']}

    # tekst
    vt=ch(root,'Tekst')
    if vt is not None:
        op=ch(vt,'RegelingOpschrift')
        o=I('Opschrift')
        if op is not None:
            for al in kids(op):
                if L(al.tag)=='Al':
                    for r in runs(al): o.append(r)
        R.append(o)
        lich=ch(vt,'Lichaam')
        if lich is not None: R.append(reshape_doccomp(lich, ann, act_naam))
        for bij in kids(vt):
            if L(bij.tag)=='Bijlage': R.append(reshape_doccomp(bij, ann, act_naam))
        for at in kids(vt):
            if L(at.tag)=='ArtikelgewijzeToelichting':
                wrap=I('ArtikelsgewijzeToelichting')
                kop=ch(at,'Kop')
                if kop is not None: wrap.append(kop_to_int(kop))   # eigen kop van de toelichting
                for c in kids(at):
                    if L(c.tag) in STRUCTUUR|{'Artikel','Lid','Divisietekst','Bijlage'}:
                        wrap.append(reshape_doccomp(c, ann, act_naam))
                if kids(wrap): R.append(wrap)

    # pools
    if co is not None:
        amb=None; locaties=[]
        loc=ch(co,'Locaties')
        for o in (kids(loc) if loc is not None else []):
            if L(o.tag)=='Ambtsgebied':
                amb=I('Ambtsgebied')
                amb.set('identificatie', ct(o,'identificatie') or '')
                amb.set('naam', ct(o,'naam') or ct(o,'identificatie') or 'ambtsgebied')
                amb.set('bestuurlijkeGrenzenId', ct(o,'bestuurlijkeGrenzenId') or '')
            elif L(o.tag)=='Locatie':
                le=I('Locatie'); le.set('identificatie', ct(o,'identificatie') or '')
                if ct(o,'noemer'): le.set('noemer', ct(o,'noemer'))
                gr=ch(o,'geometrieRef')
                if gr is not None and gr.get('ref'): le.set('geometrieRef', gr.get('ref'))
                gio=ch(o,'gioRef')
                if gio is not None and gio.get('ref'): le.set('gioRef', gio.get('ref'))
                locaties.append(le)
        if amb is not None: R.append(amb)
        rg=ch(co,'Regelingsgebied')
        if rg is not None:
            e=I('Regelingsgebied'); e.set('identificatie',ct(rg,'identificatie') or '')
            la=ch(rg,'locatieaanduiding')
            if la is not None: e.set('locatieRef',la.get('ref'))
            R.append(e)
        if locaties:
            lv=I('Locaties')
            for le in locaties: lv.append(le)
            R.append(lv)
        ga=ch(co,'Gebiedsaanwijzingen')
        if ga is not None and kids(ga):
            gv=I('Gebiedsaanwijzingen')
            for o in kids(ga):
                e=I('Gebiedsaanwijzing')
                for f in ('identificatie','naam','type','groep'):
                    if ct(o,f) is not None: e.set(f,ct(o,f))
                la=ch(o,'locatieaanduiding')
                if la is not None: e.set('locatieRef',la.get('ref'))
                gio=ch(o,'gioRef')
                if gio is not None and gio.get('ref'): e.set('gioRef', gio.get('ref'))
                gv.append(e)
            R.append(gv)
        nm=ch(co,'Normen')
        if nm is not None and kids(nm):
            nv=I('Omgevingsnormen')
            for o in kids(nm):
                e=I('Omgevingsnorm')
                for f in ('identificatie','naam','type','eenheid','groep'):
                    if ct(o,f) is not None: e.set(f,ct(o,f))
                gio=ch(o,'gioRef')
                if gio is not None and gio.get('ref'): e.set('gioRef', gio.get('ref'))
                for w in kids(o):
                    if L(w.tag)!='Normwaarde': continue
                    nw=I('Normwaarde')
                    for f in ('identificatie','kwantitatieveWaarde','kwalitatieveWaarde'):
                        if ct(w,f) is not None: nw.set(f,ct(w,f))
                    for la in kids(w):
                        if L(la.tag)=='locatieaanduiding':
                            lr=I('LocatieRef'); lr.text=la.get('ref'); nw.append(lr)
                    e.append(nw)
                nv.append(e)
            R.append(nv)
        pv_src=ch(co,'Ponsen')
        if pv_src is not None and kids(pv_src):
            pv=I('Ponsen')
            for o in kids(pv_src):
                e=I('Pons'); e.set('identificatie',ct(o,'identificatie') or '')
                la=ch(o,'locatieaanduiding')
                if la is not None: e.set('locatieRef',la.get('ref'))
                pv.append(e)
            R.append(pv)
        hv_src=ch(co,'Hoofdlijnen')
        if hv_src is not None and kids(hv_src):
            hv=I('Hoofdlijnen')
            for o in kids(hv_src):
                e=I('Hoofdlijn')
                for f in ('identificatie','naam','soort','type'):
                    if ct(o,f) is not None: e.set(f,ct(o,f))
                hv.append(e)
            R.append(hv)
        av=ch(co,'Activiteiten')
        if av is not None and kids(av):
            avv=I('Activiteiten')
            for o in kids(av):
                e=I('Activiteit')
                for f in ('identificatie','naam','omschrijving','groep','type'):
                    if ct(o,f) is not None: e.set(f,ct(o,f))
                bov=ch(o,'bovenliggendeActiviteit')
                if bov is not None: e.set('bovenliggendeIdentificatie',bov.get('ref'))
                for jr in kids(o):
                    if L(jr.tag)=='juridischeRegelRef':
                        rr=I('JuridischeRegelRef'); rr.text=jr.get('ref'); e.append(rr)
                avv.append(e)
            R.append(avv)
        gios=ch(co,'Gios')
        if gios is not None and kids(gios):
            gv=I('Gios')
            for o in kids(gios):
                g=I('Gio'); g.set('identificatie', ct(o,'identificatie') or '')
                if ct(o,'naam'): g.set('naam', ct(o,'naam'))
                if ct(o,'geometrieBestand'): g.set('geometrieBestand', ct(o,'geometrieBestand'))
                gv.append(g)
            R.append(gv)
        bs=ch(co,'Bestanden')
        if bs is not None and kids(bs):
            bv=I('Bestanden')
            for o in kids(bs):
                e=I('Bestand')
                for a in ('type','naam','mimeType','gridfsId','frbrExpression'):
                    if o.get(a): e.set(a,o.get(a))
                bv.append(e)
            R.append(bv)
    return R

def rapport(compact_path):
    R=transform(compact_path)
    sch=etree.XMLSchema(etree.parse(str(XSD)))
    ok=sch.validate(etree.ElementTree(R))
    print('storm-integrated valideert:', 'JA' if ok else 'NEE')
    for e in list(sch.error_log)[:12]: print('  ',e.line,e.message[:130])
    return R

if __name__=='__main__':
    import sys
    src=sys.argv[1] if len(sys.argv)>1 else r"C:\GIT\Storm\standaard\voorbeelden\Gemeentestad-compact\storm-compact.xml"
    R=rapport(src)
    if len(sys.argv)>2:
        etree.ElementTree(R).write(sys.argv[2],xml_declaration=True,encoding='UTF-8',pretty_print=True)
        print('geschreven:',sys.argv[2])
