#!/usr/bin/env python3
"""Lanceur : menu pour démarrer NetHack ou l'éditeur de carte."""

import argparse
import configparser
import os
import random
import re
import shlex
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import curses
except ImportError:  # module absent (par exemple sous Windows)
    curses = None

FICHIER_CONFIG = Path(__file__).resolve().parent / "config.ini"
SECTION_OPTIONS = "options"  # section de config.ini qui n'est pas une entrée du menu

LOGO = r"""
 _   _      _   _   _            _
| \ | | ___| |_| | | | __ _  ___| | __
|  \| |/ _ \ __| |_| |/ _` |/ __| |/ /
| |\  |  __/ |_|  _  | (_| | (__|   <
|_| \_|\___|\__|_| |_|\__,_|\___|_|\_\
"""

LARGEUR = 40
DESCRIPTION_QUITTER = "Quitter le lanceur."

# Couleurs du terminal, dans l'ordre des codes ANSI (30 + indice) et de curses
COULEURS = ["noir", "rouge", "vert", "jaune", "bleu", "magenta", "cyan", "blanc"]
ATTRIBUTS_ANSI = {"gras": "1", "pale": "2"}

# Mise en forme de chaque élément de l'affichage : (couleur ou None, attributs...).
# Un thème peut redéfinir n'importe lequel de ces éléments.
STYLES_COMMUNS = {
    "titre": (None, "gras"),
    "titre_infos": (None, "gras"),
    "invite": (None, "gras"),
    "texte": (None,),
    "discret": (None, "pale"),
    "aide": (None, "pale"),
    "indisponible": (None, "pale"),
}
THEMES = {
    "classique": {
        "logo": ("jaune", "gras"),
        "separateur": ("bleu",),
        "groupe": ("bleu", "gras"),
        "numero": ("cyan",),
        "touche": ("jaune", "gras"),
        "erreur": ("rouge", "gras"),
        "rumeur": ("cyan",),
        "description": ("cyan",),
    },
    "cyber": {
        "logo": ("magenta", "gras"),
        "titre": ("cyan", "gras"),
        "separateur": ("cyan",),
        "groupe": ("magenta", "gras"),
        "numero": ("vert",),
        "touche": ("cyan", "gras"),
        "erreur": ("rouge", "gras"),
        "rumeur": ("vert",),
        "description": ("magenta",),
    },
    "sobre": {
        "logo": (None, "gras"),
        "separateur": (None,),
        "groupe": (None, "gras"),
        "numero": (None,),
        "touche": (None, "gras"),
        "erreur": (None, "gras"),
        "rumeur": (None,),
        "description": (None,),
    },
}
THEME_PAR_DEFAUT = "classique"

# Thème utilisé : option « theme » de config.ini, ou --theme
theme = THEMES[THEME_PAR_DEFAUT]
# Peut être forcé à False par l'option --sans-couleur
couleurs_autorisees = True


def styles_du_theme():
    """Renvoie la mise en forme de chaque élément pour le thème utilisé."""
    return {**STYLES_COMMUNS, **theme}


def couleurs_actives(flux=sys.stdout):
    """Indique si les couleurs ANSI peuvent être utilisées sur ce flux."""
    return (
        couleurs_autorisees
        and flux.isatty()
        and "NO_COLOR" not in os.environ
        and os.environ.get("TERM") != "dumb"
    )


def style(texte, element, flux=sys.stdout):
    """Met en forme le texte selon l'élément du thème, si les couleurs sont actives."""
    if not couleurs_actives(flux):
        return texte
    couleur, *attributs = styles_du_theme().get(element, (None,))
    codes = [ATTRIBUTS_ANSI[a] for a in attributs]
    if couleur:
        codes.insert(0, str(30 + COULEURS.index(couleur)))
    if not codes:
        return texte
    return f"\033[{';'.join(codes)}m{texte}\033[0m"


def erreur(message):
    print(style(message, "erreur", flux=sys.stderr), file=sys.stderr)


@dataclass
class Entree:
    nom: str  # nom de la section dans config.ini
    libelle: str
    chemin: Path
    arguments: list = field(default_factory=list)
    touche: str = ""  # raccourci clavier (une lettre), facultatif
    groupe: str = ""  # titre du groupe sous lequel l'entrée est rangée, facultatif
    description: str = ""  # affichée en bas du menu plein écran quand l'entrée est choisie

    def probleme(self):
        """Renvoie la raison pour laquelle le programme ne peut pas être lancé, sinon None."""
        if not self.chemin.is_file():
            return "introuvable"
        if not os.access(self.chemin, os.X_OK):
            return "non exécutable"
        return None


