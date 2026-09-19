"""
Demarre tout Eagle-1 en une commande : l'API, puis les interfaces.

    uv run python lancer.py

Ctrl+C arrete l'ensemble.
"""

import subprocess
import sys
import time
import webbrowser

import requests

PORT_API = 8000
PORT_INTERFACES = 8501
DELAI_DEMARRAGE = 60  # secondes accordees a l'API pour repondre


def demarre(commande: list[str]) -> subprocess.Popen:
    return subprocess.Popen(commande, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def attend_api(adresse: str) -> bool:
    for _ in range(DELAI_DEMARRAGE):
        try:
            requests.get(f"{adresse}/health", timeout=1).raise_for_status()
            return True
        except Exception:
            time.sleep(1)
    return False


def main() -> None:
    adresse_api = f"http://127.0.0.1:{PORT_API}"
    adresse_interfaces = f"http://127.0.0.1:{PORT_INTERFACES}"
    processus: list[subprocess.Popen] = []

    try:
        print("Demarrage de l'API...")
        processus.append(demarre([
            sys.executable, "-m", "uvicorn", "api:app",
            "--port", str(PORT_API), "--log-level", "warning",
        ]))

        if not attend_api(adresse_api):
            print("\nL'API n'a pas demarre. Causes possibles :")
            print(f"  - le port {PORT_API} est deja occupe")
            print("  - ppo_lunarlander.zip est absent, il est produit par l'etape 2 du notebook")
            return

        print("Demarrage des interfaces...")
        processus.append(demarre([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", str(PORT_INTERFACES),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ]))
        time.sleep(4)

        print()
        print("  Interfaces  ", adresse_interfaces, " (deux onglets en haut)")
        print("  API         ", f"{adresse_api}/docs")
        print()
        print("  Ctrl+C pour tout arreter.")
        webbrowser.open(adresse_interfaces)

        while True:
            time.sleep(1)
            for p in processus:
                if p.poll() is not None:
                    print("\nUn composant s'est arrete, fermeture de l'ensemble.")
                    return

    except KeyboardInterrupt:
        print("\nArret demande.")
    finally:
        for p in processus:
            if p.poll() is None:
                p.terminate()
        for p in processus:
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()
        print("Tout est arrete.")


if __name__ == "__main__":
    main()
