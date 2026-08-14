#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# RuscaWriter — three-column writing editor for non-fiction
# Copyright (C) 2026  Nunzio Curcuruto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
RuscaWriter — GTK 4 user interface / interfaccia grafica GTK 4
Versione / Version: vedi model.APP_VERSION_SHORT / see model.APP_VERSION_SHORT
Autore / Author: Nunzio Curcuruto

EN — Three-column writing editor built with Python + GTK 4 (PyGObject),
with no extra graphical libraries.

 - Left column   : list of the project's chapters/sections.
 - Center column : writing area for the text (black serif).
 - Right column  : notes attached to the selected chapter.

Project format: an .rwr file = a tar.gz archive containing
    01.md  01n.md    (chapter 01 text + its note)
    02.md  02n.md
    ...
    img_001.png ...  (images attached to the chapters)
    cover.png/jpg/webp, meta.json, frontispiece.json, colophon.json

This module was ported from GTK 3 to GTK 4. Main differences:
  - Gtk.Application / Gtk.ApplicationWindow as the app skeleton.
  - Menus built with Gio.Menu + Gtk.PopoverMenuBar and GAction; shortcuts
    registered with app.set_accels_for_action.
  - Asynchronous dialogs (Dialog.run() no longer exists in GTK 4): themed
    windows with callbacks, and Gtk.FileDialog for open/save.
  - set_child()/append() instead of add()/pack_start().
  - Chapter list with Gtk.ListView + Gtk.StringList + Gtk.SingleSelection.
  - Events via controllers (GestureClick) instead of event signals.

IT — Editor di scrittura a tre colonne scritto in Python + GTK 4
(PyGObject), senza librerie grafiche aggiuntive.

 - Colonna sinistra : elenco dei capitoli/sezioni del progetto.
 - Colonna centrale : area di scrittura del testo (serif nero).
 - Colonna destra   : note relative al capitolo selezionato.

Formato progetto: file .rwr = archivio tar.gz contenente
    01.md  01n.md    (testo capitolo 01 + sua nota)
    02.md  02n.md
    ...
    img_001.png ...  (immagini allegate ai capitoli)
    cover.png/jpg/webp, meta.json, frontispiece.json, colophon.json

Questo modulo e' stato portato da GTK 3 a GTK 4. Differenze principali:
  - Gtk.Application / Gtk.ApplicationWindow come struttura dell'app.
  - Menu costruiti con Gio.Menu + Gtk.PopoverMenuBar e GAction; le scorciatoie
    sono registrate con app.set_accels_for_action.
  - Dialoghi asincroni (Dialog.run() non esiste piu' in GTK 4): finestre con
    il nostro tema e callback, e Gtk.FileDialog per aprire/salvare.
  - set_child()/append() al posto di add()/pack_start().
  - Lista capitoli con Gtk.ListView + Gtk.StringList + Gtk.SingleSelection.
  - Eventi tramite controller (GestureClick) invece dei segnali event.
"""

import os
import json
import locale

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Pango, GLib, Gio
try:
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
except Exception:
    GdkPixbuf = None

# GtkSourceView 5: serve come vista di scrittura quando si usa libspelling,
# perche' il suo adapter richiede un GtkSource.Buffer. E' opzionale: se manca,
# si usa un normale Gtk.TextView e il controllo ortografico resta inattivo.
try:
    gi.require_version("GtkSource", "5")
    from gi.repository import GtkSource
except Exception:
    GtkSource = None

# Controllo ortografico opzionale.
#
# ATTENZIONE alla versione: con GTK 4 NON si possono usare ne' GtkSpell ne'
# Gspell 1.x, perche' quei binding sono compilati contro GTK 3 (caricarli dopo
# GTK 4 fallisce con "Requiring namespace 'Gtk' version '3.0', but '4.0' is
# already loaded"). Il backend giusto per GTK 4 e' libspelling (namespace
# 'Spelling'), la stessa libreria usata da GNOME Text Editor; in subordine si
# tenta Gspell 2.x (namespace 'Gspell' versione '2'), che e' la prima serie di
# Gspell compatibile con GTK 4.
#
#   Debian/Ubuntu (libspelling): sudo apt install gir1.2-spelling-1 \
#                                 hunspell-it hunspell-en-us
#
# SPELL_BACKEND vale "spelling" | "gspell2" | None.
SPELL_BACKEND = None
Spelling = None
Gspell = None
try:
    gi.require_version("Spelling", "1")
    from gi.repository import Spelling
    SPELL_BACKEND = "spelling"
except Exception:
    Spelling = None
    try:
        # solo Gspell 2.x e' compatibile con GTK 4 (la 1.x e' legata a GTK 3)
        gi.require_version("Gspell", "2")
        from gi.repository import Gspell
        SPELL_BACKEND = "gspell2"
    except Exception:
        Gspell = None
        SPELL_BACKEND = None
HAVE_SPELL = SPELL_BACKEND is not None
HAVE_GTKSPELL = HAVE_SPELL   # nome storico mantenuto per compatibilita'

from . import paths
from . import model as pw_model
from .model import (
    APP_NAME, APP_VERSION, APP_VERSION_SHORT, APP_AUTHOR, APP_RELEASE_DATE,
    TYPEWRITER_FAMILY, TYPEWRITER_FILE, TYPEWRITER_FILES,
    SERIF_FILES,
    MIN_FONT_SIZE, MAX_FONT_SIZE,
    PDF_PAGE_SIZES, PDF_DEFAULT_PAGE_SIZE, PDF_PAGE_SIZE_LABELS,
    Project, read_ttf_metrics,
    TYPEWRITER_FAMILY as _TW_FAMILY, SERIF_FAMILY,
    system_font_families, font_files_for_family,
    HAVE_PYPHEN, hyphenation_available,
)
# EN/IT: theme families (plum "rusca" and neutral "standard", each in a light
# and a dark version). All colours come from theme_palette(): the interface
# never writes a colour of its own.
# Famiglie di tema (prugna "rusca" e neutra "standard", ciascuna in versione
# chiara e scura). Tutti i colori arrivano da theme_palette(): l'interfaccia
# non scrive mai un colore per conto suo.
from .model import (
    DEFAULT_THEME, theme_palette, build_css, resolve_theme,
    load_user_themes, register_user_themes,
    theme_label as model_theme_label,
)
# NB: THEMES cresce a runtime con i temi trovati su disco, quindi si legge
# sempre come pw_model.THEMES (il modulo e' gia' importato qui sopra) e non si
# copia mai in un nome locale, o i temi dell'utente resterebbero invisibili.
# EN/IT: the Markdown rules, shared with every export: the preview and the
# live highlighting must show what the exports will produce.
# Le regole del Markdown, in comune con tutti gli export: anteprima ed
# evidenziazione devono mostrare cio' che gli export produrranno.
from .model import (classify_md_line, parse_inline, inline_spans,
                    wrapped_runs, unwrap_hard_breaks)
from .i18n import (Translator, LANGUAGES, available_languages,
                   ensure_language_files, spell_locale_for,
                   RTL_LANGUAGES, COMPLETE_LANGUAGES)

APP_ID = "org.ruscalinux.RuscaWriter"
# Indirizzi pubblici del progetto, mostrati nel dialogo Informazioni.
APP_WEBSITE = "https://www.ruscalinux.org/ruscawriter/"
APP_SOURCE = "https://github.com/ruscalinux-dev/ruscawriter"
# EN: release date of this build (year, month, day). The readable form is
#     composed in the interface language via the translated month names
#     (keys "month_1"..."month_12") and the "date_format" pattern in the
#     language files; missing those, it falls back to English, then ISO.
# IT: data di rilascio di questa build (anno, mese, giorno). La forma
#     leggibile viene composta nella lingua dell'interfaccia tramite i nomi
#     dei mesi tradotti (chiavi "month_1"..."month_12") e il pattern
#     "date_format" nei file di lingua; in mancanza, si ripiega sull'inglese
#     e infine sull'ISO.
#     La data NON si scrive piu' qui: arriva da model.APP_RELEASE_DATE, che e'
#     l'unico posto da aggiornare a ogni rilascio.
#     The date is NOT written here any more: it comes from
#     model.APP_RELEASE_DATE, the single place to update at each release.
APP_DATE = APP_RELEASE_DATE

# EN/IT: fallback strings (only if translated month keys are missing) /
# stringhe di riserva (usate solo se mancano le chiavi tradotte dei mesi).
# Composte dalla data, cosi' non vanno piu' aggiornate a mano.
_MONTHS_IT = ("Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
              "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre")
_MONTHS_EN = ("January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December")
APP_DATE_IT = "%d %s %d" % (APP_DATE[2], _MONTHS_IT[APP_DATE[1] - 1], APP_DATE[0])
APP_DATE_EN = "%s %d, %d" % (_MONTHS_EN[APP_DATE[1] - 1], APP_DATE[2], APP_DATE[0])

ICON_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="body" x1="0" y1="0" x2="1" y2="0.4">
      <stop offset="0"    stop-color="#B0273D"/>
      <stop offset="0.4"  stop-color="#86142A"/>
      <stop offset="1"    stop-color="#560A1A"/>
    </linearGradient>
    <linearGradient id="bodyHi" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0"   stop-color="#E27486" stop-opacity="0.85"/>
      <stop offset="1"   stop-color="#E27486" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="0.6">
      <stop offset="0"    stop-color="#FBE9A6"/>
      <stop offset="0.45" stop-color="#E3B23C"/>
      <stop offset="1"    stop-color="#9A6E12"/>
    </linearGradient>
    <linearGradient id="goldB" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0"   stop-color="#FFF3C4"/>
      <stop offset="1"   stop-color="#C68A1C"/>
    </linearGradient>
    <linearGradient id="bgA" x1="0" y1="0" x2="0.8" y2="1">
      <stop offset="0"   stop-color="#6E1024"/>
      <stop offset="0.55" stop-color="#4A0A18"/>
      <stop offset="1"   stop-color="#2C0610"/>
    </linearGradient>
    <radialGradient id="bgAglow" cx="0.32" cy="0.26" r="0.8">
      <stop offset="0"   stop-color="#E27486" stop-opacity="0.45"/>
      <stop offset="0.5" stop-color="#E27486" stop-opacity="0.10"/>
      <stop offset="1"   stop-color="#E27486" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect x="2" y="2" width="60" height="60" rx="15" fill="url(#bgA)"/>
  <rect x="2" y="2" width="60" height="60" rx="15" fill="url(#bgAglow)"/>
  <rect x="2.6" y="2.6" width="58.8" height="58.8" rx="14.4" fill="none"
        stroke="url(#goldB)" stroke-width="1" opacity="0.55"/>
  <g transform="rotate(-42 32 32)">
    <rect x="25.2" y="8.6" width="13.6" height="48" rx="6"
          fill="#000000" opacity="0.22" transform="translate(1.8,2.2)"/>
    <rect x="25" y="8" width="14" height="19" rx="5.5" fill="url(#body)"/>
    <rect x="26.4" y="9.5" width="3.4" height="16" rx="1.7" fill="url(#bodyHi)"/>
    <rect x="27.5" y="6.4" width="9" height="3.2" rx="1.6" fill="url(#goldB)"/>
    <rect x="27.5" y="6.6" width="9" height="1" rx="0.5" fill="#FFF3C4" opacity="0.7"/>
    <rect x="25" y="11.4" width="14" height="2.4" fill="url(#goldB)"/>
    <rect x="30.9" y="13.6" width="2.2" height="10.5" rx="1.1" fill="url(#gold)"/>
    <circle cx="32" cy="24" r="1.7" fill="url(#gold)"/>
    <rect x="24.4" y="27" width="15.2" height="6" rx="1.6" fill="url(#gold)"/>
    <rect x="24.4" y="27.6" width="15.2" height="1" fill="#FFF3C4" opacity="0.75"/>
    <rect x="24.4" y="31.6" width="15.2" height="1" fill="#8A5E10" opacity="0.6"/>
    <path d="M25 33 H39 L37.4 48 Q35.5 50 32 50 Q28.5 50 26.6 48 Z" fill="url(#body)"/>
    <rect x="26.6" y="33" width="3.4" height="15" rx="1.5" fill="url(#bodyHi)"/>
    <rect x="27.2" y="49.4" width="9.6" height="2.4" rx="1" fill="url(#gold)"/>
    <path d="M28 51.6 H36 L34 57 H30 Z" fill="#171012"/>
    <path d="M29 51.6 H30.6 L29.8 57 H29.4 Z" fill="#3C2B2F" opacity="0.7"/>
    <path d="M29.6 56.6 H34.4 L33.1 59.6 Q32 62.6 32 62.6 Q32 62.6 30.9 59.6 Z"
          fill="url(#gold)"/>
    <path d="M29.6 56.6 H34.4 L33.1 59.6 Q32 62.6 32 62.6 Q32 62.6 30.9 59.6 Z"
          fill="none" stroke="#8A5E10" stroke-width="0.4"/>
    <line x1="32" y1="57.4" x2="32" y2="61.6" stroke="#7A5410" stroke-width="0.85"/>
    <circle cx="32" cy="58.2" r="1.05" fill="#7A5410"/>
  </g>
</svg>"""


def load_texture(size):
    """Carica l'icona della stilografica come Gdk.Texture alla dimensione data."""
    if GdkPixbuf is None:
        return None
    try:
        loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
        loader.set_size(size, size)
        loader.write(ICON_SVG)
        loader.close()
        pixbuf = loader.get_pixbuf()
        if pixbuf is None:
            return None
        return Gdk.Texture.new_for_pixbuf(pixbuf)
    except Exception:
        return None


DEFAULT_FONT_SIZE = 14


def register_bundled_font():
    """Registra i font .ttf della cartella assets/. True se il Regular c'e'."""
    here = paths.ASSETS_DIR
    try:
        import ctypes
        try:
            fc = ctypes.CDLL("libfontconfig.so.1")
        except OSError:
            fc = ctypes.CDLL("libfontconfig.so")
        fc.FcConfigAppFontAddFile.restype = ctypes.c_int
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        regular_ok = False
        for style, fname in TYPEWRITER_FILES.items():
            path = os.path.join(here, fname)
            if os.path.exists(path):
                ok = bool(fc.FcConfigAppFontAddFile(None, path.encode("utf-8")))
                if style == "regular":
                    regular_ok = ok
        # registra anche il serif EB Garamond, cosi' eventuali anteprime di
        # EPUB/HTML aperte sullo stesso sistema possono usarlo per nome.
        for fname in SERIF_FILES.values():
            path = os.path.join(here, fname)
            if os.path.exists(path):
                fc.FcConfigAppFontAddFile(None, path.encode("utf-8"))
        return regular_ok
    except Exception:
        return os.path.exists(os.path.join(here, TYPEWRITER_FILE))


LEFT_FRAC   = 0.20
RIGHT_FRAC  = 0.22
LEFT_MIN_PX  = 180
RIGHT_MIN_PX = 200
# EN: the centre column is what the program is for. Left and right were each
#     capped at 40% of the width, but INDEPENDENTLY: together they could take
#     80% and squeeze the writing area into a sliver. This is the floor the
#     text keeps, whatever the side columns ask for.
# IT: la colonna centrale e' il motivo per cui il programma esiste. Sinistra e
#     destra erano capate ciascuna al 40% della larghezza, ma in modo
#     INDIPENDENTE: insieme potevano prendersene l'80% e ridurre l'area di
#     scrittura a una fessura. Questo e' il minimo che il testo conserva,
#     qualunque cosa chiedano le colonne laterali.
CENTER_MIN_PX = 360


def split_columns(total, left_px=None, right_px=None,
                  left_visible=True, right_visible=True):
    """Larghezza delle tre colonne, dato lo spazio disponibile.

    Restituisce (sinistra, centro, destra) in pixel. Sta fuori dal widget di
    proposito: cosi' la regola si prova con dei numeri, senza aver bisogno di
    una finestra vera, ed e' li' che si era nascosto l'errore.

    La regola: le colonne laterali chiedono, la centrale decide. Se insieme
    lascerebbero al testo meno di CENTER_MIN_PX, le laterali si restringono in
    proporzione. Su una finestra troppo stretta perche' il minimo stia in
    piedi, si cede anche su quello, ma sempre a partire dai lati.
    """
    if total <= 1:
        return (0, max(0, total), 0)

    left_w = 0
    if left_visible:
        left_w = max(LEFT_MIN_PX,
                     min(left_px or int(total * LEFT_FRAC), int(total * 0.4)))
    right_w = 0
    if right_visible:
        right_w = max(RIGHT_MIN_PX,
                      min(right_px or int(total * RIGHT_FRAC), int(total * 0.4)))

    minimo = min(CENTER_MIN_PX, max(1, total - LEFT_MIN_PX - RIGHT_MIN_PX))
    centro = total - left_w - right_w
    if centro < minimo and (left_w + right_w) > 0:
        da_togliere = minimo - centro
        somma = left_w + right_w
        if left_w:
            left_w = max(LEFT_MIN_PX,
                         left_w - int(da_togliere * left_w / somma) - 1)
        if right_w:
            right_w = max(RIGHT_MIN_PX,
                          right_w - int(da_togliere * right_w / somma) - 1)
        # finestra molto stretta: si cede anche sui minimi laterali
        eccesso = (total - left_w - right_w) - minimo
        if eccesso < 0 and right_w:
            right_w = max(0, right_w + eccesso)
        eccesso = (total - left_w - right_w) - minimo
        if eccesso < 0 and left_w:
            left_w = max(0, left_w + eccesso)
    return (left_w, total - left_w - right_w, right_w)
READING_MAX_PX = 980


def _config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    # Cartella di configurazione dell'applicazione.
    d = os.path.join(base, "ruscawriter")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "settings.json")


ESEMPIO_TEMA = """\
# ---------------------------------------------------------------------------
# Come si scrive un tema per RuscaWriter
#
# Copia questo file, chiamalo come vuoi purche' finisca in .theme
# (per esempio  verde.theme )  e mettilo in questa stessa cartella.
# Riavvia RuscaWriter: il tema comparira' in  Visualizza -> Tema.
#
# Servono un nome e sette colori, uno per riga, nella forma  chiave = #RRGGBB
# Le righe vuote e quelle che iniziano con # sono note come questa.
# Tutto il resto dell'interfaccia (lino, avorio, grafite) e' gia' pronto:
# questi sette colori sono la tinta che lo attraversa.
#
# Ogni tema vale sia in chiaro sia in scuro: la versione chiara e quella scura
# si costruiscono da soli a partire da questi colori.
# ---------------------------------------------------------------------------

# Il nome che vedrai nel menu
nome = Standard verde

# Il colore principale: barre, pulsanti, testo selezionato
accento        = #2E7D4F

# Una versione piu' scura: titoli e scritte sul chiaro
accento-scuro  = #1B5233

# Una versione molto chiara: sfumature e sfondi tenui
accento-chiaro = #C7E3D3

# Una versione luminosa: si usa sul fondo scuro, dove il colore pieno sparirebbe
accento-acceso = #8FD3AC

# Il colore del testo a spaziatura fissa (i `backtick` del Markdown)
codice         = #2A6B48

# Il velo che segnala i paragrafi spezzati, nel tema chiaro
velo-chiaro    = #E4F2E9

# Lo stesso velo, nel tema scuro
velo-scuro     = #23372C

# Consiglio: scegli accento e accento-scuro abbastanza carichi da leggere il
# bianco sopra, e accento-acceso abbastanza chiaro da leggersi sul grafite.
#
# Se invece vuoi un accento CHIARO (barre grigie o pastello, come nel tema
# Standard), aggiungi queste due righe, altrimenti il testo bianco sopra le
# barre sparirebbe:
#
#   testo-su-accento = #26231F     il colore del testo sulle barre
#   testo            = #3A3632     titoli, nomi dei capitoli, barra di stato
#
# Puoi anche cambiare la CARTA e il fondo, che sono meta' del carattere di un
# tema. Se non li indichi valgono quelli di Quiete. Un consiglio: niente
# bianco pieno e niente nero pieno — il primo abbaglia, il secondo fa sbordare
# le lettere. Il testo sta bene fra 12:1 e 14:1 di contrasto.
#
#   carta        = #FBF7F0     l'area di scrittura, tema chiaro
#   pannelli     = #F2EBE0     le colonne laterali
#   inchiostro   = #2E2822     il testo sul chiaro
#   fondo-scuro  = #171A21     lo sfondo del tema scuro
#   carta-scura  = #131519     l'area di scrittura, tema scuro
#   testo-scuro  = #DCD5C8     il testo sullo scuro
#
# Le fasce dell'interfaccia possono restare neutre mentre il colore resta
# sulla sola selezione — e' cosi' che sono fatti Quiete e Velluto:
#
#   fasce = #F2EBE0    menu = #F2EBE0    testo-fasce = #2E2822
"""


