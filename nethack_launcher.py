#!/usr/bin/env python3
"""Lanceur : menu pour démarrer NetHack ou l'éditeur de carte."""

import argparse
import configparser
import glob
import os
import random
import re
import shlex
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import curses
except ImportError:  # module absent (par exemple sous Windows)
    curses = None

FICHIER_CONFIG = Path(__file__).resolve().parent / "config.ini"  # valeurs par défaut
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
    fichiers_recents: list = field(default_factory=list)  # motifs, ex. ~/cartes/*.lua

    def probleme(self):
        """Renvoie la raison pour laquelle le programme ne peut pas être lancé, sinon None."""
        if not self.chemin.is_file():
            return "introuvable"
        if not os.access(self.chemin, os.X_OK):
            return "non exécutable"
        return None


def fichier_journal_par_defaut():
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "nethack_launcher" / "journal.tsv"


@dataclass
class Options:
    dossier_nethack: Path = None  # dossier de données de NetHack (HACKDIR)
    nombre_scores: int = 3
    rumeur: bool = True
    fichier_rumeurs: Path = None  # par défaut : rumors ou rumors.* du dossier NetHack
    theme: str = THEME_PAR_DEFAUT
    souris: bool = True  # clic et molette dans le menu plein écran
    journal: Path = field(default_factory=fichier_journal_par_defaut)  # None : pas de journal


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
    try:
        options.souris = section.getboolean("souris", options.souris)
    except ValueError:
        raise ValueError(f"section [{SECTION_OPTIONS}] : souris doit valoir oui ou non")
    if "journal" in section:
        valeur = section["journal"].strip()
        options.journal = chemin_config(valeur) if valeur else None
    options.theme = section.get("theme", options.theme).strip().lower()
    if options.theme not in THEMES:
        raise ValueError(
            f"section [{SECTION_OPTIONS}] : thème inconnu « {options.theme} »"
            f" (thèmes disponibles : {', '.join(THEMES)})"
        )
    return options


def fichier_config_utilisateur():
    """Configuration personnelle, qui complète ou remplace celle du projet."""
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "nethack_launcher" / "config.ini"


def fichiers_config():
    """Fichiers de configuration à lire, du plus général au plus personnel."""
    fichiers = [FICHIER_CONFIG]
    if fichier_config_utilisateur().is_file():
        fichiers.append(fichier_config_utilisateur())
    return fichiers


def charger_config(fichiers):
    """Lit les fichiers de configuration et renvoie (entrées du menu, options).

    Les fichiers sont lus dans l'ordre : chaque clé d'un fichier remplace la même
    clé des fichiers précédents, et les nouvelles sections s'ajoutent au menu.
    """
    for fichier in fichiers:
        if not fichier.is_file():
            raise ValueError(f"fichier de configuration introuvable : {fichier}")

    config = configparser.ConfigParser(interpolation=None)
    config.BOOLEAN_STATES = {**config.BOOLEAN_STATES, "oui": True, "non": False}
    config.read(fichiers, encoding="utf-8")

    entrees = []
    touches = {}
    for section in config.sections():
        if section == SECTION_OPTIONS:
            continue
        try:
            # « masquer = oui » retire du menu une entrée définie par un autre fichier
            if config[section].getboolean("masquer", False):
                continue
        except ValueError:
            raise ValueError(f"section [{section}] : masquer doit valoir oui ou non")
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
        try:
            motifs = [
                str(chemin_config(motif))
                for motif in shlex.split(config[section].get("fichiers_recents", ""))
            ]
        except ValueError as e:
            raise ValueError(f"section [{section}] : fichiers_recents invalides ({e})")
        entrees.append(
            Entree(section, libelle, chemin, arguments, touche, groupe, description, motifs)
        )

    if not entrees:
        raise ValueError("aucune entrée définie")
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
    champs: dict = field(default_factory=dict)  # tous les champs de la ligne du xlogfile


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
            Partie(
                points, personnage, champs.get("death", "?"),
                champs.get("deathdate", ""), mode, champs,
            )
        )
    return parties


