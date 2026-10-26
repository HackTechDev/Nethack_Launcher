#!/usr/bin/env python3
"""Lanceur : menu pour démarrer NetHack ou l'éditeur de carte."""

import argparse
import configparser
import os
import subprocess
import sys
from dataclasses import dataclass
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


@dataclass
class Entree:
    nom: str  # nom de la section dans config.ini
    libelle: str
    chemin: Path


def charger_entrees(fichier: Path):
    """Lit le fichier de configuration et renvoie la liste des entrées du menu."""
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
        entrees.append(Entree(section, libelle, Path(chemin).expanduser()))

    if not entrees:
        raise ValueError(f"aucune entrée définie dans {fichier}")
    return entrees


def trouver_entree(entrees, choix: str):
    """Renvoie l'entrée désignée par son numéro ou son nom de section, sinon None."""
    choix = choix.strip().lower()
    if choix.isdigit():
        if 1 <= int(choix) <= len(entrees):
            return entrees[int(choix) - 1]
        return None
    for entree in entrees:
        if entree.nom.lower() == choix:
            return entree
    return None


def effacer_ecran():
    os.system("clear" if os.name != "nt" else "cls")


def afficher_menu(entrees):
    print(LOGO)
    print("=" * LARGEUR)
    print("LANCEUR".center(LARGEUR).rstrip())
    print("=" * LARGEUR)
    for i, entree in enumerate(entrees, start=1):
        print(f"  {i}. {entree.libelle}")
    print("  q. Quitter")
    print("=" * LARGEUR)


def lancer(entree: Entree):
    """Lance le programme de l'entrée et renvoie son code de sortie."""
    chemin = entree.chemin
    if not chemin.is_file():
        print(f"Erreur : fichier introuvable : {chemin}", file=sys.stderr)
        return 1
    if not os.access(chemin, os.X_OK):
        print(f"Erreur : fichier non exécutable : {chemin}", file=sys.stderr)
        return 1
    try:
        # Exécution depuis le dossier du programme (utile pour les scripts relatifs)
        return subprocess.run([str(chemin)], cwd=chemin.parent).returncode
    except KeyboardInterrupt:
        return 130
    except OSError as e:
        print(f"Erreur au lancement : {e}", file=sys.stderr)
        return 1


def menu(entrees):
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
        entree = trouver_entree(entrees, choix)
        if entree:
            lancer(entree)
            input("\nAppuyez sur Entrée pour revenir au menu...")
        else:
            input("Choix invalide. Appuyez sur Entrée pour continuer...")


def analyser_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Menu pour lancer NetHack ou l'éditeur de carte."
    )
    parser.add_argument(
        "entree",
        nargs="?",
        help="entrée à lancer directement, sans menu (numéro ou nom de section)",
    )
    parser.add_argument(
        "-l", "--liste", action="store_true", help="affiche les entrées disponibles"
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = analyser_arguments(argv)

    try:
        entrees = charger_entrees(FICHIER_CONFIG)
    except (ValueError, configparser.Error) as e:
        print(f"Erreur de configuration : {e}", file=sys.stderr)
        return 1

    if args.liste:
        for i, entree in enumerate(entrees, start=1):
            print(f"{i}. {entree.nom} : {entree.libelle}")
        return 0

    if args.entree is not None:
        entree = trouver_entree(entrees, args.entree)
        if entree is None:
            print(f"Erreur : entrée inconnue : {args.entree}", file=sys.stderr)
            print("Utilisez --liste pour voir les entrées disponibles.", file=sys.stderr)
            return 2
        return lancer(entree)

    return menu(entrees)


if __name__ == "__main__":
    sys.exit(main())
