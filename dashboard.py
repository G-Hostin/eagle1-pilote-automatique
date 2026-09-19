"""
Tableau de bord du pilote automatique d'Eagle-1.

Repond aux trois questions du brief de mission : le pilote est-il fiable, precis et
econome ? Toutes les parties sont jouees par l'API, ce fichier ne contient aucune
logique d'apprentissage par renforcement.

Lancement, seul ou via app.py :
    uv run streamlit run dashboard.py
"""

import pandas as pd
import requests
import streamlit as st

API_DEFAUT = "http://127.0.0.1:8000"

# Quatre couleurs qui restent distinguables, y compris en vision des couleurs
# deficiente. L'ordre est fixe : une manoeuvre garde sa couleur sur tous les
# graphiques.
ORDRE_MANOEUVRES = [
    "moteur principal",
    "moteur d'orientation gauche",
    "moteur d'orientation droit",
    "ne rien faire",
]
# Noms courts pour les legendes, qui seraient tronquees autrement.
NOMS_COURTS = {
    "moteur principal": "principal",
    "moteur d'orientation gauche": "orientation gauche",
    "moteur d'orientation droit": "orientation droite",
    "ne rien faire": "aucune poussee",
}
COULEURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
GRIS = "#8c8b85"

# set_page_config n'est autorise qu'une fois : app.py s'en charge quand la page est
# ouverte dans l'onglet. En lancement isole, c'est ici que ca se joue.
try:
    st.set_page_config(page_title="Eagle-1, controle qualite", layout="wide")
except Exception:
    pass

st.title("Controle qualite du pilote")
st.caption(
    "Une campagne de parties jouees a la demande. L'autre onglet montre une partie "
    "en images, celui-ci en mesure plusieurs dizaines."
)

# ----------------------------------------------------------------- campagne

with st.sidebar:
    st.subheader("Campagne")
    api = st.text_input("Adresse de l'API", API_DEFAUT, key="api_dashboard")
    try:
        requests.get(f"{api}/health", timeout=5).raise_for_status()
        api_prete = True
    except Exception:
        st.error("API injoignable")
        st.caption("Lancer : `uv run python lancer.py`")
        api_prete = False

    n_episodes = st.slider("Nombre de parties", 10, 200, 40, step=10)
    if st.button("Lancer la campagne", type="primary", disabled=not api_prete):
        with st.spinner(f"{n_episodes} parties en cours..."):
            reponse = requests.post(f"{api}/evaluate", json={"n_episodes": n_episodes}, timeout=900)
            reponse.raise_for_status()
            st.session_state.campagne = reponse.json()

if "campagne" not in st.session_state:
    st.info("Regler le nombre de parties a gauche, puis lancer la campagne.")
    st.stop()

donnees = st.session_state.campagne
parties = pd.DataFrame(donnees["episodes"])
seuil = donnees["seuil_reussite"]
zone = donnees["demi_largeur_zone"]
resume = donnees["resume"]

# ----------------------------------------------------------------- verdict

if resume["recompense_moyenne"] >= seuil:
    st.success(
        f"**Critere de la mission tenu.** Recompense moyenne de "
        f"{resume['recompense_moyenne']:.1f} sur {donnees['n_episodes']} parties, "
        f"pour un seuil fixe a {seuil:.0f}."
    )
else:
    st.error(
        f"**Critere non tenu.** Recompense moyenne de {resume['recompense_moyenne']:.1f} "
        f"pour un seuil fixe a {seuil:.0f}."
    )

# ----------------------------------------------------------------- 1. fiabilite

st.subheader("Fiabilite")

colonnes = st.columns(4)
colonnes[0].metric(
    "Recompense moyenne",
    f"{resume['recompense_moyenne']:.1f}",
    delta=f"{resume['recompense_moyenne'] - seuil:+.1f} vs seuil",
)
colonnes[1].metric("Parties au-dessus du seuil", f"{resume['taux_reussite']:.0%}")
colonnes[2].metric("Ecart-type", f"{resume['ecart_type']:.1f}",
                   help="Plus il est faible, plus le pilote est regulier.")
colonnes[3].metric("Pire partie", f"{resume['pire_partie']:.1f}")

tronquees = int((parties["steps"] >= 1000).sum())
if tronquees:
    st.caption(
        f"{tronquees} partie(s) sur {len(parties)} se terminent a la limite de 1000 steps : "
        "le module reste en vol sans se poser. C'est le mode d'echec principal du pilote."
    )

st.line_chart(
    pd.DataFrame({
        "recompense": parties["recompense"],
        "seuil de la mission": [seuil] * len(parties),
    }),
    color=[COULEURS[0], GRIS],
    x_label="Partie",
    y_label="Recompense",
)

# ----------------------------------------------------------------- 2. precision

st.subheader("Precision d'atterrissage")

