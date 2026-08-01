# Storm-services — transformatie-architectuur (C# .NET + SimplicIT)

**Status:** ontwerp (2026-07-31). Legt vast *hoe en wat* Storm-services bouwt
voor de transformaties die in SimplicIT geïntegreerd moeten worden.

## 1. Aanleiding

De transformaties moeten integreerbaar zijn in **SimplicIT** (OW-plansoftware).
SimplicIT is **C#/.NET 10 + MongoDB**. Dus de productie-transformaties worden
**C#**. De bestaande Python-code (`naar_volledig.py` c.s.) blijft de
**referentie-kiem** en de generator van de repo-voorbeelden; de C#-library is
het integratie- en productiepad. Beide valideren tegen dezelfde XSD's — de
standaard (`Storm`-repo) blijft de enige bron van waarheid.

## 2. De transformatie-matrix

```
   Download+IMTR ⇄ volledig ⇄ integrated ⇄ SimplicIT-DB (Mongo Project)
                     │            │
                     └──────┬─────┘
                            ▼
                         compact
```

| Transformatie | Richting | Verlies | Waar / hergebruik |
|---|---|---|---|
| **Download+IMTR ↔ volledig** | beide | verliesvrij | `Storm.Dso` + `Storm.Imtr`; hergebruikt SimplicIT-parsers, vult SimplicIT-gaten |
| **volledig ↔ integrated** | beide* | integrated→volledig verliesvrij; volledig→integrated normaliseert (n:1→1:1) | `Storm.Core` (pure STORM) |
| **volledig → compact** | één | lossy | `Storm.Core` |
| **integrated → compact** | één | lossy (terug = hard, buiten scope) | `Storm.Core` |
| **integrated ↔ SimplicIT-DB** | beide | verliesvrij (near-isomorf) | `Storm.SimplicIT`-adapter ↔ `SimplicIT.Domain` |

\* integrated→volledig is de dragende garantie voor "eigen plan publiceren";
volledig→integrated normaliseert een externe download (zie varianten-designnote
in de Storm-repo).

## 3. SimplicIT: wat er al is en wat ontbreekt

.NET 10 + MongoDB, single container (Railway). Eén omgevingsplan = één embedded
`Project`-document; OW-pakketten/GML/PDF in GridFS.

**Bestaat al (leespad compleet):**
- DSO-ZIP inlezen, pakbon-gedreven — `SimplicIT.Core/Services/ZipImportService.cs`,
  `Core/Data/ImportCatalogus.cs`.
- STOP-tekst → typed model (1.4.1) — `Core/Parsers/StopXmlParser.cs`,
  `ContentBlokConverter.cs`, `InlineTekstParser.cs`.
- IMOW-deelbestanden → model (activiteit/GA/norm/ambtsgebied/locatie +
  tekst↔IMOW-koppeling via wId) — `Core/Parsers/OwObjectParser.cs`.
- Model → STOP-tekst + LVBB-versie-XML + locatie-GIO-GML —
  `Core/Generators/StopXmlGenerator.cs`, `LvbbXmlGenerator.cs`, `GioBuilder.cs`.
- Id-generatie (wId/eId/uId/owId, autoritair) —
  `Core/Generators/IdentifierGenerator.cs`.

**Ontbreekt (schrijfpad) — precies STORM's meerwaarde:**
- **OW-object-XML schrijven** (activiteiten/locaties/normen/`manifest-ow`). ❌
- **Volledig aanleverpakket assembleren** (pakbon/opdracht/ZIP). ❌
- **STTR/IMTR/DMN** (toepasbare regels) — volledig afwezig. ❌

STORM is dus **niet redundant** met SimplicIT; het **completeert het schrijfpad
en voegt de IMTR-poot toe.**

## 4. Kerninzicht: SimplicIT.Domain ≈ Storm-integrated

SimplicIT's `Project` (`SimplicIT.Domain/Projecten/Project.cs`) is qua vorm
Storm-integrated:

