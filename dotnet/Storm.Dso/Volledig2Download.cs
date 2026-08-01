using System.Xml.Linq;
using Storm.Core;

namespace Storm.Dso;

/// <summary>Reverse: storm-volledig -> download(act)-vorm. Tekst + metadata
/// verbatim terug; de IMOW-objecten gereconstrueerd met mappings die uit de
/// bron worden geleerd (namespace per objecttype/*Ref, en (wrapper,doeltype)->
/// RefName via het objecttype-segment in de ref). Port van de Python-referentie
/// (roundtrip 620.268/620.268 owObjecten canoniek identiek).</summary>
public static class Volledig2Download
{
    static readonly XNamespace T = StormNamespaces.Tekst;
    static readonly XNamespace O = StormNamespaces.Ow;
    static readonly XNamespace Xlink = "http://www.w3.org/1999/xlink";
    const string StopTekst = "https://standaarden.overheid.nl/stop/imop/tekst/";
    const string Deelbestand = "http://www.geostandaarden.nl/imow/bestanden/deelbestand";

    static readonly Dictionary<string, string> RegtypeElem = new()
    {
        ["compact"] = "RegelingCompact", ["vrijetekst"] = "RegelingVrijetekst",
        ["klassiek"] = "RegelingKlassiek", ["tijdelijkdeel"] = "RegelingTijdelijkdeel",
    };
    static readonly HashSet<string> SectieContainers =
        ["Regels", "Normen", "Activiteiten", "Locaties", "Gebiedsaanwijzingen",
         "VrijeTekst", "Kaarten"];

    public sealed class Learned
    {
        public Dictionary<string, string> ObjNs = new();
        public Dictionary<string, string> RefNs = new();
        public Dictionary<string, string> RefChild = new();
        public Dictionary<(string, string?), string> RefMap = new();
    }

    static string? Seg(string? refv)
    {
        if (refv == null) return null;
        var p = refv.Split('.');
        return p.Length >= 3 ? p[2] : null;
    }

    public static Learned LearnOw(string pkgDir)
    {
        var lz = new Learned();
        var owDir = Path.Combine(pkgDir, "OW-bestanden");
        foreach (var f in Directory.GetFiles(owDir, "*.xml"))
        {
            if (Path.GetFileName(f) == "manifest-ow.xml") continue;
            foreach (var obj in Xml.Load(f).Descendants(XName.Get("owObject", Deelbestand)))
                foreach (var e in obj.DescendantsAndSelf())
                {
                    var lc = e.Local();
                    if (char.IsUpper(lc[0]))
                        (lc.EndsWith("Ref") ? lz.RefNs : lz.ObjNs)[lc] = e.Name.NamespaceName;
                    if (char.IsLower(lc[0]))
                        foreach (var ch in e.Elements().Where(ch => ch.Local().EndsWith("Ref")))
                        {
                            lz.RefChild.TryAdd(lc, ch.Local());
                            lz.RefMap[(lc, Seg(ch.Href()))] = ch.Local();
                        }
                }
        }
        return lz;
    }

    static string Cap(string s) => char.ToUpper(s[0]) + s[1..];

    public static XElement RevObj(XElement sel, string parentNs, Learned lz)
    {
        var lc = sel.Local();
        var myns = lz.ObjNs.GetValueOrDefault(lc, parentNs);
        var el = new XElement(XName.Get(lc, myns));
        var wid = (string?)sel.Attribute("wId");
        if (wid != null) el.SetAttributeValue("wId", wid);

        var cs = sel.Elements().ToList();
        int i = 0;
        while (i < cs.Count)
        {
            var c = cs[i]; var clc = c.Local();
            bool IsRef(XElement x) => x.Attribute("ref") != null && !x.Elements().Any();
            if (IsRef(c))
            {
                var grp = new List<XElement> { c }; int j = i + 1;
                while (j < cs.Count && cs[j].Local() == clc && IsRef(cs[j])) { grp.Add(cs[j]); j++; }
                if (clc == "activiteit")
                {
                    var rns = lz.RefNs.GetValueOrDefault("ActiviteitRef", myns);
                    foreach (var g in grp)
                        el.Add(Ref("ActiviteitRef", rns, (string?)g.Attribute("ref")));
                }
                else if (clc.EndsWith("Ref"))
                {
                    var rns = lz.RefNs.GetValueOrDefault(clc, myns);
                    foreach (var g in grp)
                        el.Add(Ref(clc, rns, (string?)g.Attribute("ref")));
                }
                else
                {
                    var w = new XElement(XName.Get(clc, myns));
                    foreach (var g in grp)
                    {
                        var rv = (string?)g.Attribute("ref");
                        var refname = lz.RefMap.GetValueOrDefault((clc, Seg(rv)))
                                      ?? lz.RefChild.GetValueOrDefault(clc) ?? Cap(clc) + "Ref";
                        var rns = lz.RefNs.GetValueOrDefault(refname, myns);
                        w.Add(Ref(refname, rns, rv));
                    }
                    el.Add(w);
                }
                i = j;
            }
            else if (c.Elements().Any()) { el.Add(RevObj(c, myns, lz)); i++; }
            else { el.Add(new XElement(XName.Get(clc, myns), c.Value)); i++; }
        }
        return el;
    }

    static XElement Ref(string name, string ns, string? href)
    {
        var r = new XElement(XName.Get(name, ns));
        r.SetAttributeValue(Xlink + "href", href);
        return r;
    }

    public static IEnumerable<XElement> RebuildObjects(XDocument vol, Learned lz)
    {
        var ow = vol.Root!.Elements().First(e => e.Local() == "OwObjecten");
        foreach (var sec in ow.Elements())
        {
            var objs = SectieContainers.Contains(sec.Local()) ? sec.Elements() : [sec];
            foreach (var o in objs) yield return RevObj(o, "", lz);
        }
    }

    // ---------- tekst terug naar STOP RegelingCompact ----------
    public static XElement RebuildTekst(XDocument vol)
    {
        var tekst = vol.Root!.Elements().First(e => e.Local() == "Tekst");
        var structuur = (string?)tekst.Attribute("structuur") ?? "compact";
        var rootName = RegtypeElem.GetValueOrDefault(structuur, "RegelingCompact");
        var root = new XElement(XName.Get(rootName, StopTekst));
        foreach (var a in tekst.Attributes().Where(a => !a.IsNamespaceDeclaration && a.Name.LocalName != "structuur"))
            root.SetAttributeValue(a.Name, a.Value);
        foreach (var c in tekst.Elements()) root.Add(RenameBack(c));
        return root;
    }

    static XElement RenameBack(XElement src)
    {
        var ns = src.Name.NamespaceName == T.NamespaceName ? StopTekst : src.Name.NamespaceName;
        var el = new XElement(XName.Get(src.Name.LocalName, ns));
        foreach (var a in src.Attributes().Where(a => !a.IsNamespaceDeclaration))
            el.SetAttributeValue(a.Name, a.Value);
        foreach (var n in src.Nodes())
        {
            if (n is XElement ce) el.Add(RenameBack(ce));
            else if (n is XText tx) el.Add(new XText(tx.Value));
        }
        return el;
    }
}
