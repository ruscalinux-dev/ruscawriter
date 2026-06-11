#!/bin/sh
# Installa le icone di RuscaWriter nel tema "hicolor" dell'utente,
# così l'icona appare nel menu applicazioni, nella dock e nel file manager.
#
# Uso:   sh install-icons.sh
# (installa per l'utente corrente, senza bisogno di permessi di root)

set -e
HERE=$(dirname "$0")
SRC="$HERE/assets/icons/hicolor"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"

echo "Installazione icone in: $DEST"
cp -r "$SRC/." "$DEST/"

# aggiorna la cache del tema icone, se lo strumento è disponibile
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DEST" 2>/dev/null || true
fi

echo "Fatto. L'icona 'ruscawriter' è ora disponibile per i file .desktop."
