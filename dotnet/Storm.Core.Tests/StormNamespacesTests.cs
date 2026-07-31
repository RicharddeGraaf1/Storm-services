using System.Linq;
using Storm.Core;
using Xunit;

namespace Storm.Core.Tests;

public class StormNamespacesTests
{
    [Fact]
    public void Envelop_namespace_klopt()
        => Assert.Equal("urn:storm:1.0", StormNamespaces.Envelop);

    [Fact]
    public void Zeven_namespaces_zijn_uniek()
    {
        string[] ns =
        [
            StormNamespaces.Envelop, StormNamespaces.Basis, StormNamespaces.Data,
            StormNamespaces.Tekst, StormNamespaces.Ow, StormNamespaces.Tr, StormNamespaces.Gio,
        ];
        Assert.Equal(ns.Length, ns.Distinct().Count());
    }

    [Fact]
    public void Drie_varianten()
        => Assert.Equal(3, System.Enum.GetValues<StormVariant>().Length);
}
