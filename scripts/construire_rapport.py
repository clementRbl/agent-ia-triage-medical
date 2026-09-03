"""Fabrique le rapport technique en PDF a partir de sa source Markdown.

Chaine : pandoc pour le Markdown vers HTML, puis le moteur de rendu de
Chrome pour le HTML vers PDF. Chrome plutot que wkhtmltopdf parce qu'il
applique reellement les regles de saut de page et les polices modernes ;
wkhtmltopdf, fige sur un vieux WebKit, ignore la moitie de la feuille de
style et couperait les tableaux au milieu.

Le nombre de pages est verifie a la fin : le cahier des charges en impose
vingt au maximum, et un depassement doit se voir ici, pas a la lecture.

Usage :
    uv run python scripts/construire_rapport.py
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = Path("rapport/rapport-technique.md")
STYLE = Path("rapport/style.css")
SORTIE = Path("rapport/Reboul_Clement_5_Rapport_082026.pdf")
PAGES_MAX = 20


def _chrome() -> str:
    for nom in ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable"):
        chemin = shutil.which(nom)
        if chemin:
            return chemin
    raise SystemExit(
        "Aucun navigateur trouvé pour le rendu PDF. Installez google-chrome ou chromium."
    )


def construire_html(source: Path, style: Path, destination: Path) -> None:
    if not shutil.which("pandoc"):
        raise SystemExit("pandoc est absent : `sudo apt install pandoc`.")
    subprocess.run(
        [
            "pandoc",
            str(source),
            "--from=markdown+raw_html+pipe_tables+footnotes",
            "--to=html5",
            "--standalone",
            f"--css={style.name}",
            "--metadata=lang=fr",
            "--metadata=title=Rapport technique",
            f"--output={destination}",
        ],
        check=True,
    )


def construire_pdf(html: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            _chrome(),
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            # Sans cette option, Chrome ajoute ses propres en-tetes et URL en
            # pied de page, ce qui n'a rien a faire sur un livrable.
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={destination.resolve()}",
            html.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
    )


def compter_pages(pdf: Path) -> int:
    """Compte les pages sans dependance supplementaire.

    Le nombre de pages figure dans le dictionnaire /Type /Pages du PDF ; le
    lire directement evite d'ajouter une bibliotheque entiere pour un entier.
    """
    contenu = pdf.read_bytes()
    marqueur = b"/Type /Pages"
    position = contenu.rfind(marqueur)
    if position == -1:
        marqueur = b"/Type/Pages"
        position = contenu.rfind(marqueur)
    if position == -1:
        return 0
    extrait = contenu[position : position + 400]
    for cle in (b"/Count ", b"/Count"):
        debut = extrait.find(cle)
        if debut != -1:
            chiffres = b""
            for octet in extrait[debut + len(cle) :]:
                caractere = bytes([octet])
                if caractere.isdigit():
                    chiffres += caractere
                elif chiffres:
                    break
            if chiffres:
                return int(chiffres)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--sortie", type=Path, default=SORTIE)
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"Source introuvable : {args.source}")

    html = args.source.with_suffix(".html")
    construire_html(args.source, STYLE, html)
    construire_pdf(html, args.sortie)

    pages = compter_pages(args.sortie)
    taille = args.sortie.stat().st_size / 1024
    print(f"écrit : {args.sortie} — {pages} pages, {taille:.0f} Ko")

    if pages > PAGES_MAX:
        print(
            f"\n⚠ {pages} pages pour un maximum de {PAGES_MAX}. Le livrable "
            "serait refusé en l'état.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
