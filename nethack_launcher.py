#!/usr/bin/env python3
"""Lanceur : menu pour démarrer NetHack ou l'éditeur de carte."""

import argparse
import configparser
import glob
import json
import os
import random
import re
import shlex
import struct
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

# Textes de l'interface. L'univers « cyber » suit la version cyberpunk du jeu
# (langue fr@cyber), l'univers « classique » la version d'origine.
TEXTES = {
    "classique": {
        "titre": "LANCEUR",
        "quitter": "Quitter",
        "description_quitter": "Quitter le lanceur.",
        "aide": "↑/↓ choisir · Entrée lancer · touche ou numéro · q quitter",
        "barre": [("↑↓", "choisir"), ("Entrée", "lancer"), ("lettre/n°", "raccourci"),
                  ("q", "quitter")],
        "logo_court": "N E T H A C K",
        "introuvable": "introuvable",
        "non_executable": "non exécutable",
        "touche_inconnue": "Touche inconnue : {touche}",
        "retour_menu": "Appuyez sur Entrée pour revenir au menu...",
        "invite": "Votre choix : ",
        "choix_invalide": "Choix invalide.",
        "continuer": " Appuyez sur Entrée pour continuer...",
        "rouvrir": "↳ Rouvrir {nom}",
        "description_rouvrir": "Ouvre {fichier} dans « {libelle} » (modifié le {date}).",
        "jouer_heros": "↳ Jouer : {nom}",
        "partie_sauvee": " (partie sauvegardée)",
        "description_heros": "{description}. Lance une partie avec ce héros de « {libelle} ».",
        "meilleurs_scores": "Meilleurs scores",
        "derniere_partie": "Dernière partie",
        "points": "pts",
        "aide_detail_texte": "Détail d'une partie : tapez {codes}",
        "description_partie": "Entrée : voir le détail de cette partie.",
        "titre_detail": "Partie de {nom}",
        "retour_detail": "Appuyez sur une touche pour revenir au menu.",
        "personnage": "Personnage",
        "score": "Points",
        "fin_partie": "Fin de la partie",
        "mode": "Mode de jeu",
        "debut": "Début",
        "fin": "Fin",
        "temps": "Temps de jeu",
        "tours": "Tours",
        "profondeur": "Profondeur",
        "valeur_profondeur": "niveau {max} au plus profond, fin au niveau {fin}",
        "points_de_vie": "Points de vie",
        "or": "Or",
        "voeux": "Vœux",
        "conduites": "Conduites respectées",
        "exploits": "Exploits",
        "aucune": "aucune",
        "aucun": "aucun",
        "rang": "rang « {rang} »",
        "mode_wizard": "wizard",
        "mode_exploration": "exploration",
    },
    "cyber": {
        "titre": "TERMINAL // NIGHT CITY",
        "quitter": "Déconnexion",
        "description_quitter": "Couper la liaison et quitter le terminal.",
        "aide": "↑/↓ naviguer · Entrée connexion · touche ou numéro · q déconnexion",
        "barre": [("↑↓", "naviguer"), ("Entrée", "connexion"), ("lettre/n°", "raccourci"),
                  ("q", "déconnexion")],
        "logo_court": "N E T H A C K  //  N I G H T  C I T Y",
        "introuvable": "hors ligne",
        "non_executable": "accès refusé",
        "touche_inconnue": "Commande inconnue : {touche}",
        "retour_menu": "Liaison terminée. Entrée pour revenir au terminal...",
        "invite": "> Commande : ",
        "choix_invalide": "Commande invalide.",
        "continuer": " Entrée pour continuer...",
        "rouvrir": "↳ Recharger {nom}",
        "description_rouvrir": "Recharge {fichier} dans « {libelle} »"
        " (dernière écriture le {date}).",
        "jouer_heros": "↳ Jack-in : {nom}",
        "partie_sauvee": " (run en pause)",
        "description_heros": "{description}. Se brancher sur Night City avec"
        " cette identité de « {libelle} ».",
        "meilleurs_scores": "Meilleurs runs",
        "derniere_partie": "Dernier run",
        "points": "pts",
        "aide_detail_texte": "Dossier d'un run : tapez {codes}",
        "description_partie": "Entrée : ouvrir le dossier de ce run.",
        "titre_detail": "Dossier du run : {nom}",
        "retour_detail": "Une touche pour refermer le dossier.",
        "personnage": "Profil",
        "score": "Score",
        "fin_partie": "Fin du run",
        "mode": "Mode",
        "debut": "Connexion",
        "fin": "Déconnexion",
        "temps": "Temps en ligne",
        "tours": "Tours",
        "profondeur": "Profondeur",
        "valeur_profondeur": "niveau {max} au plus profond, fin au niveau {fin}",
        "points_de_vie": "Points de vie",
        "or": "Eddies",
        "voeux": "Vœux",
        "conduites": "Protocoles respectés",
        "exploits": "Exploits",
        "aucune": "aucun",
        "aucun": "aucun",
        "rang": "rang « {rang} »",
        "mode_wizard": "debug",
        "mode_exploration": "exploration",
    },
}

# Univers et traductions utilisés : choisis au démarrage selon la langue du jeu
textes = TEXTES["classique"]


