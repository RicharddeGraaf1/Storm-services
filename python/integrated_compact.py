"""storm-integrated -> storm-compact: inverse structuur-hervorming.

Ontvouwt de annotatie terug naar losse Regeltekst/JuridischeRegel-objecten,
en hervormt ContentBlok/TekstRun -> STOP-tekst (tekst-namespace). Pools:
attribuut -> child-element. idealisatie is bij compact->integrated weggevallen
en wordt hier op Exact gezet (bekend rondreis-verlies).
"""
from pathlib import Path
from lxml import etree

INT="urn:storm:integrated"; TEKST="urn:storm:tekst"; COMPACT="urn:storm:compact"
XSI="http://www.w3.org/2001/XMLSchema-instance"
EXACT="http://standaarden.omgevingswet.overheid.nl/idealisatie/id/concept/Exact"
XSD=Path(r"C:\GIT\Storm\standaard\xsd\storm-compact.xsd")
XSD_URL=("https://raw.githubusercontent.com/RicharddeGraaf1/Storm/main/"
         "standaard/xsd/storm-compact.xsd")

def L(t): return t.split('}')[-1] if isinstance(t,str) and '}' in t else t
def kids(e): return [c for c in e if isinstance(c.tag,str)]
def ch(e,n): return next((c for c in kids(e) if L(c.tag)==n),None)
def T(n): return etree.Element(f"{{{TEKST}}}{n}")
def C(n,text=None):
    e=etree.Element(f"{{{COMPACT}}}{n}")
    if text is not None: e.text=text
    return e

STRUCTUUR={'Boek','Deel','Hoofdstuk','Titel','Afdeling','Paragraaf','Subparagraaf',
           'Subsubparagraaf','Divisie'}
MARK_EL={'italic':'i','strong':'b','underline':'u','sup':'sup','sub':'sub',
         'intRef':'IntRef','extRef':'ExtRef','intIoRef':'IntIoRef','extIoRef':'ExtIoRef'}

# ---------- tekst: ContentBlok/TekstRun -> STOP-tekst ----------
def _append_text(parent, text):
    if len(parent): parent[-1].tail=(parent[-1].tail or '')+text
    else: parent.text=(parent.text or '')+text

def append_run(parent, run):
    text=run.get('tekst') or ''
    if run.get('soort')=='Noot':
        noot=T('Noot')
        nn=T('NootNummer'); nn.text=run.get('nummer') or ''  # nummer zit op Noot-attr
        n=ch(run,'Noot')
        if n is not None and n.get('nummer'): nn.text=n.get('nummer')
        noot.append(nn)
        for inl in kids(n if n is not None else run):
            if L(inl.tag)=='TekstRun':
                al=T('Al'); append_run(al,inl); noot.append(al)
        parent.append(noot); return
    marks=[m for m in kids(run) if L(m.tag)=='Mark']
    if not marks:
        _append_text(parent, text); return
    outer=None; cur=None
    for m in marks:
        name=MARK_EL.get(m.get('kind'))
        if not name: continue
        el=T(name)
        for a in ('ref','scope','soort','eId','wId'):
            if m.get(a): el.set(a,m.get(a))
        if outer is None: outer=cur=el
        else: cur.append(el); cur=el
    if outer is None: _append_text(parent,text); return
    cur.text=text; parent.append(outer)

def runs_to(parent, el_with_runs):
    for r in kids(el_with_runs):
        if L(r.tag)=='TekstRun': append_run(parent, r)