@dataclass
class Options:
    dossier_nethack: Path = None  # dossier de données de NetHack (HACKDIR)
    nombre_scores: int = 3
    rumeur: bool = True
    fichier_rumeurs: Path = None  # par défaut : rumors ou rumors.* du dossier NetHack
    theme: str = THEME_PAR_DEFAUT


def chemin_config(valeur: str):
    return Path(os.path.expandvars(valeur)).expanduser()


def charger_options(config):
    options = Options()
    if not config.has_section(SECTION_OPTIONS):
        return options
    section = config[SECTION_OPTIONS]
    if section.get("dossier_nethack", "").strip():
        options.dossier_nethack = chemin_config(section["dossier_nethack"].strip())
    try:
        options.nombre_scores = section.getint("nombre_scores", options.nombre_scores)
    except ValueError:
        raise ValueError(f"section [{SECTION_OPTIONS}] : nombre_scores doit être un entier")
    try:
        options.rumeur = section.getboolean("rumeur", options.rumeur)
    except ValueError:
        raise ValueError(f"section [{SECTION_OPTIONS}] : rumeur doit valoir oui ou non")
    if section.get("fichier_rumeurs", "").strip():
        options.fichier_rumeurs = chemin_config(section["fichier_rumeurs"].strip())
    options.theme = section.get("theme", options.theme).strip().lower()
    if options.theme not in THEMES:
        raise ValueError(
            f"section [{SECTION_OPTIONS}] : thème inconnu « {options.theme} »"
            f" (thèmes disponibles : {', '.join(THEMES)})"
        )
    return options


def charger_config(fichier: Path):
    """Lit le fichier de configuration et renvoie (entrées du menu, options)."""
    if not fichier.is_file():
        raise ValueError(f"fichier de configuration introuvable : {fichier}")

    config = configparser.ConfigParser(interpolation=None)
    config.BOOLEAN_STATES = {**config.BOOLEAN_STATES, "oui": True, "non": False}
    config.read(fichier, encoding="utf-8")

    entrees = []
    touches = {}
    for section in config.sections():
        if section == SECTION_OPTIONS:
            continue
        if "chemin" not in config[section]:
            raise ValueError(f"section [{section}] : clé « chemin » manquante")
        chemin = chemin_config(config[section]["chemin"])
        libelle = config[section].get("libelle", section)
        try:
            arguments = [
                os.path.expanduser(os.path.expandvars(arg))
                for arg in shlex.split(config[section].get("arguments", ""))
            ]
        except ValueError as e:
            raise ValueError(f"section [{section}] : arguments invalides ({e})")
        touche = config[section].get("touche", "").strip().lower()
        if touche:
            if len(touche) != 1 or not touche.isalpha():
                raise ValueError(f"section [{section}] : la touche doit être une lettre")
            if touche == "q":
                raise ValueError(f"section [{section}] : la touche « q » est réservée")
            if touche in touches:
                raise ValueError(
                    f"section [{section}] : touche « {touche} » déjà utilisée"
                    f" par [{touches[touche]}]"
                )
            touches[touche] = section
        groupe = config[section].get("groupe", "").strip()
        # Une description sur plusieurs lignes dans config.ini est remise sur une seule
        description = " ".join(config[section].get("description", "").split())
        entrees.append(
            Entree(section, libelle, chemin, arguments, touche, groupe, description)
        )

    if not entrees:
        raise ValueError(f"aucune entrée définie dans {fichier}")
    # Les entrées d'un même groupe sont rassemblées, dans l'ordre d'apparition des groupes
    ordre_groupes = {}
    for entree in entrees:
        ordre_groupes.setdefault(entree.groupe, len(ordre_groupes))
    entrees.sort(key=lambda e: ordre_groupes[e.groupe])
    return entrees, charger_options(config)


@dataclass
class Partie:
    points: int
    personnage: str  # rôle, race, genre et alignement, ex. « Val Hum Fem Law »
    mort: str
    date: str  # AAAAMMJJ
    mode: str  # "" pour une partie normale, sinon « wizard » ou « exploration »