ROLES = {
    "Arc": "Archéologue", "Bar": "Barbare", "Cav": "Homme des cavernes",
    "Hea": "Guérisseur", "Kni": "Chevalier", "Mon": "Moine", "Pri": "Prêtre",
    "Ran": "Rôdeur", "Rog": "Voleur", "Sam": "Samouraï", "Tou": "Touriste",
    "Val": "Valkyrie", "Wiz": "Magicien",
}
ROLES_FEMININS = {
    "Arc": "Archéologue", "Cav": "Femme des cavernes", "Hea": "Guérisseuse",
    "Kni": "Chevalière", "Mon": "Moniale", "Pri": "Prêtresse", "Ran": "Rôdeuse",
    "Rog": "Voleuse", "Wiz": "Magicienne",
}
RACES = {"Hum": "humain", "Elf": "elfe", "Dwa": "nain", "Gno": "gnome", "Orc": "orc"}
GENRES = {"Mal": "homme", "Fem": "femme"}
ALIGNEMENTS = {"Law": "loyal", "Neu": "neutre", "Cha": "chaotique"}
CONDUITES = {
    "foodless": "sans manger", "vegan": "végétalien", "vegetarian": "végétarien",
    "atheist": "athée", "weaponless": "sans arme", "pacifist": "pacifiste",
    "illiterate": "illettré", "polyless": "sans polymorphie d'objet",
    "polyselfless": "sans se polymorpher", "wishless": "sans vœu",
    "artiwishless": "sans vœu d'artefact", "genocideless": "sans génocide",
    "elberethless": "sans Elbereth", "sokoban": "Sokoban sans tricher",
    "blind": "aveugle", "nudist": "nudiste", "bonesless": "sans ossements",
    "petless": "sans familier", "unrerolled": "sans relance",
}
EXPLOITS = {
    "entered_the_gnomish_mines": "Mines des gnomes", "entered_mine_town": "Minetown",
    "entered_a_shop": "une boutique", "entered_a_temple": "un temple",
    "consulted_the_oracle": "consulté l'Oracle", "read_a_Discworld_novel": "lu un roman",
    "entered_sokoban": "Sokoban", "entered_bigroom": "la Grande salle",
    "entered_gehennom": "la Géhenne",
}
DESCRIPTION_PARTIE = "Entrée : voir le détail de cette partie."


def decrire_personnage(champs):
    """Ex. « Valkyrie humaine, femme, loyale (Val Hum Fem Law) »."""
    role, race = champs.get("role", "?"), champs.get("race", "?")
    genre, alignement = champs.get("gender", "?"), champs.get("align", "?")
    feminin = genre == "Fem"
    nom_role = (ROLES_FEMININS.get(role) if feminin else None) or ROLES.get(role, role)
    nom_race = RACES.get(race, race)
    nom_alignement = ALIGNEMENTS.get(alignement, alignement)
    if feminin:
        nom_race = {"humain": "humaine", "nain": "naine"}.get(nom_race, nom_race)
        nom_alignement = {"loyal": "loyale"}.get(nom_alignement, nom_alignement)
    return (
        f"{nom_role} {nom_race}, {GENRES.get(genre, genre)}, {nom_alignement}"
        f" ({role} {race} {genre} {alignement})"
    )


def traduire_exploit(exploit):
    if exploit.startswith("attained_the_rank_of_"):
        return "rang « " + exploit.removeprefix("attained_the_rank_of_").replace("_", " ") + " »"
    return EXPLOITS.get(exploit, exploit.replace("_", " "))


def details_partie(partie: Partie, largeur=76):
    """Renvoie les lignes de l'écran de détail d'une partie, en couples (style, texte)."""
    c = partie.champs
    lignes = [("titre_infos", f"Partie de {c.get('name', '?')}"), ("texte", "")]
    marge = 24

    def ajouter(etiquette, valeur):
        if valeur in (None, ""):
            return
        for i, morceau in enumerate(textwrap.wrap(str(valeur), width=max(largeur - marge, 20))):
            lignes.append(("texte", f"  {etiquette if i == 0 else '':<{marge - 2}}{morceau}"))

    def entier(cle):
        try:
            return int(c[cle])
        except (KeyError, ValueError):
            return None

    def horodatage(cle_epoch, cle_date):
        if entier(cle_epoch):
            return f"{datetime.fromtimestamp(entier(cle_epoch)):%d/%m/%Y à %H:%M}"
        return formater_date(c.get(cle_date, ""))

    ajouter("Personnage", decrire_personnage(c))
    ajouter("Points", partie.points)
    fin = c.get("death", "?") + (f", while {c['while']}" if c.get("while") else "")
    ajouter("Fin de la partie", fin)
    ajouter("Mode de jeu", partie.mode)
    ajouter("Début", horodatage("starttime", "birthdate"))
    ajouter("Fin", horodatage("endtime", "deathdate"))
    if entier("realtime") is not None:
        ajouter("Temps de jeu", formater_duree(entier("realtime")))
    ajouter("Tours", c.get("turns"))
    if entier("maxlvl") is not None:
        ajouter("Profondeur", f"niveau {entier('maxlvl')} au plus profond,"
                f" fin au niveau {c.get('deathlev', '?')}")
    if entier("hp") is not None:
        ajouter("Points de vie", f"{entier('hp')} / {c.get('maxhp', '?')}")
    ajouter("Or", c.get("gold"))
    if entier("wish_cnt"):
        ajouter("Vœux", c["wish_cnt"])
    conduites = [CONDUITES.get(x, x) for x in c.get("conductX", "").split(",") if x]
    ajouter("Conduites respectées", ", ".join(conduites) or "aucune")
    exploits = [traduire_exploit(x) for x in c.get("achieveX", "").split(",") if x]
    ajouter("Exploits", ", ".join(exploits) or "aucun")
    return lignes


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


