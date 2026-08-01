using System.Xml.Linq;
using Storm.Core;

namespace Storm.Dso;

/// <summary>Transformeert een geconsolideerd DSO-downloadpakket (act) naar een
/// storm-volledig-document. Faithful spiegel: tekst + metadata verbatim, de
/// IMOW-objecten hermodelleerd naar storm-ow. Port van de Python-referentie
/// (Storm-services/python), getoetst op hetzelfde 261-corpus.</summary>
public static class Download2Volledig
{
    static readonly XNamespace S = StormNamespaces.Envelop;   // urn:storm:1.0
    static readonly XNamespace T = StormNamespaces.Tekst;
    static readonly XNamespace O = StormNamespaces.Ow;
    static readonly XNamespace D = StormNamespaces.Data;
    static readonly XNamespace Xsi = "http://www.w3.org/2001/XMLSchema-instance";
    static readonly XNamespace Xlink = "http://www.w3.org/1999/xlink";
    const string StopTekst = "https://standaarden.overheid.nl/stop/imop/tekst/";
    const string Deelbestand = "http://www.geostandaarden.nl/imow/bestanden/deelbestand";
    const string XsdUrl =
        "https://raw.githubusercontent.com/RicharddeGraaf1/Storm/main/standaard/xsd/storm-volledig.xsd";

    static readonly string[] MetaModules =
        ["Identificatie.xml", "VersieMetadata.xml", "Metadata.xml", "Momentopname.xml"];

    // objecttype -> (sectie, sorteersleutel binnen sectie)
    static readonly Dictionary<string, (string sec, int key)> Sectie = new()
    {
        ["Regeltekst"] = ("Regels", 0), ["RegelVoorIedereen"] = ("Regels", 1),
        ["Instructieregel"] = ("Regels", 1), ["Omgevingswaarderegel"] = ("Regels", 1),
        ["Omgevingsnorm"] = ("Normen", 0), ["Omgevingswaarde"] = ("Normen", 0),
        ["Activiteit"] = ("Activiteiten", 0),
        ["Gebied"] = ("Locaties", 0), ["Gebiedengroep"] = ("Locaties", 0),
        ["Ambtsgebied"] = ("Locaties", 0), ["Punt"] = ("Locaties", 0),
        ["Puntengroep"] = ("Locaties", 0), ["Lijn"] = ("Locaties", 0),
        ["Lijnengroep"] = ("Locaties", 0),
        ["Gebiedsaanwijzing"] = ("Gebiedsaanwijzingen", 0),
        ["Regelingsgebied"] = ("Regelingsgebied", 0), ["Pons"] = ("Pons", 0),
        ["Tekstdeel"] = ("VrijeTekst", 0), ["Divisie"] = ("VrijeTekst", 1),
        ["Divisietekst"] = ("VrijeTekst", 2), ["Hoofdlijn"] = ("VrijeTekst", 3),
        ["Kaart"] = ("Kaarten", 0),
    };
    static readonly string[] SectieOrder =
        ["Regels", "Normen", "Activiteiten", "Locaties", "Gebiedsaanwijzingen",
         "Regelingsgebied", "Pons", "VrijeTekst", "Kaarten"];
    static readonly HashSet<string> Single = ["Regelingsgebied", "Pons"];

    static readonly HashSet<string> RefWrappers =
    [
        "artikelOfLid", "locatieaanduiding", "gebiedsaanwijzing", "kaartaanduiding",
        "omgevingsnormaanduiding", "omgevingswaardeaanduiding", "gerelateerdeRegeltekst",
        "gerelateerdeActiviteit", "bovenliggendeActiviteit", "gerelateerdeHoofdlijn",
        "hoofdlijnaanduiding", "divisieaanduiding", "groepselement",
        "normweergave", "activiteitlocatieweergave", "gebiedsaanwijzingweergave",
    ];
    static readonly HashSet<string> Skip = ["eigenSymbolisatie"];
    static readonly Dictionary<string, string> RegelingType = new()
    {
        ["RegelingCompact"] = "compact", ["RegelingVrijetekst"] = "vrijetekst",
        ["RegelingKlassiek"] = "klassiek", ["RegelingTijdelijkdeel"] = "tijdelijkdeel",
    };

