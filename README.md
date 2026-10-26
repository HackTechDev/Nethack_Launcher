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

Tapez le numéro de l'entrée voulue, ou `q` pour quitter. Quand le programme lancé se termine, le menu s'affiche de nouveau.

## Personnalisation

Les entrées du menu sont définies dans la liste `ENTREES`, en haut de `nethack_launcher.py`. Pour ajouter une entrée, ajoutez-y un couple `(libellé, chemin)`.
