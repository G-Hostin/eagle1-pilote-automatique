"""
API du pilote automatique d'Eagle-1.

Seul composant du projet qui connaisse l'apprentissage par renforcement : il charge le
modele entraine et fait tourner la simulation. Les interfaces ne font que l'interroger.

Lancement :
    uv run uvicorn api:app
    documentation interactive sur http://127.0.0.1:8000/docs
"""

import base64
import io
from typing import Optional

import gymnasium as gym
import numpy as np
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field
from stable_baselines3 import PPO

FICHIER_MODELE = "ppo_lunarlander"
ENVIRONNEMENT = "LunarLander-v3"

# Criteres de la mission
SEUIL_REUSSITE = 200.0
DEMI_LARGEUR_ZONE = 0.2        # la zone entre les deux drapeaux va de -0.2 a +0.2

# Cout en recompense de chaque image de poussee, defini par l'environnement.
# Sert a estimer le carburant consomme, second objectif du brief.
COUT_MOTEUR_PRINCIPAL = 0.30
COUT_MOTEUR_LATERAL = 0.03

MOTEUR_PRINCIPAL = 2
MOTEURS_LATERAUX = (1, 3)

NOMS_ACTIONS = {
    0: "ne rien faire",
    1: "moteur d'orientation gauche",
    2: "moteur principal",
    3: "moteur d'orientation droit",
}

NOMS_OBSERVATIONS = [
    "position_x",
    "position_y",
    "vitesse_x",
    "vitesse_y",
    "angle",
    "vitesse_rotation",
    "contact_gauche",
    "contact_droit",
]

app = FastAPI(
    title="Pilote automatique Eagle-1",
    description="Acces au modele d'atterrissage entraine par renforcement.",
    version="2.0",
)

try:
    modele = PPO.load(FICHIER_MODELE)
except Exception as erreur:  # pragma: no cover
    raise RuntimeError(
        f"Modele introuvable ou illisible ({FICHIER_MODELE}.zip). "
        f"Il est produit par l'etape 2 du notebook. Detail : {erreur}"
    ) from erreur


# ----------------------------------------------------------------- schemas


class Etat(BaseModel):
    """Une observation : les 8 valeurs que percoit l'agent."""

    observation: list[float] = Field(..., min_length=8, max_length=8)


class DemandeEpisode(BaseModel):
    seed: Optional[int] = Field(None, description="Fixe le tirage pour rejouer la meme partie.")
    avec_images: bool = Field(True, description="Renvoie les images du rendu.")


class DemandeEvaluation(BaseModel):
    n_episodes: int = Field(30, ge=1, le=200)


# ----------------------------------------------------------------- mesures


def _mesure(observations: list[list[float]], actions: list[int], total: float) -> dict:
    """Traduit une partie en indicateurs de mission : fiabilite, precision, carburant."""
    tableau = np.asarray(observations)
    gestes = np.asarray(actions)

    # Precision : ecart horizontal a la cible au moment ou une jambe touche le sol.
    contact = (tableau[:, 6] + tableau[:, 7]) > 0
    pose = bool(contact.any())
    instant = int(np.argmax(contact)) if pose else len(tableau) - 1
    ecart = abs(float(tableau[instant, 0]))

    # Carburant : chaque image de poussee coute des points de recompense.
    n_principal = int((gestes == MOTEUR_PRINCIPAL).sum())
    n_lateraux = int(np.isin(gestes, MOTEURS_LATERAUX).sum())
    carburant = n_principal * COUT_MOTEUR_PRINCIPAL + n_lateraux * COUT_MOTEUR_LATERAL

    return {
        "recompense": total,
        "steps": len(actions),
        "reussite": total >= SEUIL_REUSSITE,
        "pose": pose,
        "ecart_cible": ecart,
        "dans_zone": pose and ecart <= DEMI_LARGEUR_ZONE,
        "carburant": round(carburant, 2),
        "images_moteur_principal": n_principal,
        "images_moteurs_lateraux": n_lateraux,
    }


