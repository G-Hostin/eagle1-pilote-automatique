"""
Interface graphique du pilote automatique d'Eagle-1.

Montre une partie jouee par l'agent, image par image, et laisse inspecter n'importe
quel instant. Ce fichier ne contient aucune logique d'apprentissage par renforcement :
la partie est jouee par l'API, il ne fait que l'afficher.

Lancement, seul ou via app.py :
    uv run streamlit run gui.py
"""

import base64
import time

import pandas as pd
import requests
import streamlit as st

API_DEFAUT = "http://127.0.0.1:8000"
IMAGES_PAR_SECONDE = 50
BLEU = "#2a78d6"

# set_page_config n'est autorise qu'une fois : app.py s'en charge quand la page est
# ouverte dans l'onglet. En lancement isole, c'est ici que ca se joue.
try:
    st.set_page_config(page_title="Eagle-1, atterrissage", layout="wide")
except Exception:
    pass

st.title("Regarder un atterrissage")
st.caption(
    "Une partie jouee par le pilote automatique, rejouee image par image. "
    "L'autre onglet mesure la qualite du pilote sur plusieurs dizaines de parties."
)

# ----------------------------------------------------------------- demande

with st.sidebar:
    st.subheader("Partie")
    api = st.text_input("Adresse de l'API", API_DEFAUT, key="api_gui")
    try:
        requests.get(f"{api}/health", timeout=5).raise_for_status()
        api_prete = True
    except Exception:
        st.error("API injoignable")
        st.caption("Lancer : `uv run python lancer.py`")
        api_prete = False

    rejouer = st.checkbox("Rejouer une partie precise")
    numero = st.number_input("Numero de partie", 0, 10_000, 0, disabled=not rejouer)

    if st.button("Lancer un atterrissage", type="primary", disabled=not api_prete):
        with st.spinner("Manoeuvre en cours..."):
            reponse = requests.post(
                f"{api}/episode",
                json={"seed": int(numero) if rejouer else None, "avec_images": True},
                timeout=300,
            )
            reponse.raise_for_status()
            st.session_state.partie = reponse.json()
        st.session_state.animer = True

if "partie" not in st.session_state:
    st.info("Cliquer sur **Lancer un atterrissage** dans le panneau de gauche.")
    st.stop()

partie = st.session_state.partie
mesure = partie["mesure"]

# ----------------------------------------------------------------- resultat

colonnes = st.columns(4)
colonnes[0].metric("Issue", "Atterrissage" if mesure["pose"] else "Echec")
colonnes[1].metric("Recompense", f"{mesure['recompense']:.1f}")
colonnes[2].metric("Ecart a la cible", f"{mesure['ecart_cible']:.3f}",
                   delta="dans la zone" if mesure["dans_zone"] else "hors zone",
                   delta_color="normal" if mesure["dans_zone"] else "inverse")
colonnes[3].metric("Carburant", f"{mesure['carburant']:.1f}",
                   help=f"{mesure['images_moteur_principal']} images de moteur principal, "
                        f"{mesure['images_moteurs_lateraux']} de moteurs lateraux.")

# ----------------------------------------------------------------- animation

images = [base64.b64decode(i) for i in partie["images"]]
zone_image = st.empty()

if st.session_state.get("animer"):
    for image in images:
        zone_image.image(image, use_container_width=False)
        time.sleep(1 / IMAGES_PAR_SECONDE)
    st.session_state.animer = False
else:
    zone_image.image(images[-1], use_container_width=False)

if st.button("Rejouer l'animation"):
    st.session_state.animer = True
    st.rerun()

# ----------------------------------------------------------------- inspection

st.subheader("Inspecter un instant")

instant = st.slider("Step", 0, len(images) - 1, len(images) - 1)
gauche, droite = st.columns([3, 2])

with gauche:
    st.image(images[instant], use_container_width=False)

with droite:
    action = partie["actions"][instant]
    st.markdown(f"### {partie['noms_actions'][str(action)]}")
    st.caption("Manoeuvre choisie par le pilote a ce step.")
    st.dataframe(
        pd.DataFrame({
            "valeur": [round(v, 3) for v in partie["observations"][instant]],
        }, index=partie["noms_observations"]),
        use_container_width=True,
    )

# ----------------------------------------------------------------- score

st.subheader("Construction du score")

cumul, total = [], 0.0
for recompense in partie["recompenses"]:
    total += recompense
    cumul.append(total)

st.line_chart(
    pd.DataFrame({"recompense cumulee": cumul}),
    color=BLEU,
    x_label="Step",
    y_label="Recompense cumulee",
)