| Storm-integrated | SimplicIT.Domain |
|---|---|
| pure tekst met annotatie op het artikel | `Regeling` → `Lichaam` → `DocumentComponent`-boom; `Artikel`/`Lid` dragen `OwRegeltekstIdentificatie` + `OwJuridischeRegelIdentificatie` |
| regel = 1:1 op regeltekst (geen aparte regel-class) | idem: juridische regel = annotatie óp `Artikel`/`Lid` (`ActiviteitAanduidingen`, `Themas`) |
| gedeelde pool activiteiten/normen/… | platte lijsten op `Project`: `Activiteiten`, `Omgevingsnormen`, `Gebiedsaanwijzingen`, `Ambtsgebied`, `Regelingsgebied`, `Pons`, `Hoofdlijn` |
| locatie = verwijzing, geometrie extern | `LocatieRef` (opake string) + GML-bytes in GridFS (`BestandRef`) |
| ContentBlok (Al/Lijst/Tabel/…) + inline-marks | `ContentBlok`-laag + `TekstRun`+`Marks` (incl. `IntIoRefMark`/`ExtIoRefMark` — de IntIoRef-keten roundtrip-veilig) |

Daarom is **`integrated ↔ SimplicIT-DB` een near-isomorfe POCO-mapping**, geen
zware transformatie. De opslag zelf (Mongo, discriminator `_t`, GridFS) doet
SimplicIT al.

## 4a. De SimplicIT.Project JSON-vorm (bij import)

Het aggregate `SimplicIT.Domain.Projecten.Project` (`Project.cs`) heeft **twee**
JSON-verschijningsvormen — niet verwarren:

| | **Opslag (MongoDB/BSON)** — `SimplicIT.Mongo/BsonRegistrations.cs` | **API-wire (System.Text.Json)** |
|---|---|---|
| Veldnamen | **PascalCase** (`AutoMap`, geen camelCase-pack) | **camelCase** (`JsonSerializerDefaults.Web`) |
| `_id` | `ObjectId` (`StringObjectIdGenerator`) | `id` als string |
| Enums | **int32** (default) | **string** (`JsonStringEnumConverter`) |
| Type-discriminator | `_t` = klassenaam | `documentComponentType` / `contentBlokType` / `kind` (`[JsonPolymorphic]`) |

De HTTP-respons is bovendien **gesplitst**: `ProjectDetailDto`
(`SimplicIT.Api/Dtos/`) geeft metadata + OW-objecten + toelichtingen **zonder**
de `regeling`-boom; die boom komt via een aparte regeling-projectie
(`DocumentComponentDto`). In Mongo staat alles in **één** document.

**Vorm (wire, ingekort):**

