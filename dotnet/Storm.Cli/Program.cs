using Storm.Core;
using Storm.Dso;

using System.Xml.Linq;

if (args is ["download2volledig", var pkg, var outFile])
{
    var doc = Download2Volledig.Transform(pkg);
    doc.Save(outFile);
    Console.WriteLine($"storm-volledig geschreven: {outFile}");
    return;
}

// GIO-laag: schrijf één storm-gio-bestand per IO-map
if (args is ["download2gio", var pkg3, var outDir3])
{
    Directory.CreateDirectory(outDir3);
    int n = 0;
    foreach (var gio in DownloadGio.Transform(pkg3))
    {
        var map = (string?)gio.Attribute("map") ?? $"gio{n}";
        new XDocument(gio).Save(Path.Combine(outDir3, map + ".storm-gio.xml"));
        n++;
    }
    Console.WriteLine($"{n} storm-gio-bestanden geschreven in {outDir3}");
    return;
}

// download -> volledig -> download' (reverse), voor de roundtrip-toets
if (args is ["dso-roundtrip", var pkg2, var outDir])
{
    var vol = Download2Volledig.Transform(pkg2);
    var lz = Volledig2Download.LearnOw(pkg2);
    Directory.CreateDirectory(outDir);
    new XDocument(Volledig2Download.RebuildTekst(vol)).Save(Path.Combine(outDir, "Tekst.xml"));
    var objecten = new XElement("objecten");
    foreach (var o in Volledig2Download.RebuildObjects(vol, lz)) objecten.Add(o);
    new XDocument(objecten).Save(Path.Combine(outDir, "ow.xml"));
    Console.WriteLine($"reconstructie geschreven in {outDir}");
    return;
}

Console.WriteLine($"STORM-services CLI — standaard {StormNamespaces.Versie}");
Console.WriteLine("Gebruik:");
Console.WriteLine("  download2volledig <pakketmap> <uitvoer.xml>   (Storm.Dso)");
Console.WriteLine();
Console.WriteLine("Transformaties (skelet — nog te implementeren):");
string[] transforms =
[
    "download2volledig  / volledig2download   (Storm.Dso + Storm.Imtr)",
    "volledig2integrated / integrated2volledig (Storm.Core)",
    "volledig2compact   / integrated2compact  (Storm.Core)",
    "integrated2simplicit / simplicit2integrated (SimplicIT.Storm-adapter)",
];
foreach (var t in transforms)
    Console.WriteLine($"  - {t}");
