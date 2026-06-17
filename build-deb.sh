#!/bin/bash
# build-deb.sh — costruisce il pacchetto .deb di RuscaWriter per RuscaLinux.
#
# RuscaLinux è una distribuzione GNU/Linux basata su Debian 13 (trixie),
# creata da ruscalinux-dev. Questo pacchetto è pensato per quella distro,
# ma resta installabile su qualunque Debian/Ubuntu compatibile.
#
# Uso:   bash build-deb.sh
# Va eseguito dalla radice del progetto (dove stanno src/, lang/, assets/,
# ruscawriter.py e ruscawriter.desktop).
#
# Produce nella cartella corrente un file come:
#   ruscawriter_0.2-1~ruscalinux1_all.deb
# che si installa con:  sudo apt install ./ruscawriter_<versione>_all.deb

set -e

# --- dati del pacchetto ------------------------------------------------------
PKG="ruscawriter"
# versione "nuda" del programma (es. 0.2), letta dal codice per restare allineata
UPSTREAM_VERSION=$(python3 -c "import sys; sys.path.insert(0,'src'); from ruscawriter.model import APP_VERSION_SHORT; print(APP_VERSION_SHORT)")
# revisione del pacchetto Debian e suffisso della distribuzione RuscaLinux.
# Schema:  <versione>-<revisione>~ruscalinux<n>
#   - la revisione (1, 2, ...) si alza se ricostruisci il pacchetto senza
#     cambiare il programma (es. correzioni alla confezione)
#   - il suffisso ~ruscalinux1 marca l'origine; la tilde "~" fa sì che, in caso,
#     una eventuale versione Debian ufficiale risulti più recente
DEB_REVISION="1"
DISTRO_SUFFIX="~ruscalinux1"
VERSION="${UPSTREAM_VERSION}-${DEB_REVISION}${DISTRO_SUFFIX}"

ARCH="all"                       # niente codice compilato: pacchetto universale
MAINTAINER="ruscalinux-dev <info@ruscalinux.org>"

BUILD="build-deb"                # cartella di lavoro temporanea
ROOT="$BUILD/${PKG}_${VERSION}_${ARCH}"

echo "Costruzione di $PKG versione $VERSION (per RuscaLinux / Debian 13) ..."

# --- pulizia e struttura cartelle -------------------------------------------
rm -rf "$BUILD"
mkdir -p "$ROOT/DEBIAN"
mkdir -p "$ROOT/usr/share/$PKG"
mkdir -p "$ROOT/usr/bin"
mkdir -p "$ROOT/usr/share/applications"
mkdir -p "$ROOT/usr/share/icons/hicolor"
mkdir -p "$ROOT/usr/share/doc/$PKG"

# --- copia del programma -----------------------------------------------------
# tutto ciò che serve a runtime finisce in /usr/share/ruscawriter
cp -a src           "$ROOT/usr/share/$PKG/"
cp -a lang          "$ROOT/usr/share/$PKG/"
cp -a assets        "$ROOT/usr/share/$PKG/"
cp -a ruscawriter.py "$ROOT/usr/share/$PKG/"
# rimuove la cache di Python (.pyc) che non deve finire nel pacchetto
find "$ROOT/usr/share/$PKG" -name "__pycache__" -type d -prune -exec rm -rf {} +

# --- documentazione del pacchetto (in /usr/share/doc, come da prassi Debian) -
[ -f README.md ]    && cp README.md    "$ROOT/usr/share/doc/$PKG/" || true
[ -f CHANGELOG.md ] && cp CHANGELOG.md "$ROOT/usr/share/doc/$PKG/" || true
[ -f LICENSE ]      && cp LICENSE      "$ROOT/usr/share/doc/$PKG/copyright" || true

# --- lanciatore in /usr/bin --------------------------------------------------
# semplice wrapper: l'utente digita "ruscawriter" e parte l'app
cat > "$ROOT/usr/bin/$PKG" <<'LAUNCHER'
#!/bin/sh
exec python3 /usr/share/ruscawriter/ruscawriter.py "$@"
LAUNCHER
chmod 755 "$ROOT/usr/bin/$PKG"

# --- file .desktop -----------------------------------------------------------
cp ruscawriter.desktop "$ROOT/usr/share/applications/$PKG.desktop"

# --- icone (tema hicolor) ----------------------------------------------------
cp -a assets/icons/hicolor/. "$ROOT/usr/share/icons/hicolor/"

# --- file di controllo del pacchetto ----------------------------------------
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VERSION
Section: editors
Priority: optional
Architecture: $ARCH
Depends: python3, python3-gi, gir1.2-gtk-4.0
Recommends: gir1.2-gtksource-5, gir1.2-spelling-1, hunspell-it, hunspell-en-us
Suggests: calibre
Maintainer: $MAINTAINER
Homepage: https://www.ruscalinux.org/ruscawriter/
Description: Three-column writing editor for text and non-fiction
 RuscaWriter is a focused, three-column writing editor for non-fiction:
 chapter list, your text and per-chapter notes side by side. Write in plain
 Markdown and export a finished book to PDF, EPUB, DOCX, ODT, HTML, Markdown
 or TXT.
 .
 Part of the RuscaLinux project, a Debian-based GNU/Linux distribution.
CONTROL

# --- script post-installazione: aggiorna le cache di icone e desktop ---------
cat > "$ROOT/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi
exit 0
POSTINST
chmod 755 "$ROOT/DEBIAN/postinst"

# stesso aggiornamento cache dopo la rimozione
cat > "$ROOT/DEBIAN/postrm" <<'POSTRM'
#!/bin/sh
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi
exit 0
POSTRM
chmod 755 "$ROOT/DEBIAN/postrm"

# --- permessi corretti per il contenuto -------------------------------------
# le cartelle 755, i file di dati 644 (il lanciatore e gli script restano 755)
find "$ROOT/usr/share/$PKG" -type d -exec chmod 755 {} \;
find "$ROOT/usr/share/$PKG" -type f -exec chmod 644 {} \;
find "$ROOT/usr/share/doc/$PKG" -type f -exec chmod 644 {} \;

# --- costruzione del .deb ----------------------------------------------------
OUT="${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$ROOT" "$OUT"

echo ""
echo "Fatto: $OUT"
echo "Installa con:  sudo apt install ./$OUT"