```jsonc
{
  "id": "…ObjectId…", "orgId": "…", "naam": "",            // naam NIET gevuld bij import
  "type": "omgevingsplan", "soortRegeling": "…", "bevoegdGezagCode": "gm0297",
  "frbrWork": "/akn/nl/act/gm0297/2020/omgevingsplan", "frbrExpression": "…@…",
  "status": "Ready", "modus": "Bewerken",
  "ambtsgebied": { "identificatie": "…", "naam": "…", "bestuurlijkeGrenzenId": "GM0297" },
  "omgevingsnormen": [ { "identificatie": "…", "naam": "Bouwhoogte", "eenheid": "m",
    "groep": "…", "normwaarden": [ { "identificatie": "…", "kwantitatieveWaarde": "13",
    "kwalitatieveWaarde": null, "locatieRefs": ["nl.imow-…gebied…"] } ] } ],
  "gebiedsaanwijzingen": [ { "identificatie": "…", "naam": "…", "type": "…",
    "groep": "…", "locatieRef": "nl.imow-…gebied…" } ],
  "regelingsgebied": null, "ponsen": [], "hoofdlijnen": [],   // mapping ontbreekt in importer
  "activiteiten": [ { "id": "…", "naam": "Bouwen", "identificatie": "nl.imow-…activiteit.Bouwen",
    "bovenliggendeIdentificatie": "…", "groep": "…/BouwactiviteitRuimtelijk",
    "type": "Activiteit", "juridischeRegelRefs": ["nl.imow-…juridischeregel…"] } ],
  "regeling": {
    "opschrift": [ { "tekst": "Omgevingsplan Zaltbommel", "soort": "Tekst" } ],
    "documentComponenten": [ {
      "documentComponentType": "Lichaam", "eId": "body", "wId": "body",
      "documentComponenten": [ {
        "documentComponentType": "Hoofdstuk", "eId": "chp_1", "wId": "…",
        "kop": { "label": "Hoofdstuk", "nummer": "1", "opschrift": [ { "tekst": "…", "soort": "Tekst" } ] },
        "documentComponenten": [ {
          "documentComponentType": "Artikel", "eId": "chp_1__art_1.1", "wId": "…",
          "kop": { "label": "Artikel", "nummer": "1.1", "opschrift": [ … ] },
          "owRegeltekstIdentificatie": "nl.imow-…regeltekst…",       // annotatie ÓP het artikel
          "owJuridischeRegelIdentificatie": "nl.imow-…juridischeregel…",
          "activiteitAanduidingen": [ { "activiteitIdentificatie": "…", "activiteitNaam": "Bouwen",
            "regelkwalificatie": "…" } ],
          "informatieobjectAanduidingen": [], "themas": ["…"],
          "leden": [ {
            "documentComponentType": "Lid", "eId": "…", "wId": "…", "nummer": "1",
            "owJuridischeRegelIdentificatie": "…", "activiteitAanduidingen": [ … ],
            "contentBlokken": [ {
              "contentBlokType": "Alinea", "uId": "…",
              "content": [
                { "tekst": "Dit artikel geldt voor ", "soort": "Tekst" },
                { "tekst": "bouwwerken", "soort": "Tekst",
                  "marks": [ { "kind": "intRef", "ref": "nl.imow-…" } ] },
                { "tekst": ".", "soort": "Tekst" } ] } ] } ] } ] } ] } ]
  },
  "algemeneToelichting": [ … ], "artikelsgewijzeToelichting": [ … ],
  "bestanden": [ { "id": "…", "type": "gml", "naam": "Bouwhoogte.gml",
    "gridfsId": "…", "frbrExpression": "…", "mimeType": "application/gml+xml" } ],
  "importWarnings": [ … ], "importNormalizations": [ … ],
  "importSource": { "soort": "OwZip", "bestandsnaam": "…", "identificatie": "…" },
  "members": [], "opmerkingen": [], "createdAt": "…", "updatedAt": "…"
}
```

**Lagen:** `regeling` → `Lichaam`/`Bijlage` → structuur (`Hoofdstuk`/`Afdeling`/
`Divisie`…) → `Artikel`/`Lid`/`Divisietekst` → `ContentBlok` (`Alinea`/`Lijst`/
`Tabel`/`Figuur`/`Begrippenlijst`/`Kadertekst`) → `TekstRun` (+ `marks`:
strong/italic/intRef/intIoRef/extIoRef…). OW-objecten als platte lijsten;
locaties alleen als **string-refs** (`locatieRef`/`locatieRefs`) — géén apart
`Locatie`-object, de GML zit in GridFS via `bestanden`.

**Mapping storm-integrated → Project (concreet):**

| storm-integrated | `Project`-veld (wire) |
|---|---|
| regeling-opschrift | `regeling.opschrift` (`TekstRun[]`) |
| tekstlichaam | `regeling.documentComponenten` (één `Lichaam` + 0..n `Bijlage`) |
| artikel/lid | `documentComponentType: "Artikel" \| "Lid"` met `eId`/`wId`/`kop` |
| annotatie op de regel | `owRegeltekstIdentificatie`, `owJuridischeRegelIdentificatie`, `activiteitAanduidingen[]`, `informatieobjectAanduidingen[]`, `themas[]` op Artikel/Lid |
| inline-opmaak + refs | `TekstRun.marks[]` (`kind` = strong/…/intRef/extRef/intIoRef/extIoRef) |
| activiteit | `activiteiten[]` (`identificatie`, `groep`, `type`, `bovenliggendeIdentificatie`, `juridischeRegelRefs[]`) |
| omgevingsnorm/-waarde | `omgevingsnormen[]` + geneste `normwaarden[]` (met `locatieRefs[]`) |
| gebiedsaanwijzing | `gebiedsaanwijzingen[]` (`locatieRef`) |
| ambtsgebied / regelingsgebied / pons / hoofdlijn | `ambtsgebied`, `regelingsgebied`, `ponsen[]`, `hoofdlijnen[]` |
| geometrie (GIO) | `bestanden[]` (`type: "gml"`, `gridfsId`, `frbrExpression`) |