def lire_parties(xlogfile: Path):
    """Lit le journal des parties de NetHack (xlogfile), dans l'ordre chronologique."""
    try:
        lignes = xlogfile.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    parties = []
    for ligne in lignes:
        champs = dict(c.split("=", 1) for c in ligne.split("\t") if "=" in c)
        try:
            points = int(champs["points"])
            drapeaux = int(champs.get("flags", "0"), 0)
        except (KeyError, ValueError):
            continue
        # Bits du champ flags : 0x1 mode wizard (debug), 0x2 mode exploration
        mode = "wizard" if drapeaux & 0x1 else "exploration" if drapeaux & 0x2 else ""
        personnage = " ".join(
            champs.get(cle, "?") for cle in ("role", "race", "gender", "align")
        )
        parties.append(
            Partie(points, personnage, champs.get("death", "?"), champs.get("deathdate", ""), mode)
        )
    return parties


def dechiffrer_rumeur(ligne: bytes):
    """Déchiffre une ligne du fichier des rumeurs (fonction xcrypt de NetHack)."""
    resultat = bytearray()
    masque = 1
    for octet in ligne:
        if octet & (32 | 64):
            octet ^= masque
        resultat.append(octet)
        masque <<= 1
        if masque >= 32:
            masque = 1
    return resultat.decode("utf-8", errors="replace")


def trouver_fichier_rumeurs(dossier: Path):
    """Cherche le fichier des rumeurs : rumors, sinon rumors.<langue>."""
    if (dossier / "rumors").is_file():
        return dossier / "rumors"
    candidats = sorted(dossier.glob("rumors.*"), key=lambda f: ("@" in f.name, f.name))
    return candidats[0] if candidats else None


def lire_rumeurs(fichier: Path):
    """Renvoie la liste des rumeurs (vraies et fausses) du fichier compilé par makedefs."""
    try:
        lignes = fichier.read_bytes().splitlines()
    except OSError:
        return []
    rumeurs = []
    for ligne in lignes:
        # On saute l'en-tête : commentaires et ligne d'index (ex. 0390,027353,00006d;...)
        if ligne.startswith(b"#") or re.fullmatch(rb"[0-9a-fA-F,;]+", ligne):
            continue
        # Les rumeurs sont complétées par des « _ » pour avoir une longueur fixe
        rumeur = dechiffrer_rumeur(ligne).rstrip("_").strip()
        if rumeur:
            rumeurs.append(rumeur)
    return rumeurs


def formater_date(date: str):
    try:
        return datetime.strptime(date, "%Y%m%d").strftime("%d/%m/%Y")
    except ValueError:
        return date


def preparer_infos(options: Options):
    """Renvoie les lignes affichées sous le menu, sous forme de couples (style, texte).

    Les styles possibles sont « titre », « texte », « discret » et « rumeur ».
    """
    infos = []
    if options.rumeur:
        fichier = options.fichier_rumeurs
        if fichier is None and options.dossier_nethack is not None:
            fichier = trouver_fichier_rumeurs(options.dossier_nethack)
        rumeurs = lire_rumeurs(fichier) if fichier else []
        if rumeurs:
            texte = f"« {random.choice(rumeurs)} »"
            for ligne in textwrap.wrap(texte, width=70):
                infos.append(("rumeur", ligne))
            infos.append(("texte", ""))

    if options.dossier_nethack is None:
        return infos

    parties = lire_parties(options.dossier_nethack / "xlogfile")
    # Les parties en mode wizard ou exploration ne comptent pas pour les scores
    classees = sorted(
        (p for p in parties if not p.mode), key=lambda p: p.points, reverse=True
    )
    if classees and options.nombre_scores > 0:
        infos.append(("titre", "Meilleurs scores"))
        for i, partie in enumerate(classees[: options.nombre_scores], start=1):
            infos.append((
                "texte",
                f"  {i}. {partie.points:>6} pts  {partie.personnage}"
                f"  {formater_date(partie.date)}  {partie.mort}",
            ))
    if parties:
        derniere = parties[-1]
        mode = f", mode {derniere.mode}" if derniere.mode else ""
        infos.append((
            "discret",
            f"Dernière partie : {derniere.points} pts, {derniere.personnage},"
            f" {derniere.mort} ({formater_date(derniere.date)}{mode})",
        ))
    return infos


