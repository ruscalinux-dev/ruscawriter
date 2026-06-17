#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuscaWriter
Versione: 0.1
Autore: ruscalinux-dev

Editor di scrittura a tre colonne scritto in Python + GTK 4 (PyGObject),
senza librerie grafiche aggiuntive.

 - Colonna sinistra : elenco dei capitoli/sezioni del progetto.
 - Colonna centrale : area di scrittura del testo (serif nero).
 - Colonna destra   : note relative al capitolo selezionato.

Formato progetto: file .rwr = archivio tar.gz contenente
    01.md  01n.md   (testo capitolo 01 + sua nota)
    02.md  02n.md
    ...

Questo modulo e' stato portato da GTK 3 a GTK 4. Differenze principali:
  - Gtk.Application / Gtk.ApplicationWindow come struttura dell'app.
  - Menu costruiti con Gio.Menu + Gtk.PopoverMenuBar e GAction; le scorciatoie
    sono registrate con app.set_accels_for_action.
  - Dialoghi asincroni (Dialog.run() non esiste piu' in GTK 4): si usano
    finestre con il nostro tema (leggibili in chiaro e scuro) e callback, e
    Gtk.FileDialog per aprire/salvare.
  - set_child()/append() al posto di add()/pack_start().
  - CSS applicato per-display (add_provider_for_display).
  - Lista capitoli con Gtk.ListView + Gtk.StringList + Gtk.SingleSelection.
  - Eventi tramite controller (GestureClick) invece dei segnali event.
"""

import os
import sys
import json
import locale

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Pango, GLib, Gio, GObject
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
#   Debian/Ubuntu (libspelling): sudo apt install gir1.2-libspelling-1 \
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
    APP_NAME, APP_VERSION, APP_VERSION_SHORT, APP_AUTHOR,
    TYPEWRITER_FAMILY, TYPEWRITER_FILE, TYPEWRITER_FILES,
    SERIF_FAMILY, SERIF_FILE, SERIF_FILES,
    MIN_FONT_SIZE, MAX_FONT_SIZE,
    FRONT_FIELDS, COLO_FIELDS,
    PDF_PAGE_SIZES, PDF_DEFAULT_PAGE_SIZE, PDF_PAGE_SIZE_LABELS,
    Chapter, Project, write_pdf, read_ttf_metrics,
)
from .model import (
    PLUM, PLUM_DARK, PLUM_LIGHT, WHITE,
    PLUM_NIGHT, PLUM_PANEL, PLUM_INK, PLUM_GLOW, PAPER,
    build_css,
)
from . import i18n as pw_i18n
from .i18n import (Translator, LANGUAGES, available_languages,
                   ensure_language_files, spell_locale_for, SPELL_LOCALES,
                   COMPLETE_LANGUAGES)

APP_ID = "org.ruscalinux.RuscaWriter"
# Indirizzi pubblici del progetto, mostrati nel dialogo Informazioni.
APP_WEBSITE = "https://www.ruscalinux.org/ruscawriter/"
APP_SOURCE = "https://github.com/ruscalinux-dev/ruscawriter"
# Data di rilascio di questa build (anno, mese, giorno). La rappresentazione
# leggibile viene composta nella lingua dell'interfaccia tramite i nomi dei mesi
# tradotti (chiavi "month_1"... "month_12") e il pattern "date_format" presenti
# nei file di lingua; in mancanza, si ripiega sull'inglese e infine sull'ISO.
APP_DATE = (2026, 6, 14)
# stringhe di riserva (usate solo se mancano le chiavi tradotte dei mesi)
APP_DATE_IT = "14 Giugno 2026"
APP_DATE_EN = "June 14, 2026"

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
        self._is_fullscreen = False

        # ultimo formato pagina PDF usato (ricordato tra le sessioni); se il
        # valore salvato non e' tra quelli validi, ripiega sul predefinito.
        saved_size = self.settings.get("pdf_page_size", PDF_DEFAULT_PAGE_SIZE)
        self._pdf_page_size = (saved_size if saved_size in PDF_PAGE_SIZES
                               else PDF_DEFAULT_PAGE_SIZE)

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
        # prepara le liste di elisione di Enchant PRIMA di creare il checker,
        # cosi' libspelling le trova gia' pronte (vedi ensure_elision_dictionaries)
        self._ensure_elision_for_spell()
        self._setup_spell()
        self._retranslate()

        self.connect("close-request", self.on_close_request)
        self.connect("notify::default-width", self._on_size_changed)
        self.connect("notify::default-height", self._on_size_changed)
        self.connect("notify::fullscreened", self._on_fullscreen_changed)

        GLib.idle_add(self._apply_layout)
        GLib.idle_add(self._finish_restore)
        GLib.idle_add(self._startup_dialog)
        # All'apertura, dai il focus all'area di scrittura: senza questo il
        # primo widget focusabile (lo SpinButton del font) riceverebbe il focus
        # e mostrerebbe il numero "14" tutto selezionato/evidenziato.
        GLib.idle_add(self._focus_editor)
        self._autosave_id = GLib.timeout_add_seconds(60, self._autosave_tick)

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

    def on_toggle_dark(self, *_):
        self.dark_mode = not self.dark_mode
        self.theme_pref = "dark" if self.dark_mode else "light"
        self.settings["theme"] = self.theme_pref
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
        css = build_css(dark=getattr(self, "dark_mode", False))
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
                                "gir1.2-libspelling-1, oppure gir1.2-gspell-2)")
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

    def _apply_layout(self):
        # La visibilita' dei pannelli va impostata SEMPRE, anche se la larghezza
        # non e' ancora nota (durante le transizioni fullscreen puo' essere <=1):
        # altrimenti, uscendo dalla modalita' concentrazione, i pannelli non
        # riapparirebbero.
        self.left_panel.set_visible(self.left_visible)
        self.right_panel.set_visible(self.right_visible)
        total = self._content_width()
        if total <= 1:
            return False
        if not self.left_visible:
            left_w = 0
        else:
            left_w = self.settings.get("left_px") or int(total * LEFT_FRAC)
            left_w = max(LEFT_MIN_PX, min(left_w, int(total * 0.4)))
        if not self.right_visible:
            right_w = 0
        else:
            right_w = self.settings.get("right_px") or int(total * RIGHT_FRAC)
            right_w = max(RIGHT_MIN_PX, min(right_w, int(total * 0.4)))
        self.paned_outer.set_position(left_w)
        inner_w = max(1, total - left_w)
        self.paned_inner.set_position(inner_w - right_w)
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
        if added:
            # seleziona l'ultimo capitolo importato
            idx = self.project.chapters.index(last_ch) if last_ch else 0
            self._refresh_chapter_list(idx)
            self._mark_dirty()
            self._info(self.t("imported_n", n=added))
        if skipped:
            self._error(self.t("import_skipped", files=", ".join(skipped)))
        return added

    def _update_reading_margins(self):
        w = self.text_view.get_allocated_width()
        if w <= 1:
            return
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

    def on_divider_moved(self, paned, _param):
        if self._restoring:
            return
        total = self._content_width()
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
            ("setdate",      self.on_update_cover_date, []),
            ("toggle_left",  self.on_toggle_left,    ["<Control>l"]),
            ("toggle_right", self.on_toggle_right,   ["<Control>r"]),
            ("fullscreen",   self.on_toggle_fullscreen, ["F11"]),
            ("font_inc",     self.on_font_increase,
             ["<Control>plus", "<Control>equal", "<Control>KP_Add"]),
            ("font_dec",     self.on_font_decrease,
             ["<Control>minus", "<Control>KP_Subtract"]),
            ("preview",      self.on_toggle_preview, ["<Control>e"]),
            ("preview_all",  self.on_toggle_preview_whole, ["<Control><Shift>e"]),
            ("dark",         self.on_toggle_dark,    ["<Control><Shift>d"]),
            ("goal",         self.on_set_goal,       []),
            ("about",        self.on_info,           ["F1"]),
        ]
        for name, handler, accels in simple:
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda a, p, h=handler: h())
            self.add_action(act)
            if accels:
                self.app.set_accels_for_action("win." + name, accels)

        lang_act = Gio.SimpleAction.new_stateful(
            "ui_lang", GLib.VariantType.new("s"), GLib.Variant("s", self.lang))
        lang_act.connect("activate", self._on_lang_action)
        self.add_action(lang_act)
        self._lang_action = lang_act

    def _on_lang_action(self, action, param):
        code = param.get_string()
        action.set_state(param)
        self.on_ui_lang_changed(code)

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
        m_edit.append_section(None, s3)
        s4 = Gio.Menu()
        s4.append(self.t("mi_setdate"), "win.setdate")
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
        v4.append(self.t("mi_dark"), "win.dark")
        v4.append(self.t("mi_goal"), "win.goal")
        m_view.append_section(None, v4)
        # Sottomenu lingua: prima le lingue tradotte per intero, poi (in una
        # sezione separata) quelle non ancora tradotte, marcate con un suffisso,
        # cosi' e' chiaro che l'interfaccia restera' in inglese (ripiego).
        m_lang = Gio.Menu()
        complete_sec = Gio.Menu()
        partial_sec = Gio.Menu()
        not_translated = self.t("lang_untranslated")
        for code, native in available_languages():
            if code in COMPLETE_LANGUAGES:
                item = Gio.MenuItem.new(native, None)
                item.set_action_and_target_value(
                    "win.ui_lang", GLib.Variant("s", code))
                complete_sec.append_item(item)
            else:
                label = f"{native} — {not_translated}"
                item = Gio.MenuItem.new(label, None)
                item.set_action_and_target_value(
                    "win.ui_lang", GLib.Variant("s", code))
                partial_sec.append_item(item)
        m_lang.append_section(None, complete_sec)
        m_lang.append_section(self.t("lang_partial_header"), partial_sec)
        m_view.append_submenu(self.t("mi_language"), m_lang)
        menubar.append_submenu(self.t("menu_view"), m_view)

        m_help = Gio.Menu()
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

        datebar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        datebar.add_css_class("rusca-toolbar")
        self.btn_setdate = Gtk.Button()
        self.btn_setdate.set_hexpand(True)
        self.btn_setdate.connect("clicked", self.on_update_cover_date)
        datebar.append(self.btn_setdate)
        left.append(datebar)

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
        head_color = PLUM_GLOW if getattr(self, "dark_mode", False) else PLUM_DARK
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
                "code", family="monospace",
                foreground=PLUM_GLOW if getattr(self, "dark_mode", False) else "#7A3B72"),
            "marker": self.text_buffer.create_tag("marker", foreground=PLUM_LIGHT),
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
        head_color = PLUM_GLOW if getattr(self, "dark_mode", False) else PLUM_DARK
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
        head_color = PLUM_GLOW if self.dark_mode else PLUM_DARK
        for name in ("h1", "h2", "h3"):
            try:
                self._md_tags[name].set_property("foreground", head_color)
                self._pv_tags[name].set_property("foreground", head_color)
            except Exception:
                pass
        try:
            self._md_tags["code"].set_property(
                "foreground", PLUM_GLOW if self.dark_mode else "#7A3B72")
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

    def _retranslate(self):
        self._rebuild_menubar()
        try:
            self._lang_action.set_state(GLib.Variant("s", self.lang))
        except Exception:
            pass
        self.btn_up.set_label(self.t("btn_up"))
        self.btn_down.set_label(self.t("btn_down"))
        self.btn_setdate.set_label(self.t("btn_setdate"))
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
        self.center_title.set_text(self.t("empty_hint"))
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

    def on_select_chapter(self, selection, position=None, n_items=None):
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
        import re
        buf = self.text_buffer
        start, end = buf.get_bounds()
        for tag in self._md_tags.values():
            buf.remove_tag(tag, start, end)
        text = buf.get_text(start, end, True)

        def apply(tag_name, a, b):
            ia = buf.get_iter_at_offset(a)
            ib = buf.get_iter_at_offset(b)
            buf.apply_tag(self._md_tags[tag_name], ia, ib)

        offset = 0
        for line in text.split("\n"):
            stripped = line.lstrip()
            mh = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if mh:
                level = len(mh.group(1))
                tag = "h1" if level == 1 else ("h2" if level == 2 else "h3")
                apply(tag, offset, offset + len(line))
            else:
                for mt in re.finditer(r"\*\*\*(.+?)\*\*\*|"
                                      r"\*\*(.+?)\*\*|"
                                      r"\*(.+?)\*|"
                                      r"`(.+?)`", line):
                    a = offset + mt.start()
                    b = offset + mt.end()
                    if mt.group(1) is not None:
                        apply("bolditalic", a, b)
                    elif mt.group(2) is not None:
                        apply("bold", a, b)
                    elif mt.group(3) is not None:
                        apply("italic", a, b)
                    else:
                        apply("code", a, b)
            offset += len(line) + 1

    def on_note_changed(self, buf):
        if self._loading or self.current is None:
            return
        s, e = buf.get_bounds()
        self.current.note = buf.get_text(s, e, True)
        self._mark_dirty()

    # ---- helper dialoghi asincroni -----------------------------------------
    def _message_dialog(self, title, body):
        """Mostra un messaggio in una finestra con il nostro tema (leggibile sia
        in chiaro sia in scuro). Sostituisce Gtk.AlertDialog, il cui testo del
        messaggio non e' raggiunto dal nostro CSS e nel tema scuro risulta poco
        leggibile."""
        dialog = Gtk.Window(transient_for=self, modal=True)
        dialog.add_css_class("rusca-dialog")
        dialog.set_title(title or "")
        dialog.set_resizable(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(20); box.set_margin_end(20)
        box.add_css_class("rusca-bg")
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
        dialog.set_child(box)
        dialog.set_default_widget(btn)
        dialog.present()
        GLib.idle_add(self._raise_dialog, dialog)
        btn.grab_focus()

    def _info(self, msg):
        self._message_dialog(None, msg)

    def _error(self, msg):
        self._message_dialog(self.t("error_title"), msg)

    def _ask_text(self, title, prompt, initial, on_ok):
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
        entry = Gtk.Entry()
        entry.set_text(initial or "")
        entry.set_activates_default(True)
        box.append(entry)
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                       halign=Gtk.Align.END)
        b_cancel = Gtk.Button(label=self.t("cancel"))
        b_ok = Gtk.Button(label=self.t("ok"))
        b_ok.add_css_class("suggested-action")
        btns.append(b_cancel); btns.append(b_ok)
        box.append(btns)
        dialog.set_child(box)
        dialog.set_default_widget(b_ok)

        def confirm(*_):
            text = entry.get_text()
            dialog.destroy()
            on_ok(text)

        b_cancel.connect("clicked", lambda *_: dialog.destroy())
        b_ok.connect("clicked", confirm)
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
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                       halign=Gtk.Align.END)
        b_cancel = Gtk.Button(label=self.t("cancel"))
        b_ok = Gtk.Button(label=self.t("ok"))
        b_ok.add_css_class("suggested-action")
        btns.append(b_cancel); btns.append(b_ok)
        box.append(btns)
        dialog.set_child(box)
        dialog.set_default_widget(b_ok)

        def confirm(*_):
            val = int(spin.get_value())
            dialog.destroy()
            on_ok(val)

        b_cancel.connect("clicked", lambda *_: dialog.destroy())
        b_ok.connect("clicked", confirm)
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
        dialog = Gtk.Window(transient_for=self, modal=True)
        dialog.add_css_class("rusca-dialog")
        dialog.set_title(title or "")
        dialog.set_resizable(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(20); box.set_margin_end(20)
        box.add_css_class("rusca-bg")
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

    def _save_file_dialog(self, title, suggested_name, patterns, filter_name, on_path):
        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        dialog.set_initial_name(suggested_name)
        if patterns:
            flt = Gtk.FileFilter()
            flt.set_name(filter_name)
            for p in patterns:
                flt.add_pattern(p)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(flt)
            dialog.set_filters(filters)
            dialog.set_default_filter(flt)

        def done(d, result):
            try:
                gfile = d.save_finish(result)
            except GLib.Error:
                return
            if gfile is not None:
                on_path(gfile.get_path())

        dialog.save(self, None, done)

    def _open_file_dialog(self, title, patterns, filter_name, on_path):
        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        if patterns:
            flt = Gtk.FileFilter()
            flt.set_name(filter_name)
            for p in patterns:
                flt.add_pattern(p)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(flt)
            dialog.set_filters(filters)
            dialog.set_default_filter(flt)

        def done(d, result):
            try:
                gfile = d.open_finish(result)
            except GLib.Error:
                return
            if gfile is not None:
                on_path(gfile.get_path())

        dialog.open(self, None, done)

    def _open_files_dialog(self, title, patterns, filter_name, on_paths):
        """Come _open_file_dialog ma permette di selezionare piu' file insieme;
        chiama on_paths(lista_di_percorsi)."""
        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        if patterns:
            flt = Gtk.FileFilter()
            flt.set_name(filter_name)
            for p in patterns:
                flt.add_pattern(p)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(flt)
            dialog.set_filters(filters)
            dialog.set_default_filter(flt)

        def done(d, result):
            try:
                files = d.open_multiple_finish(result)
            except GLib.Error:
                return
            paths = []
            for i in range(files.get_n_items()):
                gf = files.get_item(i)
                try:
                    p = gf.get_path()
                except Exception:
                    p = None
                if p:
                    paths.append(p)
            if paths:
                on_paths(paths)

        dialog.open_multiple(self, None, done)

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

    def on_update_cover_date(self, *_):
        row = self._current_index()
        if row < 0 or not self.project.chapters[row].is_cover:
            self._error(self.t("setdate_only_cover"))
            return
        self._commit_current()
        self.project.update_cover_date()
        self.current = self.project.chapters[row]
        self._loading = True
        self.text_buffer.set_text(self.current.text)
        self._loading = False
        self._mark_dirty()
        self._info(self.t("date_updated"))

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
                blocks_start = text.lstrip().split("\n", 1)[0] if text.strip() else ""
                if not blocks_start.startswith("#"):
                    buf.insert_with_tags(buf.get_end_iter(),
                                         ch_title + "\n", self._pv_tags["h1"])
                self._render_markdown_into(text)
        else:
            text = self.current.text if self.current is not None else ""
            self._render_markdown_into(text)

    def _render_markdown_into(self, text):
        import re
        buf = self.preview_buffer

        def insert_inline(line, base_tags):
            pattern = re.compile(
                r"(\*\*\*|___)(.+?)\1"
                r"|(\*\*|__)(.+?)\3"
                r"|(\*|_)(.+?)\5"
                r"|`(.+?)`")
            pos = 0
            for m in pattern.finditer(line):
                if m.start() > pos:
                    buf.insert_with_tags(buf.get_end_iter(),
                                         line[pos:m.start()], *base_tags)
                if m.group(2) is not None:
                    tag = self._pv_tags["bolditalic"]; content = m.group(2)
                elif m.group(4) is not None:
                    tag = self._pv_tags["bold"]; content = m.group(4)
                elif m.group(6) is not None:
                    tag = self._pv_tags["italic"]; content = m.group(6)
                else:
                    tag = self._pv_tags["code"]; content = m.group(7)
                buf.insert_with_tags(buf.get_end_iter(), content, tag, *base_tags)
                pos = m.end()
            if pos < len(line):
                buf.insert_with_tags(buf.get_end_iter(), line[pos:], *base_tags)

        for raw in text.split("\n"):
            s = raw.rstrip("\n")
            stripped = s.strip()
            m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if m:
                lvl = min(3, len(m.group(1)))
                tag = self._pv_tags[f"h{lvl}"]
                buf.insert_with_tags(buf.get_end_iter(), m.group(2) + "\n", tag)
            elif stripped[:2] in ("- ", "* ", "+ "):
                buf.insert(buf.get_end_iter(), "  •  ")
                insert_inline(stripped[2:], [])
                buf.insert(buf.get_end_iter(), "\n")
            elif re.match(r"^\d+\.\s+", stripped):
                num = stripped.split(".", 1)[0]
                buf.insert(buf.get_end_iter(), f"  {num}.  ")
                insert_inline(re.sub(r"^\d+\.\s+", "", stripped), [])
                buf.insert(buf.get_end_iter(), "\n")
            elif stripped.startswith(">"):
                insert_inline(stripped.lstrip(">").strip(),
                              [self._pv_tags["quote"]])
                buf.insert(buf.get_end_iter(), "\n")
            else:
                insert_inline(s, [])
                buf.insert(buf.get_end_iter(), "\n")

    # ---- informazioni -------------------------------------------------------
    def on_edit_sections(self, *_):
        """Dialogo per gestire le tre sezioni editoriali: immagine di copertina,
        frontespizio e colophon. Le modifiche vengono applicate al progetto solo
        quando si preme Salva."""
        dialog = Gtk.Window(transient_for=self, modal=True)
        dialog.add_css_class("rusca-dialog")
        dialog.set_title(self.t("sections_title"))
        dialog.set_default_size(560, 640)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(16); outer.set_margin_bottom(16)
        outer.set_margin_start(18); outer.set_margin_end(18)
        outer.add_css_class("rusca-bg")

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
        b_remove = Gtk.Button(label=self.t("sec_cover_remove"))

        def do_attach():
            def on_path(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    low = path.lower()
                    if low.endswith((".jpg", ".jpeg")):
                        fmt = "jpeg"
                    elif low.endswith(".png"):
                        fmt = "png"
                    else:
                        # determina dal contenuto: PNG inizia con \x89PNG
                        fmt = "png" if data[:4] == b"\x89PNG" else "jpeg"
                    pending["image"] = data
                    pending["fmt"] = fmt
                    refresh_preview()
                except Exception as exc:
                    self._error(self.t("err_open", e=exc))
            self._open_file_dialog(self.t("sec_cover_attach"),
                                   ["*.png", "*.jpg", "*.jpeg"],
                                   self.t("filter_image"), on_path)

        def do_remove():
            pending["image"] = None
            pending["fmt"] = None
            refresh_preview()

        b_attach.connect("clicked", lambda *_: do_attach())
        b_remove.connect("clicked", lambda *_: do_remove())
        btnrow.append(b_attach)
        btnrow.append(b_remove)
        body.append(btnrow)

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
        dialog = Gtk.Window(transient_for=self, modal=True)
        dialog.add_css_class("rusca-dialog")
        dialog.set_title(self.t("mi_about"))
        dialog.set_default_size(460, 520)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(20); box.set_margin_bottom(20)
        box.set_margin_start(24); box.set_margin_end(24)
        box.add_css_class("rusca-bg")

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

    # ---- export -------------------------------------------------------------
    def on_export(self, *_):
        self._commit_current()
        self._save_file_dialog(self.t("dlg_export_title"),
                               f"{self.project.title}.txt", None, None,
                               self._do_export_txt)

    def _do_export_txt(self, path):
        if not path.endswith(".txt"):
            path += ".txt"
        try:
            self.project.export_txt(path)
            self._info(self.t("exported", p=path))
        except Exception as exc:
            self._error(self.t("err_export", e=exc))

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

        def choose(size_key):
            self._pdf_page_size = size_key
            # ricorda la scelta tra le sessioni
            self.settings["pdf_page_size"] = size_key
            try:
                save_settings(self.settings)
            except Exception:
                pass
            self._save_file_dialog(self.t("dlg_export_pdf_title"),
                                   f"{self.project.title}.pdf", ["*.pdf"],
                                   self.t("filter_pdf"), self._do_export_pdf)

        dialog = Gtk.Window(transient_for=self, modal=True)
        dialog.add_css_class("rusca-dialog")
        dialog.set_title(self._t_or("dlg_pdf_size_title", "Formato pagina"))
        dialog.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(20); box.set_margin_end(20)
        box.add_css_class("rusca-bg")

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

        def finish(size_key):
            if state["done"]:
                return
            state["done"] = True
            dialog.destroy()
            if size_key is not None:
                GLib.idle_add(lambda: (choose(size_key), False)[1])

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
            for style, ffile in SERIF_FILES.items():
                metrics = read_ttf_metrics(os.path.join(here, ffile))
                if metrics:
                    embed_fonts[style] = metrics
            if "regular" in embed_fonts:
                fname = "EBGaramond"
            else:
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
                                                      PDF_DEFAULT_PAGE_SIZE))
            self._info(self.t("exported", p=path))
        except Exception as exc:
            self._error(self.t("err_export", e=exc))

    def on_export_epub(self, *_):
        self._commit_current()
        self._save_file_dialog(self.t("dlg_export_epub_title"),
                               f"{self.project.title}.epub", ["*.epub"],
                               self.t("filter_epub"), self._do_export_epub)

    def _do_export_epub(self, path):
        if not path.endswith(".epub"):
            path += ".epub"
        try:
            self.project.export_epub(path)
            self._info(self.t("exported", p=path))
        except Exception as exc:
            self._error(self.t("err_export", e=exc))

    def _export_simple(self, ext, filter_key, method):
        self._commit_current()

        def on_path(path):
            if not path.endswith("." + ext):
                path += "." + ext
            try:
                method(path)
                self._info(self.t("exported", p=path))
            except Exception as exc:
                self._error(self.t("err_export", e=exc))

        self._save_file_dialog(self.t("export"),
                               f"{self.project.title}.{ext}", [f"*.{ext}"],
                               self.t(filter_key), on_path)

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
        dialog = Gtk.Window(transient_for=self, modal=True)
        dialog.add_css_class("rusca-dialog")
        dialog.set_title(f"{APP_NAME} v{APP_VERSION}")
        dialog.set_default_size(420, 360)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(24); box.set_margin_bottom(24)
        box.set_margin_start(24); box.set_margin_end(24)
        box.add_css_class("rusca-bg")
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
