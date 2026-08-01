using Storm.Core;
using Storm.Dso;

if (args is ["download2volledig", var pkg, var outFile])
{
    var doc = Download2Volledig.Transform(pkg);
    doc.Save(outFile);
    Console.WriteLine($"storm-volledig geschreven: {outFile}");
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
