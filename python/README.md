# python/ — referentie + voorbeeld-generator

De **productie-transformaties leven in C#** (`../dotnet/`, zie
[../TRANSFORMATIE-ARCHITECTUUR.md](../TRANSFORMATIE-ARCHITECTUUR.md)). Python is
hier bewust **thin**:

- **`naar_volledig.py`** — genereert het `Gemeentestad-volledig`-voorbeeldpakket
  in de Storm-repo uit de echte bron (kiem van `download2volledig`). Onderhouden
  zolang de C#-CLI de voorbeelden nog niet genereert.
- Snelle prototyping/exploratie.

Geen dubbele transform-library: de transform-logica staat alleen in C#.

## `legacy/`

`legacy/` bevat de eerste Python-implementatie (`src/storm` + `tests`,
42 tests) die gebouwd was voor het **oude, monolithische `storm.xsd` v0.5** —
vóór de split in `volledig`/`integrated`/`compact` met drie namespaces. Bewaard
als referentie voor de C#-port (de bhkv/imtr-adapters, `canoniek.py`,
compact-degradatieregels), maar **niet meer onderhouden** en niet passend op het
huidige model.