    public static XDocument Transform(string pkgDir)
    {
        var regDir = Path.Combine(pkgDir, "Regeling");
        var tekstRoot = Xml.Load(Path.Combine(regDir, "Tekst.xml")).Root!;
        var structuur = RegelingType.GetValueOrDefault(tekstRoot.Local(), "compact");

        var R = new XElement(S + "Regeling",
            new XAttribute("variant", "volledig"),
            new XAttribute("schemaversie", "0.6.0"),
            new XAttribute(XNamespace.Xmlns + "data", D.NamespaceName),
            new XAttribute(XNamespace.Xmlns + "tekst", T.NamespaceName),
            new XAttribute(XNamespace.Xmlns + "ow", O.NamespaceName),
            new XAttribute(Xsi + "schemaLocation", $"{S.NamespaceName} {XsdUrl}"));

        // Identificatie
        var idRoot = Xml.Load(Path.Combine(regDir, "Identificatie.xml")).Root!;
        var work = idRoot.Descendants().FirstOrDefault(e => e.Local() == "FRBRWork")?.Value;
        var expr = idRoot.Descendants().FirstOrDefault(e => e.Local() == "FRBRExpression")?.Value;
        var ident = new XElement(S + "Identificatie");
        if (work != null) ident.Add(new XElement(S + "FRBRWork", work));
        if (expr != null) ident.Add(new XElement(S + "FRBRExpression", expr));
        var bg = work?.Split('/');
        if (bg is { Length: > 4 }) ident.Add(new XElement(S + "bevoegdGezag", bg[4]));
        R.Add(ident);

        // Metadata (regeling-modules verbatim)
        var meta = new XElement(D + "Metadata");
        var regMeta = new XElement(D + "Regeling");
        foreach (var mf in MetaModules)
        {
            var f = Path.Combine(regDir, mf);
            if (File.Exists(f)) regMeta.Add(new XElement(Xml.Load(f).Root!));
        }
        meta.Add(regMeta);
        R.Add(meta);

        // Tekstlaag: alle STOP-tekst-kinderen verbatim (namespace hernoemd)
        var tekst = new XElement(T + "Tekst", new XAttribute("structuur", structuur));
        foreach (var a in tekstRoot.Attributes().Where(a => !a.IsNamespaceDeclaration))
            tekst.SetAttributeValue(a.Name, a.Value);       // componentnaam/wordt/schemaversie
        foreach (var c in tekstRoot.Elements().Where(c => c.Name.NamespaceName == StopTekst))
            tekst.Add(MirrorTekst(c));
        R.Add(tekst);

        // Objectlaag
        var buckets = ReadObjects(pkgDir);
        var ow = new XElement(O + "OwObjecten");
        foreach (var sec in SectieOrder)
        {
            if (!buckets.TryGetValue(sec, out var items)) continue;
            var ordered = items.OrderBy(x => x.key).Select(x => x.el);
            if (Single.Contains(sec)) foreach (var el in ordered) ow.Add(el);
            else
            {
                var s = new XElement(O + sec);
                foreach (var el in ordered) s.Add(el);
                ow.Add(s);
            }
        }
        R.Add(ow);
        return new XDocument(R);
    }

    // ---------- tekst: verbatim spiegel (namespace STOP-tekst -> urn:storm:tekst) ----------
    static XElement MirrorTekst(XElement src)
    {
        var ns = src.Name.NamespaceName == StopTekst ? T.NamespaceName : src.Name.NamespaceName;
        var el = new XElement(XName.Get(src.Name.LocalName, ns));
        foreach (var a in src.Attributes().Where(a => !a.IsNamespaceDeclaration))
            el.SetAttributeValue(a.Name, a.Value);
        foreach (var n in src.Nodes())
        {
            if (n is XElement ce) el.Add(MirrorTekst(ce));
            else if (n is XText tx) el.Add(new XText(tx.Value));
        }
        return el;
    }

    // ---------- object: hermodelleren naar storm-ow ----------
    static XElement OwEl(string name, string? text = null) =>
        text != null ? new XElement(O + name, text) : new XElement(O + name);

    static XElement StructMirror(XElement src)
    {
        var outEl = OwEl(src.Local());
        if (!src.Elements().Any()) { outEl.Value = src.Value; return outEl; }
        foreach (var c in src.Elements()) outEl.Add(StructMirror(c));
        return outEl;
    }

