using System.Xml.Linq;
using Storm.Core;

namespace Storm.Dso;

/// <summary>GIO-laag: bundelt elke download-IO-map (module-bestanden +
/// symbolisatie + geometrie) verbatim in één storm-gio-element. Binaire IO
/// (PDF e.d.) blijft een los pakketbestand (bijlage-referentie). Port van de
/// Python-referentie (GIO-roundtrip 65.561/65.561 canoniek identiek).</summary>
public static class DownloadGio
{
    static readonly XNamespace G = StormNamespaces.Gio;
    static readonly string[] Modules =
        ["Identificatie.xml", "VersieMetadata.xml", "Metadata.xml",
         "Momentopname.xml", "JuridischeBorgingVan.xml"];

    public static List<XElement> Transform(string pkgDir)
    {
        var gios = new List<XElement>();
        foreach (var iod in Directory.GetDirectories(pkgDir, "IO-*").OrderBy(x => x))
        {
            var gio = new XElement(G + "GeoInformatieObject",
                new XAttribute("map", Path.GetFileName(iod)));
            var md = new XElement(G + "Metadata");
            foreach (var mf in Modules)
            {
                var f = Path.Combine(iod, mf);
                if (File.Exists(f)) md.Add(new XElement(Xml.Load(f).Root!));
            }
            gio.Add(md);

            XElement? symb = null, geo = null;
            foreach (var f in Directory.GetFiles(iod).OrderBy(x => x))
            {
                var name = Path.GetFileName(f);
                if (Modules.Contains(name)) continue;
                var ext = Path.GetExtension(f).ToLowerInvariant();
                XElement? root = ext is ".xml" or ".gml" ? TryLoad(f) : null;
                if (root == null) gio.SetAttributeValue("bijlage", name);   // binair
                else if (root.Local() == "FeatureTypeStyle") { gio.SetAttributeValue("symbBestand", name); symb = root; }
                else { gio.SetAttributeValue("geoBestand", name); geo = root; }
            }
            if (symb != null) gio.Add(new XElement(G + "Symbolisatie", symb));
            if (geo != null) gio.Add(new XElement(G + "Geo", geo));
            gios.Add(gio);
        }
        return gios;
    }

    static XElement? TryLoad(string path)
    {
        try { return Xml.Load(path).Root; } catch { return null; }
    }
}
