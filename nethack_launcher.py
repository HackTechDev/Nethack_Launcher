#!/usr/bin/env python3
"""Lanceur : menu pour démarrer NetHack ou l'éditeur de carte."""

import os
import subprocess
import sys
from pathlib import Path

HOME = Path.home()

ENTREES = [
    ("Jouer à NetHack", HOME / "nh/install/games/nethack"),
    ("Éditeur de carte", HOME / "JEUX/NETHACK/NetHack_MapEditor/nhmapedit.sh"),
]


def effacer_ecran():
    os.system("clear" if os.name != "nt" else "cls")


def afficher_menu():
    print("=" * 34)
    print("        NETHACK - LANCEUR")
    print("=" * 34)
    for i, (libelle, _) in enumerate(ENTREES, start=1):
        print(f"  {i}. {libelle}")
    print("  q. Quitter")
    print("=" * 34)


def lancer(chemin: Path):
    if not chemin.is_file():
        print(f"Erreur : fichier introuvable : {chemin}")
        return
    if not os.access(chemin, os.X_OK):
        print(f"Erreur : fichier non exécutable : {chemin}")
        return
    try:
        # Exécution depuis le dossier du programme (utile pour les scripts relatifs)
        subprocess.run([str(chemin)], cwd=chemin.parent)
    except KeyboardInterrupt:
        pass
    except OSError as e:
        print(f"Erreur au lancement : {e}")


def main():
    while True:
        effacer_ecran()
        afficher_menu()
        try:
            choix = input("Votre choix : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choix in ("q", "quit", "quitter"):
            return 0
        if choix.isdigit() and 1 <= int(choix) <= len(ENTREES):
            _, chemin = ENTREES[int(choix) - 1]
            lancer(chemin)
            input("\nAppuyez sur Entrée pour revenir au menu...")
        else:
            input("Choix invalide. Appuyez sur Entrée pour continuer...")


if __name__ == "__main__":
    sys.exit(main())