**Wat de DSO-import wél/niet vult** (`ZipImportService.LeesOwZip` +
`IProjectRepository.FillFromImport` `$set`-lijst):

- **Wel:** `type`, `soortRegeling`, `frbrWork/Expression`, `bevoegdGezagCode`
  (van de organisatie, niet uit het pakket), `regeling`, alle toelichtingen,
  `activiteiten`, `gebiedsaanwijzingen`, `omgevingsnormen`(+`normwaarden`),
  `ambtsgebied`, `bestanden`, `importWarnings`, `importNormalizations`.
- **Niet (blijft leeg/`null`):** `naam` (bewust), **`regelingsgebied`, `ponsen`,
  `hoofdlijnen`** (mapping ontbreekt in de importer, terwijl de velden wél
  bestaan én worden weggeschreven), `versienummer`, `datum`, `autoNummering`,
  `members`, `opmerkingen`, `bewerkingen`.

> **Gat voor de adapter:** `storm-volledig` draagt `Regelingsgebied`/`Pons`
> (en de VrijeTekst-`Hoofdlijn`) nu wél verliesloos; een `volledig → SimplicIT`-
> adapter kan die drie lijsten dus vullen waar de huidige DSO-import ze leeg laat.

## 5. C#-projectstructuur in Storm-services

Nieuwe map `dotnet/` met `Storm.sln`:

```
dotnet/
  Storm.Core/         STORM-objectmodel (volledig/integrated/compact) +
                        XML (de)serialisatie + XSD-validatie +
                        pure-STORM-transforms (volledig↔integrated, →compact).
                        Alleen System.Xml. Geen SimplicIT-afhankelijkheid.
  Storm.Dso/          Download ↔ volledig: STOP/IMOW lezen + OW-object-XML
                        schrijven + aanleverpakket assembleren (vult de
                        SimplicIT-gaten). Poort van de Python-kiem.
  Storm.Imtr/         STTR/DMN: toepasbare regels ↔ volledig (DMN verbatim).
  Storm.Cli/          `storm` CLI over alle transforms.
  Storm.*.Tests/      xUnit; rondreis-tests tegen de repo-voorbeelden.
python/               de bestaande Python-kiem + voorbeeld-generator (referentie)
```

**Consumptie door SimplicIT.** Een nieuw project **`SimplicIT.Storm`** (in de
SimplicIT-solution) refereert `Storm.Core` (+ `Storm.Dso`/`Storm.Imtr`) en bevat
de `integrated ↔ SimplicIT.Domain`-adapter. Zo blijft Storm-services
**SimplicIT-agnostisch** (de afhankelijkheid loopt één kant op: SimplicIT →
Storm). Distributie: `Storm.Core` als **NuGet-package** (GitHub Packages of
lokale feed), versie gekoppeld aan de standaard-versie.

## 6. Per transformatie — hoe & waar

### 6a. Download+IMTR ↔ volledig (`Storm.Dso`, `Storm.Imtr`)
- **download → volledig**: STOP-besluit + IMOW-deelbestanden + GIO's lezen en
  faithful naar `storm-volledig` (3 namespaces + `storm-gio` + `Metadata`)
  serialiseren. Kan SimplicIT's `StopXmlParser`/`OwObjectParser` als
  parse-frontend hergebruiken (via een interface), of standalone parsen zodat
  STORM zelfstandig blijft. **Aanbevolen:** standalone in `Storm.Dso` (poort van
  de Python-kiem), met een adapter zodat SimplicIT z'n eigen parsers kan
  injecteren.
- **volledig → download**: de OW-objecten terug naar `activiteiten.xml`/
  `locaties.xml`/`omgevingsnormen.xml`/`manifest-ow.xml`, de tekst naar
  STOP (hergebruik `StopXmlGenerator`/`LvbbXmlGenerator`), de `storm-gio`'s
  splitsen naar GIO-wrapper + `.gml` (hergebruik `GioBuilder`), en het geheel
  tot pakbon/opdracht/ZIP assembleren. **Dit is de grootste SimplicIT-gat-vuller.**
