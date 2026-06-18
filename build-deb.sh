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
#   ruscawriter_0.2-1.ruscalinux1_all.deb
# che si installa con:  sudo apt install ./ruscawriter_<versione>_all.deb
#
# Nota sui nomi: la VERSIONE interna del pacchetto usa la tilde
# (0.2-1~ruscalinux1), come vuole la convenzione Debian. Il NOME DEL FILE
# invece usa un punto al posto della tilde (0.2-1.ruscalinux1), perché alcuni
# servizi (fra cui GitHub Releases) e i download dei browser sostituiscono la
# "~" nei nomi dei file: tenerla creerebbe un disallineamento con SHA256SUMS.

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

# Versione "sicura per i nomi di file": identica a VERSION ma con la tilde
# sostituita da un punto. Usata SOLO per comporre il nome del .deb, mai nel
# campo Version: del control (che resta con la tilde, come richiede Debian).
VERSION_FS="${VERSION//\~/.}"

ARCH="all"                       # niente codice compilato: pacchetto universale
MAINTAINER="ruscalinux-dev <info@ruscalinux.org>"

BUILD="build-deb"                # cartella di lavoro temporanea
ROOT="$BUILD/${PKG}_${VERSION_FS}_${ARCH}"

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

# --- file copyright in formato Debian (machine-readable DEP-5) ---------------
# Non si copia l'intero testo della GPL: si rimanda al file comune di sistema
# /usr/share/common-licenses/GPL-3, come richiede la Debian Policy.
cat > "$ROOT/usr/share/doc/$PKG/copyright" <<COPYRIGHT
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: RuscaWriter
Upstream-Contact: ruscalinux-dev <info@ruscalinux.org>
Source: https://github.com/ruscalinux-dev/ruscawriter

Files: *
Copyright: 2026 ruscalinux-dev <info@ruscalinux.org>
License: GPL-3+
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 .
 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.
 .
 On Debian systems, the full text of the GNU General Public License
 version 3 can be found in the file /usr/share/common-licenses/GPL-3.

Files: assets/fonts/*
Copyright: 2011 The EB Garamond Project Authors
           2013 The Courier Prime Authors
License: OFL-1.1
 The fonts bundled with RuscaWriter (EB Garamond, Courier Prime) are
 licensed under the SIL Open Font License, Version 1.1. The full license
 text is distributed alongside the font files in assets/.
COPYRIGHT

# --- changelog Debian (richiesto dalla Policy, formato rigido) ---------------
# È il registro delle modifiche DEL PACCHETTO, distinto dal CHANGELOG.md del
# progetto. Va compresso con gzip -9 e installato come changelog.Debian.gz.
_DATE_RFC="$(date -R)"
cat > "$ROOT/usr/share/doc/$PKG/changelog.Debian" <<CHANGELOG
$PKG ($VERSION) trixie; urgency=medium

  * RuscaWriter $UPSTREAM_VERSION packaged for RuscaLinux.
    See /usr/share/doc/$PKG/README.md and the project CHANGELOG for the
    full list of changes in this release.

 -- ruscalinux-dev <info@ruscalinux.org>  $_DATE_RFC
CHANGELOG
gzip -9 -n "$ROOT/usr/share/doc/$PKG/changelog.Debian"

# --- lanciatore in /usr/bin --------------------------------------------------
# semplice wrapper: l'utente digita "ruscawriter" e parte l'app
cat > "$ROOT/usr/bin/$PKG" <<'LAUNCHER'
#!/bin/sh
exec python3 /usr/share/ruscawriter/ruscawriter.py "$@"
LAUNCHER
chmod 755 "$ROOT/usr/bin/$PKG"

# --- pagina di manuale (man 1) ----------------------------------------------
# La Policy raccomanda un man per ogni comando in /usr/bin. Pagina minima ma
# valida, installata compressa in /usr/share/man/man1.
mkdir -p "$ROOT/usr/share/man/man1"
cat > "$ROOT/usr/share/man/man1/$PKG.1" <<MANPAGE
.TH RUSCAWRITER 1 "$(date '+%B %Y')" "RuscaWriter $UPSTREAM_VERSION" "User Commands"
.SH NAME
ruscawriter \- three-column writing editor for text and non-fiction
.SH SYNOPSIS
.B ruscawriter
.RI [ FILE ]
.SH DESCRIPTION
.B RuscaWriter
is a focused, three-column writing editor: chapter list, your text and
per-chapter notes side by side. You write in plain Markdown and export a
finished book to PDF, EPUB, DOCX, ODT, HTML, Markdown or TXT.
.PP
If a project FILE (a .rwr file) is given, it is opened on startup.
.SH FILES
.TP
.I ~/.config/ruscawriter/
User settings.
.SH HOMEPAGE
https://www.ruscalinux.org/ruscawriter/
.SH AUTHOR
ruscalinux-dev <info@ruscalinux.org>
.SH COPYRIGHT
Copyright \(co 2026 ruscalinux-dev. License GPLv3+: GNU GPL version 3 or later.
MANPAGE
gzip -9 -n "$ROOT/usr/share/man/man1/$PKG.1"

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
find "$ROOT/usr/share/man" -type f -exec chmod 644 {} \;

# --- costruzione del .deb ----------------------------------------------------
# Il nome del FILE usa VERSION_FS (con il punto), così resta integro su GitHub
# e nei download. Il pacchetto INTERNO mantiene la versione con tilde.
OUT="${PKG}_${VERSION_FS}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$ROOT" "$OUT"

# --- checksum: generato dallo stesso file appena prodotto -------------------
# Così SHA256SUMS è SEMPRE coerente con il .deb e con il suo nome: niente più
# disallineamenti da correggere a mano prima di caricarlo su GitHub.
sha256sum "$OUT" > SHA256SUMS

echo ""
echo "Fatto: $OUT"
echo "  (versione interna del pacchetto: $VERSION)"
echo "Checksum: SHA256SUMS (generato e verificato)"
echo "Installa con:  sudo apt install ./$OUT"