def stop_contentblok(cb):
    t=L(cb.tag)
    if t=='Alinea':
        al=T('Al')
        if cb.get('uId'): al.set('wId',cb.get('uId'))
        runs_to(al, cb); return al
    if t=='Lijst':
        lj=T('Lijst')
        if cb.get('eId'): lj.set('eId',cb.get('eId'))
        if cb.get('wId'): lj.set('wId',cb.get('wId'))
        aan=ch(cb,'Aanhef')
        if aan is not None:
            la=T('Lijstaanhef'); runs_to(la,aan); lj.append(la)
        for it in kids(cb):
            if L(it.tag)!='Item': continue
            li=T('Li')
            if it.get('eId'): li.set('eId',it.get('eId'))
            if it.get('wId'): li.set('wId',it.get('wId'))
            if it.get('nummer'):
                ln=T('LiNummer'); ln.text=it.get('nummer'); li.append(ln)
            for c in kids(it):
                if L(c.tag) in ('Alinea','Lijst','Figuur','Tabel'):
                    sub=stop_contentblok(c)
                    if sub is not None: li.append(sub)
            lj.append(li)
        return lj
    if t=='Begrippenlijst':
        bl=T('Begrippenlijst')
        if cb.get('eId'): bl.set('eId',cb.get('eId'))
        if cb.get('wId'): bl.set('wId',cb.get('wId'))
        for g in kids(cb):
            if L(g.tag)!='Begrip': continue
            bg=T('Begrip')
            if g.get('eId'): bg.set('eId',g.get('eId'))
            if g.get('wId'): bg.set('wId',g.get('wId'))
            term=ch(g,'Term')
            if term is not None:
                tt=T('Term'); runs_to(tt,term); bg.append(tt)
            defi=ch(g,'Definitie')
            if defi is not None:
                d=T('Definitie')
                for c in kids(defi):
                    sub=stop_contentblok(c)
                    if sub is not None: d.append(sub)
                bg.append(d)
            bl.append(bg)
        return bl
    if t=='Tabel':
        return tabel_to_stop(cb)
    # Figuur/Kadertekst/Citaat: aanzet -> overslaan
    return None

def tabel_to_stop(cb):
    tb=T('table')
    if cb.get('eId'): tb.set('eId',cb.get('eId'))
    if cb.get('wId'): tb.set('wId',cb.get('wId'))
    tg=etree.SubElement(tb,f"{{{TEKST}}}tgroup")
    kolommen=[k for k in kids(cb) if L(k.tag)=='Kolom']
    tg.set('cols',str(len(kolommen)) if kolommen else '1')
    for i,k in enumerate(kolommen,1):
        cs=etree.SubElement(tg,f"{{{TEKST}}}colspec"); cs.set('colname',k.get('naam') or f'c{i}')
    def rijen(name, tag):
        rs=[r for r in kids(cb) if L(r.tag)=='Rij' and (r.get('kop')=='true')==(name=='thead')]
        if not rs: return
        blk=etree.SubElement(tg,f"{{{TEKST}}}{name}")
        for r in rs:
            row=etree.SubElement(blk,f"{{{TEKST}}}row")
            for cel in kids(r):
                if L(cel.tag)!='Cel': continue
                entry=etree.SubElement(row,f"{{{TEKST}}}entry")
                al=ch(cel,'Alinea')
                if al is not None: runs_to(entry, al)
    rijen('thead','thead'); rijen('tbody','tbody')
    return tb

def stop_kop(kop):
    k=T('Kop')
    if kop.get('label'): lb=T('Label'); lb.text=kop.get('label'); k.append(lb)
    if kop.get('nummer'): nm=T('Nummer'); nm.text=kop.get('nummer'); k.append(nm)
    op=ch(kop,'Opschrift')
    if op is not None:
        o=T('Opschrift'); runs_to(o,op); k.append(o)
    return k