    static IEnumerable<(string name, string? text)> Leaves(XElement e)
    {
        foreach (var c in e.Elements())
            if (c.Elements().Any())
                foreach (var l in Leaves(c)) yield return l;
            else
                yield return (c.Local(), c.Value);
    }

    static XElement MirrorObj(XElement src)
    {
        var outEl = OwEl(src.Local());
        var wid = (string?)src.Attribute("wId");
        if (wid != null) outEl.SetAttributeValue("wId", wid);
        foreach (var c in src.Elements())
        {
            var lc = c.Local();
            if (Skip.Contains(lc)) continue;
            if (RefWrappers.Contains(lc))
            {
                foreach (var g in c.Elements().Where(g => g.Local().EndsWith("Ref")))
                {
                    var r = OwEl(lc); r.SetAttributeValue("ref", g.Href()); outEl.Add(r);
                }
            }
            else if (lc == "activiteitaanduiding")
            {
                var aa = OwEl("activiteitaanduiding");
                foreach (var g in c.Elements())
                {
                    if (g.Local() == "ActiviteitRef")
                    { var a = OwEl("activiteit"); a.SetAttributeValue("ref", g.Href()); aa.Add(a); }
                    else if (g.Local() == "ActiviteitLocatieaanduiding") aa.Add(MirrorObj(g));
                }
                outEl.Add(aa);
            }
            else if (lc == "normwaarde")
            {
                var nw = OwEl("normwaarde");
                foreach (var g in c.Elements().Where(g => g.Local() == "Normwaarde")) nw.Add(MirrorObj(g));
                outEl.Add(nw);
            }
            else if (lc == "geometrie")
            {
                var g = OwEl("geometrie"); var gr = OwEl("GeometrieRef");
                foreach (var gg in c.Elements().Where(gg => gg.Local() == "GeometrieRef"))
                    gr.SetAttributeValue("ref", gg.Href());
                g.Add(gr); outEl.Add(g);
            }
            else if (lc == "uitsnede")
            {
                var u = OwEl("uitsnede");
                foreach (var g in c.Elements().Where(g => g.Local() == "Kaartextent"))
                {
                    var ke = OwEl("Kaartextent");
                    foreach (var (name, text) in Leaves(g)) ke.Add(OwEl(name, text));
                    u.Add(ke);
                }
                outEl.Add(u);
            }
            else if (lc == "kaartlagen")
            {
                var kl = OwEl("kaartlagen");
                foreach (var g in c.Elements().Where(g => g.Local() == "Kaartlaag")) kl.Add(MirrorObj(g));
                outEl.Add(kl);
            }
            else if (lc == "hoogte")
            {
                var w = OwEl("hoogte");
                foreach (var (name, text) in Leaves(c)) w.Add(OwEl(name, text));
                outEl.Add(w);
            }
            else if (lc.Equals("bestuurlijkeGrenzenVerwijzing", StringComparison.OrdinalIgnoreCase))
            {
                outEl.Add(StructMirror(c));   // datatype-laag behouden
            }
            else if (c.Elements().Any())
            {
                outEl.Add(StructMirror(c));
            }
            else
            {
                outEl.Add(OwEl(lc, c.Value));  // waarde verbatim
            }
        }
        return outEl;
    }

    static Dictionary<string, List<(int key, XElement el)>> ReadObjects(string pkgDir)
    {
        var buckets = new Dictionary<string, List<(int, XElement)>>();
        var owDir = Path.Combine(pkgDir, "OW-bestanden");
        foreach (var f in Directory.GetFiles(owDir, "*.xml").OrderBy(x => x))
        {
            if (Path.GetFileName(f) == "manifest-ow.xml") continue;
            foreach (var obj in Xml.Load(f).Descendants(XName.Get("owObject", Deelbestand)))
            {
                var typed = obj.Elements().FirstOrDefault();
                if (typed == null) continue;
                if (Sectie.TryGetValue(typed.Local(), out var sk))
                {
                    if (!buckets.TryGetValue(sk.sec, out var list))
                        buckets[sk.sec] = list = [];
                    list.Add((sk.key, MirrorObj(typed)));
                }
            }
        }
        return buckets;
    }
}
