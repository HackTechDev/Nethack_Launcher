# NetHack Launcher

Petit lanceur en Python qui affiche un menu en terminal pour démarrer :

1. **NetHack** — `~/nh/install/games/nethack`
2. **L'éditeur de secteurs** (cartes) — `~/JEUX/NETHACK/NetHack_MapEditor/nhmapedit.sh`
3. **La fabrique de robots** (éditeur de monstres) — `~/JEUX/NETHACK/NetHack_MonsterEditor/nhmonedit.sh`
4. **Le convertisseur Doom** (niveaux Doom vers NetHack) — `~/JEUX/NETHACK/Doom2Nethack/Doom2Nethack.sh`

Le lanceur suit l'univers du jeu : avec la version cyberpunk de NetHack (`OPTIONS=language:fr@cyber`), il devient un terminal de Night City, avec les mêmes noms que le jeu (voir [Univers et traductions](#univers-et-traductions)).

![Capture d'écran du menu du lanceur](docs/capture.png)

## Prérequis

- Python 3.9 ou plus récent
- Les deux programmes ci-dessus installés et exécutables

## Utilisation

```sh
./nethack_launcher.py
```

ou

```sh
python3 nethack_launcher.py
```

ou, depuis n'importe quel dossier (y compris via un lien symbolique, par exemple dans `~/bin`) :

```sh
./nethack_launcher.sh
```

Le menu s'affiche en plein écran, dans des cadres :

- en haut, le titre, le logo (ou une ligne de titre si le terminal est peu haut) et l'heure ;
- à gauche, le panneau des entrées, rangées par groupe ; la touche de chaque entrée est devant son libellé (son numéro si elle n'a pas de touche) ;
- à droite, le panneau de détail : la description de la ligne choisie, puis les meilleurs scores et la dernière partie ;
- sous les panneaux, une rumeur, et tout en bas la barre des touches.

Dans un terminal de moins de 72 colonnes, le panneau de détail passe sous celui des entrées.

- `↑` / `↓` pour choisir une entrée, `Entrée` pour la lancer (la ligne « Déconnexion », ou « Quitter », est aussi accessible aux flèches) ;
- ou directement le numéro de l'entrée ou sa touche (`n` pour NetHack, `e` pour l'éditeur de secteurs, `m` pour la fabrique de robots, `d` pour le convertisseur Doom) ;
- `q` ou `Échap` pour quitter ;
- à la souris : un clic choisit une ligne, un double-clic la lance, la molette monte ou descend.

Quand le programme lancé se termine, appuyez sur Entrée pour revenir au menu.

L'option `--texte` affiche à la place un menu simple, où l'on tape son choix puis Entrée. Ce menu est aussi utilisé automatiquement si l'entrée ou la sortie n'est pas un terminal.

Le menu affiche une rumeur de NetHack tirée au hasard (celles des fortune cookies), les meilleurs scores et un résumé de la dernière partie, lus dans le journal des parties de NetHack (`xlogfile`). Les parties en mode wizard ou exploration ne comptent pas dans les meilleurs scores.

Les lignes des scores et de la dernière partie, dans le panneau de droite, se choisissent aussi, avec les flèches (après « Déconnexion ») ou la souris. Entrée affiche alors le détail de la partie : personnage, fin de la partie, dates, temps de jeu, nombre de tours, profondeur atteinte, points de vie, or, conduites respectées et exploits. Dans le menu `--texte`, tapez `s1`, `s2`… pour le détail d'un score, ou `sd` pour la dernière partie.

Si le programme d'une entrée n'existe pas ou n'est pas exécutable, le menu l'indique à côté de son libellé, par exemple `(introuvable)`.

Le menu est affiché en couleurs dans un terminal. Elles sont désactivées automatiquement si la sortie n'est pas un terminal, si la variable d'environnement `NO_COLOR` est définie ou si `TERM=dumb`, ou à la demande avec l'option `--sans-couleur`.

### Lancement direct, sans menu

Indiquez l'entrée voulue, par son numéro, sa touche ou le nom de sa section dans `config.ini` :

```sh
./nethack_launcher.sh 1          # première entrée du menu
./nethack_launcher.sh e          # entrée de touche « e »
./nethack_launcher.sh nethack    # section [nethack]
./nethack_launcher.sh --liste    # affiche les entrées disponibles
```

Les arguments placés après l'entrée sont transmis au programme, après ceux de `config.ini` :

```sh
./nethack_launcher.sh nethack -u MonPerso
```

Le lanceur se termine alors avec le code de sortie du programme lancé.

## Configuration

Les chemins des programmes sont définis dans `config.ini`, à côté du script. Chaque section correspond à une entrée du menu, affichée dans l'ordre du fichier :

```ini
[nethack]
libelle = Jack-in : NetHack
chemin = ~/nh/install/games/nethack
touche = n
groupe = Réseau
description = Se brancher sur Night City pour un nouveau run, ou reprendre le run sauvegardé.

[editeur]
libelle = Éditeur de secteurs
chemin = ~/JEUX/NETHACK/NetHack_MapEditor/nhmapedit.sh
touche = e
groupe = Atelier
description = Dessine les plans des secteurs spéciaux de Night City (scripts Lua).
fichiers_recents = ~/JEUX/NETHACK/NetHack_MapEditor/essais/*.lua ~/nh/install/games/lib/nethackdir/*.lua

[monstres]
libelle = Fabrique de robots
chemin = ~/JEUX/NETHACK/NetHack_MonsterEditor/nhmonedit.sh
touche = m
groupe = Atelier
description = Conçoit les robots et mechas de Night City et les injecte dans le jeu.
fichiers_recents = ~/JEUX/NETHACK/NetHack_MonsterEditor/*.json

[heros]
libelle = Clinique d'identités
chemin = ~/JEUX/NETHACK/NetHack_HeroEditor/nhheroedit.sh
touche = h
groupe = Atelier
description = Façonne les héros de Night City (rôle, race, implants de départ, tuile) et lance un run avec eux.
fichiers_recents = ~/JEUX/NETHACK/NetHack_HeroEditor/*.json
heros = oui

[doom]
libelle = Convertisseur Doom
chemin = ~/JEUX/NETHACK/Doom2Nethack/Doom2Nethack.sh
touche = d
groupe = Atelier
description = Pirate les niveaux de Doom (fichiers WAD) et les recompile en secteurs de Night City.
```

- `libelle` : texte affiché dans le menu (facultatif, le nom de la section est utilisé par défaut)
- `chemin` : programme à lancer ; `~` et les variables d'environnement (`$HOME`…) sont acceptés
- `arguments` : options passées au programme (facultatif). Les guillemets permettent d'inclure des espaces : `arguments = -u "Mon Perso" -p Valkyrie`
- `touche` : raccourci clavier pour choisir l'entrée dans le menu (facultatif). Une seule lettre, différente pour chaque entrée ; `q` est réservée pour quitter
- `groupe` : titre du groupe où ranger l'entrée (facultatif). Le menu affiche un titre pour chaque groupe et rassemble les entrées d'un même groupe, dans l'ordre où les groupes apparaissent dans le fichier
- `description` : texte affiché en bas du menu plein écran quand l'entrée est sélectionnée (facultatif). Il est aussi affiché par `--liste`
- `fichiers_recents` : motifs de fichiers séparés par des espaces, par exemple `~/cartes/*.lua` ou `~/cartes/**/*.lua` pour inclure les sous-dossiers (facultatif). Le menu ajoute sous l'entrée une ligne « ↳ Rouvrir *fichier* », qui lance le programme sur le fichier modifié le plus récemment. Cette ligne est mise à jour à chaque retour au menu, et peut être lancée directement avec `./nethack_launcher.sh editeur-recent`
- `heros` : `oui` pour l'éditeur de héros [nhheroedit](../NetHack_HeroEditor) (facultatif). Le menu ajoute sous l'entrée une ligne « ↳ Jack-in : *nom* » par héros de son projet (le projet par défaut de l'éditeur, ou celui donné dans `arguments`), avec en description son rôle, sa race et son historique (nombre de parties, record, dernière fin), et « run en pause » s'il a une partie sauvegardée. Cette ligne lance la partie directement, avec les options complètes et la biographie du héros (`nhheroedit.sh --jouer NOM`) ; elle peut aussi être lancée avec `./nethack_launcher.sh heros-kestrel`

Pour ajouter une entrée au menu, il suffit d'ajouter une nouvelle section. Par exemple, pour lancer directement un personnage précis ou le mode exploration :

```ini
[valkyrie]
libelle = NetHack - Valkyrie
chemin = ~/nh/install/games/nethack
arguments = -u Brunehilde -p Valkyrie
touche = v

[exploration]
libelle = NetHack - Mode exploration
chemin = ~/nh/install/games/nethack
arguments = -X
```

### Configuration personnelle

Pour adapter le menu sans modifier `config.ini` (suivi par git), créez le fichier `~/.config/nethack_launcher/config.ini` (ou `$XDG_CONFIG_HOME/nethack_launcher/config.ini`). Il est lu après celui du projet :

- une clé redéfinie remplace celle du projet, les autres clés de la section sont conservées ;
- une nouvelle section ajoute une entrée au menu ;
- `masquer = oui` retire du menu une entrée du projet.

```ini
[options]
theme = cyber

[nethack]
arguments = -u MonPerso

[monstres]
masquer = oui
```

`./nethack_launcher.sh --liste` indique les fichiers de configuration utilisés.

### Choisir un autre fichier de configuration

L'option `--config` (ou `-c`) utilise le fichier indiqué **à la place** de `config.ini` et de la configuration personnelle. Elle peut être répétée : les fichiers sont alors lus dans l'ordre, comme ci-dessus.

```sh
./nethack_launcher.sh --config ~/nethack-tournoi.ini
./nethack_launcher.sh -c config.ini -c ~/essais.ini
```

### Journal des lancements

Chaque lancement est noté dans un journal, avec sa date, sa durée et le code de sortie du programme. Par défaut, il se trouve dans `~/.local/state/nethack_launcher/journal.tsv` (ou `$XDG_STATE_HOME/nethack_launcher/journal.tsv`).

`./nethack_launcher.sh --journal` (ou `-j`) affiche le temps passé dans chaque programme et les derniers lancements :

```
Programme            Lancements  Temps total  Dernier lancement
Jack-in : NetHack            12   5 h 32 min  28/10/2026 20:15
Éditeur de secteurs           4       47 min  27/10/2026 18:02
Total                        16   6 h 19 min
```

### Options du lanceur

La section `[options]` est réservée : ce n'est pas une entrée du menu.

```ini
[options]
dossier_nethack = ~/nh/install/games/lib/nethackdir
nombre_scores = 3
rumeur = oui
langue = auto
theme = auto
souris = oui
journal = ~/.local/state/nethack_launcher/journal.tsv
```

- `dossier_nethack` : dossier de données de NetHack (le `HACKDIR` défini dans le script `nethack`), où se trouve le fichier `xlogfile`. Laissez la valeur vide pour ne pas afficher les scores
- `nombre_scores` : nombre de meilleurs scores affichés (`0` pour aucun)
- `rumeur` : affiche une rumeur au hasard (`oui` ou `non`)
- `fichier_rumeurs` : fichier des rumeurs à utiliser (facultatif). Par défaut, le lanceur prend `rumors.<langue>` (par exemple `rumors.fr@cyber`), sinon `rumors`, dans `dossier_nethack`
- `langue` : langue des noms du jeu, par exemple `fr@cyber` ou `fr` (voir [Univers et traductions](#univers-et-traductions)). Avec `auto`, le lanceur prend celle de l'option `language` de NetHack, dans `~/.nethackrc` ou la variable `NETHACKOPTIONS`. L'option `--langue` permet d'en essayer une autre, par exemple `./nethack_launcher.sh --langue fr`
- `theme` : couleurs du menu, parmi :
  - `auto` : `cyber` pour la version cyberpunk du jeu, sinon `classique` (par défaut)
  - `classique` : logo jaune, séparateurs bleus
  - `cyber` : néons magenta, cyan et vert, assortis à la version cyberpunk de NetHack
  - `sobre` : sans couleur, uniquement du gras et du texte atténué

  L'option `--theme` permet d'essayer un thème sans modifier `config.ini`, par exemple `./nethack_launcher.sh --theme cyber`
- `souris` : clic, double-clic et molette dans le menu plein écran (`oui` ou `non`). Avec `non`, le terminal garde la sélection de texte habituelle à la souris
- `journal` : fichier du journal des lancements. Laissez la valeur vide pour ne pas tenir de journal

### Univers et traductions

Le lanceur reprend les noms du jeu au lieu de les traduire lui-même : il lit le catalogue de traductions de NetHack (`<langue>.mo`, par exemple `fr@cyber.mo`, dans `dossier_nethack`). Les rôles, races, alignements, monstres, causes de mort, rangs, exploits et la monnaie s'affichent donc comme dans le jeu, au masculin ou au féminin selon le personnage :

| Dans le xlogfile | Version classique (`fr`) | Version cyberpunk (`fr@cyber`) |
|---|---|---|
| `Arc Hum Mal` | Archéologue humain | Techie humain |
| `Pri Hum Fem` | Prêtresse humaine | Technoprêtresse humaine |
| `killed by a kobold` | tué par un kobold | tué par un voyou |
| `entered_the_gnomish_mines` | entré dans les Mines des gnomes | entré dans les Bas-fonds |
| `gold` | Or | Eddies |

Les rumeurs viennent aussi du fichier de la langue du jeu (`rumors.fr@cyber`).

Avec une langue en `@cyber`, les textes du lanceur lui-même passent dans l'univers de Night City : « TERMINAL // NIGHT CITY », « Déconnexion », « Meilleurs runs », « Dossier du run »…, et le thème de couleurs `auto` devient `cyber`. Sans catalogue de traductions, les noms sont affichés en français classique.

## Licence

Distribué sous licence MIT. Voir le fichier [LICENSE](LICENSE).