def _themes_dir():
    """Cartella dei temi dell'utente, accanto alle impostazioni.
    Alla prima esecuzione ci si trova un file di esempio, commentato riga per
    riga, da copiare e modificare."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, "ruscawriter", "themes")
    try:
        os.makedirs(d, exist_ok=True)
        esempio = os.path.join(d, "ESEMPIO-copiami.txt")
        if not os.path.exists(esempio):
            with open(esempio, "w", encoding="utf-8") as f:
                f.write(ESEMPIO_TEMA)
    except Exception:
        pass
    return d


def load_settings():
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data):
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def detect_system_language():
    candidates = []
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        val = os.environ.get(var)
        if val:
            candidates.extend(val.split(":"))
    try:
        loc = locale.getlocale()[0]
        if not loc and hasattr(locale, "getdefaultlocale"):
            loc = locale.getdefaultlocale()[0]
        if loc:
            candidates.append(loc)
    except Exception:
        pass
    for c in candidates:
        if not c:
            continue
        code = c.split(".")[0].split("_")[0].lower()
        if code in LANGUAGES:
            return code
    return "en"


# ---- correzione dell'elisione (italiano, francese) -------------------------
# Perche' serve: il controllo ortografico di GTK 4 (libspelling) usa ICU per
# spezzare il testo in parole, e ICU taglia sull'apostrofo. Cosi' "dell'anima"
# diventa due token, "dell" e "anima", e "dell" da solo non e' nel dizionario:
# viene segnalato come errore. La vecchia versione GTK 3 (Gspell) usava invece
# la segmentazione di Pango, che scartava il frammento di elisione, quindi il
# problema non si vedeva.
#
# Soluzione indipendente dalla libreria: aggiungiamo i frammenti di elisione
# (dell, quell, nell, j, qu, ...) alle "parole personali" di Enchant, che e' il
# motore dei dizionari sotto libspelling. Enchant carica automaticamente il
# file <config>/<locale>.dic (una parola per riga) e lo somma al dizionario.

# Frammenti che restano a sinistra dell'apostrofo, per lingua di base.
_ELISION_FRAGMENTS = {
    # Italiano: articoli e preposizioni articolate elise, pronomi, troncamenti
    # e apocopi piu' comuni.
    "it": [
        "l", "un", "dell", "nell", "all", "dall", "sull", "coll", "pell",
        "quell", "quest", "bell", "sant", "tutt", "anch", "dov", "com",
        "cos", "po", "be", "mo", "ce", "ne", "se", "gliel", "me", "te",
        "buon", "gran", "fin", "senz", "grand", "vent", "cent",
    ],
    # Francese: elisioni obbligatorie dei monosillabi grammaticali.
    "fr": [
        "l", "d", "j", "n", "s", "c", "t", "m", "qu", "jusqu", "lorsqu",
        "puisqu", "quoiqu", "presqu", "quelqu", "aujourd",
    ],
}


def _elision_words_for(base_lang):
    """Restituisce l'insieme dei frammenti di elisione per una lingua base
    (es. 'it'), includendo le varianti con iniziale maiuscola (inizio frase:
    'Dell'', 'L'') e tutto maiuscolo, cosi' non vengono segnalate nemmeno li'."""
    frags = _ELISION_FRAGMENTS.get(base_lang, [])
    out = set()
    for w in frags:
        out.add(w)
        out.add(w.capitalize())
        out.add(w.upper())
    return out


def _enchant_config_dir():
    """Cartella di configurazione di Enchant dove finiscono le liste personali.
    Rispetta ENCHANT_CONFIG_DIR, poi XDG_CONFIG_HOME, infine ~/.config."""
    env = os.environ.get("ENCHANT_CONFIG_DIR")
    if env:
        return env
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "enchant")


# File "collaterale" in cui teniamo traccia delle parole che ABBIAMO aggiunto
# noi, per poterle gestire in modo idempotente SENZA sporcare il file .dic che
# Enchant legge. Importante: nel file .dic le parole vanno scritte "nude", una
# per riga, perche' Enchant interpreta '#' come commento SOLO a inizio riga: un
# commento a fine riga finirebbe dentro la parola e la renderebbe inutile.
_ELISION_SIDECAR_SUFFIX = ".ruscawriter-added"


def ensure_elision_dictionaries(locales):
    """Per ciascun locale dato (es. 'it_IT', 'fr_FR'), assicura che la lista
    personale di Enchant <config>/<locale>.dic contenga i frammenti di elisione
    di quella lingua, scritti come parole nude (una per riga).

    Idempotente e non distruttiva: le parole aggiunte dall'utente restano; le
    nostre vengono ricalcolate. Per distinguerle senza inquinare il .dic,
    teniamo l'elenco delle nostre parole in un file collaterale
    <locale>.dic.ruscawriter-added accanto.

    Restituisce la lista dei file .dic effettivamente scritti/aggiornati."""
    written = []
    try:
        cfg = _enchant_config_dir()
        os.makedirs(cfg, exist_ok=True)
    except Exception:
        return written

    for loc in locales:
        base = loc.split("_")[0].lower()
        words = _elision_words_for(base)
        if not words:
            continue
        path = os.path.join(cfg, f"{loc}.dic")
        sidecar = path + _ELISION_SIDECAR_SUFFIX

        # parole attualmente nel .dic (tutte, nude)
        current = []
        current_set = set()
        raw_lines = []          # righe grezze sul disco (per capire se "sporco")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for raw in f:
                        raw_lines.append(raw.rstrip("\n"))
                        line = raw.strip()
                        if not line or line.startswith("#"):
                            continue
                        # MIGRAZIONE da una versione precedente che, per errore,
                        # scriveva un commento a fine riga ("dell  # ...-elision"):
                        # quelle righe sono inutili per Enchant. Le ripuliamo
                        # tenendo solo la parola prima del '#'.
                        if "#" in line:
                            line = line.split("#", 1)[0].strip()
                            if not line:
                                continue
                        # una riga con piu' token non e' valida: prendi la prima
                        parts = line.split()
                        w = parts[0] if parts else ""
                        if w and w not in current_set:
                            current.append(w)
                            current_set.add(w)
        except Exception:
            current, current_set, raw_lines = [], set(), []

        # parole che avevamo aggiunto noi in passato (dal collaterale)
        prev_ours = set()
        try:
            if os.path.exists(sidecar):
                with open(sidecar, "r", encoding="utf-8") as f:
                    for raw in f:
                        w = raw.strip()
                        if w and not w.startswith("#"):
                            prev_ours.add(w)
        except Exception:
            prev_ours = set()

        # parole "dell'utente" = quelle presenti che NON erano nostre
        user_words = [w for w in current if w not in prev_ours]
        user_set = set(user_words)

        # nostre parole da garantire: tutti i frammenti che l'utente non abbia
        # gia' inserito a mano (per non duplicarli)
        our_words = sorted(w for w in words if w not in user_set)

        # contenuto desiderato del .dic = parole utente + nostre
        desired = user_words + [w for w in our_words if w not in user_set]

        # Il file su disco e' gia' "pulito e giusto" solo se le righe grezze
        # coincidono esattamente con le parole desiderate (nessun commento,
        # nessun marcatore, nessun ordine diverso). In caso contrario riscrivi.
        clean_on_disk = (raw_lines == desired)
        if clean_on_disk and prev_ours == set(our_words):
            continue

        try:
            with open(path, "w", encoding="utf-8") as f:
                for w in desired:
                    f.write(w + "\n")
            with open(sidecar, "w", encoding="utf-8") as f:
                f.write("# Parole aggiunte automaticamente da RuscaWriter "
                        "(frammenti di elisione). Non modificare a mano.\n")
                for w in our_words:
                    f.write(w + "\n")
            written.append(path)
        except Exception:
            pass
    return written


class RuscaWriterWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=f"{APP_NAME} v{APP_VERSION}")
        self.app = app
        self.settings = load_settings()
        w = self.settings.get("win_w", 1200)
        h = self.settings.get("win_h", 760)
        self.set_default_size(w, h)
        # EN: a maximised window must come back maximised. Without this, its
        #     size was saved WHILE maximised and restored as an ordinary window
        #     of screen size — spilling under the taskbar, with the window
        #     buttons off the edge. See _on_size_changed: the size is now only
        #     recorded when the window is not maximised, so the value kept is
        #     the one to return to.
        # IT: una finestra massimizzata deve riaprirsi massimizzata. Senza
        #     questo, le sue dimensioni venivano salvate MENTRE era
        #     massimizzata e ripristinate come finestra normale grande quanto
        #     lo schermo: sbordava sotto la barra delle applicazioni e i
        #     pulsanti finivano fuori. Vedi _on_size_changed: le dimensioni si
        #     registrano solo quando NON e' massimizzata, così il valore
        #     conservato e' quello a cui tornare.
        if self.settings.get("win_maximized"):
            self.maximize()

        ensure_language_files()
        sys_lang = detect_system_language()
        self.lang = self.settings.get("ui_lang", sys_lang)
        if self.lang not in LANGUAGES:
            self.lang = sys_lang if sys_lang in LANGUAGES else "en"
        self.translator = Translator(self.lang)
        self.project = Project()
        self.project._lang = self.lang
        self.current = None
        self._loading = False
        self.left_visible = self.settings.get("left_visible", True)
        self.right_visible = self.settings.get("right_visible", True)
        self._restoring = True

        self.font_available = register_bundled_font()
        self.font_size = int(self.settings.get("font_size", DEFAULT_FONT_SIZE))
        self.font_size = max(MIN_FONT_SIZE, min(self.font_size, MAX_FONT_SIZE))
        # Carattere dei documenti ESPORTATI. Vuoto = comportamento predefinito
        # (il serif da lettura incorporato). Puo' essere il nome di una
        # famiglia installata sulla macchina.
        self.doc_font = self.settings.get("doc_font", "")
        self.font_family = self.settings.get(
            "font_family",
            TYPEWRITER_FAMILY if self.font_available else "Monospace")
        if self.font_family in ("Special Elite",) and self.font_available:
            self.font_family = TYPEWRITER_FAMILY

        self.spell_lang = self.settings.get("spell_lang", self.lang)
        self.spell_checker = None
        self.spell_error = None

        self._dirty = False
        self.word_goal = int(self.settings.get("word_goal", 0))

        self.theme_pref = self.settings.get("theme", "auto")
        self.dark_mode = self._resolve_dark(self.theme_pref)
        # Famiglia di colori dell'interfaccia: "rusca" (prugna, abbinato a
        # RuscaLinux) oppure "standard" (neutro, ispirato a Scrivener). E'
        # indipendente da chiaro/scuro: ogni famiglia ha entrambe le versioni.
        # Un valore salvato non piu' valido ripiega sul predefinito.
        # Temi dell'utente: si leggono PRIMA di scegliere quale applicare,
        # altrimenti un tema personalizzato salvato nelle impostazioni non
        # risulterebbe ancora valido e si ripiegherebbe sul predefinito.
        self.themes_dir = _themes_dir()
        temi_utente, self._theme_errors = load_user_themes(self.themes_dir)
        register_user_themes(temi_utente)
        # resolve_theme traduce anche i codici dei temi vecchi, così chi aveva
        # una variante non piu' esistente si ritrova sullo Standard e non
        # rimbalza sul predefinito senza spiegazione.
        self.theme_family = resolve_theme(
            self.settings.get("theme_family", DEFAULT_THEME))
        # Vista "Mostra le interruzioni": tinge i paragrafi spezzati a colonna
        # fissa. Non modifica il testo, si limita a farlo vedere.
        self.show_breaks = bool(self.settings.get("show_breaks", False))
        # Ricucitura automatica all'importazione: SPENTA di partenza. Modifica
        # il testo di chi scrive, quindi non si accende da sola: si attiva dal
        # menu, e da quel momento RuscaWriter ricuce i file importati senza
        # chiedere altro. Chi non la accende puo' sempre usare il comando
        # manuale su un capitolo alla volta.
        self.reflow_on_import = bool(self.settings.get("reflow_on_import", False))
        self._is_fullscreen = False

        # ultimo formato pagina PDF usato (ricordato tra le sessioni); se il
        # valore salvato non e' tra quelli validi, ripiega sul predefinito.
        saved_size = self.settings.get("pdf_page_size", PDF_DEFAULT_PAGE_SIZE)
        self._pdf_page_size = (saved_size if saved_size in PDF_PAGE_SIZES
                               else PDF_DEFAULT_PAGE_SIZE)

        # preferenze di impaginazione PDF ricordate tra le sessioni:
        # giustificazione del testo e sillabazione. La sillabazione richiede il
        # pacchetto opzionale Pyphen E un dizionario per la lingua (su Debian
        # un pacchetto hyphen-<lingua>): se manca l'uno o l'altro la teniamo
        # sempre a False, a prescindere da cio' che e' salvato.
        self._pdf_justify = bool(self.settings.get("pdf_justify", False))
        self._pdf_hyphenate = bool(
            self.settings.get("pdf_hyphenate", False)) and hyphenation_available(
                getattr(self, "lang", "it"))

        # Evita che gli entry/spinbutton selezionino tutto il testo quando
        # ricevono il focus (in GTK 4 e' il comportamento predefinito): senza
        # questo, lo SpinButton del font mostrerebbe "14" tutto evidenziato.
        try:
            gtk_settings = Gtk.Settings.get_default()
            if gtk_settings is not None:
                gtk_settings.set_property("gtk-entry-select-on-focus", False)
        except Exception:
            pass

        self._apply_css()
        self._build_actions()
        self._build_ui()
        self._apply_editor_font()
        # orienta l'area di scrittura fin dall'avvio, non solo al cambio lingua
        self._apply_text_direction()
        # prepara le liste di elisione di Enchant PRIMA di creare il checker,
        # cosi' libspelling le trova gia' pronte (vedi ensure_elision_dictionaries)
        self._ensure_elision_for_spell()
        self._setup_spell()
        self._retranslate()

        self.connect("close-request", self.on_close_request)
        self.connect("notify::default-width", self._on_size_changed)
        self.connect("notify::default-height", self._on_size_changed)
        self.connect("notify::maximized", self._on_size_changed)
        self.connect("notify::fullscreened", self._on_fullscreen_changed)

        GLib.idle_add(self._apply_layout)
        GLib.idle_add(self._finish_restore)
        GLib.idle_add(self._startup_dialog)
        # Se un file di tema e' scritto male, dirlo: chi l'ha appena creato
        # deve sapere perche' non compare nel menu.
        if getattr(self, "_theme_errors", None):
            GLib.idle_add(self._report_theme_errors)
        # All'apertura, dai il focus all'area di scrittura: senza questo il
        # primo widget focusabile (lo SpinButton del font) riceverebbe il focus
        # e mostrerebbe il numero "14" tutto selezionato/evidenziato.
        GLib.idle_add(self._focus_editor)
        self._autosave_id = GLib.timeout_add_seconds(60, self._autosave_tick)

    def _report_theme_errors(self):
        self._error(self.t("theme_file_errors",
                           e="\n".join(self._theme_errors)))
        self._theme_errors = []
        return False

    def _focus_editor(self):
        try:
            self.text_view.grab_focus()
        except Exception:
            pass
        return False

    def _raise_dialog(self, dialog):
        """Riporta un dialogo in primo piano: utile quando la finestra
        principale è a schermo intero e il window manager lo metterebbe dietro."""
        try:
            if dialog.get_visible():
                dialog.present()
        except Exception:
            pass
        return False

    def _finish_restore(self):
        self._restoring = False
        return False

    # ---- salvataggio sicuro -------------------------------------------------
    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._update_window_title()

    def _mark_clean(self):
        self._dirty = False
        self._update_window_title()

    def _update_window_title(self):
        base = f"{APP_NAME} v{APP_VERSION}"
        proj = getattr(self.project, "title", "") or ""
        if proj:
            if self._dirty:
                self.set_title(self.t("title_dirty", t=proj) + f" — {base}")
            else:
                self.set_title(f"{proj} — {base}")
        else:
            self.set_title(base)

    def _autosave_path(self):
        if self.project.path:
            return self.project.path + ".autosave"
        return None

    def _autosave_tick(self):
        try:
            if self._dirty and self.project.path:
                self._commit_current()
                self.project.meta["font_size"] = self.font_size
                self.project.meta["font_family"] = self.font_family
                self.project.meta["spell_lang"] = self.spell_lang
                self.project.save(self._autosave_path(), update_path=False)
        except Exception:
            pass
        return True

    def on_close_request(self, *_):
        if not self._dirty:
            self._persist_layout()
            return False

        def on_choice(idx):
            if idx == 0:          # scarta
                self._cleanup_autosave()
                self._persist_layout()
                self._force_close()
            elif idx == 2:        # salva (senza popup) e poi chiudi
                def after_save():
                    self._cleanup_autosave()
                    self._persist_layout()
                    self._force_close()
                self.on_save(announce=False, then=after_save)
            # idx == 1 (annulla) o chiusura: resta aperto

        self._confirm(self.t("unsaved_title"), self.t("unsaved_body"),
                      [self.t("btn_discard"), self.t("btn_cancel"),
                       self.t("btn_save_changes")],
                      default_idx=2, cancel_idx=1, on_choice=on_choice)
        return True   # blocca questa chiusura; decidiamo nel callback

    def _force_close(self):
        self._dirty = False
        self.destroy()

    def _cleanup_autosave(self):
        p = self._autosave_path()
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    # ---- traduzione ---------------------------------------------------------
    def t(self, key, **kw):
        return self.translator.t(key, **kw)

    def _t_or(self, key, default, **kw):
        """Come t(), ma se la chiave non e' presente nei file di lingua
        (t() ripiegherebbe sulla chiave grezza) usa il testo 'default'.
        Serve per voci nuove non ancora tradotte: l'interfaccia mostra
        comunque un testo sensato, e quando il JSON conterra' la chiave
        verra' usata la traduzione."""
        val = self.translator.t(key, **kw)
        if val == key:
            return default.format(**kw) if kw else default
        return val

    @property
    def app_date(self):
        """Data di rilascio nella lingua dell'interfaccia.

        Compone giorno/mese/anno usando il nome del mese tradotto
        ("month_1".."month_12") e il pattern "date_format" (con i segnaposto
        {d}=giorno, {m}=mese, {y}=anno). Se queste chiavi non sono presenti
        nella lingua scelta, il Translator ripiega sull'inglese; se mancano
        anche li', si usano le stringhe storiche IT/EN e infine l'ISO."""
        year, month, day = APP_DATE
        month_name = self.translator.t(f"month_{month}")
        # se la chiave del mese non e' tradotta (t() restituisce la chiave
        # stessa) ripieghiamo sulle stringhe storiche
        if month_name == f"month_{month}":
            return APP_DATE_IT if self.lang == "it" else APP_DATE_EN
        fmt = self.translator.t("date_format")
        if fmt == "date_format":
            fmt = "{d} {m} {y}"     # ripiego neutro: "14 Giugno 2026"
        try:
            return fmt.format(d=day, m=month_name, y=year)
        except Exception:
            return f"{day} {month_name} {year}"

    # ---- stile --------------------------------------------------------------
    def _system_prefers_dark(self):
        try:
            settings = Gtk.Settings.get_default()
            prefer = settings.get_property("gtk-application-prefer-dark-theme")
            if prefer:
                return True
            name = settings.get_property("gtk-theme-name") or ""
            return "dark" in name.lower()
        except Exception:
            return False

    def _resolve_dark(self, pref):
        if pref == "dark":
            return True
        if pref == "light":
            return False
        return self._system_prefers_dark()

    def palette(self):
        """Tavolozza corrente: famiglia di tema + chiaro/scuro.

        Unico punto da cui l'interfaccia prende i colori (compresi quelli dei
        titoli Markdown nell'editor), così le quattro combinazioni restano
        coerenti fra loro."""
        return theme_palette(getattr(self, "theme_family", DEFAULT_THEME),
                             getattr(self, "dark_mode", False))

    def theme_label(self, code):
        """Nome da mostrare nel menu: tradotto per i temi incorporati, letto
        dal file per quelli dell'utente.

        Davanti al nome va il pallino del colore, dove c'e'. Le etichette dei
        menu GTK sono testo semplice — non si possono colorare voce per voce —
        quindi il colore entra come carattere, non come tinta dell'etichetta."""
        nome = model_theme_label(code, translate=self._t_or)
        pallino = pw_model.theme_dot(code)
        return f"{pallino}  {nome}" if pallino else nome

    def _sync_switch(self, nome, attivo):
        """Riallinea la spunta di un interruttore nel menu al suo valore
        vero. Va chiamata a ogni cambio, o la spunta e la realta' divergono."""
        act = getattr(self, "_switch_actions", {}).get(nome)
        if act is not None:
            act.set_state(GLib.Variant.new_boolean(bool(attivo)))

    def on_toggle_dark(self, *_):
        self.dark_mode = not self.dark_mode
        self.theme_pref = "dark" if self.dark_mode else "light"
        self.settings["theme"] = self.theme_pref
        save_settings(self.settings)
        self._sync_switch("dark", self.dark_mode)
        self._apply_css()
        self._update_tag_colors()

    def on_theme_family(self, code):
        """Cambia famiglia di colori (prugna RuscaLinux / Standard) senza
        toccare la preferenza chiaro-scuro, che resta com'era."""
        if (code not in pw_model.THEMES
                or code == getattr(self, "theme_family", None)):
            return
        self.theme_family = code
        self.settings["theme_family"] = code
        save_settings(self.settings)
        self._apply_css()
        self._update_tag_colors()

    def _apply_css(self):
        if not hasattr(self, "_theme_provider"):
            self._theme_provider = Gtk.CssProvider()
            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display, self._theme_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        css = build_css(dark=getattr(self, "dark_mode", False),
                        theme=getattr(self, "theme_family", DEFAULT_THEME))
        try:
            self._theme_provider.load_from_data(css.encode("utf-8"))
        except Exception:
            try:
                self._theme_provider.load_from_data(css, -1)
            except Exception:
                pass

    # ---- layout -------------------------------------------------------------
    def _content_width(self):
        w = self.paned_outer.get_allocated_width()
        return w if w > 1 else self.settings.get("win_w", 1200)

    def _apply_editor_font(self):
        if not hasattr(self, "_font_css_provider"):
            self._font_css_provider = Gtk.CssProvider()
            display = Gdk.Display.get_default()
            if display is not None:
                Gtk.StyleContext.add_provider_for_display(
                    display, self._font_css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        css = ('textview.text-editor, textview.text-editor text '
               '{{ font-family: "{fam}"; font-size: {sz}pt; }}').format(
                   fam=self.font_family, sz=self.font_size)
        try:
            self._font_css_provider.load_from_data(css.encode("utf-8"))
        except Exception:
            try:
                self._font_css_provider.load_from_data(css, -1)
            except Exception:
                pass
        if hasattr(self, "font_size_spin"):
            self.font_size_spin.set_value(self.font_size)

    # ---- controllo ortografico ---------------------------------------------
    def _setup_spell(self):
        """Collega il controllo ortografico al TextView. Usa libspelling
        (backend 'spelling') o, in subordine, Gspell 2.x ('gspell2'). Salva
        l'oggetto attivo in self.spell_checker e, per libspelling, l'adapter
        in self._spell_adapter (serve per cambiare lingua e abilitare/menu)."""
        self.spell_error = None
        self.spell_checker = None
        self._spell_adapter = None
        if SPELL_BACKEND is None:
            self.spell_error = ("nessun backend di controllo ortografico "
                                "compatibile con GTK 4 (installa "
                                "gir1.2-spelling-1)")
            return
        loc = self._spell_locale()
        try:
            if SPELL_BACKEND == "spelling":
                # libspelling vuole un GtkSource.Buffer: se GtkSourceView non
                # e' disponibile la vista e' un Gtk.TextView normale e l'adapter
                # rifiuterebbe il buffer. Segnaliamo il motivo invece di fallire.
                if GtkSource is None or not isinstance(self.text_buffer,
                                                       GtkSource.Buffer):
                    raise RuntimeError(
                        "libspelling richiede GtkSourceView 5 "
                        "(installa gir1.2-gtksource-5)")
                self._setup_spell_libspelling(loc)
            else:  # gspell2
                self._setup_spell_gspell2(loc)
        except Exception as exc:
            self.spell_checker = None
            self._spell_adapter = None
            self.spell_error = str(exc) or repr(exc)

    def _make_spelling_checker(self, loc):
        """Crea un Spelling.Checker per il locale dato, con vari ripieghi a
        seconda della versione dell'API di libspelling disponibile."""
        provider = None
        try:
            provider = Spelling.Provider.get_default()
        except Exception:
            provider = None
        # tentativo 1: Checker.new(provider, code)
        if provider is not None:
            try:
                ck = Spelling.Checker.new(provider, loc)
                if ck is not None:
                    return ck
            except Exception:
                pass
            # tentativo 2: anche solo con la sigla lingua (es. 'it')
            try:
                ck = Spelling.Checker.new(provider, loc.split("_")[0])
                if ck is not None:
                    return ck
            except Exception:
                pass
        # ripiego finale: checker predefinito (lingua di sistema)
        return Spelling.Checker.get_default()

    def _setup_spell_libspelling(self, loc):
        checker = self._make_spelling_checker(loc)
        if checker is None:
            raise RuntimeError("impossibile creare il checker libspelling")
        adapter = Spelling.TextBufferAdapter.new(
            self.text_view.get_buffer(), checker)
        # menu contestuale dei suggerimenti + gruppo di azioni 'spelling'
        try:
            extra_menu = adapter.get_menu_model()
            self.text_view.set_extra_menu(extra_menu)
        except Exception:
            pass
        try:
            self.text_view.insert_action_group("spelling", adapter)
        except Exception:
            pass
        adapter.set_enabled(True)
        self.spell_checker = checker
        self._spell_adapter = adapter

    def _setup_spell_gspell2(self, loc):
        lang = Gspell.Language.lookup(loc)
        if lang is None:
            raise RuntimeError("dizionario '%s' non trovato" % loc)
        checker = Gspell.Checker.new(lang)
        buf = Gspell.TextBuffer.get_from_gtk_text_buffer(
            self.text_view.get_buffer())
        buf.set_spell_checker(checker)
        gview = Gspell.TextView.get_from_gtk_text_view(self.text_view)
        gview.set_inline_spell_checking(True)
        gview.set_enable_language_menu(True)
        self.spell_checker = checker

    def _populate_spell_combo(self):
        self._spell_combo_loading = True
        self.spell_combo.remove_all()
        langs = self._available_spell_langs()
        for code in langs:
            self.spell_combo.append(code, LANGUAGES[code][0])
        if self.spell_lang in langs:
            self.spell_combo.set_active_id(self.spell_lang)
        elif langs:
            self.spell_lang = langs[0]
            self.spell_combo.set_active_id(langs[0])
        self._spell_combo_loading = False

    def _spell_locale(self):
        return spell_locale_for(self.spell_lang)

    def _ensure_elision_for_spell(self):
        """Genera/aggiorna le liste personali di Enchant con i frammenti di
        elisione per la lingua ortografica corrente (e per le altre lingue con
        elisione, cosi' il passaggio di lingua e' gia' coperto). Va chiamata
        prima di creare/ricreare il checker."""
        try:
            locales = set()
            # lingua attiva
            locales.add(self._spell_locale())
            # tutte le lingue con elisione note, cosi' funziona anche dopo un
            # cambio lingua senza dover rigenerare nulla
            for base in _ELISION_FRAGMENTS:
                locales.add(spell_locale_for(base))
            ensure_elision_dictionaries(locales)
        except Exception:
            pass   # il controllo ortografico non deve mai bloccare l'avvio

    def _available_spell_langs(self):
        available = []
        if SPELL_BACKEND == "gspell2" and Gspell is not None:
            try:
                installed = {l.get_code() for l in Gspell.Language.get_available()}
                for code in LANGUAGES:
                    loc = spell_locale_for(code)
                    if loc in installed or loc.split("_")[0] in installed or any(
                            ic.split("_")[0] == loc.split("_")[0] for ic in installed):
                        available.append(code)
            except Exception:
                available = []
        elif SPELL_BACKEND == "spelling" and Spelling is not None:
            # libspelling espone le lingue tramite il provider predefinito; i
            # nomi dei metodi variano tra le versioni, quindi proviamo i piu'
            # comuni e, se nulla funziona, ripieghiamo sull'elenco completo.
            try:
                provider = Spelling.Provider.get_default()
                codes = set()
                langs = None
                for meth in ("list_languages", "get_languages", "dup_languages"):
                    fn = getattr(provider, meth, None)
                    if fn is not None:
                        try:
                            langs = fn()
                            break
                        except Exception:
                            langs = None
                if langs is not None:
                    for lg in langs:
                        code = None
                        for attr in ("get_code", "get_language", "get_id"):
                            getter = getattr(lg, attr, None)
                            if getter is not None:
                                try:
                                    code = getter()
                                    break
                                except Exception:
                                    code = None
                        if isinstance(lg, str):
                            code = lg
                        if code:
                            codes.add(code)
                if codes:
                    for code in LANGUAGES:
                        loc = spell_locale_for(code)
                        if loc in codes or loc.split("_")[0] in {
                                c.split("_")[0] for c in codes}:
                            available.append(code)
            except Exception:
                available = []
        if not available:
            available = [c for c in LANGUAGES]
        available = sorted(set(available),
                           key=lambda c: (c != self.lang, LANGUAGES[c][0].lower()))
        return available

    def _set_spell_lang(self, lang):
        self.spell_lang = lang
        self.settings["spell_lang"] = lang
        if not self._restoring:
            save_settings(self.settings)
        # assicura i frammenti di elisione per la nuova lingua prima del checker
        self._ensure_elision_for_spell()
        if self.spell_checker is not None:
            try:
                loc = self._spell_locale()
                if SPELL_BACKEND == "spelling":
                    # crea un nuovo checker per la lingua e applicalo all'adapter
                    new_checker = self._make_spelling_checker(loc)
                    applied = False
                    if self._spell_adapter is not None:
                        for meth in ("set_checker", "set_spell_checker"):
                            fn = getattr(self._spell_adapter, meth, None)
                            if fn is not None and new_checker is not None:
                                try:
                                    fn(new_checker)
                                    applied = True
                                    break
                                except Exception:
                                    applied = False
                    if applied and new_checker is not None:
                        self.spell_checker = new_checker
                    else:
                        # ripiego: ricollega tutto da capo con la nuova lingua
                        self._setup_spell()
                else:  # gspell2
                    glang = Gspell.Language.lookup(loc)
                    if glang is None:
                        raise RuntimeError("dizionario non trovato")
                    self.spell_checker.set_language(glang)
            except Exception as exc:
                self.spell_error = str(exc)
                self._setup_spell()
        elif HAVE_SPELL:
            # il checker non era partito: riprova con la nuova lingua
            self._setup_spell()
        if self.project is not None:
            self.project.meta["spell_lang"] = lang

    def on_spell_lang_changed(self, combo):
        if getattr(self, "_spell_combo_loading", False):
            return
        lang = combo.get_active_id()
        if lang and lang != self.spell_lang:
            self._set_spell_lang(lang)
            if self.spell_checker is None and self.spell_error:
                self._info(self.t("spell_unavailable", e=self.spell_error))

    def _set_font_size(self, size):
        size = max(MIN_FONT_SIZE, min(int(size), MAX_FONT_SIZE))
        if size == self.font_size:
            return
        self.font_size = size
        self._apply_editor_font()
        self.settings["font_size"] = size
        if not self._restoring:
            save_settings(self.settings)

    def on_font_size_changed(self, spin):
        self._set_font_size(spin.get_value_as_int())
        # togli l'eventuale selezione del numero (sicurezza in piu' oltre a
        # gtk-entry-select-on-focus): porta il cursore in fondo senza selezione
        try:
            spin.select_region(0, 0)
        except Exception:
            pass

    def on_font_increase(self, *_):
        self._set_font_size(self.font_size + 1)
        return True

    def on_font_decrease(self, *_):
        self._set_font_size(self.font_size - 1)
        return True

    def _apply_layout(self, _retries=0):
        # La visibilita' dei pannelli va impostata SEMPRE, anche se la larghezza
        # non e' ancora nota (durante le transizioni fullscreen puo' essere <=1):
        # altrimenti, uscendo dalla modalita' concentrazione, i pannelli non
        # riapparirebbero.
        self.left_panel.set_visible(self.left_visible)
        self.right_panel.set_visible(self.right_visible)
        # EN: only move the dividers once the window really has a width. At
        #     startup this runs before the first allocation, and positioning an
        #     unallocated GtkPaned makes GTK complain that it is being asked to
        #     draw a part that has no size yet. Retry on the next idle turn
        #     instead of guessing; after a while, fall back to the saved width
        #     so a window that never gets allocated still opens usably.
        # IT: sposta i separatori solo quando la finestra ha davvero una
        #     larghezza. All'avvio questo metodo parte prima della prima
        #     allocazione, e posizionare un GtkPaned non ancora allocato fa
        #     protestare GTK, che si trova a disegnare una parte senza misure.
        #     Invece di indovinare si riprova al giro successivo; dopo un po'
        #     si ripiega sulla larghezza salvata, così una finestra che non
        #     venisse mai allocata si aprirebbe comunque in modo utilizzabile.
        allocated = self.paned_outer.get_allocated_width()
        if allocated <= 1:
            if _retries < 20:
                GLib.idle_add(self._apply_layout, _retries + 1)
                return False
            total = self._content_width()
        else:
            total = allocated
        if total <= 1:
            return False
        left_w, _centro, right_w = split_columns(
            total,
            self.settings.get("left_px"), self.settings.get("right_px"),
            self.left_visible, self.right_visible)

        self.paned_outer.set_position(left_w)
        inner_w = max(1, total - left_w)
        self.paned_inner.set_position(max(0, inner_w - right_w))
        # I margini di lettura dipendono dalla larghezza dell'AREA DI
        # SCRITTURA, che cambia proprio adesso: si ricalcolano al giro
        # successivo, quando GTK ha applicato le posizioni appena chieste.
        # Senza questo restavano quelli calcolati prima che i pannelli
        # togliessero spazio al centro, e il testo usciva incolonnato
        # stretto in mezzo a due margini enormi.
        GLib.idle_add(self._update_reading_margins)
        return False

    def _block_file_drops_on_editor(self):
        """Installa sull'area di scrittura un gestore di trascinamento: quando si
        rilascia uno o piu' file .txt/.md, ciascun file viene aggiunto come UN
        nuovo capitolo in fondo al progetto (un file = un capitolo). Il testo non
        viene inserito dentro il capitolo corrente, per non mescolare contenuti.

        (Il nome del metodo resta per compatibilita' con il punto di chiamata.)"""
        try:
            drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
            try:
                drop.set_gtypes([Gdk.FileList, Gio.File])
            except Exception:
                pass
            drop.connect("drop", self._on_editor_file_drop)
            self.text_view.add_controller(drop)
        except Exception:
            pass

    def _on_editor_file_drop(self, _target, value, _x, _y):
        """Gestisce il rilascio di file sull'area di scrittura importando ogni
        file di testo come nuovo capitolo. Restituisce True se ha gestito il
        rilascio. Rifiuta i tipi non-file (cosi' il testo trascinato non viene
        inserito alla rinfusa nel capitolo)."""
        files = []
        try:
            if isinstance(value, Gdk.FileList):
                files = list(value.get_files())
            elif isinstance(value, Gio.File):
                files = [value]
        except Exception:
            files = []
        if not files:
            return False
        paths = []
        for gf in files:
            try:
                p = gf.get_path()
            except Exception:
                p = None
            if p:
                paths.append(p)
        if not paths:
            return False
        added = self._import_files_as_chapters(paths)
        return bool(added)

    def _import_files_as_chapters(self, paths):
        """Importa una lista di file .txt/.md, ciascuno come nuovo capitolo in
        fondo al progetto. Salta i file non testuali. Restituisce il numero di
        capitoli aggiunti e seleziona l'ultimo importato."""
        self._commit_current()
        accepted = (".txt", ".md", ".markdown")
        added = 0
        last_ch = None
        skipped = []
        for path in paths:
            if not path.lower().endswith(accepted):
                skipped.append(os.path.basename(path))
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read()
            except Exception as exc:
                self._error(self.t("err_open", e=exc))
                continue
            title = os.path.splitext(os.path.basename(path))[0]
            last_ch = self.project.add_chapter_from_text(raw, title=title)
            added += 1
        if added and self.reflow_on_import:
            # la preferenza e' accesa: ricuci i capitoli appena importati
            self.project.rejoin_paragraphs()
        if added:
            # seleziona l'ultimo capitolo importato
            idx = self.project.chapters.index(last_ch) if last_ch else 0
            self._refresh_chapter_list(idx)
            self._mark_dirty()
            self._info(self.t("imported_n", n=added))
        if skipped:
            self._error(self.t("import_skipped", files=", ".join(skipped)))
        return added

    def _update_reading_margins(self, _tentativi=0):
        w = self.text_view.get_allocated_width()
        if w <= 1:
            # non ancora allocata: si riprova, invece di fissare un margine
            # su una misura che non esiste
            if _tentativi < 20:
                GLib.idle_add(self._update_reading_margins, _tentativi + 1)
            return False
        # limita la larghezza della colonna di scrittura per comodita' di lettura
        # e la centra quando l'area e' molto piu' larga del massimo di lettura
        if w > READING_MAX_PX + 40:
            side = int((w - READING_MAX_PX) / 2)
        else:
            side = 16
        if getattr(self, "_last_side", None) != side:
            self._last_side = side
            self.text_view.set_left_margin(side)
            self.text_view.set_right_margin(side)
        return False

    def on_divider_moved(self, _paned, _param):
        if self._restoring:
            return
        # Si registra solo quando la finestra ha una larghezza VERA. Prima
        # bastava _content_width(), che quando l'allocazione manca ripiega
        # sulla larghezza salvata: durante l'avvio venivano cosi' memorizzate
        # posizioni prese da una finestra che non esisteva ancora, e al
        # riavvio successivo le colonne ripartivano storte — un errore che si
        # ricopiava da solo di sessione in sessione.
        # I margini seguono comunque il divisore: e' l'unica cosa che
        # conta anche prima che la finestra abbia una larghezza definitiva.
        self._update_reading_margins()
        total = self.paned_outer.get_allocated_width()
        if total <= 1:
            return
        left_w = self.paned_outer.get_position()
        inner_pos = self.paned_inner.get_position()
        inner_w = max(1, total - left_w)
        right_w = max(0, inner_w - inner_pos)
        if self.left_visible and left_w > 0:
            self.settings["left_px"] = left_w
        if self.right_visible and right_w > 0:
            self.settings["right_px"] = right_w
        self._update_reading_margins()

    def _on_size_changed(self, *_):
        if not self._restoring:
            massimizzata = self.is_maximized()
            self.settings["win_maximized"] = bool(massimizzata)
            # Le dimensioni si registrano solo a finestra normale: quelle di
            # una massimizzata non sono una misura a cui tornare, sono lo
            # schermo.
            if not massimizzata:
                w = self.get_width()
                h = self.get_height()
                if w > 1:
                    self.settings["win_w"] = w
                if h > 1:
                    self.settings["win_h"] = h
        self._update_reading_margins()

    def _persist_layout(self):
        self.settings["left_visible"] = self.left_visible
        self.settings["right_visible"] = self.right_visible
        save_settings(self.settings)

    def on_toggle_left(self, *_):
        self.left_visible = not self.left_visible
        self._apply_layout()
        self._persist_layout()

    def on_toggle_right(self, *_):
        self.right_visible = not self.right_visible
        self._apply_layout()
        self._persist_layout()

    def _on_fullscreen_changed(self, *_):
        self._is_fullscreen = bool(self.is_fullscreen())
        self._sync_menu_chrome()

    def _sync_menu_chrome(self):
        """In finestra normale: barra dei menu visibile, pulsante ☰ nascosto.
        A schermo intero: barra dei menu nascosta (i suoi popover non si aprono
        in modo affidabile), pulsante ☰ visibile come via d'accesso ai menu."""
        full = bool(getattr(self, "_is_fullscreen", False))
        if getattr(self, "menubar_widget", None) is not None:
            self.menubar_widget.set_visible(not full)
        if getattr(self, "menu_button", None) is not None:
            self.menu_button.set_visible(full)

    def on_toggle_fullscreen(self, *_):
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()
        return True

    def on_quit(self, *_):
        self.close()
        return True

    # ---- azioni e scorciatoie ----------------------------------------------
    def _build_actions(self):
        simple = [
            ("new",          self.on_new,            ["<Control>n"]),
            ("open",         self.on_open,           ["<Control>o"]),
            ("save",         self.on_save,           ["<Control>s"]),
            ("import_chapters", self.on_import_chapters, ["<Control>i"]),
            ("sections",     self.on_edit_sections,  []),
            ("export_txt",   self.on_export,         []),
            ("export_md",    self.on_export_markdown, []),
            ("export_pdf",   self.on_export_pdf,     []),
            ("export_epub",  self.on_export_epub,    []),
            ("export_azw3",  self.on_export_azw3,    []),
            ("export_odt",   self.on_export_odt,     []),
            ("export_docx",  self.on_export_docx,    []),
            ("export_html",  self.on_export_html,    []),
            ("quit",         self.on_quit,           ["<Control>q"]),
            ("add",          self.on_add_chapter,    ["<Control><Shift>n"]),
            ("del",          self.on_delete_chapter, []),
            ("rename",       self.on_rename_chapter, ["F2"]),
            ("up",           self.on_move_up,        ["<Control><Shift>Up"]),
            ("down",         self.on_move_down,      ["<Control><Shift>Down"]),
            ("find",         self.on_find_replace,   ["<Control>f"]),
            # EN/IT: manual paragraph re-flow, and the view that shows where
            # the hard-wrapped paragraphs are.
            ("reflow",       self.on_reflow_paragraphs, []),
            ("choose_font",  self.on_choose_font,     []),
            # EN: attach an image (PNG/JPEG/WebP) into the current chapter
            # IT: allega un'immagine (PNG/JPEG/WebP) nel capitolo corrente
            ("insert_image", self.on_insert_image,   ["<Control><Shift>i"]),
            ("toggle_left",  self.on_toggle_left,    ["<Control>l"]),
            ("toggle_right", self.on_toggle_right,   ["<Control>r"]),
            ("fullscreen",   self.on_toggle_fullscreen, ["F11"]),
            ("font_inc",     self.on_font_increase,
             ["<Control>plus", "<Control>equal", "<Control>KP_Add"]),
            ("font_dec",     self.on_font_decrease,
             ["<Control>minus", "<Control>KP_Subtract"]),
            ("preview",      self.on_toggle_preview, ["<Control>e"]),
            ("preview_all",  self.on_toggle_preview_whole, ["<Control><Shift>e"]),
            ("goal",         self.on_set_goal,       []),
            ("about",        self.on_info,           ["F1"]),
            ("md_help",      self.on_md_help,        ["<Shift>F1"]),
        ]
        self._switch_actions = {}
        for name, handler, accels in simple:
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda a, p, h=handler: h())
            self.add_action(act)
            if accels:
                self.app.set_accels_for_action("win." + name, accels)

        # EN/IT: switches, not commands. A stateful boolean action makes GTK
        # draw a tick beside the entry, so the menu says whether the dark theme
        # is on instead of always reading the same. A plain action cannot: it
        # has no state to show.
        # Interruttori, non comandi. Un'azione booleana "con stato" fa
        # disegnare a GTK la spunta accanto alla voce, così il menu dice se il
        # tema scuro e' acceso invece di leggersi sempre uguale. Un'azione
        # semplice non puo': non ha uno stato da mostrare.
        for nome, attivo, gestore, accels in (
                ("dark", self.dark_mode, self.on_toggle_dark,
                 ["<Control><Shift>d"]),
                ("show_breaks", self.show_breaks, self.on_toggle_show_breaks,
                 ["<Control><Shift>b"])):
            act = Gio.SimpleAction.new_stateful(
                nome, None, GLib.Variant.new_boolean(bool(attivo)))
            act.connect("activate", lambda a, p, h=gestore: h())
            self.add_action(act)
            self.app.set_accels_for_action("win." + nome, accels)
            self._switch_actions[nome] = act

        lang_act = Gio.SimpleAction.new_stateful(
            "ui_lang", GLib.VariantType.new("s"), GLib.Variant("s", self.lang))
        lang_act.connect("activate", self._on_lang_action)
        self.add_action(lang_act)
        self._lang_action = lang_act

        # Famiglia di tema: azione "con stato", come la lingua, cosi' il menu
        # mostra il pallino accanto alla voce attiva.
        theme_act = Gio.SimpleAction.new_stateful(
            "theme_family", GLib.VariantType.new("s"),
            GLib.Variant("s", self.theme_family))
        theme_act.connect("activate", self._on_theme_family_action)
        self.add_action(theme_act)
        self._theme_action = theme_act

        # Ricucitura automatica: azione booleana, cosi' il menu mostra la
        # spunta e si vede a colpo d'occhio se e' attiva.
        reflow_act = Gio.SimpleAction.new_stateful(
            "reflow_auto", None,
            GLib.Variant.new_boolean(self.reflow_on_import))
        reflow_act.connect("activate", self._on_reflow_auto_action)
        self.add_action(reflow_act)
        self._reflow_action = reflow_act

    def _on_reflow_auto_action(self, action, _param):
        self.reflow_on_import = not self.reflow_on_import
        action.set_state(GLib.Variant.new_boolean(self.reflow_on_import))
        self.settings["reflow_on_import"] = self.reflow_on_import
        save_settings(self.settings)
        self._info(self.t("reflow_auto_on") if self.reflow_on_import
                   else self.t("reflow_auto_off"))

    def _on_lang_action(self, action, param):
        code = param.get_string()
        action.set_state(param)
        self.on_ui_lang_changed(code)

    def _on_theme_family_action(self, action, param):
        code = param.get_string()
        action.set_state(param)
        self.on_theme_family(code)

    def _build_menu_model(self):
        menubar = Gio.Menu()
        m_file = Gio.Menu()
        m_file.append(self.t("mi_new"), "win.new")
        m_file.append(self.t("mi_open"), "win.open")
        m_file.append(self.t("mi_import_chapters"), "win.import_chapters")
        m_file.append(self.t("mi_save"), "win.save")
        m_file.append(self.t("mi_sections"), "win.sections")
        m_export = Gio.Menu()
        m_export.append(self.t("mi_export_txt"), "win.export_txt")
        m_export.append(self.t("mi_export_md"), "win.export_md")
        m_export.append(self.t("mi_export_pdf"), "win.export_pdf")
        m_export.append(self.t("mi_export_epub"), "win.export_epub")
        m_export.append(self.t("mi_export_azw3"), "win.export_azw3")
        m_export.append(self.t("mi_export_odt"), "win.export_odt")
        m_export.append(self.t("mi_export_docx"), "win.export_docx")
        m_export.append(self.t("mi_export_html"), "win.export_html")
        m_file.append_submenu(self.t("mi_export_sub"), m_export)
        sec = Gio.Menu()
        sec.append(self.t("mi_quit"), "win.quit")
        m_file.append_section(None, sec)
        menubar.append_submenu(self.t("menu_file"), m_file)

        m_edit = Gio.Menu()
        s1 = Gio.Menu()
        s1.append(self.t("mi_add"), "win.add")
        s1.append(self.t("mi_del"), "win.del")
        s1.append(self.t("mi_rename"), "win.rename")
        m_edit.append_section(None, s1)
        s2 = Gio.Menu()
        s2.append(self.t("mi_up"), "win.up")
        s2.append(self.t("mi_down"), "win.down")
        m_edit.append_section(None, s2)
        s3 = Gio.Menu()
        s3.append(self.t("mi_find"), "win.find")
        s3.append(self._t_or("mi_reflow", "Ricuci i paragrafi"), "win.reflow")
        s3.append(self._t_or("mi_reflow_auto",
                             "Ricuci automaticamente i testi importati"),
                  "win.reflow_auto")
        m_edit.append_section(None, s3)
        s4 = Gio.Menu()
        s4.append(self.t("mi_insert_image"), "win.insert_image")
        m_edit.append_section(None, s4)
        menubar.append_submenu(self.t("menu_edit"), m_edit)

        m_view = Gio.Menu()
        v1 = Gio.Menu()
        v1.append(self.t("mi_toggle_left"), "win.toggle_left")
        v1.append(self.t("mi_toggle_right"), "win.toggle_right")
        m_view.append_section(None, v1)
        v2 = Gio.Menu()
        v2.append(self.t("mi_fullscreen"), "win.fullscreen")
        m_view.append_section(None, v2)
        v3 = Gio.Menu()
        v3.append(self.t("mi_font_inc"), "win.font_inc")
        v3.append(self.t("mi_font_dec"), "win.font_dec")
        m_view.append_section(None, v3)
        v4 = Gio.Menu()
        v4.append(self.t("mi_preview"), "win.preview")
        v4.append(self.t("mi_preview_all"), "win.preview_all")
        v4.append(self._t_or("mi_show_breaks", "Mostra le interruzioni"),
                  "win.show_breaks")
        v4.append(self.t("mi_dark"), "win.dark")
        # Sottomenu tema: sceglie la FAMIGLIA di colori (prugna RuscaLinux o
        # Standard ispirato a Scrivener). Il chiaro/scuro resta la voce sopra:
        # le due scelte sono indipendenti e si combinano.
        m_theme = Gio.Menu()
        for code in pw_model.THEMES:
            item = Gio.MenuItem.new(self.theme_label(code), None)
            item.set_action_and_target_value(
                "win.theme_family", GLib.Variant("s", code))
            m_theme.append_item(item)
        v4.append_submenu(self._t_or("mi_theme", "Tema"), m_theme)
        v4.append(self._t_or("mi_font", "Caratteri…"), "win.choose_font")
        v4.append(self.t("mi_goal"), "win.goal")
        m_view.append_section(None, v4)
        # Sottomenu lingua: prima le lingue tradotte per intero, poi (in una
        # sezione separata) quelle non ancora tradotte, marcate con un suffisso,
        # cosi' e' chiaro che l'interfaccia restera' in inglese (ripiego).
        m_lang = Gio.Menu()
        complete_sec = Gio.Menu()
        partial_sec = Gio.Menu()
        # EN: for a language whose interface is not translated yet, say what
        #     the choice DOES rather than only what it lacks: the interface
        #     stays in English, but the PDF hyphenation dictionary follows the
        #     language — which in a book-making program is not a detail.
        #     Only 15 of the 33 have a dictionary, so the entry is checked one
        #     by one instead of promising the same to everybody.
        # IT: per una lingua la cui interfaccia non e' ancora tradotta, dire
        #     cosa la scelta FA invece che solo cosa le manca: l'interfaccia
        #     resta in inglese, ma il dizionario di sillabazione del PDF segue
        #     la lingua — e in un programma da libri non e' un dettaglio.
        #     Solo 15 delle 33 hanno un dizionario, quindi la voce si controlla
        #     una per una invece di promettere a tutte la stessa cosa.
        solo_inglese = self._t_or("lang_english_ui", "interfaccia in inglese")
        con_sillabazione = self._t_or(
            "lang_english_ui_hyph",
            "interfaccia in inglese, sillabazione disponibile")
        for code, native in available_languages():
            if code in COMPLETE_LANGUAGES:
                item = Gio.MenuItem.new(native, None)
                item.set_action_and_target_value(
                    "win.ui_lang", GLib.Variant("s", code))
                complete_sec.append_item(item)
            else:
                nota = (con_sillabazione if hyphenation_available(code)
                        else solo_inglese)
                label = f"{native} — {nota}"
                item = Gio.MenuItem.new(label, None)
                item.set_action_and_target_value(
                    "win.ui_lang", GLib.Variant("s", code))
                partial_sec.append_item(item)
        m_lang.append_section(None, complete_sec)
        m_lang.append_section(self.t("lang_partial_header"), partial_sec)
        m_view.append_submenu(self.t("mi_language"), m_lang)
        menubar.append_submenu(self.t("menu_view"), m_view)

        m_help = Gio.Menu()
        m_help.append(self._t_or("mi_md_help", "Guida ai comandi Markdown"),
                      "win.md_help")
        m_help.append(self.t("mi_about"), "win.about")
        menubar.append_submenu(self.t("menu_help"), m_help)
        return menubar

    def _rebuild_menubar(self):
        self.menubar_widget.set_menu_model(self._build_menu_model())
        # aggiorna anche il menu del pulsante hamburger (stesso modello)
        if getattr(self, "menu_popover", None) is not None:
            self.menu_popover.set_menu_model(self._build_menu_model())
        if getattr(self, "menu_button", None) is not None:
            self.menu_button.set_tooltip_text(self.t("menu_button_tip"))

    # ---- interfaccia --------------------------------------------------------
    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.add_css_class("rusca-bg")
        self.set_child(root)

        tex = load_texture(64)
        self._icon_texture = tex

        self.menubar_widget = Gtk.PopoverMenuBar.new_from_model(
            self._build_menu_model())
        self.menubar_widget.add_css_class("rusca-menubar")
        root.append(self.menubar_widget)

        topbar = Gtk.CenterBox()
        topbar.add_css_class("rusca-header")
        topbar.add_css_class("rusca-toolbar")
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        if tex is not None:
            img = Gtk.Image.new_from_paintable(tex)
            img.set_pixel_size(28)
            left_box.append(img)
        self.title_label = Gtk.Label(label="")
        self.title_label.add_css_class("column-title")
        left_box.append(self.title_label)
        topbar.set_start_widget(left_box)

        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        # Pulsante "hamburger" (☰) con lo STESSO modello di menu della menubar.
        # Serve come via d'accesso affidabile alle voci di menu anche a schermo
        # intero, dove il popover della PopoverMenuBar puo' non aprirsi su alcuni
        # window manager. Riusa _build_menu_model(), quindi niente duplicazioni.
        self.menu_button = Gtk.MenuButton()
        # "open-menu-symbolic" è un'icona standard presente in tutti i temi
        # icone GTK; mostra il classico glifo ☰.
        self.menu_button.set_icon_name("open-menu-symbolic")
        self.menu_button.add_css_class("rusca-menubtn")
        self.menu_button.set_tooltip_text(self.t("menu_button_tip"))
        self.menu_popover = Gtk.PopoverMenu.new_from_model(
            self._build_menu_model())
        self.menu_button.set_popover(self.menu_popover)
        # In finestra normale si usa la barra dei menu in alto, quindi il
        # pulsante ☰ resta nascosto: comparirà solo a schermo intero (dove la
        # barra dei menu non riesce ad aprire i popover). Vedi _sync_menu_chrome.
        self.menu_button.set_visible(False)
        right_box.append(self.menu_button)
        self.font_label = Gtk.Label()
        self.font_label.add_css_class("rusca-fontlabel")
        right_box.append(self.font_label)
        adj = Gtk.Adjustment(value=self.font_size, lower=MIN_FONT_SIZE,
                             upper=MAX_FONT_SIZE, step_increment=1, page_increment=2)
        self.font_size_spin = Gtk.SpinButton()
        self.font_size_spin.set_adjustment(adj)
        self.font_size_spin.set_numeric(True)
        self.font_size_spin.connect("value-changed", self.on_font_size_changed)
        self.font_size_spin.set_tooltip_text(self.t("tip_font_size"))
        right_box.append(self.font_size_spin)
        self.spell_combo = Gtk.ComboBoxText()
        self._populate_spell_combo()
        self.spell_combo.connect("changed", self.on_spell_lang_changed)
        self.spell_combo.set_tooltip_text(self.t("tip_spell_lang"))
        right_box.append(self.spell_combo)
        topbar.set_end_widget(right_box)
        root.append(topbar)

        paned_outer = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned_inner = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned_outer.set_vexpand(True)
        paned_outer.set_hexpand(True)
        root.append(paned_outer)

        # colonna sinistra
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.lbl_left = Gtk.Label(label="", xalign=0)
        self.lbl_left.add_css_class("column-title")
        left.append(self.lbl_left)

        self.list_store = Gtk.StringList()
        self.list_selection = Gtk.SingleSelection(model=self.list_store)
        self.list_selection.set_autoselect(False)
        self.list_selection.set_can_unselect(True)
        self.list_selection.connect("selection-changed", self.on_select_chapter)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._chapter_item_setup)
        factory.connect("bind", self._chapter_item_bind)
        self.tree = Gtk.ListView(model=self.list_selection, factory=factory)
        self.tree.add_css_class("chapter-list")
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("pressed", self.on_list_click)
        self.tree.add_controller(click)
        sw_left = Gtk.ScrolledWindow()
        sw_left.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw_left.set_vexpand(True)
        sw_left.set_child(self.tree)
        left.append(sw_left)

        movebar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2,
                          homogeneous=True)
        movebar.add_css_class("rusca-toolbar")
        self.btn_up = Gtk.Button()
        self.btn_down = Gtk.Button()
        self.btn_up.connect("clicked", self.on_move_up)
        self.btn_down.connect("clicked", self.on_move_down)
        movebar.append(self.btn_up)
        movebar.append(self.btn_down)
        left.append(movebar)

        # colonna centrale
        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._center_box = center
        self._find_bar = None
        self.center_title = Gtk.Label(label="Testo", xalign=0)
        self.center_title.add_css_class("column-title")
        center.append(self.center_title)

        # Area di scrittura. libspelling (Spelling.TextBufferAdapter) richiede
        # un GtkSource.Buffer, non un Gtk.TextBuffer normale: quindi, se
        # GtkSourceView 5 e' disponibile, costruiamo un GtkSource.View con il
        # suo GtkSource.Buffer (entrambi sottoclassi di Gtk.TextView/TextBuffer,
        # percio' tutto il resto del codice resta invariato). Disattiviamo
        # l'evidenziazione di sintassi di GtkSourceView per non interferire con
        # i nostri tag markdown. Se GtkSourceView manca, ripieghiamo su un
        # normale Gtk.TextView (e il controllo ortografico restera' inattivo).
        if GtkSource is not None:
            self.text_buffer = GtkSource.Buffer()
            try:
                self.text_buffer.set_highlight_syntax(False)
                self.text_buffer.set_highlight_matching_brackets(False)
            except Exception:
                pass
            self.text_view = GtkSource.View.new_with_buffer(self.text_buffer)
        else:
            self.text_view = Gtk.TextView()
            self.text_buffer = self.text_view.get_buffer()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.add_css_class("text-editor")
        self.text_view.set_top_margin(16)
        self.text_view.set_bottom_margin(16)
        pal = self.palette()
        head_color = pal["head"]
        self._md_tags = {
            "h1": self.text_buffer.create_tag("h1", weight=Pango.Weight.BOLD,
                                              scale=1.6, foreground=head_color),
            "h2": self.text_buffer.create_tag("h2", weight=Pango.Weight.BOLD,
                                              scale=1.35, foreground=head_color),
            "h3": self.text_buffer.create_tag("h3", weight=Pango.Weight.BOLD,
                                              scale=1.18, foreground=head_color),
            "bold": self.text_buffer.create_tag("bold", weight=Pango.Weight.BOLD),
            "italic": self.text_buffer.create_tag("italic", style=Pango.Style.ITALIC),
            "bolditalic": self.text_buffer.create_tag(
                "bolditalic", weight=Pango.Weight.BOLD, style=Pango.Style.ITALIC),
            "code": self.text_buffer.create_tag(
                "code", family="monospace", foreground=pal["code"]),
            "marker": self.text_buffer.create_tag("marker",
                                                  foreground=pal["marker"]),
            # Tinge le righe che il comando "Ricuci i paragrafi" unirebbe.
            # paragraph-background colora la riga per tutta la sua larghezza,
            # cosi' la spezzatura si vede anche dove il testo finisce prima.
            "wrapmark": self.text_buffer.create_tag(
                "wrapmark", paragraph_background=pal["wrapmark"]),
        }
        self.text_buffer.connect("changed", self.on_text_changed)
        self._block_file_drops_on_editor()
        self._autocap_busy = False
        self.text_buffer.connect("insert-text", self.on_insert_autocap)
        sw_center = Gtk.ScrolledWindow()
        sw_center.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw_center.set_vexpand(True)
        sw_center.set_child(self.text_view)
        self._sw_center = sw_center

        self.preview_view = Gtk.TextView()
        self.preview_view.set_editable(False)
        self.preview_view.set_cursor_visible(False)
        self.preview_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.preview_view.set_left_margin(24)
        self.preview_view.set_right_margin(24)
        self.preview_view.set_top_margin(12)
        self.preview_view.add_css_class("text-editor")
        self.preview_buffer = self.preview_view.get_buffer()
        head_color = self.palette()["head"]
        self._pv_tags = {
            "h1": self.preview_buffer.create_tag("h1", weight=Pango.Weight.BOLD,
                                                 scale=1.7, foreground=head_color),
            "h2": self.preview_buffer.create_tag("h2", weight=Pango.Weight.BOLD,
                                                 scale=1.4, foreground=head_color),
            "h3": self.preview_buffer.create_tag("h3", weight=Pango.Weight.BOLD,
                                                 scale=1.2, foreground=head_color),
            "bold": self.preview_buffer.create_tag("bold", weight=Pango.Weight.BOLD),
            "italic": self.preview_buffer.create_tag("italic", style=Pango.Style.ITALIC),
            "bolditalic": self.preview_buffer.create_tag(
                "bolditalic", weight=Pango.Weight.BOLD, style=Pango.Style.ITALIC),
            "code": self.preview_buffer.create_tag("code", family="monospace"),
            "quote": self.preview_buffer.create_tag(
                "quote", style=Pango.Style.ITALIC, left_margin=40, foreground=head_color),
            "sep": self.preview_buffer.create_tag(
                "sep", justification=Gtk.Justification.CENTER, foreground=head_color),
        }
        sw_preview = Gtk.ScrolledWindow()
        sw_preview.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw_preview.set_vexpand(True)
        sw_preview.set_child(self.preview_view)

        self.center_stack = Gtk.Stack()
        self.center_stack.add_named(sw_center, "editor")
        self.center_stack.add_named(sw_preview, "preview")
        self.center_stack.set_visible_child_name("editor")
        self.center_stack.set_vexpand(True)
        self._preview_mode = False
        center.append(self.center_stack)

        # colonna destra
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.lbl_right = Gtk.Label(label="", xalign=0)
        self.lbl_right.add_css_class("column-title")
        right.append(self.lbl_right)
        self.note_view = Gtk.TextView()
        self.note_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.note_view.add_css_class("notes-editor")
        self.note_buffer = self.note_view.get_buffer()
        self.note_buffer.connect("changed", self.on_note_changed)
        sw_right = Gtk.ScrolledWindow()
        sw_right.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw_right.set_vexpand(True)
        sw_right.set_child(self.note_view)
        right.append(sw_right)

        self.paned_outer = paned_outer
        self.paned_inner = paned_inner
        self.left_panel = left
        self.right_panel = right

        paned_inner.set_start_child(center)
        paned_inner.set_resize_start_child(True)
        paned_inner.set_shrink_start_child(False)
        paned_inner.set_end_child(right)
        paned_inner.set_resize_end_child(False)
        paned_inner.set_shrink_end_child(False)
        paned_outer.set_start_child(left)
        paned_outer.set_resize_start_child(False)
        paned_outer.set_shrink_start_child(False)
        paned_outer.set_end_child(paned_inner)
        paned_outer.set_resize_end_child(True)
        paned_outer.set_shrink_end_child(False)
        paned_outer.connect("notify::position", self.on_divider_moved)
        paned_inner.connect("notify::position", self.on_divider_moved)

        statusbar = Gtk.CenterBox()
        statusbar.add_css_class("rusca-statusbar")
        self.wordcount_label = Gtk.Label(label="Parole: 0", xalign=0)
        self.wordcount_label.add_css_class("statusbar-label")
        statusbar.set_start_widget(self.wordcount_label)
        self.detail_label = Gtk.Label(label="", xalign=0.5)
        self.detail_label.add_css_class("statusbar-label")
        statusbar.set_center_widget(self.detail_label)
        self.totalcount_label = Gtk.Label(label="Totale progetto: 0", xalign=1)
        self.totalcount_label.add_css_class("statusbar-label")
        statusbar.set_end_widget(self.totalcount_label)
        root.append(statusbar)

        # stato iniziale corretto di barra menu / pulsante hamburger
        self._sync_menu_chrome()
        GLib.idle_add(self._update_reading_margins)

    def _chapter_item_setup(self, factory, list_item):
        label = Gtk.Label(xalign=0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.add_css_class("chapter-list")
        list_item.set_child(label)

    def _chapter_item_bind(self, factory, list_item):
        label = list_item.get_child()
        item = list_item.get_item()
        label.set_text(item.get_string())

    def _update_tag_colors(self):
        """Riallinea i colori del testo Markdown alla tavolozza corrente.
        Chiamata a ogni cambio di famiglia di tema e di chiaro/scuro."""
        pal = self.palette()
        head_color = pal["head"]
        for name in ("h1", "h2", "h3"):
            try:
                self._md_tags[name].set_property("foreground", head_color)
                self._pv_tags[name].set_property("foreground", head_color)
            except Exception:
                pass
        try:
            self._md_tags["code"].set_property("foreground", pal["code"])
            self._md_tags["marker"].set_property("foreground", pal["marker"])
            self._md_tags["wrapmark"].set_property("paragraph-background",
                                                  pal["wrapmark"])
            self._pv_tags["quote"].set_property("foreground", head_color)
            self._pv_tags["sep"].set_property("foreground", head_color)
        except Exception:
            pass

    @staticmethod
    def _count_words(text):
        return len(text.split())

    @staticmethod
    def _count_chars(text):
        return sum(len(line) for line in text.splitlines())

    def _update_wordcount(self):
        if self.current is not None and not self.current.is_cover:
            chapter_words = self._count_words(self.current.text)
        else:
            chapter_words = 0
        total = sum(self._count_words(c.text)
                    for c in self.project.chapters if not c.is_cover)
        total_chars = sum(self._count_chars(c.text)
                          for c in self.project.chapters if not c.is_cover)
        self.wordcount_label.set_text(self.t("wc_chapter", n=chapter_words))
        self.totalcount_label.set_text(self.t("wc_total", n=total))
        pages = max(1, round(total / 250)) if total else 0
        detail = (self.t("wc_chars", n=total_chars) + "    "
                  + self.t("wc_pages", n=pages))
        if getattr(self, "word_goal", 0) > 0:
            pct = min(100, round(total * 100 / self.word_goal))
            detail += "    " + self.t("goal_status",
                                      c=total, g=self.word_goal, p=pct)
        self.detail_label.set_text(detail)

    def _chapter_title(self, ch):
        return ch.title_with_fallback(self.t("chapter_n"), self.t("cover_label"))

    def on_ui_lang_changed(self, code):
        if code == self.lang:
            return
        self.lang = code
        self.translator.set_language(code)
        self.project._lang = code
        self.settings["ui_lang"] = code
        save_settings(self.settings)
        self._retranslate()
        self._refresh_chapter_list(max(0, self._current_index()))
        if hasattr(self, "spell_combo"):
            self._populate_spell_combo()

    def _apply_text_direction(self):
        """Orienta le aree di scrittura secondo la lingua dell'interfaccia.

        Arabo, urdu, persiano ed ebraico si scrivono da destra a sinistra.
        RTL_LANGUAGES lo dichiarava gia', ma nessuno lo leggeva: si potevano
        scegliere quelle quattro lingue e ritrovarsi il cursore a sinistra e il
        testo che partiva dal lato sbagliato.

        NB: questo orienta l'AREA DI SCRITTURA. L'impaginatore PDF compone
        ancora da sinistra a destra: per quelle lingue l'export non e' ancora
        corretto, ed e' un lavoro a se'."""
        verso = (Gtk.TextDirection.RTL if self.lang in RTL_LANGUAGES
                 else Gtk.TextDirection.LTR)
        for widget in (getattr(self, "text_view", None),
                       getattr(self, "note_view", None),
                       getattr(self, "preview_view", None)):
            if widget is not None:
                try:
                    widget.set_direction(verso)
                except Exception:
                    pass   # l'orientamento non deve mai impedire di scrivere

    def _retranslate(self):
        self._apply_text_direction()
        self._rebuild_menubar()
        try:
            self._lang_action.set_state(GLib.Variant("s", self.lang))
        except Exception:
            pass
        self.btn_up.set_label(self.t("btn_up"))
        self.btn_down.set_label(self.t("btn_down"))
        self.font_label.set_text(self.t("font_label"))
        self.font_size_spin.set_tooltip_text(self.t("tip_font_size"))
        self.spell_combo.set_tooltip_text(self.t("tip_spell_lang"))
        self.lbl_left.set_text(self.t("col_chapters"))
        self.lbl_right.set_text(self.t("col_notes"))
        if self.current is not None:
            self.center_title.set_text(self._chapter_title(self.current))
        else:
            self.center_title.set_text(self.t("col_text"))
        self._update_wordcount()

    # ---- modello visuale ---------------------------------------------------
    def _cover_offset(self):
        """1 se il primo capitolo e' la copertina (nascosta dalla lista), 0 se no.
        La copertina resta nel progetto ma non compare piu' come voce di lista:
        il suo contenuto ora viene dai campi del frontespizio."""
        chs = self.project.chapters
        return 1 if (chs and chs[0].is_cover) else 0

    def _row_to_index(self, row):
        """Riga visibile della lista -> indice reale in project.chapters."""
        return row + self._cover_offset()

    def _index_to_row(self, index):
        """Indice in project.chapters -> riga visibile (>=0)."""
        return max(0, index - self._cover_offset())

    def _refresh_chapter_list(self, select_index=0):
        # select_index e' un INDICE in project.chapters (come passato dai chiamanti)
        self._loading = True
        n = self.list_store.get_n_items()
        if n:
            self.list_store.splice(0, n, [])
        off = self._cover_offset()
        for ch in self.project.chapters[off:]:   # salta la copertina
            self.list_store.append(self._chapter_title(ch))
        self._loading = False
        if self.list_store.get_n_items():
            self._set_editing_enabled(True)
            self._select_row(self._index_to_row(select_index))
        else:
            # nessun capitolo: stato neutro, aree di testo vuote e non
            # modificabili finche' l'utente non crea un capitolo
            self._show_empty_state()
        self.title_label.set_text(self.project.title)
        self._update_wordcount()
        self._update_window_title()

    def _show_empty_state(self):
        """Progetto senza capitoli: svuota i buffer, disabilita la scrittura e
        mostra un suggerimento al centro. Evita che il testo digitato finisca
        nel nulla (current e' None) o che restino i contenuti del progetto
        precedente."""
        self.current = None
        self._loading = True
        self.text_buffer.set_text("")
        self.note_buffer.set_text("")
        self._loading = False
        # La scia del menu ("Capitolo -> Aggiungi capitolo") non e' scritta a
        # mano nella frase: arriva dalle voci di menu vere. Cosi' se un giorno
        # una voce cambia nome, o viene tradotta, il suggerimento la segue e
        # non puo' piu' indicare un comando che non esiste.
        self.center_title.set_text(self.t("empty_hint",
                                          menu=self.t("menu_edit"),
                                          item=self.t("mi_add")))
        self._set_editing_enabled(False)

    def _set_editing_enabled(self, enabled):
        self.text_view.set_editable(enabled)
        self.text_view.set_cursor_visible(enabled)
        self.note_view.set_editable(enabled)
        self.note_view.set_cursor_visible(enabled)

    def _select_row(self, row):
        if 0 <= row < self.list_store.get_n_items():
            self.list_selection.set_selected(row)
            self._load_row(row)

    def _commit_current(self):
        if self.current is None:
            return
        s, e = self.text_buffer.get_bounds()
        self.current.text = self.text_buffer.get_text(s, e, True)
        s, e = self.note_buffer.get_bounds()
        self.current.note = self.note_buffer.get_text(s, e, True)

    def on_list_click(self, gesture, n_press, x, y):
        if n_press != 1:
            return
        row_index = self._row_at_y(y)
        if row_index is None:
            return
        if self.list_selection.get_selected() == row_index:
            self._commit_current()
            self.current = None
            self.list_selection.unselect_all()
            self._loading = True
            self.text_buffer.set_text("")
            self.note_buffer.set_text("")
            self.center_title.set_text(self.t("col_text"))
            self._loading = False
            self._update_wordcount()
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _row_at_y(self, y):
        n = self.list_store.get_n_items()
        if n == 0:
            return None
        child = self.tree.get_first_child()
        row_h = 0
        while child is not None:
            h = child.get_allocated_height()
            if h > 0:
                row_h = h
                break
            child = child.get_next_sibling()
        if row_h <= 0:
            return None
        idx = int(y // row_h)
        if 0 <= idx < n:
            return idx
        return None

    # firma imposta dal segnale "selection-changed": i tre parametri
    # arrivano da GTK e non servono, la selezione si rilegge dal modello
    def on_select_chapter(self, _selection=None, _position=None,
                          _n_items=None):
        if self._loading:
            return
        sel = self.list_selection.get_selected()
        if sel == Gtk.INVALID_LIST_POSITION:
            self._commit_current()
            self.current = None
            self._loading = True
            self.text_buffer.set_text("")
            self.note_buffer.set_text("")
            self.center_title.set_text(self.t("col_text"))
            self._loading = False
            self._update_wordcount()
            return
        self._load_row(sel)

    def _load_row(self, row):
        index = self._row_to_index(row)
        if not (0 <= index < len(self.project.chapters)):
            return
        if self.current is self.project.chapters[index]:
            return
        self._commit_current()
        self.current = self.project.chapters[index]
        self._loading = True
        self.text_buffer.set_text(self.current.text)
        self.note_buffer.set_text(self.current.note)
        self.center_title.set_text(self._chapter_title(self.current))
        self._loading = False
        self._highlight_markdown()
        self._update_wordcount()
        if getattr(self, "_preview_mode", False):
            self._render_preview()

    def on_insert_autocap(self, buf, location, text, length):
        if self._loading or self._autocap_busy:
            return
        if length != 1 or not text.isalpha() or not text.islower():
            return
        it_prev = location.copy()
        if not it_prev.backward_char():
            self._do_autocap(buf, location, text)
            return
        prev = it_prev.get_char()
        if prev not in (" ", "\n", "\t"):
            return
        scan = it_prev.copy()
        ch = prev
        while ch in (" ", "\t"):
            if not scan.backward_char():
                self._do_autocap(buf, location, text)
                return
            ch = scan.get_char()
        if ch in (".", "!", "?", "\n"):
            self._do_autocap(buf, location, text)

    def _do_autocap(self, buf, location, text):
        self._autocap_busy = True
        buf.stop_emission_by_name("insert-text")
        buf.insert(location, text.upper(), -1)
        self._autocap_busy = False

    def on_text_changed(self, buf):
        if self._loading or self.current is None:
            return
        s, e = buf.get_bounds()
        self.current.text = buf.get_text(s, e, True)
        self._mark_dirty()
        row = self._current_row()
        if row >= 0:
            title = self._chapter_title(self.current)
            if self.list_store.get_string(row) != title:
                self._loading = True
                self.list_store.splice(row, 1, [title])
                self.list_selection.set_selected(row)
                self._loading = False
            self.center_title.set_text(title)
        self._highlight_markdown()
        self._update_wordcount()

    def _highlight_markdown(self):
        """Colora il Markdown mentre si scrive. Usa le stesse regole degli
        export (model.classify_md_line / model.inline_spans): ciò che qui
        appare in grassetto uscirà in grassetto anche nel PDF."""
        buf = self.text_buffer
        start, end = buf.get_bounds()
        for tag in self._md_tags.values():
            buf.remove_tag(tag, start, end)
        text = buf.get_text(start, end, True)

        def apply(tag_name, a, b):
            tag = self._md_tags.get(tag_name)
            if tag is None:
                return
            buf.apply_tag(tag, buf.get_iter_at_offset(a),
                          buf.get_iter_at_offset(b))

        lines = text.split("\n")
        offset = 0
        starts = []
        for line in lines:
            starts.append(offset)
            kind, _body, extra = classify_md_line(line)
            if kind == "heading":
                apply(f"h{min(3, extra)}", offset, offset + len(line))
            else:
                for a, b, style in inline_spans(line):
                    apply(style, offset + a, offset + b)
            offset += len(line) + 1

        # Vista "Mostra le interruzioni": tinge i gruppi di righe che il
        # comando di ricucitura unirebbe. Sono decisi da model.wrapped_runs,
        # la stessa funzione che poi esegue l'unione: cio' che si vede
        # evidenziato e' esattamente cio' che verrebbe toccato.
        if getattr(self, "show_breaks", False):
            for first, last in wrapped_runs(text):
                apply("wrapmark", starts[first],
                      starts[last] + len(lines[last]))

    def on_note_changed(self, buf):
        if self._loading or self.current is None:
            return
        s, e = buf.get_bounds()
        self.current.note = buf.get_text(s, e, True)
        self._mark_dirty()

    # ---- helper dialoghi asincroni -----------------------------------------
    def _dialog_shell(self, title, size=None, spacing=12, margin=20):
        """Costruisce la finestra di dialogo e il suo contenitore.

        Tutti i dialoghi dell'applicazione — messaggi, conferme, sezioni
        editoriali, informazioni, guida, formato pagina, avvio — hanno lo
        stesso involucro: finestra modale figlia della principale, classe
        "rusca-dialog" per il tema, contenitore verticale con la classe di
        sfondo e margini uguali sui quattro lati. Sta scritto qui una volta,
        così i margini restano coerenti fra un dialogo e l'altro.

        Restituisce (finestra, contenitore): il chiamante riempie il
        contenitore e chiude con _dialog_present()."""
        dialog = Gtk.Window(transient_for=self, modal=True)
        dialog.add_css_class("rusca-dialog")
        dialog.set_title(title or "")
        if size is None:
            dialog.set_resizable(False)
        else:
            dialog.set_default_size(*size)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        box.set_margin_top(margin); box.set_margin_bottom(margin)
        box.set_margin_start(margin); box.set_margin_end(margin)
        box.add_css_class("rusca-bg")
        return dialog, box

    def _ok_cancel_row(self, box, on_ok, on_cancel=None):
        """Aggiunge in fondo al dialogo la coppia Annulla / OK.

        Tre dialoghi la ripetevano identica: stessa spaziatura, stesso
        allineamento a destra, stessa classe sul pulsante principale. Sta qui
        una volta, così restano uguali fra loro anche in futuro.

        Restituisce il pulsante OK, che il chiamante passa a
        _dialog_present() come predefinito."""
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                       halign=Gtk.Align.END)
        b_cancel = Gtk.Button(label=self.t("cancel"))
        b_ok = Gtk.Button(label=self.t("ok"))
        b_ok.add_css_class("suggested-action")
        btns.append(b_cancel)
        btns.append(b_ok)
        box.append(btns)
        b_cancel.connect("clicked", on_cancel or (lambda *_a: None))
        b_ok.connect("clicked", on_ok)
        return b_ok

    def _dialog_present(self, dialog, box, default_widget=None):
        """Aggancia il contenitore, mostra il dialogo e gli da' il fuoco.
        Chiusura speculare di _dialog_shell(): stessi tre passi ovunque."""
        dialog.set_child(box)
        if default_widget is not None:
            dialog.set_default_widget(default_widget)
        dialog.present()
        GLib.idle_add(self._raise_dialog, dialog)
        if default_widget is not None:
            default_widget.grab_focus()

    def _message_dialog(self, title, body):
        """Mostra un messaggio in una finestra con il nostro tema (leggibile sia
        in chiaro sia in scuro). Sostituisce Gtk.AlertDialog, il cui testo del
        messaggio non e' raggiunto dal nostro CSS e nel tema scuro risulta poco
        leggibile."""
        dialog, box = self._dialog_shell(title, margin=18)
        if title:
            head = Gtk.Label()
            head.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
            head.add_css_class("rusca-dialog-text")
            head.set_xalign(0.5)
            box.append(head)
        lbl = Gtk.Label(label=str(body))
        lbl.add_css_class("rusca-dialog-text")
        lbl.set_wrap(True)
        lbl.set_justify(Gtk.Justification.CENTER)
        lbl.set_xalign(0.5)
        lbl.set_max_width_chars(48)
        box.append(lbl)
        btn = Gtk.Button(label=self.t("ok"))
        btn.add_css_class("suggested-action")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda *_: dialog.destroy())
        box.append(btn)
        self._dialog_present(dialog, box, btn)

    def _info(self, msg):
        self._message_dialog(None, msg)

    def _error(self, msg):
        self._message_dialog(self.t("error_title"), msg)

    def _ask_text(self, title, prompt, initial, on_ok):
        dialog, box = self._dialog_shell(title, size=(360, -1),
                                         spacing=8, margin=12)
        prompt_lbl = Gtk.Label(label=prompt, xalign=0)
        prompt_lbl.add_css_class("rusca-dialog-text")
        box.append(prompt_lbl)
        entry = Gtk.Entry()
        entry.set_text(initial or "")
        entry.set_activates_default(True)
        box.append(entry)
        def confirm(*_):
            text = entry.get_text()
            dialog.destroy()
            on_ok(text)

        b_ok = self._ok_cancel_row(box, confirm, lambda *_: dialog.destroy())
        dialog.set_child(box)
        dialog.set_default_widget(b_ok)
        entry.connect("activate", confirm)
        dialog.present()
        entry.grab_focus()

    def _ask_number(self, title, prompt, initial, lower, upper, step, on_ok):
        dialog = Gtk.Window(title=title, transient_for=self, modal=True)
        dialog.add_css_class("rusca-dialog")
        dialog.set_default_size(360, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12); box.set_margin_bottom(12)
        box.set_margin_start(12); box.set_margin_end(12)
        box.add_css_class("rusca-bg")
        prompt_lbl = Gtk.Label(label=prompt, xalign=0)
        prompt_lbl.add_css_class("rusca-dialog-text")
        box.append(prompt_lbl)
        adj = Gtk.Adjustment(value=initial, lower=lower, upper=upper,
                             step_increment=step, page_increment=step * 10)
        spin = Gtk.SpinButton()
        spin.set_adjustment(adj)
        spin.set_numeric(True)
        spin.set_activates_default(True)
        box.append(spin)
        def confirm(*_):
            val = int(spin.get_value())
            dialog.destroy()
            on_ok(val)

        b_ok = self._ok_cancel_row(box, confirm, lambda *_: dialog.destroy())
        dialog.set_child(box)
        dialog.set_default_widget(b_ok)
        dialog.present()
        spin.grab_focus()

    def _confirm(self, title, body, buttons, default_idx, cancel_idx, on_choice):
        """Dialogo di conferma con N pulsanti, reso con il nostro tema (leggibile
        in chiaro e in scuro). on_choice(idx) riceve l'indice del pulsante; se
        l'utente chiude la finestra dalla 'X' vale cancel_idx.

        Il callback viene chiamato UNA sola volta, dopo aver chiuso il dialogo,
        tramite GLib.idle_add: cosi' non viene eseguito dentro l'emissione di un
        segnale del dialogo (cosa che rendeva inaffidabile la chiusura della
        finestra principale)."""
        dialog, box = self._dialog_shell(title, margin=18)
        if title:
            head = Gtk.Label()
            head.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
            head.add_css_class("rusca-dialog-text")
            head.set_xalign(0.5)
            box.append(head)
        if body:
            lbl = Gtk.Label(label=body)
            lbl.add_css_class("rusca-dialog-text")
            lbl.set_wrap(True)
            lbl.set_justify(Gtk.Justification.CENTER)
            lbl.set_xalign(0.5)
            lbl.set_max_width_chars(48)
            box.append(lbl)
        btnbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                         halign=Gtk.Align.CENTER)

        state = {"done": False}
        default_btn = None

        def finish(idx):
            # esegui una sola volta, e fuori dai segnali del dialogo
            if state["done"]:
                return
            state["done"] = True
            dialog.destroy()
            GLib.idle_add(lambda: (on_choice(idx), False)[1])

        for i, label in enumerate(buttons):
            b = Gtk.Button(label=label)
            if i == default_idx:
                b.add_css_class("suggested-action")
                default_btn = b
            b.connect("clicked", lambda _w, idx=i: finish(idx))
            btnbox.append(b)
        box.append(btnbox)
        dialog.set_child(box)
        if default_btn is not None:
            dialog.set_default_widget(default_btn)

        # chiusura dalla 'X' o con Esc: equivale all'indice di annulla
        def on_close_req(*_):
            if not state["done"]:
                idx = cancel_idx if cancel_idx is not None else -1
                finish(idx)
            return False   # lascia chiudere

        dialog.connect("close-request", on_close_req)
        dialog.present()
        GLib.idle_add(self._raise_dialog, dialog)
        if default_btn is not None:
            default_btn.grab_focus()

    def _file_dialog(self, title, patterns, filter_name,
                     suggested_name=None, multiple=False, on_result=None):
        """Selettore di file: unico punto in cui si costruisce un Gtk.FileDialog.

        I tre casi — salva, apri, apri piu' file — differiscono solo per il
        metodo da chiamare e per quello che restituiscono; il titolo, il filtro
        e la gestione dell'annullamento sono identici e stanno qui una volta
        sola. La richiamata riceve un percorso, o una lista di percorsi se
        multiple=True. Se l'utente annulla, non viene chiamata."""
        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        if suggested_name is not None:
            dialog.set_initial_name(suggested_name)
        if patterns:
            flt = Gtk.FileFilter()
            flt.set_name(filter_name)
            for pattern in patterns:
                flt.add_pattern(pattern)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(flt)
            dialog.set_filters(filters)
            dialog.set_default_filter(flt)

        def done(d, result):
            try:
                answer = finish(d, result)
            except GLib.Error:
                return          # l'utente ha annullato: nulla da fare
            if multiple:
                paths = []
                for i in range(answer.get_n_items()):
                    try:
                        path = answer.get_item(i).get_path()
                    except Exception:
                        path = None
                    if path:
                        paths.append(path)
                if paths:
                    on_result(paths)
            elif answer is not None:
                on_result(answer.get_path())

        if suggested_name is not None:
            finish = Gtk.FileDialog.save_finish
            dialog.save(self, None, done)
        elif multiple:
            finish = Gtk.FileDialog.open_multiple_finish
            dialog.open_multiple(self, None, done)
        else:
            finish = Gtk.FileDialog.open_finish
            dialog.open(self, None, done)

    def _save_file_dialog(self, title, suggested_name, patterns, filter_name, on_path):
        self._file_dialog(title, patterns, filter_name,
                          suggested_name=suggested_name or "", on_result=on_path)

    def _open_file_dialog(self, title, patterns, filter_name, on_path):
        self._file_dialog(title, patterns, filter_name, on_result=on_path)

    def _open_files_dialog(self, title, patterns, filter_name, on_paths):
        """Come _open_file_dialog ma permette di selezionare piu' file insieme;
        chiama on_paths(lista_di_percorsi)."""
        self._file_dialog(title, patterns, filter_name,
                          multiple=True, on_result=on_paths)

    def on_import_chapters(self, *_):
        """File -> Importa come capitoli: ogni file .txt/.md scelto diventa un
        nuovo capitolo in fondo al progetto (il progetto resta, non viene
        sostituito)."""
        self._open_files_dialog(self.t("dlg_import_title"),
                                ["*.txt", "*.md", "*.markdown"],
                                self.t("filter_text"),
                                self._import_files_as_chapters)

    # ---- File: nuovo / apri / salva ----------------------------------------
    def on_new(self, *_):
        def proceed():
            self._ask_text(self.t("dlg_new_title"), self.t("dlg_new_prompt"),
                           self.t("default_project"), self._do_new)
        self._guard_discard(proceed)

    def _do_new(self, title):
        title = (title or "").strip() or self.t("default_project")
        self.current = None
        self.project.new(title)
        self.project._lang = self.lang
        self._refresh_chapter_list(0)
        self._mark_clean()

    def on_open(self, *_):
        def proceed():
            self._open_file_dialog(self.t("dlg_open_title"), ["*.rwr"],
                                   self.t("filter_project"), self._do_open)
        self._guard_discard(proceed)

    def _do_open(self, path):
        recovered = self._maybe_recover(path, self._do_open_finish)
        if recovered == "pending":
            return
        self._do_open_finish(path, recovered)

    def _do_open_finish(self, path, recovered):
        try:
            self.current = None
            if recovered is not None:
                self.project.load(recovered)
                self.project._lang = self.lang
            fs = self.project.meta.get("font_size")
            ff = self.project.meta.get("font_family")
            if isinstance(fs, int):
                self.font_size = max(MIN_FONT_SIZE, min(fs, MAX_FONT_SIZE))
            if ff and ff not in ("Special Elite",):
                self.font_family = ff
            elif ff in ("Special Elite",) and self.font_available:
                self.font_family = TYPEWRITER_FAMILY
            self._apply_editor_font()
            sl = self.project.meta.get("spell_lang")
            if sl in ("it", "en"):
                if hasattr(self, "spell_combo"):
                    self.spell_combo.set_active_id(sl)
                # applica la lingua ortografica del documento tramite il
                # percorso unico (gestisce libspelling e gspell2)
                self._set_spell_lang(sl)
            self._refresh_chapter_list(0)
            self._mark_clean()
        except Exception as exc:
            self._error(self.t("err_open", e=exc))

    def _maybe_recover(self, path, finish_cb):
        auto = path + ".autosave"
        try:
            if (os.path.exists(auto)
                    and os.path.getmtime(auto) > os.path.getmtime(path)):
                yes = self.translator._strings.get("yes", "Sì")
                no = self.translator._strings.get("no", "No")

                def choice(idx):
                    if idx == 0:
                        try:
                            self.project.load(auto)
                            self.project.path = path
                        except Exception as exc:
                            self._error(self.t("err_open", e=exc))
                            return
                        finish_cb(path, None)
                    else:
                        finish_cb(path, path)

                self._confirm(self.t("recover_title"), self.t("recover_body"),
                              [yes, no], default_idx=0, cancel_idx=1,
                              on_choice=choice)
                return "pending"
        except Exception:
            pass
        return path

    def on_save(self, *_, announce=True, then=None):
        self._commit_current()
        if not self.project.path:
            self._save_file_dialog(self.t("dlg_save_title"),
                                   f"{self.project.title}.rwr", ["*.rwr"],
                                   self.t("filter_project"),
                                   lambda p: self._do_save_as(p, announce=announce,
                                                              then=then))
            return
        self._do_save(None, announce=announce, then=then)

    def _do_save_as(self, path, announce=True, then=None):
        if not path.endswith(".rwr"):
            path += ".rwr"
        self._do_save(path, announce=announce, then=then)

    def _do_save(self, path, announce=True, then=None):
        try:
            self.project.meta["font_size"] = self.font_size
            self.project.meta["font_family"] = self.font_family
            self.project.meta["spell_lang"] = self.spell_lang
            self.project.save(path)
            self._refresh_chapter_list(max(0, self._current_index()))
            self._mark_clean()
            self._cleanup_autosave()
            if announce:
                self._info(self.t("saved"))
            if then is not None:
                then()
        except Exception as exc:
            self._error(self.t("err_save", e=exc))

    def _guard_discard(self, proceed):
        if not self._dirty:
            proceed()
            return

        def choice(idx):
            if idx == 0:
                proceed()
            elif idx == 2:
                # salva (senza popup) e, se riuscito, prosegui con l'azione
                self.on_save(announce=False, then=proceed)

        self._confirm(self.t("unsaved_title"), self.t("unsaved_body"),
                      [self.t("btn_discard"), self.t("btn_cancel"),
                       self.t("btn_save_changes")],
                      default_idx=2, cancel_idx=1, on_choice=choice)

    # ---- capitoli -----------------------------------------------------------
    def on_add_chapter(self, *_):
        self._commit_current()
        self.project.add_chapter()
        self._refresh_chapter_list(len(self.project.chapters) - 1)
        self._mark_dirty()

    def on_delete_chapter(self, *_):
        if not self.project.chapters:
            return
        row = self._current_index()
        if row < 0:
            return
        ch = self.project.chapters[row]
        if ch.is_cover:
            self._error(self.t("del_cover"))
            return
        # (e' consentito eliminare anche l'ultimo capitolo: un progetto senza
        # capitoli e' uno stato legittimo, gestito dallo stato vuoto)

        def choice(idx):
            if idx != 0:
                return
            self.current = None
            self.project.delete_chapter(row)
            new_sel = min(row, len(self.project.chapters) - 1)
            self._refresh_chapter_list(new_sel)
            self._mark_dirty()

        self._confirm(self.t("del_title"),
                      self.t("del_body", t=self._chapter_title(ch)),
                      [self.t("ok"), self.t("cancel")],
                      default_idx=0, cancel_idx=1, on_choice=choice)

    def on_move_up(self, *_):
        self._move(-1)

    def on_move_down(self, *_):
        self._move(+1)

    def on_insert_image(self, *_):
        """EN: Attach an image (PNG/JPEG/WebP) to the current chapter: the
        file is copied INTO the project (it travels inside the .rwr archive)
        and a Markdown line ![caption](img_NNN.ext) is inserted at the
        cursor. The exports render it as a real picture.
        IT: Allega un'immagine (PNG/JPEG/WebP) al capitolo corrente: il file
        viene copiato DENTRO il progetto (viaggia nell'archivio .rwr) e una
        riga Markdown ![didascalia](img_NNN.ext) viene inserita al cursore.
        Gli export la rendono come immagine vera e propria."""
        row = self._current_index()
        if row < 0 or self.project.chapters[row].is_cover:
            # EN/IT: images belong to content chapters, not to the cover
            # (the cover has its own image in File -> Editorial sections).
            self._error(self.t("img_only_chapter"))
            return

        def on_path(path):
            try:
                with open(path, "rb") as f:
                    data = f.read()
                name = self.project.add_image(data)
            except ValueError:
                self._error(self.t("err_img_format"))
                return
            except Exception as exc:
                self._error(self.t("err_open", e=exc))
                return
            # EN: default caption = the original file name (editable text).
            # IT: didascalia predefinita = nome del file originale
            #     (testo modificabile).
            caption = os.path.splitext(os.path.basename(path))[0]
            snippet = f"\n![{caption}]({name})\n"
            self.text_buffer.insert_at_cursor(snippet)
            self._commit_current()
            self._mark_dirty()

        self._open_file_dialog(self.t("mi_insert_image"),
                               ["*.png", "*.jpg", "*.jpeg", "*.webp"],
                               self.t("filter_image"), on_path)

    def _move(self, direction):
        row = self._current_index()
        if row < 0:
            return
        self._commit_current()
        new_row = self.project.move_chapter(row, direction)
        if new_row != row:
            self._refresh_chapter_list(new_row)
            self._mark_dirty()

    def on_rename_chapter(self, *_):
        row = self._current_index()
        if row < 0:
            return
        ch = self.project.chapters[row]
        if ch.is_cover:
            self._error(self.t("rename_cover"))
            return

        def on_ok(new_title):
            ch.custom_title = (new_title or "").strip()
            self._refresh_chapter_list(row)
            if self.current is ch:
                self.center_title.set_text(self._chapter_title(ch))
            self._mark_dirty()

        self._ask_text(self.t("rename_title"), self.t("rename_prompt"),
                       ch.custom_title, on_ok)

    def on_set_goal(self, *_):
        def on_ok(val):
            self.word_goal = max(0, int(val))
            self.settings["word_goal"] = self.word_goal
            save_settings(self.settings)
            self._update_wordcount()

        self._ask_number(self.t("goal_title"), self.t("goal_prompt"),
                         self.word_goal, 0, 10_000_000, 500, on_ok)

    # ---- ricerca / sostituzione --------------------------------------------
    def on_find_replace(self, *_):
        if getattr(self, "_find_bar", None) is not None:
            self._find_entry.grab_focus()
            return
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        bar.add_css_class("rusca-findbar")
        bar.set_margin_top(4); bar.set_margin_bottom(4)
        bar.set_margin_start(4); bar.set_margin_end(4)

        self._find_entry = Gtk.SearchEntry()
        self._find_entry.set_placeholder_text(self.t("find_label"))
        self._find_entry.set_hexpand(True)
        self._replace_entry = Gtk.Entry()
        self._replace_entry.set_placeholder_text(self.t("replace_label"))
        self._replace_entry.set_hexpand(True)

        btn_prev = Gtk.Button(label=self.t("find_prev"))
        btn_next = Gtk.Button(label=self.t("find_next"))
        btn_one = Gtk.Button(label=self.t("replace_one"))
        btn_all = Gtk.Button(label=self.t("replace_all"))
        btn_close = Gtk.Button(label="✕")

        btn_next.connect("clicked", lambda *_: self._find_step(+1))
        btn_prev.connect("clicked", lambda *_: self._find_step(-1))
        btn_one.connect("clicked", self._replace_one)
        btn_all.connect("clicked", self._replace_all)
        btn_close.connect("clicked", lambda *_: self._close_find_bar())
        self._find_entry.connect("activate", lambda *_: self._find_step(+1))
        self._find_entry.connect("stop-search", lambda *_: self._close_find_bar())

        for w in (self._find_entry, btn_prev, btn_next,
                  self._replace_entry, btn_one, btn_all, btn_close):
            bar.append(w)

        self._center_box.prepend(bar)
        self._find_bar = bar
        self._find_entry.grab_focus()

    def _close_find_bar(self):
        if getattr(self, "_find_bar", None) is not None:
            self._center_box.remove(self._find_bar)
            self._find_bar = None
            self.text_view.grab_focus()

    def _find_step(self, direction):
        if getattr(self, "_find_bar", None) is None:
            return
        needle = self._find_entry.get_text()
        if not needle:
            return
        buf = self.text_buffer
        text = buf.get_text(*buf.get_bounds(), True)
        hay = text.lower()
        ndl = needle.lower()
        if buf.get_has_selection():
            sa, sb = buf.get_selection_bounds()
            start_fwd = sb.get_offset()
            start_bwd = sa.get_offset()
        else:
            ins = buf.get_iter_at_mark(buf.get_insert()).get_offset()
            start_fwd = start_bwd = ins
        if direction > 0:
            idx = hay.find(ndl, start_fwd)
            if idx < 0:
                idx = hay.find(ndl, 0)
        else:
            idx = hay.rfind(ndl, 0, max(0, start_bwd))
            if idx < 0:
                idx = hay.rfind(ndl)
        if idx < 0:
            self._flash_status(self.t("find_none"))
            return
        a = buf.get_iter_at_offset(idx)
        b = buf.get_iter_at_offset(idx + len(needle))
        buf.select_range(b, a)
        self.text_view.scroll_to_iter(a, 0.1, False, 0, 0)

    def _replace_one(self, *_):
        if getattr(self, "_find_bar", None) is None:
            return
        buf = self.text_buffer
        needle = self._find_entry.get_text()
        if not needle:
            return
        if buf.get_has_selection():
            a, b = buf.get_selection_bounds()
            sel = buf.get_text(a, b, True)
            if sel.lower() == needle.lower():
                rep = self._replace_entry.get_text()
                buf.delete(a, b)
                buf.insert(a, rep)
        self._find_step(+1)

    def _replace_all(self, *_):
        if getattr(self, "_find_bar", None) is None:
            return
        needle = self._find_entry.get_text()
        if not needle:
            return
        rep = self._replace_entry.get_text()
        buf = self.text_buffer
        text = buf.get_text(*buf.get_bounds(), True)
        import re
        count = len(re.findall(re.escape(needle), text, flags=re.IGNORECASE))
        if count:
            new_text = re.sub(re.escape(needle), lambda m: rep,
                              text, flags=re.IGNORECASE)
            self._loading = True
            buf.set_text(new_text)
            self._loading = False
            if self.current is not None:
                self.current.text = new_text
            self._highlight_markdown()
            self._update_wordcount()
            self._mark_dirty()
        self._flash_status(self.t("replaced_n", n=count))

    def _flash_status(self, msg):
        self.wordcount_label.set_text(msg)
        GLib.timeout_add_seconds(2, lambda: (self._update_wordcount(), False)[1])

    # ---- anteprima ----------------------------------------------------------
    def on_toggle_preview(self, *_):
        self._toggle_preview(whole=False)

    def on_toggle_preview_whole(self, *_):
        self._toggle_preview(whole=True)

    # ---- carattere ---------------------------------------------------------
    def _font_choices(self):
        """Elenco dei caratteri offerti: prima i due incorporati, poi le
        famiglie TrueType installate. Ogni voce e' (etichetta, famiglia)."""
        incorporato = self._t_or("font_builtin", "incorporato")
        voci = [(f"{_TW_FAMILY} ({incorporato})", _TW_FAMILY),
                (f"{SERIF_FAMILY} ({incorporato})", SERIF_FAMILY)]
        interne = {_TW_FAMILY, SERIF_FAMILY}
        voci += [(fam, fam) for fam in sorted(system_font_families())
                 if fam not in interne]
        return voci

    def on_choose_font(self, *_):
        """Sceglie DUE caratteri, separati: quello con cui si scrive e legge a
        schermo, e quello con cui escono i documenti esportati.

        Sono mestieri diversi. A schermo si sta ore su un testo in lavorazione,
        e c'e' chi ci vuole una macchina da scrivere; il PDF e' il libro, e li'
        di solito si vuole un serif da lettura. Percio' due tendine, non una,
        con i predefiniti storici gia' selezionati."""
        voci = self._font_choices()
        etichette = [v[0] for v in voci]

        def indice_di(famiglia, ripiego):
            for i, (_lbl, fam) in enumerate(voci):
                if fam == famiglia:
                    return i
            for i, (_lbl, fam) in enumerate(voci):
                if fam == ripiego:
                    return i
            return 0

        dialog, box = self._dialog_shell(
            self._t_or("dlg_font_title", "Caratteri"), size=(460, -1))

        def riga(chiave, ripiego_testo, selezione):
            lbl = Gtk.Label(label=self._t_or(chiave, ripiego_testo), xalign=0)
            lbl.add_css_class("rusca-dialog-text")
            box.append(lbl)
            tendina = Gtk.DropDown.new_from_strings(etichette)
            tendina.set_selected(selezione)
            box.append(tendina)
            return tendina

        t_schermo = riga("font_screen_label",
                         "Scrittura e lettura a schermo",
                         indice_di(getattr(self, "font_family", _TW_FAMILY),
                                   _TW_FAMILY))
        t_export = riga("font_export_label",
                        "Documenti esportati (PDF)",
                        indice_di(getattr(self, "doc_font", "") or SERIF_FAMILY,
                                  SERIF_FAMILY))

        nota = Gtk.Label(
            label=self._t_or("font_ttf_note",
                             "Sono elencate le famiglie TrueType: sono le sole "
                             "che si possono incorporare nel PDF."),
            xalign=0)
        nota.set_wrap(True)
        nota.add_css_class("rusca-dialog-text")
        box.append(nota)

        def conferma(*_a):
            self.font_family = voci[t_schermo.get_selected()][1]
            self.doc_font = voci[t_export.get_selected()][1]
            self.settings["font_family"] = self.font_family
            self.settings["doc_font"] = self.doc_font
            save_settings(self.settings)
            self._apply_editor_font()
            dialog.destroy()
            self._info(self.t("font_chosen", s=self.font_family,
                              e=self.doc_font))

        ok = self._ok_cancel_row(box, conferma,
                                 lambda *_a: dialog.destroy())
        self._dialog_present(dialog, box, ok)

    # ---- interruzioni di riga ----------------------------------------------
    def on_toggle_show_breaks(self, *_):
        """Accende o spegne l'evidenziazione dei paragrafi spezzati. Non tocca
        il testo: serve a vedere se e dove c'e' qualcosa da ricucire."""
        self.show_breaks = not self.show_breaks
        self.settings["show_breaks"] = self.show_breaks
        save_settings(self.settings)
        self._sync_switch("show_breaks", self.show_breaks)
        self._highlight_markdown()
        if self.show_breaks:
            n = len(wrapped_runs(self._chapter_text()))
            self._info(self.t("breaks_found", n=n) if n
                       else self.t("breaks_none"))

    def _chapter_text(self):
        """Testo del capitolo aperto, così com'e' nell'area di scrittura."""
        s, e = self.text_buffer.get_bounds()
        return self.text_buffer.get_text(s, e, True)

    def on_reflow_paragraphs(self, *_):
        """Ricuce a mano i paragrafi spezzati del capitolo aperto.

        E' la versione manuale di cio' che l'importazione fa da sola: serve
        quando il testo e' arrivato per altre strade — incollato, o importato
        con una versione precedente."""
        if self.current is None:
            return
        text = self._chapter_text()
        runs = wrapped_runs(text)
        if not runs:
            self._info(self.t("breaks_none"))
            return
        righe = sum(last - first for first, last in runs)
        new_text = unwrap_hard_breaks(text)
        if new_text == text:
            self._info(self.t("breaks_none"))
            return
        self.text_buffer.set_text(new_text)
        self._commit_current()
        self._highlight_markdown()
        self._mark_dirty()
        self._update_wordcount()
        self._info(self.t("reflow_done", n=len(runs), lines=righe))

    def _toggle_preview(self, whole):
        if self._preview_mode and bool(getattr(self, "_preview_whole", False)) == whole:
            self._preview_mode = False
            self.center_stack.set_visible_child_name("editor")
        else:
            self._preview_mode = True
            self._preview_whole = whole
            self._commit_current()
            self._render_preview()
            self.center_stack.set_visible_child_name("preview")

    def _render_preview(self):
        buf = self.preview_buffer
        buf.set_text("")
        if getattr(self, "_preview_whole", False):
            chapters = self.project._ordered_chapters()
            for i, (ch_title, text) in enumerate(chapters):
                if i > 0:
                    buf.insert(buf.get_end_iter(), "\n")
                    buf.insert_with_tags(buf.get_end_iter(),
                                         "* * *\n\n", self._pv_tags["sep"])
                first = text.lstrip().split("\n", 1)[0] if text.strip() else ""
                if classify_md_line(first)[0] != "heading":
                    buf.insert_with_tags(buf.get_end_iter(),
                                         ch_title + "\n", self._pv_tags["h1"])
                self._render_markdown_into(text)
        else:
            text = self.current.text if self.current is not None else ""
            self._render_markdown_into(text)

    def _render_markdown_into(self, text):
        """Riversa il Markdown nel buffer dell'anteprima. Riconoscimento delle
        righe e della formattazione inline: entrambi dal parser condiviso in
        model.py, così l'anteprima mostra esattamente ciò che finirà negli
        export."""
        buf = self.preview_buffer

        def insert_inline(line, base_tags):
            for seg, style in parse_inline(line):
                tag = self._pv_tags.get(style)
                tags = ([tag] if tag is not None else []) + list(base_tags)
                buf.insert_with_tags(buf.get_end_iter(), seg, *tags)

        for raw in text.split("\n"):
            kind, body, extra = classify_md_line(raw)
            end = buf.get_end_iter
            if kind == "heading":
                buf.insert_with_tags(end(), body + "\n",
                                     self._pv_tags[f"h{min(3, extra)}"])
            elif kind == "bullet":
                buf.insert(end(), "  \u2022  ")
                insert_inline(body, [])
                buf.insert(end(), "\n")
            elif kind == "number":
                buf.insert(end(), f"  {extra}.  ")
                insert_inline(body, [])
                buf.insert(end(), "\n")
            elif kind == "quote":
                insert_inline(body, [self._pv_tags["quote"]])
                buf.insert(end(), "\n")
            elif kind == "image":
                # nell'anteprima la figura non c'e': resta la didascalia,
                # in corsivo, dove comparira' l'immagine
                insert_inline(body, [self._pv_tags["italic"]])
                buf.insert(end(), "\n")
            else:
                insert_inline(raw.rstrip("\n"), [])
                buf.insert(end(), "\n")

    # ---- informazioni -------------------------------------------------------
    def _cover_generator_dialog(self, on_done, parent=None):
        """EN: Cover generator: composes a typographic cover (colour ground,
        double rule frame, author, optional picture, title, publisher) with a
        live preview, and hands the resulting PNG bytes to 'on_done'. It is an
        ALTERNATIVE to attaching a ready-made image, never a replacement: the
        caller keeps its Attach/Remove buttons untouched.
        IT: Generatore di copertine: compone una copertina tipografica (fondo
        colorato, cornice a doppio filetto, autore, immagine facoltativa,
        titolo, editore) con anteprima dal vivo, e passa i byte PNG ottenuti a
        'on_done'. E' un'ALTERNATIVA all'allegare un'immagine gia' pronta, mai
        un sostituto: i pulsanti Allega/Rimuovi del chiamante restano intatti."""
        # EN: initial values taken from the frontispiece metadata the user has
        #     already filled in (title/author/publisher), so the generator
        #     opens with the book's own data instead of placeholders.
        # IT: valori iniziali presi dai dati del frontespizio gia' compilati
        #     dall'utente (titolo/autore/editore), cosi' il generatore si apre
        #     con i dati del libro invece che con segnaposto.
        front = getattr(self.project, "frontispiece_fields", {}) or {}
        st = {
            "fmt": getattr(self, "_pdf_page_size", pw_model.COVER_DEFAULT_FORMAT),
            "bg": pw_model.COVER_DEFAULT_COLOR,
            "txt": "#111111",
            "author": (front.get("author") or "").strip(),
            "title": (front.get("title") or self.project.title or "").strip(),
            "publisher": (front.get("publisher") or "").strip(),
            "image": None,
        }
        if st["fmt"] not in pw_model.COVER_FORMATS:
            st["fmt"] = pw_model.COVER_DEFAULT_FORMAT

        dialog = Gtk.Window(transient_for=(parent or self), modal=True)
        dialog.add_css_class("rusca-dialog")
        dialog.set_title(self._t_or("cover_gen_title", "Genera copertina"))
        dialog.set_default_size(760, 640)

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        outer.set_margin_top(16); outer.set_margin_bottom(16)
        outer.set_margin_start(18); outer.set_margin_end(18)
        outer.add_css_class("rusca-bg")

        # ---- colonna sinistra: controlli (scorrevole) ----
        ctrl_scroll = Gtk.ScrolledWindow()
        ctrl_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        ctrl_scroll.set_vexpand(True)
        ctrl_scroll.set_size_request(320, -1)
        ctrl = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        ctrl_scroll.set_child(ctrl)
        outer.append(ctrl_scroll)

        # ---- colonna destra: anteprima ----
        prev_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        prev_box.set_hexpand(True)
        preview = Gtk.Picture()
        preview.set_can_shrink(True)
        preview.set_vexpand(True)
        prev_box.append(preview)
        outer.append(prev_box)

        def _label(text, bold=False):
            l = Gtk.Label(xalign=0)
            if bold:
                l.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")
            else:
                l.set_text(text)
            l.add_css_class("rusca-dialog-text")
            return l

        # --- anteprima: ridisegnata a ogni modifica ---
        def refresh():
            data = pw_model.render_cover_image(
                fmt_key=st["fmt"], dpi=pw_model.COVER_PREVIEW_DPI,
                bg_color=st["bg"], text_color=st["txt"],
                author=st["author"], title=st["title"],
                publisher=st["publisher"], image_bytes=st["image"],
                out_format="png", font_dir=paths.ASSETS_DIR)
            if not data or GdkPixbuf is None:
                preview.set_paintable(None)
                return
            try:
                loader = GdkPixbuf.PixbufLoader()
                loader.write(data); loader.close()
                preview.set_pixbuf(loader.get_pixbuf())
            except Exception:
                preview.set_paintable(None)

        # --- campi di testo ---
        ctrl.append(_label(self._t_or("cover_gen_texts", "Testi"), bold=True))

        def text_field(label_key, default_label, key):
            ctrl.append(_label(self._t_or(label_key, default_label)))
            e = Gtk.Entry()
            e.add_css_class("rusca-dialog")
            e.set_text(st[key] or "")

            def changed(entry):
                st[key] = entry.get_text()
                refresh()
            e.connect("changed", changed)
            ctrl.append(e)
            return e

        text_field("cover_gen_author", "Autore", "author")
        text_field("cover_gen_book_title", "Titolo", "title")
        text_field("cover_gen_publisher", "Casa editrice", "publisher")

        # --- immagine facoltativa ---
        ctrl.append(_label(self._t_or("cover_gen_image", "Immagine"), bold=True))
        img_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        b_pick = Gtk.Button(label=self._t_or("cover_gen_pick", "Scegli…"))
        b_clear = Gtk.Button(label=self._t_or("cover_gen_clear", "Togli"))

        def pick_image():
            def on_path(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    if pw_model.image_format(data) is None:
                        self._error(self.t("err_img_format"))
                        return
                    st["image"] = data
                    refresh()
                except Exception as exc:
                    self._error(self.t("err_open", e=exc))
            self._open_file_dialog(self._t_or("cover_gen_pick", "Scegli…"),
                                   ["*.png", "*.jpg", "*.jpeg", "*.webp"],
                                   self.t("filter_image"), on_path)

        b_pick.connect("clicked", lambda *_: pick_image())

        def clear_image(*_):
            st["image"] = None
            refresh()
        b_clear.connect("clicked", clear_image)
        img_row.append(b_pick); img_row.append(b_clear)
        ctrl.append(img_row)

        # --- formato pagina ---
        ctrl.append(_label(self._t_or("cover_gen_format", "Formato"), bold=True))
        fmt_keys = list(pw_model.COVER_FORMATS.keys())
        fmt_combo = Gtk.ComboBoxText()
        for k in fmt_keys:
            # le etichette gia' contengono le misure in centimetri
            fmt_combo.append_text(PDF_PAGE_SIZE_LABELS.get(k, k))
        fmt_combo.set_active(fmt_keys.index(st["fmt"]))

        def fmt_changed(cb):
            i = cb.get_active()
            if 0 <= i < len(fmt_keys):
                st["fmt"] = fmt_keys[i]
                refresh()
        fmt_combo.connect("changed", fmt_changed)
        ctrl.append(fmt_combo)

        # --- colore del fondo: tavolozza + scelta libera ---
        ctrl.append(_label(self._t_or("cover_gen_color", "Colore"), bold=True))
        grid = Gtk.Grid()
        grid.set_row_spacing(6); grid.set_column_spacing(6)
        for i, hexcol in enumerate(pw_model.COVER_COLORS):
            sw = Gtk.Button()
            sw.set_size_request(34, 26)
            # pastiglia colorata come contenuto del pulsante
            css = Gtk.CssProvider()
            css.load_from_data(
                f"button {{ background-image:none; background-color:{hexcol}; }}"
                .encode("utf-8"))
            sw.get_style_context().add_provider(
                css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            sw.set_tooltip_text(hexcol)

            def pick(_b, c=hexcol):
                st["bg"] = c
                refresh()
            sw.connect("clicked", pick)
            grid.attach(sw, i % 6, i // 6, 1, 1)
        ctrl.append(grid)

        free_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        free_row.append(_label(self._t_or("cover_gen_custom", "Personalizzato")))
        color_btn = Gtk.ColorButton()
        try:
            rgba = Gdk.RGBA(); rgba.parse(st["bg"])
            color_btn.set_rgba(rgba)
        except Exception:
            pass

        def color_set(btn):
            c = btn.get_rgba()
            st["bg"] = "#%02x%02x%02x" % (int(c.red * 255 + .5),
                                          int(c.green * 255 + .5),
                                          int(c.blue * 255 + .5))
            refresh()
        color_btn.connect("color-set", color_set)
        free_row.append(color_btn)
        ctrl.append(free_row)

        # --- colore del testo ---
        ctrl.append(_label(self._t_or("cover_gen_text_color", "Testo"), bold=True))
        txt_combo = Gtk.ComboBoxText()
        txt_combo.append_text(self._t_or("cover_gen_text_dark", "Testo nero"))
        txt_combo.append_text(self._t_or("cover_gen_text_light", "Testo bianco"))
        txt_combo.set_active(0)

        def txt_changed(cb):
            st["txt"] = "#ffffff" if cb.get_active() == 1 else "#111111"
            refresh()
        txt_combo.connect("changed", txt_changed)
        ctrl.append(txt_combo)

        # ---- pulsanti finali ----
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(Gtk.Align.END)
        b_cancel = Gtk.Button(label=self.t("btn_cancel"))
        b_use = Gtk.Button(label=self._t_or("cover_gen_use", "Usa come copertina"))
        b_use.add_css_class("suggested-action")
        actions.append(b_cancel); actions.append(b_use)
        prev_box.append(actions)

        def close(*_):
            dialog.destroy()
        b_cancel.connect("clicked", close)

        def confirm(*_):
            # immagine finale a piena risoluzione (300 DPI), non l'anteprima
            data = pw_model.render_cover_image(
                fmt_key=st["fmt"], dpi=pw_model.COVER_EXPORT_DPI,
                bg_color=st["bg"], text_color=st["txt"],
                author=st["author"], title=st["title"],
                publisher=st["publisher"], image_bytes=st["image"],
                out_format="png", font_dir=paths.ASSETS_DIR)
            dialog.destroy()
            if data:
                on_done(data)
            else:
                self._error(self._t_or(
                    "cover_gen_failed",
                    "Non è stato possibile generare la copertina."))
        b_use.connect("clicked", confirm)

        dialog.set_child(outer)
        dialog.set_default_widget(b_use)
        refresh()
        dialog.present()
        GLib.idle_add(self._raise_dialog, dialog)

    def on_edit_sections(self, *_):
        """Dialogo per gestire le tre sezioni editoriali: immagine di copertina,
        frontespizio e colophon. Le modifiche vengono applicate al progetto solo
        quando si preme Salva."""
        dialog, outer = self._dialog_shell(self.t("sections_title"),
                                           size=(560, 640), margin=18)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        scroller.set_child(body)
        outer.append(scroller)

        # stato locale modificabile prima del salvataggio
        pending = {"image": self.project.cover_image,
                   "fmt": self.project.cover_image_fmt}

        # --- sezione COPERTINA (immagine) ---
        cov_head = Gtk.Label(xalign=0)
        cov_head.set_markup(f"<b>{GLib.markup_escape_text(self.t('sec_cover'))}</b>")
        cov_head.add_css_class("rusca-dialog-text")
        body.append(cov_head)

        cov_hint = Gtk.Label(label=self.t("sec_cover_hint"), xalign=0)
        cov_hint.add_css_class("rusca-dialog-text")
        cov_hint.set_wrap(True)
        body.append(cov_hint)

        preview = Gtk.Picture()
        preview.set_size_request(-1, 200)
        preview.set_can_shrink(True)

        def refresh_preview():
            data = pending["image"]
            if data and GdkPixbuf is not None:
                try:
                    loader = GdkPixbuf.PixbufLoader()
                    loader.write(data); loader.close()
                    preview.set_pixbuf(loader.get_pixbuf())
                    preview.set_visible(True)
                except Exception:
                    preview.set_visible(False)
            else:
                preview.set_visible(False)
            status_lbl.set_text(self.t("sec_cover_set") if pending["image"]
                                else self.t("sec_cover_none"))

        status_lbl = Gtk.Label(xalign=0)
        status_lbl.add_css_class("rusca-dialog-text")
        body.append(preview)
        body.append(status_lbl)

        btnrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        b_attach = Gtk.Button(label=self.t("sec_cover_attach"))
        b_generate = Gtk.Button(
            label=self._t_or("sec_cover_generate", "Genera…"))
        b_remove = Gtk.Button(label=self.t("sec_cover_remove"))

        def do_attach():
            def on_path(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    # EN: format detected from the CONTENT (magic bytes),
                    #     so a wrong extension cannot fool the export.
                    # IT: formato riconosciuto dal CONTENUTO (byte iniziali),
                    #     cosi' un'estensione sbagliata non inganna l'export.
                    fmt = pw_model.image_format(data)
                    if fmt is None:
                        self._error(self.t("err_img_format"))
                        return
                    pending["image"] = data
                    pending["fmt"] = fmt
                    refresh_preview()
                except Exception as exc:
                    self._error(self.t("err_open", e=exc))
            self._open_file_dialog(self.t("sec_cover_attach"),
                                   ["*.png", "*.jpg", "*.jpeg", "*.webp"],
                                   self.t("filter_image"), on_path)

        def do_remove():
            pending["image"] = None
            pending["fmt"] = None
            refresh_preview()

        def do_generate():
            # EN: the generator returns PNG bytes; they enter the very same
            #     pending slot used by an attached image, so saving, preview
            #     and every export treat both origins identically.
            # IT: il generatore restituisce byte PNG; entrano nello stesso
            #     spazio "pending" di un'immagine allegata, cosi' salvataggio,
            #     anteprima ed export trattano le due origini allo stesso modo.
            def on_done(data):
                if not data:
                    return
                pending["image"] = data
                pending["fmt"] = pw_model.image_format(data) or "png"
                refresh_preview()
            self._cover_generator_dialog(on_done, parent=dialog)

        b_attach.connect("clicked", lambda *_: do_attach())
        b_generate.connect("clicked", lambda *_: do_generate())
        b_remove.connect("clicked", lambda *_: do_remove())
        btnrow.append(b_attach)
        btnrow.append(b_generate)
        btnrow.append(b_remove)
        body.append(btnrow)

        # senza Pillow non si puo' disegnare il testo della copertina: il
        # generatore resta visibile ma disattivato, con una spiegazione.
        if not pw_model.cover_generator_available():
            b_generate.set_sensitive(False)
            b_generate.set_tooltip_text(self._t_or(
                "sec_cover_generate_needs_pil",
                "Per generare una copertina serve Pillow: "
                "sudo apt install python3-pil"))

        # helper per creare una riga "etichetta + campo"
        def field_row(label_text, value=""):
            lbl = Gtk.Label(xalign=0, label=label_text)
            lbl.add_css_class("rusca-dialog-text")
            entry = Gtk.Entry()
            entry.add_css_class("rusca-dialog")
            entry.set_hexpand(True)
            entry.set_text(value or "")
            body.append(lbl)
            body.append(entry)
            return entry

        def group_head(text):
            h = Gtk.Label(xalign=0)
            h.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")
            h.add_css_class("rusca-dialog-text")
            body.append(h)

        fr = self.project.frontispiece_fields
        co = self.project.colophon_fields

        hint = Gtk.Label(xalign=0, label=self.t("sec_fields_hint"))
        hint.add_css_class("rusca-dialog-text"); hint.set_wrap(True)
        body.append(hint)

        # --- DATI DELL'OPERA: titolo (precompilato), sottotitolo, autore ---
        group_head(self.t("grp_work"))
        e_title = field_row(self.t("fld_title"),
                            fr.get("title", "") or self.project.title)
        e_subtitle = field_row(self.t("fld_subtitle"), fr.get("subtitle", ""))
        e_author = field_row(self.t("fld_author"), fr.get("author", ""))

        # --- PUBBLICAZIONE: editore (unico), luogo/anno, edizione, ISBN ----
        group_head(self.t("grp_pub"))
        e_publisher = field_row(self.t("fld_publisher"),
                                fr.get("publisher", "") or co.get("publisher", ""))
        e_place = field_row(self.t("fld_place_year"), fr.get("place_year", ""))
        e_edition = field_row(self.t("fld_edition"), co.get("edition", ""))
        e_isbn = field_row(self.t("fld_isbn"), co.get("isbn", ""))

        # --- COLOPHON: copyright (auto se vuoto), licenza, note ------------
        group_head(self.t("sec_colophon"))
        e_copyright = field_row(self.t("fld_copyright"), co.get("copyright", ""))
        e_license = field_row(self.t("fld_license"), co.get("license", ""))
        lbl_notes = Gtk.Label(xalign=0, label=self.t("fld_notes"))
        lbl_notes.add_css_class("rusca-dialog-text")
        body.append(lbl_notes)
        co_notes_view = Gtk.TextView()
        co_notes_view.set_wrap_mode(Gtk.WrapMode.WORD)
        co_notes_view.add_css_class("rusca-dialog")
        co_notes_view.get_buffer().set_text(co.get("notes", ""))
        nf = Gtk.ScrolledWindow()
        nf.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        nf.set_child(co_notes_view)
        nf.set_size_request(-1, 70)
        body.append(nf)

        # --- pulsanti finali ---
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                          halign=Gtk.Align.END)
        b_cancel = Gtk.Button(label=self.t("cancel"))
        b_save = Gtk.Button(label=self.t("save"))
        b_save.add_css_class("suggested-action")

        def do_save():
            self.project.cover_image = pending["image"]
            self.project.cover_image_fmt = pending["fmt"]
            fr["title"] = e_title.get_text().strip()
            fr["subtitle"] = e_subtitle.get_text().strip()
            fr["author"] = e_author.get_text().strip()
            fr["place_year"] = e_place.get_text().strip()
            # l'editore si inserisce UNA volta e vale per frontespizio e colophon
            pub = e_publisher.get_text().strip()
            fr["publisher"] = pub
            co["publisher"] = pub
            co["edition"] = e_edition.get_text().strip()
            co["isbn"] = e_isbn.get_text().strip()
            co["license"] = e_license.get_text().strip()
            b = co_notes_view.get_buffer()
            co["notes"] = b.get_text(b.get_start_iter(), b.get_end_iter(),
                                     False).strip()
            # copyright: se lasciato vuoto ma c'e' l'autore, lo generiamo noi
            cpy = e_copyright.get_text().strip()
            if not cpy and fr["author"]:
                import datetime
                cpy = "© %d %s" % (datetime.date.today().year, fr["author"])
            co["copyright"] = cpy
            self._mark_dirty()
            dialog.destroy()

        b_cancel.connect("clicked", lambda *_: dialog.destroy())
        b_save.connect("clicked", lambda *_: do_save())
        actions.append(b_cancel)
        actions.append(b_save)
        outer.append(actions)

        dialog.set_child(outer)
        refresh_preview()
        dialog.present()
        GLib.idle_add(self._raise_dialog, dialog)

    def on_info(self, *_):
        if self.spell_checker is not None:
            spell_state = self.t("spell_active",
                                 backend=SPELL_BACKEND, loc=self._spell_locale())
        else:
            spell_state = self.t("spell_inactive",
                                 e=self.spell_error or self.t("spell_unknown"))
        import datetime
        copyright_line = "Copyright © %d %s" % (
            datetime.date.today().year, APP_AUTHOR)
        detail = (self.t("info_secondary", v=APP_VERSION_SHORT, d=self.app_date,
                         a=APP_AUTHOR, app=APP_NAME, copyright=copyright_line)
                  + "\n\n" + spell_state)

        # In GTK 4 Gtk.AlertDialog e' solo testo (niente immagine), quindi per
        # mostrare la stilografica costruiamo una finestra dedicata, come quella
        # di avvio: icona in alto, nome, testo informativo e pulsante Chiudi.
        dialog, box = self._dialog_shell(self.t("mi_about"),
                                         size=(460, 520), spacing=10, margin=22)

        tex = load_texture(96)
        if tex is not None:
            img = Gtk.Image.new_from_paintable(tex)
            img.set_pixel_size(96)
            box.append(img)

        name = Gtk.Label()
        name.set_markup(f"<span size='x-large' weight='bold'>{APP_NAME}</span>")
        name.add_css_class("column-title")
        box.append(name)

        body = Gtk.Label(label=detail)
        body.add_css_class("rusca-dialog-text")
        body.set_wrap(True)
        body.set_justify(Gtk.Justification.CENTER)
        # NON selezionabile: una label selezionabile, ricevendo il focus,
        # mostrerebbe tutto il testo evidenziato all'apertura della finestra.
        body.set_selectable(False)
        body.set_xalign(0.5)

        # il testo della licenza e' lungo: mettiamolo in un'area scorrevole
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(body)
        box.append(scroller)

        # Link: sito web del progetto e codice sorgente (software libero).
        links = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        links.set_halign(Gtk.Align.CENTER)
        link_site = Gtk.LinkButton.new_with_label(APP_WEBSITE, self.t("info_website"))
        link_src = Gtk.LinkButton.new_with_label(APP_SOURCE, self.t("info_source"))
        links.append(link_site)
        links.append(link_src)
        box.append(links)

        btn = Gtk.Button(label=self.t("ok"))
        btn.add_css_class("suggested-action")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda *_: dialog.destroy())
        box.append(btn)

        dialog.set_child(box)
        dialog.set_default_widget(btn)
        # Se la finestra principale è a schermo intero, alcuni window manager
        # collocano il dialogo dietro di essa: assicuriamoci che sia in primo
        # piano presentandolo di nuovo a finestra realizzata.
        dialog.present()
        GLib.idle_add(self._raise_dialog, dialog)
        # dai il focus al pulsante OK: altrimenti il primo widget focusabile
        # (l'etichetta selezionabile) verrebbe focalizzato e apparirebbe con
        # tutto il testo evidenziato.
        btn.grab_focus()

    def on_md_help(self, *_):
        """Finestra 'Guida ai comandi Markdown': elenca in breve la sintassi
        Markdown che l'editor riconosce e impagina negli export (specialmente
        nel PDF). E' costruita come una griglia a due colonne: a sinistra
        l'esempio di sintassi (in monospazio), a destra l'effetto. I testi
        vengono dai file di lingua con ripiego in italiano, cosi' la guida e'
        traducibile senza toccare il codice."""
        # ogni voce: (chiave_traduzione, esempio_sintassi, descrizione_fallback)
        rows = [
            ("md_h1",     "# Titolo",          "Titolo di primo livello"),
            ("md_h2",     "## Sottotitolo",    "Titoli minori (fino a ######)"),
            ("md_bold",   "**grassetto**",     "Testo in grassetto"),
            ("md_italic", "*corsivo*",         "Testo in corsivo"),
            ("md_both",   "***entrambi***",    "Grassetto e corsivo insieme"),
            ("md_code",   "`codice`",          "Testo a spaziatura fissa"),
            ("md_quote",  "> citazione",       "Citazione (resa in corsivo)"),
            ("md_ul",     "- elenco",          "Elenco puntato (anche * o +)"),
            ("md_ol",     "1. elenco",         "Elenco numerato"),
            ("md_link",   "[testo](url)",      "Collegamento (resta il testo)"),
            ("md_img",    "![didascalia](img)", "Immagine allegata con didascalia"),
            ("md_para",   "riga vuota",        "Una riga vuota separa i paragrafi"),
        ]

        dialog, box = self._dialog_shell(
            self._t_or("mi_md_help", "Guida ai comandi Markdown"),
            size=(480, 540), margin=22)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>%s</span>"
                         % GLib.markup_escape_text(
                             self._t_or("mi_md_help",
                                        "Guida ai comandi Markdown")))
        title.set_xalign(0.5)
        title.add_css_class("column-title")
        box.append(title)

        intro = Gtk.Label(label=self._t_or(
            "md_help_intro",
            "L'editor usa Markdown. Scrivi normalmente e usa questi simboli "
            "per la formattazione: verranno resi negli export (PDF, EPUB, "
            "ODT, DOCX, HTML)."))
        intro.add_css_class("rusca-dialog-text")
        intro.set_wrap(True)
        intro.set_justify(Gtk.Justification.CENTER)
        intro.set_xalign(0.5); intro.set_max_width_chars(48)
        box.append(intro)

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(18)
        grid.set_margin_start(4); grid.set_margin_end(4)
        for i, (key, syntax, fallback) in enumerate(rows):
            code = Gtk.Label()
            # esempio in monospazio, cosi' i simboli si distinguono bene
            code.set_markup("<tt>%s</tt>" % GLib.markup_escape_text(syntax))
            code.set_xalign(0.0)
            code.add_css_class("rusca-dialog-text")
            code.set_selectable(True)
            desc = Gtk.Label(label=self._t_or(key, fallback))
            desc.set_xalign(0.0)
            desc.set_wrap(True)
            desc.set_max_width_chars(30)
            desc.add_css_class("rusca-dialog-text")
            grid.attach(code, 0, i, 1, 1)
            grid.attach(desc, 1, i, 1, 1)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(grid)
        box.append(scroller)

        btn = Gtk.Button(label=self.t("ok"))
        btn.add_css_class("suggested-action")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", lambda *_: dialog.destroy())
        box.append(btn)

        self._dialog_present(dialog, box, btn)

    # ---- export -------------------------------------------------------------
    def on_export(self, *_):
        self._export_simple("txt", None, self.project.export_txt,
                            title_key="dlg_export_title")

    def on_export_pdf(self, *_):
        self._commit_current()
        # Dialogo di scelta del formato pagina: i formati sono molti (5), quindi
        # li disponiamo in COLONNA. Ogni riga mostra una piccola ANTEPRIMA delle
        # proporzioni del formato (un rettangolo in scala) accanto al pulsante
        # con l'etichetta. Il formato ricordato dall'ultima volta e' evidenziato
        # e ha il focus. Alla scelta salviamo la preferenza e proseguiamo col
        # normale salvataggio del file.
        sizes = list(PDF_PAGE_SIZES.keys())
        current = getattr(self, "_pdf_page_size", PDF_DEFAULT_PAGE_SIZE)
        if current not in PDF_PAGE_SIZES:
            current = PDF_DEFAULT_PAGE_SIZE

        def choose(size_key, justify, hyphenate):
            self._pdf_page_size = size_key
            self._pdf_justify = bool(justify)
            self._pdf_hyphenate = bool(hyphenate) and hyphenation_available(
                getattr(self, "lang", "it"))
            # ricorda le scelte tra le sessioni
            self.settings["pdf_page_size"] = size_key
            self.settings["pdf_justify"] = self._pdf_justify
            self.settings["pdf_hyphenate"] = self._pdf_hyphenate
            try:
                save_settings(self.settings)
            except Exception:
                pass
            self._save_file_dialog(self.t("dlg_export_pdf_title"),
                                   f"{self.project.title}.pdf", ["*.pdf"],
                                   self.t("filter_pdf"), self._do_export_pdf)

        dialog, box = self._dialog_shell(
            self._t_or("dlg_pdf_size_title", "Formato pagina"),
            spacing=10, margin=18)

        head = Gtk.Label()
        head.set_markup("<b>%s</b>" % GLib.markup_escape_text(
            self._t_or("dlg_pdf_size_title", "Formato pagina")))
        head.add_css_class("rusca-dialog-text")
        head.set_xalign(0.5)
        box.append(head)

        hint = Gtk.Label(label=self._t_or(
            "dlg_pdf_size_body", "Scegli il formato della pagina per il PDF."))
        hint.add_css_class("rusca-dialog-text")
        hint.set_wrap(True); hint.set_justify(Gtk.Justification.CENTER)
        hint.set_xalign(0.5); hint.set_max_width_chars(40)
        box.append(hint)

        state = {"done": False}
        # riferimenti alle caselle tipografiche, lette al momento della scelta
        opts = {"justify": None, "hyphenate": None}

        def finish(size_key):
            if state["done"]:
                return
            state["done"] = True
            j = opts["justify"].get_active() if opts["justify"] else False
            h = opts["hyphenate"].get_active() if opts["hyphenate"] else False
            dialog.destroy()
            if size_key is not None:
                GLib.idle_add(
                    lambda: (choose(size_key, j, h), False)[1])

        # altezza dell'anteprima in pixel: il rettangolo piu' alto (formato piu'
        # allungato) occupa quasi tutta questa altezza; gli altri in proporzione.
        PREVIEW_H = 46
        PREVIEW_BOX = 56   # larghezza dell'area di disegno (spazio per i formati larghi)
        max_h = max(s["h"] for s in PDF_PAGE_SIZES.values())

        def make_preview(spec, highlight):
            area = Gtk.DrawingArea()
            area.set_content_width(PREVIEW_BOX)
            area.set_content_height(PREVIEW_H + 6)

            def draw(_a, cr, w, h, *_):
                # scala il formato cosi' che l'altezza massima entri in PREVIEW_H
                scale = PREVIEW_H / max_h
                rw = spec["w"] * scale
                rh = spec["h"] * scale
                x = (w - rw) / 2.0
                y = (h - rh) / 2.0
                # colore: prugna se evidenziato, grigio altrimenti
                if highlight:
                    cr.set_source_rgb(0.557, 0.271, 0.522)   # #8E4585
                else:
                    cr.set_source_rgb(0.60, 0.60, 0.60)
                cr.set_line_width(1.5)
                cr.rectangle(x, y, rw, rh)
                cr.stroke_preserve()
                # leggero riempimento
                if highlight:
                    cr.set_source_rgba(0.557, 0.271, 0.522, 0.12)
                else:
                    cr.set_source_rgba(0.60, 0.60, 0.60, 0.08)
                cr.fill()

            area.set_draw_func(draw)
            return area

        default_btn = None
        for key in sizes:
            spec = PDF_PAGE_SIZES[key]
            is_current = (key == current)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.append(make_preview(spec, is_current))

            label = PDF_PAGE_SIZE_LABELS.get(key, key)
            b = Gtk.Button(label=label)
            b.set_hexpand(True)
            if is_current:
                b.add_css_class("suggested-action")
                default_btn = b
            b.connect("clicked", lambda _w, k=key: finish(k))
            row.append(b)
            box.append(row)

        # --- opzioni tipografiche: giustifica e sillaba --------------------
        # Un separatore leggero e due caselle. La sillabazione richiede il
        # pacchetto opzionale Pyphen (python3-pyphen) E un dizionario per la
        # lingua corrente (su Debian un pacchetto hyphen-<lingua>): se manca
        # l'uno o l'altro la casella e' disattivata e un testo di aiuto spiega
        # come abilitarla.
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(4); sep.set_margin_bottom(4)
        box.append(sep)

        # la sillabazione e' realmente possibile solo se c'e' Pyphen E un
        # dizionario per la lingua dell'interfaccia
        cur_lang = getattr(self, "lang", "it")
        hyph_ok = hyphenation_available(cur_lang)

        chk_justify = Gtk.CheckButton(
            label=self._t_or("dlg_pdf_justify", "Giustifica il testo"))
        chk_justify.add_css_class("rusca-dialog-text")
        chk_justify.set_active(getattr(self, "_pdf_justify", False))
        box.append(chk_justify)
        opts["justify"] = chk_justify

        chk_hyphen = Gtk.CheckButton(
            label=self._t_or("dlg_pdf_hyphenate", "Sillaba le parole a fine riga"))
        chk_hyphen.add_css_class("rusca-dialog-text")
        if hyph_ok:
            chk_hyphen.set_active(getattr(self, "_pdf_hyphenate", False))
        else:
            # senza Pyphen o senza dizionario della lingua la sillabazione non
            # e' possibile: casella spenta e disattivata, cosi' l'utente vede
            # che l'opzione esiste ma richiede qualcosa in piu'.
            chk_hyphen.set_active(False)
            chk_hyphen.set_sensitive(False)
        box.append(chk_hyphen)
        opts["hyphenate"] = chk_hyphen

        # la sillabazione ha senso solo col testo giustificato: quando la
        # giustificazione e' spenta, disattiviamo (visivamente) la casella
        # della sillabazione. Resta comunque innocua se attiva da sola.
        def _sync_hyphen(*_):
            can = chk_justify.get_active() and hyph_ok
            chk_hyphen.set_sensitive(can)
            if not can:
                chk_hyphen.set_active(False)
        chk_justify.connect("toggled", _sync_hyphen)
        _sync_hyphen()

        if not hyph_ok:
            # messaggio diverso a seconda del motivo: manca proprio Pyphen,
            # oppure Pyphen c'e' ma non il dizionario della lingua corrente.
            if not HAVE_PYPHEN:
                hint_text = self._t_or(
                    "dlg_pdf_hyphenate_hint",
                    "Per sillabare installa Pyphen e un dizionario:\n"
                    "sudo apt install python3-pyphen hyphen-it")
            else:
                hint_text = self._t_or(
                    "dlg_pdf_hyphenate_hint_dict",
                    "Per sillabare in questa lingua installa il dizionario:\n"
                    "sudo apt install hyphen-<lingua>")
            hyp_hint = Gtk.Label(label=hint_text)
            hyp_hint.add_css_class("rusca-dialog-text")
            hyp_hint.set_wrap(True)
            hyp_hint.set_justify(Gtk.Justification.CENTER)
            hyp_hint.set_xalign(0.5); hyp_hint.set_max_width_chars(46)
            hyp_hint.set_opacity(0.75)
            box.append(hyp_hint)

        cancel = Gtk.Button(label=self.t("btn_cancel"))
        cancel.connect("clicked", lambda _w: finish(None))
        box.append(cancel)

        dialog.set_child(box)
        if default_btn is not None:
            dialog.set_default_widget(default_btn)

        def on_close_req(*_):
            if not state["done"]:
                finish(None)
            return False

        dialog.connect("close-request", on_close_req)
        dialog.present()
        GLib.idle_add(self._raise_dialog, dialog)
        if default_btn is not None:
            default_btn.grab_focus()

    def _do_export_pdf(self, path):
        if not path.endswith(".pdf"):
            path += ".pdf"
        try:
            # Per i documenti esportati usiamo un serif da lettura (EB Garamond),
            # piu' adatto di un monospace come il Courier Prime dell'editor.
            here = paths.ASSETS_DIR
            embed_fonts = {}
            fname = None
            # 1) carattere scelto da chi scrive, se e' una famiglia di sistema
            scelto = getattr(self, "doc_font", "")
            # i due caratteri incorporati si riconoscono per nome e si
            # prendono dalla cartella assets, senza cercarli nel sistema
            incorporati = {SERIF_FAMILY: SERIF_FILES,
                           _TW_FAMILY: TYPEWRITER_FILES}
            if scelto in incorporati:
                for style, ffile in incorporati[scelto].items():
                    metrics = read_ttf_metrics(os.path.join(here, ffile))
                    if metrics:
                        embed_fonts[style] = metrics
                if "regular" in embed_fonts:
                    fname = scelto.replace(" ", "")
                else:
                    embed_fonts = {}
            elif scelto:
                for style, ffile in font_files_for_family(scelto).items():
                    metrics = read_ttf_metrics(ffile)
                    if metrics:
                        embed_fonts[style] = metrics
                if "regular" in embed_fonts:
                    # il nome dentro il PDF non ammette spazi
                    fname = scelto.replace(" ", "")
                else:
                    embed_fonts = {}
            # 2) altrimenti il serif da lettura incorporato
            if not embed_fonts:
                for style, ffile in SERIF_FILES.items():
                    metrics = read_ttf_metrics(os.path.join(here, ffile))
                    if metrics:
                        embed_fonts[style] = metrics
                if "regular" in embed_fonts:
                    fname = "EBGaramond"
            if "regular" not in embed_fonts:
                # ripiego: se i .ttf del serif non ci sono, prova il Courier Prime
                embed_fonts = {}
                for style, ffile in TYPEWRITER_FILES.items():
                    metrics = read_ttf_metrics(os.path.join(here, ffile))
                    if metrics:
                        embed_fonts[style] = metrics
                fname = "CourierPrime"
                if "regular" not in embed_fonts:
                    embed_fonts = None
            self.project.export_pdf(path, font_size=self.font_size,
                                    embed_fonts=embed_fonts, embed_font_name=fname,
                                    page_size=getattr(self, "_pdf_page_size",
                                                      PDF_DEFAULT_PAGE_SIZE),
                                    justify=getattr(self, "_pdf_justify", False),
                                    hyphenate=getattr(self, "_pdf_hyphenate", False),
                                    hyphen_lang=getattr(self, "lang", "it"))
            self._info(self.t("exported", p=path))
        except Exception as exc:
            self._error(self.t("err_export", e=exc))

    def on_export_epub(self, *_):
        self._export_simple("epub", "filter_epub", self.project.export_epub,
                            title_key="dlg_export_epub_title")

    def _export_simple(self, ext, filter_key, method, title_key="export"):
        """Esporta in un formato che non chiede altre scelte all'utente.

        Sette export su otto seguono la stessa sequenza: chiedi dove salvare,
        aggiungi l'estensione se manca, esporta, avvisa dell'esito. Sta qui una
        volta sola; PDF e HTML, che prima del salvataggio fanno domande in piu',
        restano a parte."""
        self._commit_current()

        def on_path(path):
            if not path.endswith("." + ext):
                path += "." + ext
            try:
                method(path)
                self._info(self.t("exported", p=path))
            except Exception as exc:
                self._error(self.t("err_export", e=exc))

        self._save_file_dialog(self.t(title_key),
                               f"{self.project.title}.{ext}",
                               [f"*.{ext}"] if filter_key else None,
                               self.t(filter_key) if filter_key else None,
                               on_path)

    def on_export_markdown(self, *_):
        self._export_simple("md", "filter_md", self.project.export_markdown)

    def on_export_odt(self, *_):
        self._export_simple("odt", "filter_odt", self.project.export_odt)

    def on_export_docx(self, *_):
        self._export_simple("docx", "filter_docx", self.project.export_docx)

    def on_export_azw3(self, *_):
        self._export_simple("azw3", "filter_azw3", self.project.export_azw3)

    def on_export_html(self, *_):
        self._commit_current()

        def choice(idx):
            # 0 = singolo, 1 = multi, 2 = annulla
            if idx == 2 or idx < 0:
                return
            multifile = (idx == 1)

            def on_path(path):
                if not multifile and not path.endswith(".html"):
                    path += ".html"
                try:
                    out = self.project.export_html(path, multifile=multifile)
                    self._info(self.t("exported", p=out))
                except Exception as exc:
                    self._error(self.t("err_export", e=exc))

            if multifile:
                self._save_file_dialog(self.t("export"), self.project.title,
                                       None, None, on_path)
            else:
                self._save_file_dialog(self.t("export"),
                                       f"{self.project.title}.html", ["*.html"],
                                       self.t("filter_html"), on_path)

        self._confirm(self.t("html_mode_title"), self.t("html_mode_body"),
                      [self.t("html_single"), self.t("html_multi"),
                       self.t("cancel")],
                      default_idx=0, cancel_idx=2, on_choice=choice)

    # ---- avvio --------------------------------------------------------------
    def _startup_dialog(self):
        tex = load_texture(160)
        dialog, box = self._dialog_shell(f"{APP_NAME} v{APP_VERSION}",
                                         size=(420, 360), spacing=10, margin=22)
        if tex is not None:
            img = Gtk.Image.new_from_paintable(tex)
            img.set_pixel_size(160)
            box.append(img)
        name = Gtk.Label()
        name.set_markup(f"<span size='xx-large' weight='bold'>{APP_NAME}</span>")
        name.add_css_class("column-title")
        box.append(name)
        sub = Gtk.Label(label=self.t("startup_secondary"))
        sub.add_css_class("rusca-dialog-text")
        sub.set_wrap(True)
        sub.set_justify(Gtk.Justification.CENTER)
        box.append(sub)
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                       halign=Gtk.Align.CENTER)
        b_open = Gtk.Button(label=self.t("startup_open"))
        b_new = Gtk.Button(label=self.t("startup_new"))
        b_new.add_css_class("suggested-action")
        btns.append(b_open); btns.append(b_new)
        box.append(btns)
        dialog.set_child(box)

        def do_open(*_):
            dialog.destroy()
            self.on_open()

        def do_new(*_):
            dialog.destroy()
            self.on_new()

        b_open.connect("clicked", do_open)
        b_new.connect("clicked", do_new)
        dialog.present()
        return False

    # ---- utilita' -----------------------------------------------------------
    def _current_row(self):
        sel = self.list_selection.get_selected()
        if sel == Gtk.INVALID_LIST_POSITION:
            return -1
        return sel

    def _current_index(self):
        """Indice in project.chapters del capitolo selezionato (-1 se nessuno)."""
        row = self._current_row()
        if row < 0:
            return -1
        return self._row_to_index(row)


class RuscaWriterApp(Gtk.Application):
    """Applicazione GTK 4. Sostituisce il vecchio Gtk.main()."""
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.win = None

    def do_activate(self):
        if self.win is None:
            self.win = RuscaWriterWindow(self)
        self.win.present()


def main():
    app = RuscaWriterApp()
    return app.run(None)


if __name__ == "__main__":
    main()
