# STORM — architectuur- en werkstructuurvoorstel

*Concept 2026-07-17, ter bespreking. Dit document beschrijft hoe de repo
wordt ingericht en waarom — nog niet de standaard zelf (die leeft in
`standaard/`).*

---

## 1. Wat STORM is (en wat de repo dus moet dragen)

STORM (STandaard Omgevingswet ReferentieModel) is één standaard die
STOP-tekst, IMOW-annotaties en IMTR-toepasbare-regels in samenhang
beschrijft. De repo draagt drie dingen, in volgorde van belangrijkheid:

1. **De standaard** — XSD, specificatie, voorbeelden. Dit is het product;
   alles hieronder is gereedschap eromheen.
2. **Transformaties** — van en naar de bestaande DSO-formaten.
3. **Renvooiservice** — vergelijken van versies: STOP-renvooi, OW-diff,
   GIO-renvooi, samenloop-detectie.

## 2. Kernprincipe: hub-and-spoke

STORM is het **naafformaat**. Elke transformatie loopt van of naar STORM,
nooit van randformaat naar randformaat:

```
  LVBB-download ⇄ STORM ⇄ BHKV-aanlevering
                    ⇅
             IMTR-aanlevering
```

Twee gevolgen die het ontwerp dragen:

- **N formaten = 2N adapters** in plaats van N×N paren. Een nieuw formaat
  (bv. IMRO voor het oude regime) kost één adapter-paar.
- **De renvooiservice werkt uitsluitend op STORM-pakketten.** Wie twee
  LVBB-downloads wil vergelijken converteert eerst; daarmee krijgt élk
  formaat met een adapter gratis renvooi. Vergelijken hoeft maar één keer
  gebouwd te worden, in één model.

## 3. Renvooi = één diff, drie gezichten

De vier gevraagde functies zijn geen vier losse bouwwerken maar **één
diffkern met drie assen** plus een afgeleide:

