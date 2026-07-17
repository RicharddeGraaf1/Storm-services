# STORM-services

Transformaties en (in aanbouw) een renvooiservice rond de **STORM-standaard**.
De standaard zelf — XSD, specificatie, voorbeelden — leeft in een aparte repo:
[Storm](https://github.com/RicharddeGraaf1/Storm).

Architectuur en fasering: [ARCHITECTUUR.md](ARCHITECTUUR.md).

## De standaard vinden

Deze repo heeft het schema (om te valideren) en de voorbeeldpakketten (om op
te toetsen) uit de standaard-repo nodig. `src/storm/paden.py` zoekt die in
deze volgorde:

1. `$STORM_STANDAARD` — expliciet pad (overschrijft alles);
2. sibling `../Storm` — jouw lokale working copy; edits aan de standaard
   werken meteen door in de tests;
3. submodule `standaard-ref/` — gepinde versie voor CI en verse clones.

Op een verse clone:

```powershell
git clone --recurse-submodules https://github.com/RicharddeGraaf1/Storm-services.git
# of, na een gewone clone:
git submodule update --init
```

Staat de `Storm`-repo al als sibling (`c:\GIT\Storm`), dan hoef je de
submodule niet te initialiseren — die sibling wordt vanzelf gebruikt.

## Quickstart

```powershell
pip install -e .[test]

# LVBB-uitlevering of BHKV-aanlevering -> STORM-pakket
storm download2storm <bronmap> <doel.xml> [--imtr <map-met-dmn-of-zips>]

# STORM-pakket -> STOP-tekst + IMOW-deelbestanden + STTR-DMN's
storm storm2download <storm.xml> <doelmap>

# STORM-pakket -> LVBB-aanleverpakket (besluit, GIO's+wrappers, OW,
# manifesten; hashes worden herberekend) [--zip]
storm storm2bhkv <storm.xml> <doelmap>

# STORM-pakket -> KV-TR-aanlever-ZIPs (manifest+opdracht+DMN per bestand)
storm storm2imtr <storm.xml> <doelmap>

# STORM-complete -> profiel compact (tekstbehoud)
storm complete2compact <storm.xml> <doel.xml>

# verliesvrijheid bewijzen
storm rondreis <bronmap> <doelmap> [--imtr <map>]

pytest            # mini-voorbeeld + externe corpora (skipt wat ontbreekt)
```

## Stand (2026-07-17)

- **Aanleverlaag (fase 1)**: `storm2bhkv` reconstrueert het complete
  LVBB-aanleverpakket (besluit envelop-verliesvrij via het
  `Envelop`-compartiment, GIO's byte-verbatim, wrapper-hashes herberekend,
  manifesten gegenereerd); `storm2imtr` levert KV-TR-ZIPs. Beide richtingen
  in tests bewezen op de Gemeentestad-aanlevering.
- `download2storm`/`storm2download` werkend en verliesvrij bewezen op vier
  corpora (omgevingsplan regelstructuur, consolidatie-fallback,
  omgevingsvisie vrijetekst, 9 echte STTR-bestanden).
- `complete2compact`: conversie naar het compact-profiel met
  tekstbehoud-invariant (bewezen op 13.835 fragmenten).
- Fase 2–4 (gepland): diffkern → STOP-renvooi, OW-diff, GIO-renvooi,
  samenloop-detectie; fase 5: FastAPI-servicelaag (`service/`).

## Structuur

```
src/storm/
├── paden.py            resolver voor de standaard-repo
├── storm_common.py     namespaces, schema-URL, helpers
├── naar_storm.py       download/bhkv -> STORM
├── van_storm.py        STORM -> download
├── adapters/           bhkv.py (LVBB-pakket), imtr.py (KV-TR-ZIPs)
├── canoniek.py         canonieke vergelijking (diff-fundament)
├── rondreis.py         XSD-validatie + verliesvrijheids-rondreis
├── profielen.py        machineleesbaar compact-profiel
├── compact.py          conversie complete -> compact
└── cli.py              click-CLI (werkwoord `storm ...`)
tests/                  mini + externe corpora + fixtures
service/                renvooiservice-contractschets (fase 5)
standaard-ref/          git-submodule: de STORM-standaard (gepind)
```
