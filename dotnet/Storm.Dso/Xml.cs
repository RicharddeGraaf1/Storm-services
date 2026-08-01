using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace Storm.Dso;

/// <summary>XML-hulp: tolerante load (de prod-OW-bestanden bevatten een kapotte
/// xmlns:schemaLocation) en kleine helpers rond LINQ-to-XML.</summary>
public static partial class Xml
{
    [GeneratedRegex("\\s+xmlns:schemaLocation=\"[^\"]*\"", RegexOptions.Singleline)]
    private static partial Regex BrokenXmlnsSchemaLocation();

    // De download-OW-bestanden declareren per abuis xmlns:schemaLocation="uri uri"
    // (moet xsi:schemaLocation zijn); dat is geen geldige namespace -> strippen.
    public static XDocument Load(string path)
    {
        var text = File.ReadAllText(path);
        text = BrokenXmlnsSchemaLocation().Replace(text, " ");
        return XDocument.Parse(text, LoadOptions.None);
    }

    public static string Local(this XElement e) => e.Name.LocalName;
    public static IEnumerable<XElement> Kids(this XElement e) => e.Elements();
    public static string? Href(this XElement e) =>
        (string?)e.Attribute(XName.Get("href", "http://www.w3.org/1999/xlink"));
}
