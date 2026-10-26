# NetHack Launcher

Petit lanceur en Python qui affiche un menu en terminal pour démarrer :

1. **NetHack** — `~/nh/install/games/nethack`
2. **L'éditeur de carte** — `~/JEUX/NETHACK/NetHack_MapEditor/nhmapedit.sh`

## Prérequis

- Python 3.6 ou plus récent
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

Tapez le numéro de l'entrée voulue, ou `q` pour quitter. Quand le programme lancé se termine, le menu s'affiche de nouveau.

## Configuration

Les chemins des programmes sont définis dans `config.ini`, à côté du script. Chaque section correspond à une entrée du menu, affichée dans l'ordre du fichier :

```ini
[nethack]
libelle = Jouer à NetHack
chemin = ~/nh/install/games/nethack

[editeur]
libelle = Éditeur de carte
chemin = ~/JEUX/NETHACK/NetHack_MapEditor/nhmapedit.sh
```

- `libelle` : texte affiché dans le menu (facultatif, le nom de la section est utilisé par défaut)
- `chemin` : programme à lancer ; `~` et les variables d'environnement (`$HOME`…) sont acceptés

Pour ajouter une entrée au menu, il suffit d'ajouter une nouvelle section.

## Licence

Distribué sous licence MIT. Voir le fichier [LICENSE](LICENSE).
