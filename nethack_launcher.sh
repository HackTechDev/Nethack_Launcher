#!/usr/bin/env bash
# Lance le menu NetHack (nethack_launcher.py), quel que soit le dossier courant.

set -euo pipefail

DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Erreur : python3 est introuvable." >&2
    exit 1
fi

exec python3 "$DIR/nethack_launcher.py" "$@"