def trouver_entree(entrees, choix: str):
    """Renvoie l'entrée désignée par son numéro, sa touche ou son nom, sinon None."""
    choix = choix.strip().lower()
    if choix.isdigit():
        if 1 <= int(choix) <= len(entrees):
            return entrees[int(choix) - 1]
        return None
    for entree in entrees:
        if entree.touche == choix:
            return entree
    for entree in entrees:
        if entree.nom.lower() == choix:
            return entree
    return None


def structure_menu(entrees):
    """Renvoie les lignes du menu, dans l'ordre d'affichage.

    Chaque ligne est un couple : ("groupe", titre) pour un titre de groupe,
    ("espace", "") pour une ligne vide séparant des entrées sans groupe,
    ou ("entree", indice) pour une entrée.
    """
    lignes = []
    precedent = ""
    for i, entree in enumerate(entrees):
        if entree.groupe != precedent:
            lignes.append(("groupe", entree.groupe) if entree.groupe else ("espace", ""))
            precedent = entree.groupe
        lignes.append(("entree", i))
    if precedent:
        lignes.append(("espace", ""))  # sépare le dernier groupe de « Quitter »
    return lignes


def titre_groupe(groupe: str):
    """Ligne de titre d'un groupe, ex. « ── Outils ───────── », de largeur LARGEUR."""
    debut = f"── {groupe} "
    return debut + "─" * max(LARGEUR - len(debut), 0)


def effacer_ecran():
    os.system("clear" if os.name != "nt" else "cls")


def afficher_menu(entrees, infos=()):
    separateur = style("=" * LARGEUR, "separateur")
    print(style(LOGO, "logo"))
    print(separateur)
    print(style("LANCEUR".center(LARGEUR).rstrip(), "titre"))
    print(separateur)
    largeur = len(str(len(entrees)))
    for genre, valeur in structure_menu(entrees):
        if genre == "groupe":
            print(style(titre_groupe(valeur), "groupe"))
            continue
        if genre == "espace":
            print()
            continue
        i, entree = valeur + 1, entrees[valeur]
        numero = style(f"{i:>{largeur}}", "numero")
        touche = style(f"[{entree.touche}]", "touche") if entree.touche else "   "
        probleme = entree.probleme()
        if probleme:
            libelle = style(entree.libelle, "indisponible") + "  " + style(f"({probleme})", "erreur")
        else:
            libelle = entree.libelle
        print(f"  {numero} {touche}  {libelle}")
    print(f"  {'':>{largeur}} {style('[q]', 'touche')}  Quitter")
    print(separateur)
    if infos:
        print()
        for nom_style, texte in infos:
            print(style(texte, "titre_infos" if nom_style == "titre" else nom_style))
        print()


def lancer(entree: Entree, supplementaires=()):
    """Lance le programme de l'entrée et renvoie son code de sortie.

    Les arguments supplémentaires sont ajoutés après ceux de la configuration.
    """
    chemin = entree.chemin
    probleme = entree.probleme()
    if probleme:
        erreur(f"Erreur : programme {probleme} : {chemin}")
        return 1
    try:
        # Exécution depuis le dossier du programme (utile pour les scripts relatifs)
        commande = [str(chemin), *entree.arguments, *supplementaires]
        return subprocess.run(commande, cwd=chemin.parent).returncode
    except KeyboardInterrupt:
        return 130
    except OSError as e:
        erreur(f"Erreur au lancement : {e}")
        return 1


def menu_texte(entrees, options):
    """Menu simple : on tape le numéro ou la touche de l'entrée puis Entrée."""
    while True:
        effacer_ecran()
        afficher_menu(entrees, preparer_infos(options))
        try:
            choix = input(style("Votre choix : ", "invite")).strip().lower()
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
            input(style("Choix invalide.", "erreur") + " Appuyez sur Entrée pour continuer...")


def menu_curses(entrees, options):
    """Menu interactif plein écran : navigation aux flèches, Entrée pour lancer."""
    return curses.wrapper(_boucle_curses, entrees, options)


def _styles_curses():
    """Renvoie l'attribut curses de chaque élément du menu, selon le thème."""
    couleurs_ok = (
        couleurs_autorisees and "NO_COLOR" not in os.environ and curses.has_colors()
    )
    if couleurs_ok:
        curses.start_color()
        try:
            curses.use_default_colors()
            fond = -1
        except curses.error:
            fond = curses.COLOR_BLACK

    attributs_curses = {"gras": curses.A_BOLD, "pale": curses.A_DIM}
    paires = {}  # couleur -> paire de couleurs curses
    styles = {"selection": curses.A_REVERSE | curses.A_BOLD}
    for element, (couleur, *attributs) in styles_du_theme().items():
        attribut = curses.A_NORMAL
        for nom in attributs:
            attribut |= attributs_curses[nom]
        if couleur and couleurs_ok:
            if couleur not in paires:
                numero = len(paires) + 1
                curses.init_pair(numero, COULEURS.index(couleur), fond)
                paires[couleur] = curses.color_pair(numero)
            attribut |= paires[couleur]
        styles[element] = attribut
    return styles


