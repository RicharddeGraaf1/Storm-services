"""STORM-CLI: transformaties en rondreis vanaf de commandoregel.

    storm download2storm <bronmap> <doel.xml> [--imtr MAP]
    storm storm2download <storm.xml> <doelmap>
    storm rondreis <bronmap> <doelmap> [--imtr MAP]

`download2storm` accepteert zowel LVBB-uitleveringen (consolidaties) als
BHKV-aanleverpakketten — de lezers herkennen beide vormen. Splitsing in
aparte adapters (bhkv/imtr, incl. ZIP/manifest-laag) volgt in fase 1.
"""

from __future__ import annotations

from pathlib import Path

import click

from . import naar_storm, van_storm
from .rondreis import rondreis as draai_rondreis


@click.group()
def cli():
    """STORM — één standaard voor STOP + IMOW + IMTR."""


@cli.command()
@click.argument("bronmap", type=click.Path(exists=True, path_type=Path))
@click.argument("doel", type=click.Path(path_type=Path))
@click.option("--imtr", type=click.Path(exists=True, path_type=Path),
              help="map met STTR-bestanden (*.dmn)")
def download2storm(bronmap: Path, doel: Path, imtr: Path | None):
    """LVBB-uitlevering of BHKV-aanlevering -> STORM-pakket."""
    naar_storm.converteer(bronmap, doel, imtr)


@cli.command()
@click.argument("storm_xml", type=click.Path(exists=True, path_type=Path))
@click.argument("doelmap", type=click.Path(path_type=Path))
def storm2download(storm_xml: Path, doelmap: Path):
    """STORM-pakket -> STOP-tekst + IMOW-deelbestanden + STTR-DMN's."""
    van_storm.converteer(storm_xml, doelmap)


@cli.command()
@click.argument("bronmap", type=click.Path(exists=True, path_type=Path))
@click.argument("doelmap", type=click.Path(path_type=Path))
@click.option("--imtr", type=click.Path(exists=True, path_type=Path))
def rondreis(bronmap: Path, doelmap: Path, imtr: Path | None):
    """Bewijs verliesvrijheid: heen, valideer, terug, vergelijk."""
    fouten = draai_rondreis(bronmap, doelmap, imtr)
    if fouten:
        for fout in fouten:
            click.echo(f"FAIL — {fout}")
        raise SystemExit(1)
    click.echo("PASS — rondreis verliesvrij")


@cli.command()
@click.argument("storm_xml", type=click.Path(exists=True, path_type=Path))
@click.argument("doelmap", type=click.Path(path_type=Path))
@click.option("--zip", "maak_zip", is_flag=True,
              help="pak de aanlevering ook in als ZIP")
@click.option("--id-levering")
@click.option("--datum-bekendmaking")
def storm2bhkv(storm_xml: Path, doelmap: Path, maak_zip: bool,
               id_levering: str | None, datum_bekendmaking: str | None):
    """STORM-pakket -> LVBB-aanleverpakket (besluit, GIO's, OW, manifesten)."""
    from .adapters.bhkv import storm2bhkv as export
    export(storm_xml, doelmap, maak_zip, id_levering, datum_bekendmaking)


@cli.command()
@click.argument("storm_xml", type=click.Path(exists=True, path_type=Path))
@click.argument("doelmap", type=click.Path(path_type=Path))
@click.option("--geldig-begindatum")
def storm2imtr(storm_xml: Path, doelmap: Path,
               geldig_begindatum: str | None):
    """STORM-pakket -> KV-TR-aanlever-ZIPs (één per regelbestand)."""
    from .adapters.imtr import storm2imtr as export
    export(storm_xml, doelmap, geldig_begindatum)


@cli.command()
@click.argument("storm_xml", type=click.Path(exists=True, path_type=Path))
@click.argument("doel", type=click.Path(path_type=Path))
def complete2compact(storm_xml: Path, doel: Path):
    """Degradeer een STORM-document naar profiel compact (tekstbehoud)."""
    import xml.etree.ElementTree as ET
    from collections import Counter

    from .compact import naar_compact
    from .storm_common import STORM, schrijf_xml

    regeling = ET.parse(storm_xml).getroot()
    tekst = regeling.find(f"{{{STORM}}}Tekst")
    meldingen = naar_compact(tekst)
    doel.parent.mkdir(parents=True, exist_ok=True)
    schrijf_xml(regeling, doel, default_ns=STORM, alleen_ns=STORM)
    for regel, n in Counter(meldingen).most_common():
        click.echo(f"  {n:>4}x {regel}")
    click.echo(f"Geschreven: {doel} (profiel compact)")


if __name__ == "__main__":
    cli()