def reshape_back(el, regels_out):
    t=L(el.tag)
    if t=='Lichaam':
        out=T('Lichaam'); out.set('eId',el.get('eId') or 'body'); out.set('wId',el.get('wId') or 'body')
        for c in kids(el):
            if L(c.tag) in STRUCTUUR|{'Artikel','Lid','Divisietekst','Bijlage'}:
                out.append(reshape_back(c, regels_out))
        return out
    if t in STRUCTUUR or t=='Bijlage':
        out=T(t)
        if el.get('eId'): out.set('eId',el.get('eId'))
        if el.get('wId'): out.set('wId',el.get('wId'))
        kop=ch(el,'Kop')
        if kop is not None: out.append(stop_kop(kop))
        if el.get('aantekening'): out.append(T(el.get('aantekening')))   # Gereserveerd/Vervallen
        for c in kids(el):
            if L(c.tag) in STRUCTUUR|{'Artikel','Lid','Divisietekst','Bijlage'}:
                out.append(reshape_back(c, regels_out))
        return out
    if t in ('Artikel','Lid','Divisietekst'):
        out=T(t)
        if el.get('eId'): out.set('eId',el.get('eId'))
        if el.get('wId'): out.set('wId',el.get('wId'))
        aant=el.get('aantekening')
        blks=[c for c in kids(el) if L(c.tag) in ('Alinea','Lijst','Begrippenlijst','Tabel','Figuur','Kadertekst','Citaat')]
        leden=[c for c in kids(el) if L(c.tag)=='Lid']
        def inhoud():
            inh=T('Inhoud')
            for c in blks:
                sub=stop_contentblok(c)
                if sub is not None: inh.append(sub)
            return inh
        if t=='Lid':
            ln=T('LidNummer'); ln.text=el.get('nummer') or '1'; out.append(ln)
            out.append(T('Vervallen') if aant=='Vervallen' else inhoud())
        else:
            kop=ch(el,'Kop')
            if kop is not None: out.append(stop_kop(kop))
            if t=='Artikel' and leden:
                for c in leden: out.append(reshape_back(c, regels_out))
            elif aant:
                out.append(T(aant))                 # Gereserveerd/Vervallen
            else:
                out.append(inhoud())                # Inhoud (evt. leeg)
        # annotatie ontvouwen -> Regeltekst + JuridischeRegel
        rtid=el.get('owRegeltekstIdentificatie'); jrid=el.get('owJuridischeRegelIdentificatie')
        if rtid:
            rt=C('Regeltekst'); rt.set('wId', out.get('wId') or '')
            rt.append(C('identificatie', rtid)); regels_out['rt'].append(rt)
        if jrid:
            jr=C('JuridischeRegel')
            jr.append(C('identificatie', jrid))
            jr.append(C('idealisatie', EXACT))          # bij compact->integrated weggevallen
            jr.append(_cref('artikelOfLid', rtid or ''))
            for aa in kids(el):
                if L(aa.tag)!='ActiviteitAanduiding': continue
                ca=C('activiteitaanduiding')
                ca.append(_cref('activiteit', aa.get('activiteitIdentificatie') or ''))
                if aa.get('regelkwalificatie'): ca.append(C('regelkwalificatie', aa.get('regelkwalificatie')))
                jr.append(ca)
            for th in kids(el):
                if L(th.tag)=='Thema': jr.append(C('thema', th.text))
            regels_out['jr'].append(jr)
        return out
    return None

def _cref(n,r):
    e=C(n); e.set('ref',r); return e

# ---------- pools: attribuut -> element ----------
def obj_from_attrs(name, src, fields, refattr=None, refname=None):
    o=C(name)
    for f in fields:
        if src.get(f) is not None: o.append(C(f, src.get(f)))
    if refattr and src.get(refattr): o.append(_cref(refname, src.get(refattr)))
    return o