def t(cle, **valeurs):
    """Texte de l'interface dans l'univers choisi."""
    return textes[cle].format(**valeurs) if valeurs else textes[cle]

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
    "cadre": (None,),
    "titre_cadre": (None, "gras"),
    "selection": (None, "gras"),  # affiché en vidéo inverse
    "accent": (None, "gras"),  # barre « ▌ » devant la ligne choisie
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
        "cadre": ("bleu",),
        "titre_cadre": ("jaune", "gras"),
        "selection": ("jaune", "gras"),
        "accent": ("jaune", "gras"),
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
        "cadre": ("cyan",),
        "titre_cadre": ("magenta", "gras"),
        "selection": ("cyan", "gras"),
        "accent": ("magenta", "gras"),
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
    heros: bool = False  # éditeur de héros : une entrée « Jack-in » par héros

    def probleme(self):
        """Renvoie la raison pour laquelle le programme ne peut pas être lancé, sinon None."""
        if not self.chemin.is_file():
            return t("introuvable")
        if not os.access(self.chemin, os.X_OK):
            return t("non_executable")
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
    theme: str = "auto"  # « auto » : cyber pour la version cyberpunk, sinon classique
    souris: bool = True  # clic et molette dans le menu plein écran
    journal: Path = field(default_factory=fichier_journal_par_defaut)  # None : pas de journal
    langue: str = "auto"  # ex. fr@cyber ; « auto » : celle des options du jeu


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
    options.langue = section.get("langue", options.langue).strip() or "auto"
    options.theme = section.get("theme", options.theme).strip().lower()
    if options.theme != "auto" and options.theme not in THEMES:
        raise ValueError(
            f"section [{SECTION_OPTIONS}] : thème inconnu « {options.theme} »"
            f" (thèmes disponibles : auto, {', '.join(THEMES)})"
        )
    return options


def langue_du_jeu():
    """Langue choisie dans les options de NetHack (OPTIONS=language:…), sinon None.

    On lit ~/.nethackrc puis la variable NETHACKOPTIONS (qui peut aussi désigner
    un autre fichier d'options avec « @fichier ») : la dernière valeur l'emporte.
    """
    lignes = []
    variable = os.environ.get("NETHACKOPTIONS", "")
    fichiers = [Path(variable[1:]).expanduser()] if variable.startswith("@") else [
        Path.home() / ".nethackrc"
    ]
    for fichier in fichiers:
        try:
            lignes += fichier.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pass
    if variable and not variable.startswith("@"):
        lignes.append(variable)
    langue = None
    for ligne in lignes:
        if ligne.lstrip().startswith("#"):
            continue
        for morceau in re.finditer(r"\blanguage:([^,\s]+)", ligne):
            langue = morceau.group(1)
    return langue