def _dessiner_curses(ecran, entrees, selection, infos, message, styles):
    ecran.erase()
    hauteur, largeur_ecran = ecran.getmaxyx()

    def ecrire(y, x, texte, attribut=curses.A_NORMAL):
        """Écrit le texte en le coupant au bord de l'écran ; renvoie la colonne suivante."""
        place = largeur_ecran - x - 1
        if y >= hauteur or place <= 0:
            return x
        try:
            ecran.addstr(y, x, texte[:place], attribut)
        except curses.error:
            pass
        return x + len(texte)

    y = 0
    for ligne in LOGO.strip("\n").splitlines():
        ecrire(y, 0, ligne, styles["logo"])
        y += 1
    y += 1
    separateur = "=" * LARGEUR
    ecrire(y, 0, separateur, styles["separateur"])
    ecrire(y + 1, 0, "LANCEUR".center(LARGEUR).rstrip(), styles["titre"])
    ecrire(y + 2, 0, separateur, styles["separateur"])
    y += 3

    largeur = len(str(len(entrees)))
    for genre, valeur in structure_menu(entrees):
        if genre == "groupe":
            ecrire(y, 0, titre_groupe(valeur), styles["groupe"])
        if genre != "entree":
            y += 1
            continue
        i, entree = valeur, entrees[valeur]
        probleme = entree.probleme()
        numero = f"{i + 1:>{largeur}}"
        touche = f"[{entree.touche}]" if entree.touche else "   "
        if i == selection:
            texte = f"  {numero} {touche}  {entree.libelle}"
            if probleme:
                texte += f"  ({probleme})"
            ecrire(y, 0, texte.ljust(LARGEUR), styles["selection"])
        else:
            x = ecrire(y, 2, numero, styles["numero"])
            x = ecrire(y, x + 1, touche, styles["touche"])
            if probleme:
                x = ecrire(y, x + 2, entree.libelle, styles["indisponible"])
                ecrire(y, x + 2, f"({probleme})", styles["erreur"])
            else:
                ecrire(y, x + 2, entree.libelle)
        y += 1
    # La ligne « Quitter » suit les entrées : elle est sélectionnée quand selection == len(entrees)
    if selection == len(entrees):
        texte = f"  {'':>{largeur}} [q]  Quitter"
        ecrire(y, 0, texte.ljust(LARGEUR), styles["selection"])
    else:
        x = ecrire(y, 2 + largeur + 1, "[q]", styles["touche"])
        ecrire(y, x + 2, "Quitter")
    ecrire(y + 1, 0, separateur, styles["separateur"])
    y += 3

    if infos:
        for nom_style, texte in infos:
            ecrire(y, 0, texte, styles["titre_infos" if nom_style == "titre" else nom_style])
            y += 1
        y += 1

    # Description de la ligne sélectionnée, si au moins une entrée en a une. On réserve
    # la place de la plus longue pour que l'aide ne bouge pas d'une entrée à l'autre.
    largeur_texte = max(min(largeur_ecran - 3, 76), 20)

    def decouper(description):
        return textwrap.wrap(description, width=largeur_texte)

    descriptions = [e.description for e in entrees]
    if any(descriptions):
        descriptions.append(DESCRIPTION_QUITTER)
    hauteur_description = max(len(decouper(d)) for d in descriptions)
    if hauteur_description:
        for i, ligne in enumerate(decouper(descriptions[selection])):
            ecrire(y + i, 0, ligne, styles["description"])
        y += hauteur_description + 1

    ecrire(y, 0, "↑/↓ choisir · Entrée lancer · touche ou numéro · q quitter", styles["aide"])
    if message:
        ecrire(y + 1, 0, message, styles["erreur"])
    ecran.refresh()


