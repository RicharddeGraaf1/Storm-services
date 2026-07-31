using Storm.Core;

Console.WriteLine($"STORM-services CLI — standaard {StormNamespaces.Versie}");
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
