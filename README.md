# Eagle-1, pilote automatique

Entraîner un agent à poser le module lunaire Eagle-1 sur sa zone cible, avec précision
et en économisant le carburant. Environnement `LunarLander-v3` de Gymnasium. Critère
fixé par la mission : récompense moyenne supérieure ou égale à 200 sur 100 épisodes
consécutifs.

## Résultat

L'agent retenu est un PPO entraîné sur 1 000 000 de steps. Sur 100 épisodes
d'évaluation : 258,1 de moyenne pour un écart-type de 23,8, médiane à 261,4,
99 épisodes au-dessus du seuil, et le pire reste à +150.

Un DQN a aussi été réglé et entraîné sur 400 000 steps. Il franchit le seuil à 201,5
de moyenne mais reste irrégulier : écart-type de 116,2, 74 épisodes sur 100 au-dessus
du seuil, pire épisode à -309,9. La comparaison complète est dans le notebook de
mission.

## Les notebooks

`Exercice_1.ipynb` explore les espaces d'observation et d'action de CartPole, puis
mesure une politique aléatoire.

`Exercice_2.ipynb` implémente le Q-Learning à la main sur FrozenLake, avec une Q-table
de 16 lignes sur 4 colonnes.

`Exercice_3.ipynb` remplace la Q-table par un réseau de neurones, d'abord écrit en
PyTorch, puis avec Stable-Baselines3.

`Mission_Eagle1.ipynb` contient la mission : exploration, base de référence, ablation
des hyperparamètres, mise en concurrence de DQN et PPO, évaluation finale.

## L'application

```
uv sync
uv run python lancer.py
```

L'API démarre sur le port 8000, les deux interfaces sur le port 8501.

`api.py` est le seul fichier qui charge le modèle et fait tourner la simulation. Les
interfaces n'importent pas Gymnasium, elles interrogent l'API et affichent ce qu'elle
renvoie.

`gui.py` montre un atterrissage image par image et laisse inspecter n'importe quel
step. `dashboard.py` joue une campagne de parties et mesure la fiabilité, la précision
d'atterrissage et la consommation de carburant. `generer_video.py` produit
`eagle1_atterrissages.mp4` en enchaînant plusieurs atterrissages réussis.

## Environnement

Python 3.13, `gymnasium[box2d]`, `stable-baselines3`, `torch` en CPU, `fastapi`,
`streamlit`. Versions exactes dans `pyproject.toml` et `uv.lock`.