def _encode(image: np.ndarray) -> str:
    tampon = io.BytesIO()
    Image.fromarray(image).save(tampon, format="PNG")
    return base64.b64encode(tampon.getvalue()).decode("ascii")


def _joue_un_episode(seed: Optional[int] = None, avec_images: bool = False) -> dict:
    """Joue une partie complete avec le modele charge."""
    env = gym.make(ENVIRONNEMENT, render_mode="rgb_array" if avec_images else None)
    observation, _ = env.reset(seed=seed)

    observations, actions, recompenses, images = [], [], [], []
    termine = tronque = False

    while not termine and not tronque:
        action, _ = modele.predict(observation, deterministic=True)
        action = int(action)

        observations.append([float(v) for v in observation])
        actions.append(action)

        observation, recompense, termine, tronque, _ = env.step(action)
        recompenses.append(float(recompense))

        if avec_images:
            images.append(env.render())

    env.close()

    return {
        "observations": observations,
        "actions": actions,
        "recompenses": recompenses,
        "images": [_encode(i) for i in images],
        "mesure": _mesure(observations, actions, float(sum(recompenses))),
    }


# ----------------------------------------------------------------- routes


@app.get("/health")
def health() -> dict:
    """Etat du service et informations sur le modele charge."""
    return {
        "statut": "ok",
        "modele": f"{FICHIER_MODELE}.zip",
        "algorithme": type(modele).__name__,
        "environnement": ENVIRONNEMENT,
        "seuil_reussite": SEUIL_REUSSITE,
        "demi_largeur_zone": DEMI_LARGEUR_ZONE,
    }


@app.get("/actions")
def actions() -> dict:
    """Signification des actions et des observations."""
    return {"actions": NOMS_ACTIONS, "observations": NOMS_OBSERVATIONS}


@app.post("/play")
def play(etat: Etat) -> dict:
    """Decide d'une action a partir d'un etat. Le coeur du pilote automatique."""
    observation = np.asarray(etat.observation, dtype=np.float32)
    if not np.all(np.isfinite(observation)):
        raise HTTPException(status_code=422, detail="L'observation contient des valeurs non finies.")

    action, _ = modele.predict(observation, deterministic=True)
    action = int(action)
    return {"action": action, "nom_action": NOMS_ACTIONS[action]}


@app.post("/episode")
def episode(demande: DemandeEpisode) -> dict:
    """Joue une partie complete et renvoie sa trajectoire, ses indicateurs et ses images."""
    partie = _joue_un_episode(seed=demande.seed, avec_images=demande.avec_images)
    partie["noms_observations"] = NOMS_OBSERVATIONS
    partie["noms_actions"] = NOMS_ACTIONS
    return partie


@app.post("/evaluate")
def evaluate(demande: DemandeEvaluation) -> dict:
    """Joue une campagne de parties et renvoie de quoi alimenter le tableau de bord.

    Les images ne sont pas produites ici : sur 200 parties elles satureraient la memoire.
    """
    mesures, decisions = [], []

    for numero in range(demande.n_episodes):
        partie = _joue_un_episode(avec_images=False)
        mesure = partie["mesure"]
        mesures.append(mesure)
        # chaque decision porte l'issue de sa partie, pour pouvoir filtrer ensuite
        for observation, action in zip(partie["observations"], partie["actions"]):
            decisions.append(dict(
                zip(NOMS_OBSERVATIONS, observation),
                action=action,
                partie=numero,
                posee=mesure["pose"],
            ))

    recompenses = np.array([m["recompense"] for m in mesures])
    return {
        "n_episodes": demande.n_episodes,
        "seuil_reussite": SEUIL_REUSSITE,
        "demi_largeur_zone": DEMI_LARGEUR_ZONE,
        "resume": {
            "recompense_moyenne": float(recompenses.mean()),
            "ecart_type": float(recompenses.std()),
            "pire_partie": float(recompenses.min()),
            "taux_reussite": float((recompenses >= SEUIL_REUSSITE).mean()),
        },
        "episodes": mesures,
        "decisions": decisions,
        "noms_actions": NOMS_ACTIONS,
    }