@dataclass
class LigneInfo:
    """Ligne affichée sous le menu. Celles qui ont une partie peuvent être choisies."""
    style: str  # « titre », « texte », « discret » ou « rumeur »
    texte: str
    partie: Partie = None
    code: str = ""  # commande du menu texte pour voir le détail, ex. « s1 »


def preparer_infos(options: Options):
    """Renvoie les lignes affichées sous le menu (rumeur, scores, dernière partie)."""
    infos = []
    if options.rumeur:
        fichier = options.fichier_rumeurs
        if fichier is None and options.dossier_nethack is not None:
            fichier = trouver_fichier_rumeurs(options.dossier_nethack)
        rumeurs = lire_rumeurs(fichier) if fichier else []
        if rumeurs:
            texte = f"« {random.choice(rumeurs)} »"
            for ligne in textwrap.wrap(texte, width=70):
                infos.append(LigneInfo("rumeur", ligne))
            infos.append(LigneInfo("texte", ""))

    if options.dossier_nethack is None:
        return infos

    parties = lire_parties(options.dossier_nethack / "xlogfile")
    # Les parties en mode wizard ou exploration ne comptent pas pour les scores
    classees = sorted(
        (p for p in parties if not p.mode), key=lambda p: p.points, reverse=True
    )
    if classees and options.nombre_scores > 0:
        infos.append(LigneInfo("titre", "Meilleurs scores"))
        for i, partie in enumerate(classees[: options.nombre_scores], start=1):
            infos.append(LigneInfo(
                "texte",
                f"  {i}. {partie.points:>6} pts  {partie.personnage}"
                f"  {formater_date(partie.date)}  {partie.mort}",
                partie,
                f"s{i}",
            ))
    if parties:
        derniere = parties[-1]
        mode = f", mode {derniere.mode}" if derniere.mode else ""
        infos.append(LigneInfo(
            "discret",
            f"Dernière partie : {derniere.points} pts, {derniere.personnage},"
            f" {derniere.mort} ({formater_date(derniere.date)}{mode})",
            derniere,
            "sd",
        ))
    return infos


def fichier_le_plus_recent(motifs):
    """Renvoie le fichier modifié le plus récemment parmi ceux des motifs, sinon None."""
    fichiers = [
        Path(f) for motif in motifs for f in glob.glob(motif, recursive=True)
        if Path(f).is_file()
    ]
    return max(fichiers, key=lambda f: f.stat().st_mtime, default=None)


def ajouter_fichiers_recents(entrees):
    """Ajoute après chaque entrée qui a des fichiers_recents une entrée « Rouvrir »,
    qui lance le même programme sur le dernier fichier modifié."""
    resultat = []
    for entree in entrees:
        resultat.append(entree)
        fichier = fichier_le_plus_recent(entree.fichiers_recents)
        if fichier is None:
            continue
        modifie = datetime.fromtimestamp(fichier.stat().st_mtime)
        resultat.append(Entree(
            nom=f"{entree.nom}-recent",
            libelle=f"↳ Rouvrir {fichier.name}",
            chemin=entree.chemin,
            arguments=[*entree.arguments, str(fichier)],
            groupe=entree.groupe,
            description=f"Ouvre {fichier} dans « {entree.libelle} »"
            f" (modifié le {modifie:%d/%m/%Y à %H:%M}).",
        ))
    return resultat


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
        for ligne in infos:
            print(style(ligne.texte, "titre_infos" if ligne.style == "titre" else ligne.style))
        codes = [ligne.code for ligne in infos if ligne.partie]
        if codes:
            print(style(f"\nDétail d'une partie : tapez {', '.join(codes)}", "aide"))
        print()