dans_zone = parties["dans_zone"].mean()
colonnes = st.columns(3)
colonnes[0].metric("Atterrissages dans la zone", f"{dans_zone:.0%}",
                   help=f"La zone entre les deux drapeaux s'etend de -{zone} a +{zone}.")
colonnes[1].metric("Ecart moyen a la cible", f"{parties['ecart_cible'].mean():.3f}")
colonnes[2].metric("Pire ecart", f"{parties['ecart_cible'].max():.3f}",
                   delta=f"{parties['ecart_cible'].max() - zone:+.3f} vs bord de zone",
                   delta_color="inverse")

st.caption(
    f"Le module se pose dans {dans_zone:.0%} des cas entre les drapeaux, avec un ecart "
    f"moyen de {parties['ecart_cible'].mean():.3f} pour une demi-largeur de zone de {zone}."
)

# ----------------------------------------------------------------- 3. carburant

st.subheader("Carburant")

cout_principal = (parties["images_moteur_principal"] * 0.30).sum()
cout_lateral = (parties["images_moteurs_lateraux"] * 0.03).sum()
part_principal = cout_principal / (cout_principal + cout_lateral)

colonnes = st.columns(3)
colonnes[0].metric("Carburant moyen par partie", f"{parties['carburant'].mean():.1f}",
                   help="Estime a partir des poussees : 0,30 point de recompense par image "
                        "de moteur principal, 0,03 par moteur lateral.")
colonnes[1].metric("Part du moteur principal", f"{part_principal:.0%}")
colonnes[2].metric("Partie la plus econome", f"{parties['carburant'].min():.1f}")

st.caption(
    f"Le moteur principal represente {part_principal:.0%} du carburant consomme. "
    "Economiser revient donc a ne l'allumer qu'au moment utile. La section suivante "
    "montre quand le pilote le declenche."
)

# ----------------------------------------------------------------- 4. manoeuvres

st.subheader("Quand les moteurs s'allument")
st.caption(
    "Les manoeuvres observees, croisees avec la situation dans laquelle elles ont ete "
    "prises."
)

decisions = pd.DataFrame(donnees["decisions"])
decisions["manoeuvre"] = decisions["action"].map(
    {int(k): v for k, v in donnees["noms_actions"].items()}
)

FILTRES = {
    "Toutes les parties": None,
    "Seulement celles qui se posent": True,
    "Seulement celles qui ne se posent pas": False,
}
choix = st.radio("Filtrer sur l'issue de la partie", list(FILTRES), horizontal=True)
if FILTRES[choix] is not None:
    decisions = decisions[decisions["posee"] == FILTRES[choix]]

if decisions.empty:
    st.info(f"Aucune partie dans cette campagne ne correspond a : {choix.lower()}.")
    st.stop()

st.caption(
    f"{len(decisions):,} decisions observees sur "
    f"{decisions['partie'].nunique()} partie(s).".replace(",", " ")
)

DECOUPAGES = {
    "Selon la vitesse de descente": (
        "vitesse_y", [-10, -0.6, -0.3, -0.1, 10],
        ["chute rapide", "chute moderee", "chute lente", "stabilise"],
    ),
    "Selon l'altitude": (
        "position_y", [-0.1, 0.15, 0.5, 1.0, 2.5],
        ["au sol", "basse", "moyenne", "haute"],
    ),
    "Selon l'ecart a la cible": (
        "position_x", [-2.5, -0.20, -0.05, 0.05, 0.20, 2.5],
        ["loin a gauche", "a gauche", "sur la cible", "a droite", "loin a droite"],
    ),
}

tableaux = {}
for titre, (colonne, bornes, etiquettes) in DECOUPAGES.items():
    # Le nom de l'index se retrouve dans la specification du graphique genere par
    # Streamlit, ou une apostrophe empeche le rendu. D'ou ce nom neutre.
    situation = pd.cut(decisions[colonne], bins=bornes, labels=etiquettes)
    situation.name = "situation"
    table = pd.crosstab(situation, decisions["manoeuvre"], normalize="index")
    table = table.reindex(columns=ORDRE_MANOEUVRES, fill_value=0.0)
    tableaux[titre] = table

    st.markdown(f"**{titre}**")
    st.bar_chart(
        table.rename(columns=NOMS_COURTS),
        horizontal=True,
        color=COULEURS,
        # sort=False garde l'ordre logique des tranches, du plus rapide au plus stable
        # par exemple, la ou le tri par defaut les remettrait dans l'ordre alphabetique.
        sort=False,
        x_label="",
        y_label="Part des manoeuvres",
        height=240,
    )

# On lit mal une proportion sur une barre empilee, d'ou le tableau chiffre ici.
with st.expander("Proportions exactes"):
    for titre, table in tableaux.items():
        st.markdown(f"**{titre}**")
        st.dataframe((table * 100).round(1), use_container_width=True)