def configurer_langue(options):
    """Charge les traductions du jeu et choisit l'univers des textes ; renvoie l'univers.

    La version cyberpunk du jeu (langue « fr@cyber ») donne l'univers « cyber ».
    """
    global trad, textes
    if options.langue == "auto":
        options.langue = langue_du_jeu() or ""
    trad = Traductions()
    if options.langue and options.dossier_nethack is not None:
        catalogue = options.dossier_nethack / f"{options.langue}.mo"
        if catalogue.is_file():
            try:
                trad = Traductions(lire_catalogue_mo(catalogue))
            except (OSError, ValueError, struct.error) as e:
                erreur(f"Traductions du jeu illisibles ({catalogue}) : {e}")
    univers = "cyber" if options.langue.endswith("@cyber") else "classique"
    textes = TEXTES[univers]
    return univers


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
        try:
            heros = config[section].getboolean("heros", False)
        except ValueError:
            raise ValueError(f"section [{section}] : heros doit valoir oui ou non")
        entrees.append(
            Entree(section, libelle, chemin, arguments, touche, groupe, description, motifs,
                   heros)
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


def lire_catalogue_mo(fichier: Path):
    """Lit un catalogue gettext compilé (.mo) : {« contexte\x04msgid » : [formes]}."""
    donnees = fichier.read_bytes()
    if donnees[:4] == b"\xde\x12\x04\x95":
        ordre = "<"
    elif donnees[:4] == b"\x95\x04\x12\xde":
        ordre = ">"
    else:
        raise ValueError(f"{fichier} n'est pas un catalogue .mo")
    nombre, debut_originaux, debut_traductions = struct.unpack(ordre + "3I", donnees[8:20])
    catalogue = {}
    for i in range(nombre):
        long_o, pos_o = struct.unpack_from(ordre + "2I", donnees, debut_originaux + 8 * i)
        long_t, pos_t = struct.unpack_from(ordre + "2I", donnees, debut_traductions + 8 * i)
        # Un message au pluriel est stocké « singulier\0pluriel » : on garde le singulier
        original = donnees[pos_o:pos_o + long_o].decode("utf-8", "replace").split("\0")[0]
        catalogue[original] = donnees[pos_t:pos_t + long_t].decode("utf-8", "replace").split("\0")
    return catalogue


class Traductions:
    """Traductions du jeu, lues dans le fichier <langue>.mo du dossier NetHack."""

    def __init__(self, catalogue=None):
        self.catalogue = catalogue or {}
        self._sans_casse = None

    def get(self, message, *contextes, pluriel=False):
        """Première traduction trouvée dans les contextes donnés (None : sans contexte)."""
        for contexte in contextes or (None,):
            formes = self.catalogue.get(f"{contexte}\x04{message}" if contexte else message)
            if formes and formes[0]:
                return formes[-1] if pluriel else formes[0]
        return None

    def get_sans_casse(self, message, *contextes):
        """Comme get, sans tenir compte des majuscules (ex. rangs : « field worker »)."""
        if self._sans_casse is None:
            self._sans_casse = {}
            for cle in self.catalogue:
                contexte, _, original = cle.rpartition("\x04")
                self._sans_casse.setdefault((contexte or None, original.lower()), cle)
        for contexte in contextes or (None,):
            cle = self._sans_casse.get((contexte, message.lower()))
            if cle and self.catalogue[cle][0]:
                return self.catalogue[cle][0]
        return None

    def prefixes(self, contexte):
        """Messages d'un contexte, du plus long au plus court (ex. « killed by »)."""
        debut = contexte + "\x04"
        return sorted(
            (cle[len(debut):] for cle in self.catalogue if cle.startswith(debut)),
            key=len, reverse=True,
        )


trad = Traductions()

# Noms anglais utilisés par le jeu, que l'on traduit avec son catalogue
ROLES_ANGLAIS = {
    "Arc": "Archeologist", "Bar": "Barbarian", "Cav": "Caveman", "Hea": "Healer",
    "Kni": "Knight", "Mon": "Monk", "Pri": "Priest", "Ran": "Ranger", "Rog": "Rogue",
    "Sam": "Samurai", "Tou": "Tourist", "Val": "Valkyrie", "Wiz": "Wizard",
}
ROLES_ANGLAIS_FEMININS = {"Cav": "Cavewoman", "Pri": "Priestess"}
RACES_ANGLAIS = {"Hum": "human", "Elf": "elf", "Dwa": "dwarf", "Gno": "gnome", "Orc": "orc"}
GENRES_ANGLAIS = {"Mal": "male", "Fem": "female"}
ALIGNEMENTS_ANGLAIS = {"Law": "lawful", "Neu": "neutral", "Cha": "chaotic"}
# Phrases du jeu qui décrivent les exploits du xlogfile (champ achieveX)
PHRASES_EXPLOITS = {
    "entered_the_gnomish_mines": "You entered the Gnomish Mines.",
    "entered_mine_town": "You entered Minetown.",
    "entered_a_shop": "You entered a shop.",
    "entered_a_temple": "You entered a temple.",
    "consulted_the_oracle": "You consulted the Oracle of Delphi.",
    "entered_sokoban": "You entered Sokoban.",
    "entered_bigroom": "You entered the Big Room.",
    "entered_gehennom": "You entered Gehennom.",
    "completed_sokoban": "You completed Sokoban.",
    "completed_the_gnomish_mines": "You completed the Gnomish Mines.",
    "defeated_medusa": "You defeated Medusa.",
    "learned_castle_drawbridge_tune":
        "You learned the tune to open and close the Castle's drawbridge.",
}
# Fins de partie sans tueur, à la 3e personne (masculin, féminin)
FINS_SIMPLES = {
    "quit": ("a abandonné", "a abandonné"),
    "escaped": ("s'est échappé", "s'est échappée"),
    "ascended": ("est monté au ciel", "est montée au ciel"),
}

# Noms français de secours, quand le catalogue du jeu est absent
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
FEMININS = {"humain": "humaine", "nain": "naine", "loyal": "loyale"}
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


def est_feminin(champs):
    return champs.get("gender") == "Fem"


def contextes_genre(champs):
    """Contextes de traduction à essayer : la forme féminine d'abord, si besoin."""
    return ("feminine", None) if est_feminin(champs) else (None,)


def traduire_code(champs, cle, anglais, francais):
    """Traduit un code du xlogfile (rôle, race…) avec le catalogue du jeu, sinon en français."""
    code = champs.get(cle, "?")
    mot_anglais = anglais.get(code)
    if cle == "role" and est_feminin(champs):
        mot_anglais = ROLES_ANGLAIS_FEMININS.get(code, mot_anglais)
    if mot_anglais:
        traduit = trad.get(mot_anglais, *contextes_genre(champs))
        if traduit:
            return traduit
    if cle == "role":
        return (ROLES_FEMININS.get(code) if est_feminin(champs) else None) or ROLES.get(code, code)
    mot = francais.get(code, code)
    return FEMININS.get(mot, mot) if est_feminin(champs) else mot


def nom_role(champs):
    return traduire_code(champs, "role", ROLES_ANGLAIS, ROLES)


def nom_race(champs):
    return traduire_code(champs, "race", RACES_ANGLAIS, RACES)


def personnage_court(champs):
    """Ex. « Techie humain » (version cyberpunk) ou « Archéologue humain »."""
    return f"{nom_role(champs)} {nom_race(champs)}"


def decrire_personnage(champs):
    """Ex. « Solo humaine, femme, loyale (Val Hum Fem Law) »."""
    genre = traduire_code(champs, "gender", GENRES_ANGLAIS, GENRES)
    alignement = traduire_code(champs, "align", ALIGNEMENTS_ANGLAIS, ALIGNEMENTS)
    codes = " ".join(champs.get(cle, "?") for cle in ("role", "race", "gender", "align"))
    return f"{personnage_court(champs)}, {genre}, {alignement} ({codes})"


def de(nom):
    """« de Méduse », « d'Athéna »."""
    return ("d'" if nom[:1].lower() in "aâàeéèêiîïoôuûyh" else "de ") + nom


def traduire_tueur(tueur):
    """Traduit « a kobold », « the Oracle »… avec le catalogue du jeu."""
    traduit = trad.get(tueur, "killer")
    if traduit:
        return traduit
    colere = re.fullmatch(r"the wrath of (.+)", tueur)
    if colere:
        return "la colère " + de(trad.get(colere[1], "god") or colere[1])
    forme = re.fullmatch(r"(a|an|the) (.+) in (\w+) form", tueur)  # ex. vampire en chauve-souris
    if forme:
        animal = trad.get(forme[3], "monster") or forme[3]
        return f"{traduire_tueur(f'{forme[1]} {forme[2]}')} sous forme {de(animal)}"
    morceaux = re.fullmatch(r"(a|an|the) (.+)", tueur)
    if not morceaux:
        return trad.get(tueur, "monster") or tueur
    article, nom = morceaux.groups()
    if article != "the":
        traduit = trad.get(nom, "killer a", "symbol a")  # article compris : « un voyou »
        if traduit:
            return traduit
    monstre = trad.get(nom, "monster")
    if not monstre:
        return tueur
    feminin = trad.get(nom, "gender") == "f"
    if article != "the":
        return ("une " if feminin else "un ") + monstre
    if monstre[:1].lower() in "aâàeéèêiîïoôuûyh":
        return "l'" + monstre
    return ("la " if feminin else "le ") + monstre


def traduire_mort(champs, avec_circonstances=True):
    """Fin de la partie dans la langue du jeu, ex. « tué par un voyou ».

    Les circonstances (« pendant un évanouissement… ») sont omises si demandé,
    pour les lignes courtes du menu.
    """
    mort = champs.get("death", "?")
    feminin = est_feminin(champs)
    if mort in FINS_SIMPLES:
        texte = FINS_SIMPLES[mort][feminin]
    else:
        texte = trad.get(mort, *contextes_genre(champs))  # ex. « starved to death »
        if not texte:
            texte = mort
            for prefixe in trad.prefixes("killed by"):
                if mort.startswith(prefixe):
                    contextes = ("feminine killed by", "killed by") if feminin else ("killed by",)
                    texte = trad.get(prefixe, *contextes) + traduire_tueur(mort[len(prefixe):])
                    break
    if champs.get("while") and avec_circonstances:
        pendant = f", while {champs['while']}"
        texte += trad.get(pendant, "while") or pendant
    return texte


def traduire_exploit(champs, exploit):
    if exploit.startswith("attained_the_rank_of_"):
        rang = exploit.removeprefix("attained_the_rank_of_").replace("_", " ")
        return t("rang", rang=trad.get_sans_casse(rang, *contextes_genre(champs)) or rang)
    phrase = PHRASES_EXPLOITS.get(exploit.lower())
    if phrase:
        contextes = ("heroine", None) if est_feminin(champs) else (None,)
        traduit = trad.get(phrase, *contextes)
        if traduit:
            # « Vous êtes entré dans les Bas-fonds. » -> « entré dans les Bas-fonds »
            exploit_traduit = re.sub(r"^Vous (avez|êtes) ", "", traduit).rstrip(".")
            if est_feminin(champs):
                exploit_traduit = re.sub(r"^entré\b", "entrée", exploit_traduit)
            return exploit_traduit
    return EXPLOITS.get(exploit, exploit.replace("_", " "))


def details_partie(partie: Partie, largeur=76):
    """Renvoie les lignes de l'écran de détail d'une partie, en couples (style, texte)."""
    c = partie.champs
    lignes = [("titre_infos", t("titre_detail", nom=c.get("name", "?"))), ("texte", "")]
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

    ajouter(t("personnage"), decrire_personnage(c))
    ajouter(t("score"), partie.points)
    ajouter(t("fin_partie"), traduire_mort(c))
    if partie.mode:
        ajouter(t("mode"), t(f"mode_{partie.mode}"))
    ajouter(t("debut"), horodatage("starttime", "birthdate"))
    ajouter(t("fin"), horodatage("endtime", "deathdate"))
    if entier("realtime") is not None:
        ajouter(t("temps"), formater_duree(entier("realtime")))
    ajouter(t("tours"), c.get("turns"))
    if entier("maxlvl") is not None:
        ajouter(t("profondeur"), t("valeur_profondeur", max=entier("maxlvl"),
                                   fin=c.get("deathlev", "?")))
    if entier("hp") is not None:
        ajouter(t("points_de_vie"), f"{entier('hp')} / {c.get('maxhp', '?')}")
    # Nom de la monnaie dans la langue du jeu (« eddies » dans la version cyberpunk)
    monnaie = trad.get("gold piece", pluriel=True)
    ajouter(monnaie.capitalize() if monnaie else t("or"), c.get("gold"))
    if entier("wish_cnt"):
        ajouter(t("voeux"), c["wish_cnt"])
    conduites = [CONDUITES.get(x, x) for x in c.get("conductX", "").split(",") if x]
    ajouter(t("conduites"), ", ".join(conduites) or t("aucune"))
    exploits = [traduire_exploit(c, x) for x in c.get("achieveX", "").split(",") if x]
    ajouter(t("exploits"), ", ".join(exploits) or t("aucun"))
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


def trouver_fichier_rumeurs(dossier: Path, langue=""):
    """Cherche le fichier des rumeurs : rumors.<langue du jeu>, rumors, sinon rumors.*."""
    if langue and (dossier / f"rumors.{langue}").is_file():
        return dossier / f"rumors.{langue}"
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
    section: str = ""  # « rumeur », « scores » ou « derniere » : panneau du menu plein écran
    panneau: str = ""  # texte dans ce panneau, s'il diffère de texte


def preparer_infos(options: Options):
    """Renvoie les lignes affichées sous le menu (rumeur, scores, dernière partie)."""
    infos = []
    if options.rumeur:
        fichier = options.fichier_rumeurs
        if fichier is None and options.dossier_nethack is not None:
            fichier = trouver_fichier_rumeurs(options.dossier_nethack, options.langue)
        rumeurs = lire_rumeurs(fichier) if fichier else []
        if rumeurs:
            rumeur = random.choice(rumeurs)
            # certaines rumeurs sont déjà entre guillemets
            texte = rumeur if rumeur.startswith("«") else f"« {rumeur} »"
            for ligne in textwrap.wrap(texte, width=70):
                infos.append(LigneInfo("rumeur", ligne, section="rumeur"))
            infos.append(LigneInfo("texte", ""))

    if options.dossier_nethack is None:
        return infos

    parties = lire_parties(options.dossier_nethack / "xlogfile")
    # Les parties en mode wizard ou exploration ne comptent pas pour les scores
    classees = sorted(
        (p for p in parties if not p.mode), key=lambda p: p.points, reverse=True
    )
    if classees and options.nombre_scores > 0:
        infos.append(LigneInfo("titre", t("meilleurs_scores")))
        for i, partie in enumerate(classees[: options.nombre_scores], start=1):
            texte = (f"{i}. {partie.points:>6} {t('points')}  {personnage_court(partie.champs)}"
                     f"  {formater_date(partie.date)}  {traduire_mort(partie.champs, False)}")
            infos.append(LigneInfo("texte", "  " + texte, partie, f"s{i}", "scores", texte))
    if parties:
        derniere = parties[-1]
        mode = f", mode {t('mode_' + derniere.mode)}" if derniere.mode else ""
        resume = (f"{derniere.points} {t('points')}, {personnage_court(derniere.champs)},"
                  f" {traduire_mort(derniere.champs, False)}"
                  f" ({formater_date(derniere.date)}{mode})")
        infos.append(LigneInfo(
            "discret", f"{t('derniere_partie')} : {resume}", derniere, "sd", "derniere", resume,
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
            libelle=t("rouvrir", nom=fichier.name),
            chemin=entree.chemin,
            arguments=[*entree.arguments, str(fichier)],
            groupe=entree.groupe,
            description=t("description_rouvrir", fichier=fichier, libelle=entree.libelle,
                          date=f"{modifie:%d/%m/%Y à %H:%M}"),
        ))
    return resultat


def lister_heros(entree: Entree):
    """Héros du projet de l'éditeur de héros (nhheroedit --heros), sinon []."""
    if entree.probleme():
        return []
    try:
        sortie = subprocess.run(
            [str(entree.chemin), *entree.arguments, "--heros"], cwd=entree.chemin.parent,
            capture_output=True, text=True, timeout=10,
        )
        heros = json.loads(sortie.stdout)["heroes"] if sortie.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return []
    return [h for h in heros if isinstance(h, dict) and h.get("name")]


def nom_section(nom: str):
    """Nom d'entrée tapable en ligne de commande : « Kestrel » -> « kestrel »."""
    return re.sub(r"[^a-z0-9]+", "-", nom.lower()).strip("-") or "heros"


def ajouter_heros(entrees):
    """Ajoute après chaque entrée « heros = oui » une entrée par héros du projet,
    qui lance directement une partie avec lui (nhheroedit --jouer NOM)."""
    resultat = []
    for entree in entrees:
        resultat.append(entree)
        if not entree.heros:
            continue
        for heros in lister_heros(entree):
            nom = heros["name"]
            resultat.append(Entree(
                nom=f"{entree.nom}-{nom_section(nom)}",
                libelle=t("jouer_heros", nom=nom)
                + (t("partie_sauvee") if heros.get("save") else ""),
                chemin=entree.chemin,
                arguments=[*entree.arguments, "--jouer", nom],
                groupe=entree.groupe,
                description=t("description_heros", description=heros.get("description", nom),
                              libelle=entree.libelle),
            ))
    return resultat


def entrees_du_menu(entrees):
    """Entrées de la configuration, avec les « Rouvrir » et les héros à jouer."""
    return ajouter_heros(ajouter_fichiers_recents(entrees))


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
    print(style(t("titre").center(LARGEUR).rstrip(), "titre"))
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
    print(f"  {'':>{largeur}} {style('[q]', 'touche')}  {t('quitter')}")
    print(separateur)
    if infos:
        print()
        for ligne in infos:
            print(style(ligne.texte, "titre_infos" if ligne.style == "titre" else ligne.style))
        codes = [ligne.code for ligne in infos if ligne.partie]
        if codes:
            print(style("\n" + t("aide_detail_texte", codes=", ".join(codes)), "aide"))
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
        entrees = entrees_du_menu(entrees_config)  # les fichiers ont pu changer
        effacer_ecran()
        infos = preparer_infos(options)
        afficher_menu(entrees, infos)
        try:
            choix = input(style(t("invite"), "invite")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choix in ("q", "quit", "quitter"):
            return 0
        parties = {ligne.code: ligne.partie for ligne in infos if ligne.partie}
        if choix in parties:
            effacer_ecran()
            afficher_partie(parties[choix])
            input("\n" + t("retour_menu"))
            continue
        entree = trouver_entree(entrees, choix)
        if entree:
            lancer(entree, journal=options.journal)
            input("\n" + t("retour_menu"))
        else:
            input(style(t("choix_invalide"), "erreur") + t("continuer"))


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
    styles["selection"] |= curses.A_REVERSE
    return styles


LARGEUR_MAX = 110  # largeur maximale du menu plein écran
LARGEUR_DEUX_PANNEAUX = 72  # en dessous, les panneaux sont l'un sous l'autre


def couper(texte: str, largeur: int):
    """Coupe le texte à la largeur donnée, en terminant par « … » s'il dépasse."""
    if largeur <= 0:
        return ""
    return texte if len(texte) <= largeur else texte[: largeur - 1] + "…"


def decouper(texte: str, largeur: int):
    """Découpe le texte en lignes, sans séparer les guillemets « » de leur mot."""
    texte = texte.replace("« ", "«\u00a0").replace(" »", "\u00a0»")
    return [ligne.replace("\u00a0", " ") for ligne in textwrap.wrap(texte, width=largeur)]


def lignes_panneau_menu(entrees):
    """Lignes du panneau du menu : (titre du cadre, lignes), chaque ligne étant
    ("groupe", titre), ("vide", None), ("entree", indice) ou ("quitter", None)."""
    lignes = [("vide" if genre == "espace" else genre, valeur)
              for genre, valeur in structure_menu(entrees)]
    titre = ""
    if lignes and lignes[0][0] == "groupe":
        titre = lignes.pop(0)[1]  # le premier groupe s'affiche dans le haut du cadre
    while lignes and lignes[0][0] == "vide":
        lignes.pop(0)
    if not lignes or lignes[-1][0] != "vide":
        lignes.append(("vide", None))
    lignes.append(("quitter", None))
    return titre, lignes


def _barre_touches(ecrire, y, largeur, styles):
    """Barre des touches en bas de l'écran : « ↑↓ naviguer  Entrée connexion… » ;
    les dernières touches sont omises si la largeur ne suffit pas."""
    x = 1
    for touche, action in textes["barre"]:
        if x + len(touche) + 1 + len(action) > largeur:
            break
        x = ecrire(y, x, touche, styles["touche"])
        x = ecrire(y, x + 1, action, styles["aide"]) + 3


def _cadre(ecrire, y, x, hauteur, largeur, titre, styles, droite="", style_titre="titre_cadre"):
    """Cadre arrondi, avec un titre en haut à gauche et un texte en haut à droite."""
    ecrire(y, x, "╭" + "─" * (largeur - 2) + "╮", styles["cadre"])
    for i in range(1, hauteur - 1):
        ecrire(y + i, x, "│", styles["cadre"])
        ecrire(y + i, x + largeur - 1, "│", styles["cadre"])
    ecrire(y + hauteur - 1, x, "╰" + "─" * (largeur - 2) + "╯", styles["cadre"])
    place = largeur - 6 - (len(droite) + 3 if droite else 0)
    if titre and place > 0:
        ecrire(y, x + 2, f" {couper(titre, place)} ", styles[style_titre])
    if droite:
        ecrire(y, x + largeur - len(droite) - 4, f" {droite} ", styles["cadre"])


def _separation(ecrire, y, x, largeur, titre, styles, style_titre="groupe"):
    """Ligne « ├─ Titre ─────┤ » qui sépare deux parties d'un cadre."""
    ecrire(y, x, "├" + "─" * (largeur - 2) + "┤", styles["cadre"])
    if titre:
        ecrire(y, x + 2, f" {couper(titre, largeur - 6)} ", styles[style_titre])


def _dessiner_curses(ecran, entrees, selection, infos, message, styles):
    """Dessine le menu et renvoie les zones cliquables : [(y, x début, x fin, indice)]."""
    ecran.erase()
    zones = []
    hauteur, largeur_ecran = ecran.getmaxyx()

    def ecrire(y, x, texte, attribut=curses.A_NORMAL):
        """Écrit le texte en le coupant au bord de l'écran ; renvoie la colonne suivante."""
        place = largeur_ecran - x - 1
        if y >= hauteur or y < 0 or place <= 0:
            return x
        try:
            ecran.addstr(y, x, texte[:place], attribut)
        except curses.error:
            pass
        return x + len(texte)

    largeur = max(min(largeur_ecran - 1, LARGEUR_MAX), 30)
    deux_panneaux = largeur >= LARGEUR_DEUX_PANNEAUX

    # --- panneau du menu ---
    titre_menu, lignes_menu = lignes_panneau_menu(entrees)
    largeur_cle = max(len(str(len(entrees))), 1)

    def libelle_complet(entree):
        probleme = entree.probleme()
        return entree.libelle + (f"  ({probleme})" if probleme else "")

    plus_long = max([len(libelle_complet(e)) for e in entrees] + [len(t("quitter"))])
    if deux_panneaux:
        largeur_menu = min(max(plus_long + largeur_cle + 8, 30), largeur // 2)
    else:
        largeur_menu = largeur

    # --- panneau de détail : description de la ligne choisie, scores, dernière partie ---
    largeur_detail = largeur - largeur_menu if deux_panneaux else largeur
    largeur_texte = largeur_detail - 4
    parties = [ligne for ligne in infos if ligne.partie]
    descriptions = [e.description for e in entrees]
    descriptions.append(t("description_quitter"))
    descriptions += [t("description_partie")] * len(parties)
    hauteur_description = max(
        len(decouper(d, largeur_texte)) for d in descriptions
    )
    lignes_detail = [("description", None)] * max(hauteur_description, 1)
    for section, titre in (("scores", t("meilleurs_scores")),
                           ("derniere", t("derniere_partie"))):
        lignes_section = [ligne for ligne in parties if ligne.section == section]
        if lignes_section:
            lignes_detail.append(("section", titre))
            lignes_detail += [("partie", ligne) for ligne in lignes_section]

    hauteur_panneaux = max(len(lignes_menu), len(lignes_detail)) + 2
    if deux_panneaux:
        hauteur_corps = hauteur_panneaux
    else:
        hauteur_corps = len(lignes_menu) + 2 + len(lignes_detail) + 2

    rumeur = " ".join(l.texte for l in infos if l.section == "rumeur")
    lignes_rumeur = decouper(rumeur, largeur - 4) if rumeur else []

    # --- en-tête : grand logo s'il y a la place, sinon une ligne ---
    logo = LOGO.strip("\n").splitlines()
    reste = hauteur - hauteur_corps - 2 - (len(lignes_rumeur) + 1 if lignes_rumeur else 0)
    grand_logo = reste >= len(logo) + 2 and largeur >= max(len(l) for l in logo) + 4
    heure = f"{datetime.now():%d/%m %H:%M}"
    y = 0
    if grand_logo:
        _cadre(ecrire, y, 0, len(logo) + 2, largeur, t("titre"), styles, heure)
        marge = (largeur - max(len(l) for l in logo)) // 2
        for i, ligne in enumerate(logo):
            ecrire(y + 1 + i, marge, ligne, styles["logo"])
        y += len(logo) + 2
    elif reste >= 3:
        _cadre(ecrire, y, 0, 3, largeur, t("titre"), styles, heure)
        court = t("logo_court")
        ecrire(y + 1, max((largeur - len(court)) // 2, 2), couper(court, largeur - 4),
               styles["logo"])
        y += 3
    else:
        ecrire(y, 1, t("titre"), styles["titre_cadre"])
        ecrire(y, largeur - len(heure) - 1, heure, styles["cadre"])
        y += 1

    # --- panneau du menu ---
    hauteur_menu = hauteur_panneaux if deux_panneaux else len(lignes_menu) + 2
    _cadre(ecrire, y, 0, hauteur_menu, largeur_menu, titre_menu, styles, style_titre="groupe")
    interieur = largeur_menu - 3  # entre la barre « ▌ » et le bord droit
    for n, (genre, valeur) in enumerate(lignes_menu):
        ligne_y = y + 1 + n
        if genre == "groupe":
            _separation(ecrire, ligne_y, 0, largeur_menu, valeur, styles)
            continue
        if genre == "vide":
            continue
        if genre == "quitter":
            indice, cle, libelle, probleme = len(entrees), "q", t("quitter"), ""
        else:
            indice, entree = valeur, entrees[valeur]
            cle = entree.touche or str(valeur + 1)
            libelle, probleme = entree.libelle, entree.probleme()
        zones.append((ligne_y, 0, largeur_menu - 1, indice))
        if indice == selection:
            texte = f" {cle:>{largeur_cle}}  {libelle_complet(entree) if probleme else libelle}"
            ecrire(ligne_y, 1, "▌", styles["accent"])
            ecrire(ligne_y, 2, couper(texte, interieur).ljust(interieur), styles["selection"])
            continue
        style_cle = "touche" if genre == "quitter" or entree.touche else "numero"
        x = ecrire(ligne_y, 3, f"{cle:>{largeur_cle}}", styles[style_cle]) + 2
        place = interieur - (x - 2)
        if probleme:
            x = ecrire(ligne_y, x, couper(libelle, place), styles["indisponible"])
            ecrire(ligne_y, x + 2, couper(f"({probleme})", place - len(libelle) - 2),
                   styles["erreur"])
        else:
            ecrire(ligne_y, x, couper(libelle, place), styles["texte"])

    # --- panneau de détail ---
    if deux_panneaux:
        x0, y0, hauteur_detail = largeur_menu, y, hauteur_panneaux
    else:
        x0, y0, hauteur_detail = 0, y + hauteur_menu, len(lignes_detail) + 2
    if selection < len(entrees):
        titre_detail = entrees[selection].libelle.lstrip("↳ ")
        description = entrees[selection].description
    elif selection == len(entrees):
        titre_detail, description = t("quitter"), t("description_quitter")
    else:
        choisie = parties[selection - len(entrees) - 1]
        titre_detail = t("titre_detail", nom=choisie.partie.champs.get("name", "?"))
        description = t("description_partie")
    _cadre(ecrire, y0, x0, hauteur_detail, largeur_detail, titre_detail, styles)
    morceaux = decouper(description or "", largeur_texte)
    indice = len(entrees) + 1
    for n, (genre, valeur) in enumerate(lignes_detail):
        ligne_y = y0 + 1 + n
        if genre == "description":
            if n < len(morceaux):
                ecrire(ligne_y, x0 + 2, morceaux[n], styles["description"])
        elif genre == "section":
            _separation(ecrire, ligne_y, x0, largeur_detail, valeur, styles, "titre_infos")
        else:
            zones.append((ligne_y, x0, x0 + largeur_detail - 1, indice))
            texte = couper(valeur.panneau or valeur.texte, largeur_texte)
            if indice == selection:
                ecrire(ligne_y, x0 + 1, "▌", styles["accent"])
                ecrire(ligne_y, x0 + 2, texte.ljust(largeur_detail - 3), styles["selection"])
            else:
                ecrire(ligne_y, x0 + 2, texte,
                       styles["texte" if valeur.section == "scores" else "discret"])
            indice += 1
    y += hauteur_corps

    # --- rumeur, message et barre des touches ---
    for n, ligne in enumerate(lignes_rumeur):
        ecrire(y + 1 + n, max((largeur - len(ligne)) // 2, 0), ligne, styles["rumeur"])
    if message:
        ecrire(hauteur - 2, 1, message, styles["erreur"])
    _barre_touches(ecrire, hauteur - 1, largeur, styles)
    ecran.refresh()
    return zones


def zone_cliquee(zones, y, x):
    """Indice de la ligne cliquée en (y, x), sinon None."""
    for zy, debut, fin, indice in zones:
        if zy == y and debut <= x <= fin:
            return indice
    return None


def _lancer_hors_curses(ecran, entree, journal):
    """Quitte temporairement le mode curses le temps d'exécuter le programme."""
    curses.def_prog_mode()
    curses.endwin()
    effacer_ecran()
    lancer(entree, journal=journal)
    try:
        input("\n" + t("retour_menu"))
    except (EOFError, KeyboardInterrupt):
        pass
    curses.reset_prog_mode()
    ecran.clear()


def _afficher_partie_curses(ecran, partie, styles):
    """Écran de détail d'une partie, dans un cadre ; une touche ou un clic ramène au menu."""
    while True:
        ecran.erase()
        hauteur, largeur_ecran = ecran.getmaxyx()

        def ecrire(y, x, texte, attribut=curses.A_NORMAL):
            place = largeur_ecran - x - 1
            if y >= hauteur or place <= 0:
                return x
            try:
                ecran.addstr(y, x, texte[:place], attribut)
            except curses.error:
                pass
            return x + len(texte)

        largeur = max(min(largeur_ecran - 1, 100), 30)
        titre, *lignes = details_partie(partie, largeur=largeur - 4)
        if lignes and not lignes[0][1]:
            lignes.pop(0)  # ligne vide sous le titre, inutile dans le cadre
        lignes = lignes[: max(hauteur - 4, 0)]
        _cadre(ecrire, 0, 0, len(lignes) + 2, largeur, titre[1], styles)
        for y, (nom_style, texte) in enumerate(lignes, start=1):
            ecrire(y, 1, couper(texte, largeur - 3), styles[nom_style])
        ecrire(min(len(lignes) + 3, hauteur - 1), 1, t("retour_detail"), styles["aide"])
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
    ecran.timeout(30000)  # redessine toutes les 30 s pour l'heure de l'en-tête
    styles = _styles_curses()
    if options.souris:
        # Clic : choisir une ligne ; double-clic : la lancer ; molette : monter ou descendre
        curses.mousemask(
            curses.BUTTON1_CLICKED
            | curses.BUTTON1_DOUBLE_CLICKED
            | curses.BUTTON4_PRESSED
            | getattr(curses, "BUTTON5_PRESSED", 0)
        )
    entrees = entrees_du_menu(entrees_config)
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
                _, x, y, _, boutons = curses.getmouse()
            except curses.error:
                continue
            if boutons & curses.BUTTON4_PRESSED:
                selection = (selection - 1) % nombre_lignes
            elif boutons & getattr(curses, "BUTTON5_PRESSED", 0):
                selection = (selection + 1) % nombre_lignes
            elif zone_cliquee(zones, y, x) is not None:
                selection = zone_cliquee(zones, y, x)
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
                message = t("touche_inconnue", touche=touche)
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
        entrees = entrees_du_menu(entrees_config)
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
        "--langue",
        metavar="LANGUE",
        help="langue des noms du jeu, ex. fr@cyber ou fr (remplace l'option « langue »)",
    )
    parser.add_argument(
        "--theme",
        choices=["auto", *THEMES],
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
    if args.langue:
        options.langue = args.langue
    univers = configurer_langue(options)
    nom_theme = args.theme or options.theme
    if nom_theme == "auto":
        nom_theme = "cyber" if univers == "cyber" else THEME_PAR_DEFAUT
    theme = THEMES[nom_theme]
    entrees_config = entrees
    entrees = entrees_du_menu(entrees)

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