def transform(int_path):
    root=etree.parse(str(int_path)).getroot()
    R=etree.Element(f"{{{COMPACT}}}Regeling", nsmap={None:COMPACT,'tekst':TEKST,'xsi':XSI})
    R.set('variant','compact'); R.set('schemaversie','0.6.0')
    R.set(f"{{{XSI}}}schemaLocation", f"{COMPACT} {XSD_URL}")
    for a in ('naam','type','soortRegeling','bevoegdGezagCode','frbrWork','frbrExpression','versienummer','datum'):
        if root.get(a): R.set(a, root.get(a))

    regels_out={'rt':[],'jr':[]}
    # tekst
    tekst=C('Tekst'); tekst.set('structuur','compact')
    op=ch(root,'Opschrift')
    if op is not None:
        ro=T('RegelingOpschrift'); ro.set('eId','longTitle'); ro.set('wId','longTitle')
        al=T('Al'); runs_to(al, op); ro.append(al); tekst.append(ro)
    lich=ch(root,'Lichaam')
    if lich is not None: tekst.append(reshape_back(lich, regels_out))
    for c in kids(root):
        if L(c.tag)=='Bijlage': tekst.append(reshape_back(c, regels_out))
    at=ch(root,'ArtikelsgewijzeToelichting')
    if at is not None:
        agt=T('ArtikelgewijzeToelichting')
        for c in kids(at):
            if L(c.tag) in STRUCTUUR|{'Artikel','Lid','Divisietekst','Bijlage'}:
                agt.append(reshape_back(c, regels_out))
        tekst.append(agt)
    R.append(tekst)

    co=C('CompactObjecten')
    # Regels
    if regels_out['rt'] or regels_out['jr']:
        regels=C('Regels')
        for rt in regels_out['rt']: regels.append(rt)
        for jr in regels_out['jr']: regels.append(jr)
        co.append(regels)
    # Activiteiten
    av=ch(root,'Activiteiten')
    if av is not None and kids(av):
        avv=C('Activiteiten')
        for a in kids(av):
            o=C('Activiteit')
            for f in ('identificatie','naam','omschrijving','groep','type'):
                if a.get(f) is not None: o.append(C(f, a.get(f)))
            if a.get('bovenliggendeIdentificatie'): o.append(_cref('bovenliggendeActiviteit', a.get('bovenliggendeIdentificatie')))
            for jr in kids(a):
                if L(jr.tag)=='JuridischeRegelRef': o.append(_cref('juridischeRegelRef', jr.text))
            avv.append(o)
        co.append(avv)
    # Normen
    nm=ch(root,'Omgevingsnormen')
    if nm is not None and kids(nm):
        nv=C('Normen')
        for a in kids(nm):
            o=C('Omgevingsnorm')
            for f in ('identificatie','naam','type','eenheid','groep'):
                if a.get(f) is not None: o.append(C(f, a.get(f)))
            for w in kids(a):
                if L(w.tag)!='Normwaarde': continue
                nw=C('Normwaarde')
                for f in ('identificatie','kwantitatieveWaarde','kwalitatieveWaarde'):
                    if w.get(f) is not None: nw.append(C(f, w.get(f)))
                for lr in kids(w):
                    if L(lr.tag)=='LocatieRef': nw.append(_cref('locatieaanduiding', lr.text))
                o.append(nw)
            nv.append(o)
        co.append(nv)
    # Gebiedsaanwijzingen
    ga=ch(root,'Gebiedsaanwijzingen')
    if ga is not None and kids(ga):
        gv=C('Gebiedsaanwijzingen')
        for a in kids(ga):
            gv.append(obj_from_attrs('Gebiedsaanwijzing', a, ('identificatie','naam','type','groep'), 'locatieRef','locatieaanduiding'))
        co.append(gv)
    # Locaties (Ambtsgebied) — integrated heeft geen Locatie-objecten
    amb=ch(root,'Ambtsgebied')
    if amb is not None:
        lv=C('Locaties')
        lv.append(obj_from_attrs('Ambtsgebied', amb, ('identificatie','naam','bestuurlijkeGrenzenId')))
        co.append(lv)
    # Regelingsgebied
    rg=ch(root,'Regelingsgebied')
    if rg is not None:
        co.append(obj_from_attrs('Regelingsgebied', rg, ('identificatie',), 'locatieRef','locatieaanduiding'))
    # Ponsen
    pv=ch(root,'Ponsen')
    if pv is not None and kids(pv):
        pvv=C('Ponsen')
        for a in kids(pv):
            pvv.append(obj_from_attrs('Pons', a, ('identificatie',), 'locatieRef','locatieaanduiding'))
        co.append(pvv)
    # Hoofdlijnen
    hv=ch(root,'Hoofdlijnen')
    if hv is not None and kids(hv):
        hvv=C('Hoofdlijnen')
        for a in kids(hv):
            hvv.append(obj_from_attrs('Hoofdlijn', a, ('identificatie','naam','soort','type')))
        co.append(hvv)
    # Bestanden
    bs=ch(root,'Bestanden')
    if bs is not None and kids(bs):
        bv=C('Bestanden')
        for a in kids(bs):
            b=C('Bestand')
            for at in ('type','naam','frbrExpression','mimeType'):
                if a.get(at): b.set(at, a.get(at))
            bv.append(b)
        co.append(bv)

    if kids(co): R.append(co)
    return R

def rapport(int_path):
    R=transform(int_path)
    sch=etree.XMLSchema(etree.parse(str(XSD)))
    ok=sch.validate(etree.ElementTree(R))
    print('storm-compact valideert:', 'JA' if ok else 'NEE')
    for e in list(sch.error_log)[:12]: print('  ',e.line,e.message[:130])
    return R

if __name__=='__main__':
    import sys
    src=sys.argv[1] if len(sys.argv)>1 else r"C:\GIT\Storm\standaard\voorbeelden\Gemeentestad-integrated\storm-integrated.xml"
    R=rapport(src)
    if len(sys.argv)>2:
        etree.ElementTree(R).write(sys.argv[2],xml_declaration=True,encoding='UTF-8',pretty_print=True)
        print('geschreven:',sys.argv[2])