def afficher_partie(partie: Partie):
    for nom_style, texte in details_partie(partie):
        print(style(texte, nom_style))


def ecrire_journal(journal: Path, entree: Entree, debut: datetime, duree: float, code: int):
    """Ajoute un lancement au journal : début, section, libellé, durée en secondes, code."""
    champs = [
        debut.isoformat(timespec="seconds"),
        entree.nom,
        entree.libelle,
        str(round(duree)),
        str(code),
    ]
    try:
        journal.parent.mkdir(parents=True, exist_ok=True)
        with journal.open("a", encoding="utf-8") as f:
            f.write("\t".join(c.replace("\t", " ") for c in champs) + "\n")
    except OSError as e:
        erreur(f"Impossible d'écrire dans le journal {journal} : {e}")


def lancer(entree: Entree, supplementaires=(), journal: Path = None):
    """Lance le programme de l'entrée et renvoie son code de sortie.

    Les arguments supplémentaires sont ajoutés après ceux de la configuration.
    Si un journal est donné, le lancement y est noté avec sa durée.
    """
    chemin = entree.chemin
    probleme = entree.probleme()
    if probleme:
        erreur(f"Erreur : programme {probleme} : {chemin}")
        return 1
    debut, chrono = datetime.now(), time.monotonic()
    try:
        # Exécution depuis le dossier du programme (utile pour les scripts relatifs)
        commande = [str(chemin), *entree.arguments, *supplementaires]
        code = subprocess.run(commande, cwd=chemin.parent).returncode
    except KeyboardInterrupt:
        code = 130
    except OSError as e:
        erreur(f"Erreur au lancement : {e}")
        return 1
    if journal is not None:
        ecrire_journal(journal, entree, debut, time.monotonic() - chrono, code)
    return code


