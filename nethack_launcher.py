#!/usr/bin/env python3
"""Lanceur : menu pour démarrer NetHack ou l'éditeur de carte."""

import configparser
import os
import subprocess
import sys
from pathlib import Path

FICHIER_CONFIG = Path(__file__).resolve().parent / "config.ini"

LOGO = r"""
 _   _      _   _   _            _
| \ | | ___| |_| | | | __ _  ___| | __
|  \| |/ _ \ __| |_| |/ _` |/ __| |/ /
| |\  |  __/ |_|  _  | (_| | (__|   <
|_| \_|\___|\__|_| |_|\__,_|\___|_|\_\
"""

LARGEUR = 40


def charger_entrees(fichier: Path):
    """Lit le fichier de configuration et renvoie la liste (libellé, chemin)."""
    if not fichier.is_file():
        raise ValueError(f"fichier de configuration introuvable : {fichier}")

    config = configparser.ConfigParser(interpolation=None)
    config.read(fichier, encoding="utf-8")

    entrees = []
    for section in config.sections():
        if "chemin" not in config[section]:
            raise ValueError(f"section [{section}] : clé « chemin » manquante")
        chemin = os.path.expandvars(config[section]["chemin"])
        libelle = config[section].get("libelle", section)
        entrees.append((libelle, Path(chemin).expanduser()))

    if not entrees:
        raise ValueError(f"aucune entrée définie dans {fichier}")
    return entrees


def effacer_ecran():
    os.system("clear" if os.name != "nt" else "cls")


def afficher_menu(entrees):
    print(LOGO)
    print("=" * LARGEUR)
    print("LANCEUR".center(LARGEUR).rstrip())
    print("=" * LARGEUR)
    for i, (libelle, _) in enumerate(entrees, start=1):
        print(f"  {i}. {libelle}")
    print("  q. Quitter")
    print("=" * LARGEUR)


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
    try:
        entrees = charger_entrees(FICHIER_CONFIG)
    except (ValueError, configparser.Error) as e:
        print(f"Erreur de configuration : {e}", file=sys.stderr)
        return 1

    while True:
        effacer_ecran()
        afficher_menu(entrees)
        try:
            choix = input("Votre choix : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choix in ("q", "quit", "quitter"):
            return 0
        if choix.isdigit() and 1 <= int(choix) <= len(entrees):
            _, chemin = entrees[int(choix) - 1]
            lancer(chemin)
            input("\nAppuyez sur Entrée pour revenir au menu...")
        else:
            input("Choix invalide. Appuyez sur Entrée pour continuer...")


if __name__ == "__main__":
    sys.exit(main())
