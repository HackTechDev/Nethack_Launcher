# Idées d'amélioration

Pistes pour faire évoluer le lanceur. Les idées marquées ⭐ sont celles à faire en priorité, celles marquées ✅ sont faites.

## Pour jouer

1. ⭐ **Reprendre une partie sauvegardée** : afficher sous le menu les parties en cours, trouvées dans le dossier `save/` de NetHack, avec le nom du personnage. Une touche permettrait de reprendre directement l'une d'elles.
2. **Statistiques globales** : nombre de parties, score moyen, causes de mort les plus fréquentes, rôle le plus joué. On les afficherait sur un écran à part (touche `s`), calculées à partir du `xlogfile`.
3. **Écran de détail d'une partie** : en sélectionnant un score, afficher le nombre de tours, le niveau maximal atteint, la durée réelle et les conduites respectées (végétarien, athée…). Tout cela se trouve déjà dans le `xlogfile`.
4. **Choix du fichier d'options** : une clé `nethackrc` dans une entrée, qui transmet la variable `NETHACKOPTIONS` au jeu. On pourrait ainsi avoir une entrée « NetHack – interface cyber » et une entrée « NetHack – classique ».
5. **Sauvegarde des parties** : une entrée de menu qui copie le dossier `save/` de NetHack dans une archive horodatée, pour se protéger contre une mort accidentelle.

## Pour les éditeurs

6. ✅ ~~**Éditeurs liés aux fichiers récents**~~ : proposer de rouvrir dans l'éditeur de carte ou de monstres le dernier fichier modifié, par exemple `monstres.json` ou un `.lua`.
7. ⭐ **Variables d'environnement par entrée** : une clé `env` dans `config.ini`, par exemple `NHMONEDIT_SRC=~/NetHack-5.0.0`, pour régler l'éditeur de monstres sans modifier son script.

## Confort du menu

8. **Recharger la configuration à chaud** : touche `r`, ou rechargement automatique si `config.ini` a changé, sans quitter le lanceur.
9. ✅ ~~**Séparateurs et groupes dans le menu**~~ : par exemple « Jeu » et « Outils », définis dans la config avec une clé `groupe`.
10. ✅ ~~**Description de l'entrée sélectionnée**~~ : une clé `description` affichée en bas quand l'entrée est en surbrillance.
11. ✅ ~~**Thèmes de couleurs**~~ : `theme = classique / cyber / sobre` dans `[options]`. Le thème « cyber » irait bien avec la version cyberpunk de NetHack.
12. ✅ ~~**Gestion de la souris**~~ dans le menu curses : clic pour choisir une entrée, double-clic pour la lancer.

## Configuration

13. ✅ ~~**Configuration utilisateur**~~ dans `~/.config/nethack_launcher/config.ini`, avec le `config.ini` du projet comme valeur par défaut. Chacun pourrait alors avoir ses propres chemins sans modifier le fichier suivi par git.
14. ✅ ~~**Option `--config fichier.ini`**~~ pour choisir un autre fichier de configuration.

## Robustesse

15. ✅ ~~**Journal des lancements**~~ : garder la date, l'entrée, la durée et le code de sortie dans un fichier, pour voir combien de temps on joue.
16. **Lancement de NetHack bloqué si une partie est déjà en cours** (fichier de verrou présent), avec un avertissement clair.

## Qualité du projet

17. ⭐ **Tests automatiques** avec `pytest`, sur la lecture de la config, des scores et des rumeurs, et sur les cas d'erreur.
18. ⭐ **Vérification automatique sur GitHub** : une GitHub Action qui lance les tests et `ruff` à chaque push.
19. **Installation** : un script `install.sh` qui crée le lien symbolique dans `~/bin`, ou un `pyproject.toml` pour installer le lanceur avec `pipx`.