def _lancer_hors_curses(ecran, entree):
    """Quitte temporairement le mode curses le temps d'exécuter le programme."""
    curses.def_prog_mode()
    curses.endwin()
    effacer_ecran()
    lancer(entree)
    try:
        input("\nAppuyez sur Entrée pour revenir au menu...")
    except (EOFError, KeyboardInterrupt):
        pass
    curses.reset_prog_mode()
    ecran.clear()


def _boucle_curses(ecran, entrees, options):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    curses.set_escdelay(25)
    ecran.keypad(True)
    styles = _styles_curses()
    selection = 0  # de 0 à len(entrees) inclus, la dernière ligne étant « Quitter »
    nombre_lignes = len(entrees) + 1
    message = ""
    infos = preparer_infos(options)

    while True:
        _dessiner_curses(ecran, entrees, selection, infos, message, styles)
        message = ""
        try:
            touche = ecran.get_wch()
        except KeyboardInterrupt:
            return 0
        except curses.error:
            continue

        if touche == curses.KEY_UP:
            selection = (selection - 1) % nombre_lignes
            continue
        if touche == curses.KEY_DOWN:
            selection = (selection + 1) % nombre_lignes
            continue
        if touche == curses.KEY_HOME:
            selection = 0
            continue
        if touche == curses.KEY_END:
            selection = nombre_lignes - 1
            continue

        if touche in ("\n", "\r", curses.KEY_ENTER):
            if selection == len(entrees):
                return 0
            entree = entrees[selection]
        elif isinstance(touche, str) and touche.isprintable() and touche != " ":
            if touche.lower() == "q":
                return 0
            entree = trouver_entree(entrees, touche)
            if entree is None:
                message = f"Touche inconnue : {touche}"
                continue
        elif touche == "\x1b":  # Échap
            return 0
        else:
            continue  # redimensionnement ou touche spéciale ignorée

        selection = entrees.index(entree)
        _lancer_hors_curses(ecran, entree)
        infos = preparer_infos(options)  # les scores ont pu changer


def terminal_interactif():
    return (
        sys.stdin.isatty()
        and sys.stdout.isatty()
        and os.environ.get("TERM", "dumb") != "dumb"
    )


def analyser_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Menu pour lancer NetHack ou l'éditeur de carte."
    )
    parser.add_argument(
        "entree",
        nargs="?",
        help="entrée à lancer directement, sans menu (numéro, touche ou nom de section)",
    )
    parser.add_argument(
        "arguments",
        nargs=argparse.REMAINDER,
        help="arguments supplémentaires transmis au programme lancé",
    )
    parser.add_argument(
        "-l", "--liste", action="store_true", help="affiche les entrées disponibles"
    )
    parser.add_argument(
        "--sans-couleur", action="store_true", help="désactive les couleurs"
    )
    parser.add_argument(
        "--theme",
        choices=THEMES,
        help="thème de couleurs (remplace l'option « theme » de config.ini)",
    )
    parser.add_argument(
        "--texte",
        action="store_true",
        help="menu simple sans navigation aux flèches (pas de curses)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    global couleurs_autorisees, theme
    args = analyser_arguments(argv)
    if args.sans_couleur:
        couleurs_autorisees = False

    try:
        entrees, options = charger_config(FICHIER_CONFIG)
    except (ValueError, configparser.Error) as e:
        erreur(f"Erreur de configuration : {e}")
        return 1
    theme = THEMES[args.theme or options.theme]

    if args.liste:
        for i, entree in enumerate(entrees, start=1):
            probleme = entree.probleme()
            suffixe = f"  ({probleme})" if probleme else ""
            commande = shlex.join([str(entree.chemin), *entree.arguments])
            touche = f" [{entree.touche}]" if entree.touche else ""
            print(f"{i}.{touche} {entree.nom} : {entree.libelle}{suffixe}\n   {commande}")
            if entree.description:
                print(f"   {entree.description}")
        return 0

    if args.entree is not None:
        entree = trouver_entree(entrees, args.entree)
        if entree is None:
            erreur(f"Erreur : entrée inconnue : {args.entree}")
            print("Utilisez --liste pour voir les entrées disponibles.", file=sys.stderr)
            return 2
        return lancer(entree, args.arguments)

    if args.texte or curses is None or not terminal_interactif():
        return menu_texte(entrees, options)
    try:
        return menu_curses(entrees, options)
    except curses.error as e:
        erreur(f"Menu plein écran indisponible ({e}), passage au menu texte.")
        return menu_texte(entrees, options)


if __name__ == "__main__":
    sys.exit(main())