- **IMTR**: `Storm.Imtr` leest KV-TR-ZIP's (manifest + opdracht + DMN) en bedt
  de DMN verbatim in `ToepasbareRegels`; en terug. Nieuw t.o.v. SimplicIT.

### 6b. volledig ↔ integrated (`Storm.Core`)
Pure-STORM hervorm: OW-objecten in-/uitvouwen op het artikel, IMOW-nummers als
herkomst (`@owId`), regel-locatie expliciet ↔ gedestilleerd. `integrated →
volledig` verliesvrij; `volledig → integrated` normaliseert (1:1). Rondreis-test
bewijst het.

### 6c. volledig/integrated → compact (`Storm.Core`)
Normaliserende reductie (≥10%-vocabulaire + 1:1-regelboek). Zie
`volledig-naar-compact.md` in de Storm-repo. Lossy; geen terugweg.

### 6d. integrated ↔ SimplicIT-DB (`SimplicIT.Storm`-adapter)
Near-isomorfe mapping `storm-integrated` ↔ `SimplicIT.Domain.Project`, daarna
persist via de bestaande seam:
- **import** (integrated → DB): bouw een `Project` (met `BevoegdGezagCode`),
  vul `Regeling.DocumentComponenten` met `Artikel`/`Lid`/`Divisietekst`, zet
  regels als annotaties (`OwJuridischeRegelIdentificatie`, `ActiviteitAanduidingen`,
  `Themas`), vul de platte OW-lijsten, upload geometrie/PDF naar GridFS als
  `BestandRef`, koppel tekst↔IMOW via wId. Hergebruik
  `DocumentComponentFactory`, `IdentifierGenerator`,
  `DocumentComponentTreeValidator`; persist via
  `IProjectRepository.FillFromImport`/`Create`. Model:
  `Core/Services/ZipImportService.LeesOwZip`.
- **export** (DB → integrated): lees `Project` → `storm-integrated`. Natuurlijk
  omdat het model al integrated-vormig is.
- **`Bewerkingen`/voorstellen/undo** blijven leeg bij import (dat is puur de
  collaboratieve editing-laag).

## 7. Identiteiten (dragende regel)

- **wId/eId/owId** worden door SimplicIT's `IdentifierGenerator` gegenereerd —
  STORM genereert nooit zelf persistente ids aan de SimplicIT-kant.
- Voor de **verliesvrije download-rondreis** draagt integrated de
  oorspronkelijke IMOW-nummers als **herkomst** mee; komt een plan uit een
  download, dan blijven die nummers exact behouden. Vers geredigeerd →
  gemunt bij export.
- STORM-`ref` (integrated) moet naar de **wId** van het doel-`Artikel`/`Lid`
  resolven — spiegelt SimplicIT's `WIdToOwIds`.

## 8. Test-/rondreisstrategie

Per transformatie een rondreis-test (canonieke vergelijking, zoals de Python-
kiem): `download → volledig → download` byte/canon-gelijk; `integrated →
volledig → integrated` verliesvrij; `integrated → DB → integrated`
model-gelijk. Fixtures: de Storm-repo-voorbeelden + SimplicIT's
`Tests.Shared/fixtures/import` en `Api.Tests/fixtures/roundtrip`.

## 9. Beslissingen (vastgelegd 2026-07-31)

1. **Adapter-locatie**: `SimplicIT.Storm` **in de SimplicIT-solution**
   (afhankelijkheid loopt één kant op: SimplicIT → Storm; Storm-services blijft
   SimplicIT-agnostisch). ✅
2. **Distributie**: `Storm.Core` als **NuGet-package** (GitHub Packages),
   versie gekoppeld aan de standaard-versie. ✅
3. **download↔volledig parse-frontend**: **standalone** in `Storm.Dso` (STORM
   zelfstandig en testbaar), met een interface zodat SimplicIT z'n eigen parsers
   kan injecteren. ✅
4. **Python**: **thin** — referentie/prototyping + voorbeeld-generator
   (`python/`). De transform-logica leeft alleen in C# (geen dubbele library).
   De oude `src/storm` (pre-split model) wordt gearchiveerd. Transitioneert
   later naar C#-only zodra `Storm.Cli` de repo-voorbeelden genereert. ✅
