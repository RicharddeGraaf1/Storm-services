namespace Storm.Core;

/// <summary>De namespaces en versie van de STORM-standaard (spiegelt de XSD's
/// in de Storm-repo). Bron van waarheid blijft de standaard zelf.</summary>
public static class StormNamespaces
{
    public const string Envelop = "urn:storm:1.0";
    public const string Basis = "urn:storm:basis";
    public const string Data = "urn:storm:data";
    public const string Tekst = "urn:storm:tekst";
    public const string Ow = "urn:storm:ow";
    public const string Tr = "urn:storm:tr";
    public const string Gio = "urn:storm:gio";

    /// <summary>Versie van de standaard waar deze library op mikt.</summary>
    public const string Versie = "0.6.0";
}

/// <summary>De drie STORM-varianten (zie de varianten-designnote in de Storm-repo).</summary>
public enum StormVariant
{
    /// <summary>Faithful spiegel van STOP/IMOW/IMTR (downloadhub).</summary>
    Volledig,

    /// <summary>Artikel-centrisch, 1:1 (authoring-hub, ≈ SimplicIT.Domain).</summary>
    Integrated,

    /// <summary>Genormaliseerde, lossy reductie.</summary>
    Compact,
}
