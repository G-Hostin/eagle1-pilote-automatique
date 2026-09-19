"""
Point d'entree des interfaces d'Eagle-1.

Reunit les deux interfaces sur un seul serveur, sous deux onglets. Chacune reste un
fichier autonome : `streamlit run gui.py` et `streamlit run dashboard.py` fonctionnent
toujours separement.

Lancement :
    uv run streamlit run app.py
ou, avec l'API en meme temps :
    uv run python lancer.py
"""

import streamlit as st

st.set_page_config(page_title="Eagle-1", layout="wide")

st.navigation(
    [
        st.Page("gui.py", title="Regarder un atterrissage", default=True),
        st.Page("dashboard.py", title="Controle qualite"),
    ],
    position="top",
).run()