| Functie | As van de diff | Output |
|---|---|---|
| STOP-renvooi | tekst (de eId/wId-boom) | renvooi-weergave (HTML; later evt. STOP-renvooi-XML) |
| OW-diff | objecten (owId's: regels, activiteiten, aanwijzingen, exportregels) | rapport toegevoegd/gewijzigd/vervallen |
| GIO-renvooi | geo (basisgeo-ids per GIO-work; geometrisch verschil optioneel) | rapport + optioneel verschil-GML |
| Samenloop-detectie | *afgeleide*: snijd de geraakte-ankers-sets van twee diffs | conflictrapport per eId/work/owId |

`storm_diff(pakket_A, pakket_B)` levert één diffmodel; de vier functies
zijn views daarop. Samenloop: besluiten B1 en B2 op dezelfde regeling
raken elk een set ankers (eId's, GIO-works, owId's) — samenloop is de
doorsnede van die sets. De canonieke-vorm-machinerie die de
rondreis-tests al gebruiken (volgorde- en whitespace-ongevoelige
vergelijking) is de kiem van deze diffkern.

## 4. De zes transformaties

| Naam (CLI-werkwoord) | Bron ⇄ Doel | Status vertrekpunt |
|---|---|---|
| `download2storm` | LVBB-uitlevering/consolidatie (consolidaties.xml + ow\*.xml + GML's) → STORM | ~80% — bestaat als `naar_storm.py` |
| `storm2download` | STORM → uitleverings-vorm (STOP-tekst + ow-deelbestanden) | ~80% — bestaat als `van_storm.py` |
| `bhkv2storm` | LVBB-aanleverpakket (opdracht + manifest + besluit + GIO's) → STORM | ~70% — zelfde lezer, mist besluit-envelop-metadata |
| `storm2bhkv` | STORM → aanlever-ZIP (opdracht, manifesten, hashes, ZIP-layout) | nieuw — bhkv-standaarden-skill kent layout + foute-tabel |
| `imtr2storm` | KV-TR-ZIP (manifest + opdracht + DMN) → STORM | ~80% — DMN-lezing bestaat; ZIP/manifest-laag ontbreekt |
| `storm2imtr` | STORM → KV-TR-ZIP per ToepasbareActiviteit | ~60% — DMN-reconstructie bestaat (verbatim) |

Gedeelde onderdelen (STOP-tekstlezer, IMOW-objectlezer, GIO/GML-lezer)
leven in de kern, niet in de adapters; `download2storm` en `bhkv2storm`
zijn dunne schillen om dezelfde lezers.

## 5. Werkstructuur

```
Storm/
├── README.md                  # oriëntatie + quickstart
├── ARCHITECTUUR.md            # dit document
│
├── standaard/                 # HET PRODUCT — geen code
│   ├── xsd/storm.xsd
│   ├── specificatie/          # STORM-specificatie.md (principes P1–P10, mappings)
│   ├── CHANGELOG.md           # versiebeleid standaard (semver, nu 0.2.0)
│   └── voorbeelden/
│       └── mini/              # klein maar volledig STORM-pakket (CI draait hierop)
│
├── src/storm/                 # python-package (src-layout, pyproject)
│   ├── pakket.py              # STORM-pakket lezen/schrijven/valideren (storm.xml + gio/)
│   ├── canoniek.py            # canonieke vormen — gedeeld door tests én diffkern
│   ├── lezers/                # gedeelde formaat-lezers (stop_tekst, imow, gio, sttr)
│   ├── adapters/
│   │   ├── download.py        # download2storm / storm2download
│   │   ├── bhkv.py            # bhkv2storm / storm2bhkv
│   │   └── imtr.py            # imtr2storm / storm2imtr
│   ├── renvooi/
│   │   ├── diff.py            # storm_diff → diffmodel (3 assen)
│   │   ├── stop_renvooi.py    # tekst-as → HTML-renvooi
│   │   ├── ow_diff.py         # object-as → rapport
│   │   ├── gio_renvooi.py     # geo-as → rapport
│   │   └── samenloop.py       # doorsnede van geraakte ankers
│   └── cli.py                 # `storm <werkwoord>`-CLI (click)
│
├── tests/                     # pytest; rondreis per corpus
│   ├── corpora.py             # paden naar externe corpora (env-var, skip indien afwezig)
│   └── test_rondreis_*.py
│
├── service/                   # LATER: dunne FastAPI-laag over renvooi/
│   └── README.md              # alleen contract-schets tot fase 5
│
└── pyproject.toml
```

**Testdata-strategie**: de grote corpora (Gemeentestad-repo, vault
`raw/voorbeeldbestanden-*`) blijven waar ze zijn en worden via
`tests/corpora.py` gevonden (env-var/config; tests skippen netjes als een
corpus ontbreekt). Alleen het `mini/`-voorbeeld leeft in de repo zelf,
zodat CI zonder externe paden draait én er altijd een normatief
voorbeeldpakket bij de standaard zit.

## 6. Keuzepunten (met voorkeur)

### 6a. Kern: direct-op-XML of objectmodel?

| | Direct-op-XML (huidig) | Volwaardig objectmodel | **Hybride (voorkeur)** |
|---|---|---|---|
| Adapters | bewezen, verliesvrij | herbouw nodig | blijven op XML |
| Diff/renvooi | vergelijken wordt ad-hoc | ideaal | canonieke laag (`canoniek.py`) als "objectmodel light" |
| Onderhoud | laag | hoog | middel |

De adapters zijn al verliesvrij op XML — dat niet herbouwen. De diffkern
krijgt zijn eigen canonieke laag; als die groeit, groeit hij organisch
richting objectmodel.

### 6b. Renvooiservice: CLI eerst of meteen HTTP?

| | CLI-first (voorkeur) | Meteen FastAPI |
|---|---|---|
| Snelheid naar werkende functie | hoog | lager |
| Deploy/beheer | geen | Railway-kosten + beheer vanaf dag 1 |
| Later alsnog HTTP | triviaal (dunne laag over dezelfde functies) | — |

`service/` blijft een contract-schets tot de renvooi-functies er zijn.

### 6c. Taal

Python 3.12+ (bestaand werk, lxml/xmlschema, shapely voor geo-optioneel).
STOP-renvooi-HTML is templating, geen reden voor een tweede taal.

## 7. Fasering

| Fase | Inhoud | Resultaat |
|---|---|---|
| 0 | Repo-skelet + migratie bestaand werk uit `schemaTestsRichard/storm` (xsd/spec → `standaard/`, converters → `adapters/download.py`+`lezers/`, rondreis → pytest) + mini-voorbeeldpakket | alle bestaande tests groen in de nieuwe structuur |
| 1 | Adapters afmaken: `storm2bhkv` (opdracht/manifest/hashes/ZIP), IMTR-ZIP in/uit | zes werkende transformaties |
| 2 | Diffkern + OW-diff + GIO-renvooi (id-niveau) | `storm diff A B` werkt |
| 3 | STOP-renvooi: tekstdiff op eId-niveau + inline markering, HTML-render | leesbare renvooi-weergave |
| 4 | Samenloop-detectie (n besluiten op één regeling) | conflictrapport |
| 5 | Service-laag (FastAPI) + evt. deploy | renvooiservice als API |

Fase 0–1 zijn vooral verhuizen en afronden; het nieuwe denkwerk zit in
fase 2–4.

## 8. Wat bewust buiten scope blijft (nu)

- **Mutaties/was-wordt als invoerformaat** (RegelingMutatie): de
  renvooiservice vergelijkt twee *volledige* versies — dat is juist de
  route om zonder mutatie-XML te kunnen. Mutatie-lezing kan later een
  adapter worden.
- **Presentatie/symbolisatie** (Kaart, SymbolisatieItem): geen inhoud.
- **Geometrische renvooi** (echte polygon-verschillen): fase 2 doet
  id-niveau; shapely-verschil is een optionele verdieping.