def formater_duree(secondes: float):
    secondes = round(secondes)
    if secondes < 60:
        return f"{secondes} s"
    heures, minutes = divmod(secondes // 60, 60)
    return f"{heures} h {minutes:02d} min" if heures else f"{minutes} min"


def afficher_journal(journal: Path, nombre_derniers=10):
    """Affiche le temps passé dans chaque programme et les derniers lancements."""
    try:
        lignes = journal.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print(f"Aucun lancement enregistré pour l'instant ({journal}).")
        return 0
    except OSError as e:
        erreur(f"Impossible de lire le journal {journal} : {e}")
        return 1

    lancements = []
    for ligne in lignes:
        champs = ligne.split("\t")
        try:
            debut, nom, libelle = datetime.fromisoformat(champs[0]), champs[1], champs[2]
            duree, code = int(champs[3]), int(champs[4])
        except (IndexError, ValueError):
            continue
        lancements.append((debut, nom, libelle, duree, code))

    print(f"Journal : {journal}\n")
    if not lancements:
        print("Aucun lancement enregistré pour l'instant.")
        return 0

    bilan = {}  # section -> [libellé le plus récent, nombre, durée totale, dernier début]
    for debut, nom, libelle, duree, _ in lancements:
        ligne = bilan.setdefault(nom, [libelle, 0, 0, debut])
        ligne[0], ligne[3] = libelle, debut
        ligne[1] += 1
        ligne[2] += duree

    largeur = max(len(l[0]) for l in bilan.values())
    print(style(f"{'Programme':<{largeur}}  Lancements  Temps total  Dernier lancement", "titre_infos"))
    for libelle, nombre, total, dernier in sorted(bilan.values(), key=lambda l: -l[2]):
        print(
            f"{libelle:<{largeur}}  {nombre:>10}  {formater_duree(total):>11}"
            f"  {dernier:%d/%m/%Y %H:%M}"
        )
    total = sum(l[2] for l in bilan.values())
    print(f"{'Total':<{largeur}}  {len(lancements):>10}  {formater_duree(total):>11}")

    print(style(f"\n{min(nombre_derniers, len(lancements))} derniers lancements", "titre_infos"))
    for debut, _, libelle, duree, code in lancements[-nombre_derniers:][::-1]:
        fin = "" if code == 0 else style(f"  (code {code})", "erreur")
        print(f"{debut:%d/%m/%Y %H:%M}  {libelle:<{largeur}}  {formater_duree(duree):>11}{fin}")
    return 0


def menu_texte(entrees_config, options):
    """Menu simple : on tape le numéro ou la touche de l'entrée puis Entrée."""
    while True:
        entrees = ajouter_fichiers_recents(entrees_config)  # les fichiers ont pu changer
        effacer_ecran()
        infos = preparer_infos(options)
        afficher_menu(entrees, infos)
        try:
            choix = input(style("Votre choix : ", "invite")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choix in ("q", "quit", "quitter"):
            return 0
        parties = {ligne.code: ligne.partie for ligne in infos if ligne.partie}
        if choix in parties:
            effacer_ecran()
            afficher_partie(parties[choix])
            input("\nAppuyez sur Entrée pour revenir au menu...")
            continue
        entree = trouver_entree(entrees, choix)
        if entree:
            lancer(entree, journal=options.journal)
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
    """Dessine le menu et renvoie {numéro de ligne à l'écran: indice sélectionnable}."""
    ecran.erase()
    zones = {}
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
        zones[y] = i
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
    zones[y] = len(entrees)
    if selection == len(entrees):
        texte = f"  {'':>{largeur}} [q]  Quitter"
        ecrire(y, 0, texte.ljust(LARGEUR), styles["selection"])
    else:
        x = ecrire(y, 2 + largeur + 1, "[q]", styles["touche"])
        ecrire(y, x + 2, "Quitter")
    ecrire(y + 1, 0, separateur, styles["separateur"])
    y += 3

    # Les lignes de parties (scores, dernière partie) se choisissent après « Quitter »
    indice = len(entrees) + 1
    if infos:
        for ligne in infos:
            nom_style = "titre_infos" if ligne.style == "titre" else ligne.style
            if ligne.partie:
                zones[y] = indice
                if indice == selection:
                    nom_style = "selection"
                indice += 1
            ecrire(y, 0, ligne.texte, styles[nom_style])
            y += 1
        y += 1

    # Description de la ligne sélectionnée, si au moins une ligne en a une. On réserve
    # la place de la plus longue pour que l'aide ne bouge pas d'une ligne à l'autre.
    largeur_texte = max(min(largeur_ecran - 3, 76), 20)

    def decouper(description):
        return textwrap.wrap(description, width=largeur_texte)

    descriptions = [e.description for e in entrees]
    descriptions.append(DESCRIPTION_QUITTER if any(descriptions) else "")
    descriptions += [DESCRIPTION_PARTIE for ligne in infos if ligne.partie]
    hauteur_description = max(len(decouper(d)) for d in descriptions)
    if hauteur_description:
        for i, ligne in enumerate(decouper(descriptions[selection])):
            ecrire(y + i, 0, ligne, styles["description"])
        y += hauteur_description + 1

    ecrire(y, 0, "↑/↓ choisir · Entrée lancer · touche ou numéro · q quitter", styles["aide"])
    if message:
        ecrire(y + 1, 0, message, styles["erreur"])
    ecran.refresh()
    return zones


def _lancer_hors_curses(ecran, entree, journal):
    """Quitte temporairement le mode curses le temps d'exécuter le programme."""
    curses.def_prog_mode()
    curses.endwin()
    effacer_ecran()
    lancer(entree, journal=journal)
    try:
        input("\nAppuyez sur Entrée pour revenir au menu...")
    except (EOFError, KeyboardInterrupt):
        pass
    curses.reset_prog_mode()
    ecran.clear()


def _afficher_partie_curses(ecran, partie, styles):
    """Écran de détail d'une partie ; une touche ou un clic ramène au menu."""
    while True:
        ecran.erase()
        hauteur, largeur_ecran = ecran.getmaxyx()
        lignes = details_partie(partie, largeur=min(largeur_ecran - 1, 100))
        lignes += [("texte", ""), ("aide", "Appuyez sur une touche pour revenir au menu.")]
        for y, (nom_style, texte) in enumerate(lignes[:hauteur]):
            try:
                ecran.addstr(y, 0, texte[: max(largeur_ecran - 1, 0)], styles[nom_style])
            except curses.error:
                pass
        ecran.refresh()
        try:
            touche = ecran.get_wch()
        except KeyboardInterrupt:
            return
        except curses.error:
            continue
        if touche == curses.KEY_MOUSE:
            try:
                curses.getmouse()
            except curses.error:
                pass
        if touche != curses.KEY_RESIZE:
            return


def _boucle_curses(ecran, entrees_config, options):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    curses.set_escdelay(25)
    ecran.keypad(True)
    styles = _styles_curses()
    if options.souris:
        # Clic : choisir une ligne ; double-clic : la lancer ; molette : monter ou descendre
        curses.mousemask(
            curses.BUTTON1_CLICKED
            | curses.BUTTON1_DOUBLE_CLICKED
            | curses.BUTTON4_PRESSED
            | getattr(curses, "BUTTON5_PRESSED", 0)
        )
    entrees = ajouter_fichiers_recents(entrees_config)
    infos = preparer_infos(options)
    # Lignes que l'on peut choisir : les entrées, « Quitter » (indice len(entrees)),
    # puis les parties affichées sous le menu
    parties = [ligne.partie for ligne in infos if ligne.partie]
    selection = 0
    nombre_lignes = len(entrees) + 1 + len(parties)
    message = ""

    while True:
        zones = _dessiner_curses(ecran, entrees, selection, infos, message, styles)
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

        if touche == curses.KEY_MOUSE:
            try:
                _, _, y, _, boutons = curses.getmouse()
            except curses.error:
                continue
            if boutons & curses.BUTTON4_PRESSED:
                selection = (selection - 1) % nombre_lignes
            elif boutons & getattr(curses, "BUTTON5_PRESSED", 0):
                selection = (selection + 1) % nombre_lignes
            elif y in zones:
                selection = zones[y]
                if boutons & curses.BUTTON1_DOUBLE_CLICKED:
                    touche = "\n"  # le double-clic vaut Entrée sur la ligne cliquée
            if touche != "\n":
                continue

        if touche in ("\n", "\r", curses.KEY_ENTER):
            if selection == len(entrees):
                return 0
            if selection > len(entrees):
                _afficher_partie_curses(ecran, parties[selection - len(entrees) - 1], styles)
                continue
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
        _lancer_hors_curses(ecran, entree, options.journal)
        infos = preparer_infos(options)  # les scores ont pu changer
        parties = [ligne.partie for ligne in infos if ligne.partie]
        # Le programme a pu créer ou modifier des fichiers : on recalcule les « Rouvrir »
        nom_choisi = entree.nom
        entrees = ajouter_fichiers_recents(entrees_config)
        nombre_lignes = len(entrees) + 1 + len(parties)
        noms = [e.nom for e in entrees]
        selection = noms.index(nom_choisi) if nom_choisi in noms else 0


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
        "-j",
        "--journal",
        action="store_true",
        help="affiche le temps passé dans chaque programme et les derniers lancements",
    )
    parser.add_argument(
        "--sans-couleur", action="store_true", help="désactive les couleurs"
    )
    parser.add_argument(
        "-c",
        "--config",
        metavar="FICHIER",
        action="append",
        type=Path,
        help="fichier de configuration à utiliser à la place de config.ini et de la"
        " configuration personnelle ; peut être répété, les fichiers étant lus dans l'ordre",
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

    fichiers = [f.expanduser() for f in args.config] if args.config else fichiers_config()
    try:
        entrees, options = charger_config(fichiers)
    except (ValueError, configparser.Error) as e:
        erreur(f"Erreur de configuration ({', '.join(map(str, fichiers))}) : {e}")
        return 1
    theme = THEMES[args.theme or options.theme]
    entrees_config = entrees
    entrees = ajouter_fichiers_recents(entrees)

    if args.journal:
        if options.journal is None:
            print("Le journal est désactivé (option « journal » vide dans [options]).")
            return 0
        return afficher_journal(options.journal)

    if args.liste:
        print(f"Configuration : {', '.join(map(str, fichiers))}\n")
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
        return lancer(entree, args.arguments, options.journal)

    if args.texte or curses is None or not terminal_interactif():
        return menu_texte(entrees_config, options)
    try:
        return menu_curses(entrees_config, options)
    except curses.error as e:
        erreur(f"Menu plein écran indisponible ({e}), passage au menu texte.")
        return menu_texte(entrees_config, options)


if __name__ == "__main__":
    sys.exit(main())
