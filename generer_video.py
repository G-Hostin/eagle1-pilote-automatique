"""
Fabrique la video de demonstration d'Eagle-1.

Demande des parties a l'API jusqu'a reunir assez d'atterrissages reussis, incruste sur
chaque image le numero de l'atterrissage et la recompense accumulee, puis monte le tout.
Aucune logique d'apprentissage par renforcement ici : le script collecte et monte.

Les images sont ecrites sur disque au fur et a mesure plutot qu'empilees en memoire :
1250 images en 400x600 representeraient pres d'un gigaoctet de RAM.

Lancement, l'API devant tourner a cote :
    uv run uvicorn api:app
    uv run python generer_video.py
"""

import base64
import io
import shutil
import tempfile
from pathlib import Path

import requests
from moviepy import ImageSequenceClip
from PIL import Image, ImageDraw, ImageFont

API = "http://127.0.0.1:8000"
SORTIE = "eagle1_atterrissages.mp4"
IMAGES_PAR_SECONDE = 50
DUREE_VISEE = 25          # secondes
MAX_TENTATIVES = 30

images_visees = DUREE_VISEE * IMAGES_PAR_SECONDE

GRIS = (176, 176, 176)
BLANC = (255, 255, 255)


def police(taille: int):
    """Une police lisible, avec repli si les polices systeme sont absentes."""
    for chemin in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(chemin, taille)
        except Exception:
            continue
    return ImageFont.load_default()


PETITE = police(16)
GRANDE = police(26)


def annote(image_png: bytes, numero: int, total: int, recompense: float, chemin: Path) -> None:
    """Incruste le numero de l'atterrissage et la recompense accumulee."""
    image = Image.open(io.BytesIO(image_png)).convert("RGB")
    dessin = ImageDraw.Draw(image)
    dessin.text((14, 12), f"Atterrissage {numero} / {total}", font=PETITE, fill=GRIS)
    dessin.text((14, 34), f"Recompense  {recompense:+.1f}", font=GRANDE, fill=BLANC)
    image.save(chemin)


def main() -> None:
    try:
        sante = requests.get(f"{API}/health", timeout=5).json()
    except Exception as erreur:
        raise SystemExit(
            f"API injoignable sur {API}. Lancer d'abord : uv run uvicorn api:app\n{erreur}"
        )
    print(f"API disponible, modele {sante['modele']}")

    # Premiere passe : on collecte les parties reussies, sans encore les ecrire.
    parties, tentatives, total_images = [], 0, 0
    while total_images < images_visees and tentatives < MAX_TENTATIVES:
        tentatives += 1
        partie = requests.post(f"{API}/episode", json={"avec_images": True}, timeout=300).json()
        mesure = partie["mesure"]

        if not mesure["reussite"]:
            print(f"  partie ecartee, recompense {mesure['recompense']:.1f}")
            continue

        parties.append(partie)
        total_images += len(partie["images"])
        print(f"  atterrissage {len(parties)} retenu, recompense "
              f"{mesure['recompense']:6.1f} | {total_images} images au total")

    if not parties:
        raise SystemExit("Aucun atterrissage reussi obtenu.")

    # Seconde passe : annotation et ecriture sur disque, image par image.
    dossier = Path(tempfile.mkdtemp(prefix="eagle1_"))
    chemins = []
    try:
        for numero, partie in enumerate(parties, 1):
            cumul = 0.0
            for image, recompense in zip(partie["images"], partie["recompenses"]):
                cumul += recompense
                chemin = dossier / f"{len(chemins):05d}.png"
                annote(base64.b64decode(image), numero, len(parties), cumul, chemin)
                chemins.append(str(chemin))

        chemins = chemins[:images_visees]
        clip = ImageSequenceClip(chemins, fps=IMAGES_PAR_SECONDE)
        clip.write_videofile(SORTIE, codec="libx264", audio=False, logger=None)
        clip.close()

        print(f"\n{SORTIE} ecrit")
        print(f"  {len(parties)} atterrissages, {len(chemins)} images, "
              f"{len(chemins) / IMAGES_PAR_SECONDE:.1f} secondes")
        print("  recompenses : "
              + ", ".join(f"{p['mesure']['recompense']:.0f}" for p in parties))
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


if __name__ == "__main__":
    main()
