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
EN — RuscaWriter data model and document generation.

This module is INDEPENDENT from the graphical interface (it never imports
GTK): it holds the project structure (Chapter, Project), the native PDF
writer (write_pdf) and every export (TXT, Markdown, PDF, EPUB, ODT, DOCX,
HTML, AZW3), plus the helpers for the images attached to chapters
(PNG/JPEG/WebP). Being separate from the GUI, it can be tested on its own
and reused by other tools (scripts, batch conversions, etc.).

IT — Modello dati e generazione documenti di RuscaWriter.

Questo modulo è INDIPENDENTE dall'interfaccia grafica (non importa mai GTK):
contiene la struttura del progetto (Chapter, Project), il generatore PDF
nativo (write_pdf) e tutti gli export (TXT, Markdown, PDF, EPUB, ODT, DOCX,
HTML, AZW3), oltre agli helper per le immagini allegate ai capitoli
(PNG/JPEG/WebP). Essendo separato dalla GUI, può essere testato da solo ed
essere riusato da altri strumenti (script, conversioni batch, ecc.).
"""
import os
import io
import re
import json
import struct
import shutil
import tarfile
import tempfile

# EN: optional hyphenation support via Pyphen. Two things are needed and both
#     are OPTIONAL: (1) the Pyphen library (Debian "python3-pyphen") and (2) a
#     hyphenation DICTIONARY for the language. The Debian package of Pyphen
#     ships WITHOUT dictionaries and pulls them from the system "hyphen-*"
#     packages (e.g. "hyphen-it", "hyphen-en-us") under /usr/share/hyphen/;
#     the PyPI/pip package instead bundles its own. So on Debian/Ubuntu the
#     user typically needs BOTH python3-pyphen AND a hyphen-<lang> package.
#     When either is missing the PDF export still works: the "hyphenate"
#     option is simply unavailable (the GUI disables it, see editor.py) and we
#     never crash.
# IT: supporto opzionale alla sillabazione tramite Pyphen. Servono due cose,
#     entrambe OPZIONALI: (1) la libreria Pyphen (pacchetto Debian
#     "python3-pyphen") e (2) un DIZIONARIO di sillabazione per la lingua. Il
#     pacchetto Debian di Pyphen NON include i dizionari e li prende dai
#     pacchetti di sistema "hyphen-*" (es. "hyphen-it", "hyphen-en-us") sotto
#     /usr/share/hyphen/; il pacchetto PyPI/pip include invece i propri. Quindi
#     su Debian/Ubuntu di norma servono SIA python3-pyphen SIA un pacchetto
#     hyphen-<lingua>. Se manca l'uno o l'altro l'export PDF funziona lo
#     stesso: l'opzione "sillaba" e' semplicemente non disponibile (la GUI la
#     disattiva, vedi editor.py) e non falliamo mai.
try:
    import pyphen as _pyphen
    HAVE_PYPHEN = True
except Exception:
    _pyphen = None
    HAVE_PYPHEN = False

# cache dei dizionari di sillabazione gia' creati, per lingua (crearli e' caro)
_HYPHEN_DICTS = {}


def get_hyphenator(lang="it"):
    """EN: Return a cached Pyphen hyphenator for 'lang' (e.g. "it", "en_US"),
    or None if Pyphen is missing OR no dictionary exists for the language (for
    instance python3-pyphen installed without any hyphen-<lang> package).
    Pyphen accepts both "it" and "it_IT"; we try progressively broader codes.
    IT: Restituisce un sillabatore Pyphen (in cache) per 'lang' (es. "it",
    "en_US"), oppure None se Pyphen manca OPPURE non esiste un dizionario per
    quella lingua (per esempio python3-pyphen installato senza alcun pacchetto
    hyphen-<lingua>). Pyphen accetta sia "it" sia "it_IT"; proviamo codici via
    via piu' generici."""
    if not HAVE_PYPHEN:
        return None
    key = lang or "it"
    if key in _HYPHEN_DICTS:
        return _HYPHEN_DICTS[key]
    dic = None
    for cand in (key, key.split("_")[0], key.split("-")[0]):
        try:
            dic = _pyphen.Pyphen(lang=cand)
            break
        except Exception:
            dic = None
    _HYPHEN_DICTS[key] = dic
    return dic


def hyphenation_available(lang="it"):
    """EN: True only if hyphenation can actually be performed for 'lang' — i.e.
    Pyphen is importable AND a dictionary for the language is present. This is
    what the GUI should check to enable the "hyphenate" option, because having
    python3-pyphen without a hyphen-<lang> dictionary is not enough.
    IT: True solo se la sillabazione e' davvero eseguibile per 'lang' — cioe'
    Pyphen e' importabile E c'e' un dizionario per la lingua. E' cio' che la
    GUI deve controllare per abilitare l'opzione "sillaba", perche' avere
    python3-pyphen senza un dizionario hyphen-<lingua> non basta."""
    return get_hyphenator(lang) is not None


# --- costanti applicative condivise -----------------------------------------
APP_NAME = "RuscaWriter"

# ---------------------------------------------------------------------------
# UNICA FONTE di versione e data / SINGLE SOURCE of version and date.
# IT: per rilasciare una nuova versione basta cambiare le DUE righe qui sotto.
#     Tutto il resto — il titolo della finestra, il dialogo Informazioni, il
#     pacchetto .deb, la man page — ne deriva, e non va toccato a mano.
# EN: to cut a new release, change ONLY the two lines below. Everything else —
#     the window title, the About screen, the .deb package, the man page —
#     derives from them and must not be edited by hand.
# ---------------------------------------------------------------------------
APP_VERSION_SHORT = "0.99"
APP_RELEASE_DATE = (2026, 8, 13)         # (anno, mese, giorno) / (year, month, day)
# ---------------------------------------------------------------------------

# data in forma ISO e versione completa: calcolate, mai scritte a mano
APP_DATE_ISO = "%04d-%02d-%02d" % APP_RELEASE_DATE
APP_VERSION = "%s (%s)" % (APP_VERSION_SHORT, APP_DATE_ISO)
APP_AUTHOR = "Nunzio Curcuruto"

# Campi strutturati del frontespizio e del colophon. L'ordine e' anche l'ordine
# di impaginazione. Tutti i campi sono opzionali: quelli vuoti non compaiono.
FRONT_FIELDS = ["title", "subtitle", "author", "publisher", "place_year"]
COLO_FIELDS = ["copyright", "publisher", "isbn", "edition", "notes", "license"]

# Formati pagina disponibili per l'esportazione PDF. Dimensioni in punti
# tipografici (1/72 di pollice), come richiede il formato PDF. 1 cm ~= 28,35 pt;
# 1 pollice = 72 pt.
#   A5            = 148 x 210 mm  -> 420   x 595   pt  (narrativa/saggistica EU)
#   6x9 pollici   = 152 x 229 mm  -> 432   x 648   pt  (standard internaz./POD)
#   17x24 cm      = 170 x 240 mm  -> 482   x 680   pt  (saggistica densa/accademica)
#   A4            = 210 x 297 mm  -> 595   x 842   pt  (manuali, documenti, bozze)
#   5x8 pollici   = 127 x 203 mm  -> 360   x 576   pt  (tascabile narrativa)
#
# Ogni formato porta i propri margini, distinti tra:
#   inner  : margine INTERNO, lato rilegatura (piu' largo, cosi' il testo non
#            sparisce nella piega di una copertina incollata o cucita);
#   outer  : margine ESTERNO, lato del taglio (piu' stretto);
#   margin : margine verticale (alto/basso), uniforme.
# Sulle pagine recto (dispari) l'interno e' a sinistra, sul verso (pari) a
# destra: l'export se ne occupa da solo spostando il blocco di testo.
PDF_PAGE_SIZES = {
    "A5":    {"w": 420.0, "h": 595.0,
              "inner": 60.0, "outer": 42.0, "margin": 54.0},
    "6x9":   {"w": 432.0, "h": 648.0,
              "inner": 64.0, "outer": 45.0, "margin": 58.0},
    "17x24": {"w": 482.0, "h": 680.0,
              "inner": 70.0, "outer": 50.0, "margin": 62.0},
    "A4":    {"w": 595.0, "h": 842.0,
              "inner": 85.0, "outer": 65.0, "margin": 72.0},
    "5x8":   {"w": 360.0, "h": 576.0,
              "inner": 54.0, "outer": 38.0, "margin": 50.0},
}
PDF_DEFAULT_PAGE_SIZE = "A5"

# Etichette leggibili dei formati, per il menu di scelta nell'interfaccia.
PDF_PAGE_SIZE_LABELS = {
    "A5":    "A5 (14,8 \u00d7 21 cm)",
    "6x9":   "6\u00d79\" (15,2 \u00d7 22,9 cm)",
    "17x24": "17 \u00d7 24 cm",
    "A4":    "A4 (21 \u00d7 29,7 cm)",
    "5x8":   "5\u00d78\" (12,7 \u00d7 20,3 cm)",
}

TYPEWRITER_FAMILY = "Courier Prime"
TYPEWRITER_FILE = "CourierPrime-Regular.ttf"
# varianti per il rendering di grassetto/corsivo nel PDF
TYPEWRITER_FILES = {
    "regular":    "CourierPrime-Regular.ttf",
    "bold":       "CourierPrime-Bold.ttf",
    "italic":     "CourierPrime-Italic.ttf",
    "bolditalic": "CourierPrime-BoldItalic.ttf",
}

# Font serif da lettura per i documenti ESPORTATI (PDF in primis): EB Garamond,
# un Garamond libero (licenza SIL Open Font License 1.1), molto più adatto a un
# libro/romanzo del monospace Courier Prime usato nell'editor. È proporzionale,
# quindi l'export PDF usa le larghezze reali dei glifi (widths_by_code).
SERIF_FAMILY = "EB Garamond"
SERIF_FILE = "EBGaramond-Regular.ttf"
SERIF_FILES = {
    "regular":    "EBGaramond-Regular.ttf",
    "bold":       "EBGaramond-Bold.ttf",
    "italic":     "EBGaramond-Italic.ttf",
    "bolditalic": "EBGaramond-BoldItalic.ttf",
}
DEFAULT_FONT_SIZE = 14
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 48

_TIMES_WIDTHS = {
    ' ': 250, '!': 333, '"': 408, '#': 500, '$': 500, '%': 833, '&': 778,
    "'": 180, '(': 333, ')': 333, '*': 500, '+': 564, ',': 250, '-': 333,
    '.': 250, '/': 278, '0': 500, '1': 500, '2': 500, '3': 500, '4': 500,
    '5': 500, '6': 500, '7': 500, '8': 500, '9': 500, ':': 278, ';': 278,
    '<': 564, '=': 564, '>': 564, '?': 444, '@': 921, 'A': 722, 'B': 667,
    'C': 667, 'D': 722, 'E': 611, 'F': 556, 'G': 722, 'H': 722, 'I': 333,
    'J': 389, 'K': 722, 'L': 611, 'M': 889, 'N': 722, 'O': 722, 'P': 556,
    'Q': 722, 'R': 667, 'S': 556, 'T': 611, 'U': 722, 'V': 722, 'W': 944,
    'X': 722, 'Y': 722, 'Z': 611, '[': 333, '\\': 278, ']': 333, '^': 469,
    '_': 500, '`': 333, 'a': 444, 'b': 500, 'c': 444, 'd': 500, 'e': 444,
    'f': 333, 'g': 500, 'h': 500, 'i': 278, 'j': 278, 'k': 500, 'l': 278,
    'm': 778, 'n': 500, 'o': 500, 'p': 500, 'q': 500, 'r': 333, 's': 389,
    't': 278, 'u': 500, 'v': 500, 'w': 722, 'x': 500, 'y': 500, 'z': 444,
    '{': 480, '|': 200, '}': 480, '~': 541,
}
_TIMES_DEFAULT_WIDTH = 500


def _char_width(ch, font_size):
    return _TIMES_WIDTHS.get(ch, _TIMES_DEFAULT_WIDTH) / 1000.0 * font_size


def _text_width(s, font_size, advance1000=None, widths_by_code=None):
    """Larghezza del testo in punti.

    - widths_by_code: dict {codice WinAnsi -> larghezza in 1/1000 em} per i font
      proporzionali incorporati (es. EB Garamond): usa la larghezza reale di
      ogni carattere. È il caso più preciso e ha la precedenza.
    - advance1000: larghezza fissa per glifo (font monospace, es. Courier).
    - altrimenti: metriche Times di ripiego."""
    if widths_by_code is not None:
        total = 0.0
        default = advance1000 if advance1000 is not None else 500
        for ch in s:
            try:
                code = ord(ch.encode("cp1252", "replace").decode("cp1252"))
            except Exception:
                code = None
            w = widths_by_code.get(code, default) if code is not None else default
            total += w
        return total / 1000.0 * font_size
    if advance1000 is not None:
        return len(s) * advance1000 / 1000.0 * font_size
    return sum(_char_width(c, font_size) for c in s)


def _parse_cmap_unicode(data, cmap_off):
    """Estrae una mappa {codepoint Unicode -> glyph id} da una tabella cmap.
    Supporta i formati 4 (BMP) e 12 (full Unicode), i piu' comuni. Restituisce
    un dict, eventualmente vuoto se nessuna sottotabella e' utilizzabile."""
    mapping = {}
    try:
        ntab = struct.unpack(">H", data[cmap_off+2:cmap_off+4])[0]
        best = None   # (preferenza, offset_sottotabella)
        for i in range(ntab):
            rec = cmap_off + 4 + i*8
            plat, enc = struct.unpack(">HH", data[rec:rec+4])
            sub_off = struct.unpack(">I", data[rec+4:rec+8])[0]
            # preferenza: Windows BMP/UCS4 (3,1)/(3,10) e Unicode (0,*)
            pref = {(3,10):4, (0,6):4, (3,1):3, (0,4):3, (0,3):3}.get(
                (plat, enc), 1 if plat == 0 else 0)
            if best is None or pref > best[0]:
                best = (pref, cmap_off + sub_off)
        if best is None:
            return mapping
        off = best[1]
        fmt = struct.unpack(">H", data[off:off+2])[0]
        if fmt == 4:
            segx2 = struct.unpack(">H", data[off+6:off+8])[0]
            segc = segx2 // 2
            p = off + 14
            ends = struct.unpack(">%dH" % segc, data[p:p+segx2]); p += segx2 + 2
            starts = struct.unpack(">%dH" % segc, data[p:p+segx2]); p += segx2
            deltas = struct.unpack(">%dh" % segc, data[p:p+segx2]); p += segx2
            range_off_pos = p
            ranges = struct.unpack(">%dH" % segc, data[p:p+segx2])
            for s in range(segc):
                start, end, delta, ro = starts[s], ends[s], deltas[s], ranges[s]
                if start == 0xFFFF:
                    continue
                for c in range(start, end+1):
                    if ro == 0:
                        g = (c + delta) & 0xFFFF
                    else:
                        gi = range_off_pos + s*2 + ro + (c - start)*2
                        if gi+2 > len(data):
                            continue
                        g = struct.unpack(">H", data[gi:gi+2])[0]
                        if g != 0:
                            g = (g + delta) & 0xFFFF
                    if g != 0:
                        mapping[c] = g
        elif fmt == 12:
            ngroups = struct.unpack(">I", data[off+12:off+16])[0]
            p = off + 16
            for _ in range(ngroups):
                sc, ec, sg = struct.unpack(">III", data[p:p+12]); p += 12
                for c in range(sc, ec+1):
                    mapping[c] = sg + (c - sc)
    except Exception:
        return {}
    return mapping


# ---------------------------------------------------------------------------
# EN: SYSTEM FONTS.
#     RuscaWriter ships two fonts — a typewriter one for the writing area and a
#     reading serif for the exports — and they stay the default. But a person
#     writing a book may well own the face they want, so the fonts installed on
#     the machine are offered too.
#
#     Only TrueType (.ttf) families are listed: the PDF writer embeds glyph
#     outlines as TrueType, so an OpenType/CFF face could be shown on screen
#     but not put inside the PDF — better not to offer what cannot be honoured.
#
# IT: FONT DI SISTEMA.
#     RuscaWriter porta con se' due font — uno da macchina da scrivere per
#     l'area di scrittura e un serif da lettura per gli export — e restano i
#     predefiniti. Ma chi scrive un libro puo' benissimo avere gia' il
#     carattere che vuole, quindi si offrono anche i font installati sulla
#     macchina.
#
#     Si elencano SOLO le famiglie TrueType (.ttf): l'impaginatore PDF
#     incorpora i contorni dei glifi in formato TrueType, quindi un font
#     OpenType/CFF si vedrebbe a schermo ma non finirebbe nel PDF. Meglio non
#     offrire cio' che non si puo' mantenere.
# ---------------------------------------------------------------------------

# Cartelle in cui i sistemi tipo Unix tengono i font.
SYSTEM_FONT_DIRS = (
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.local/share/fonts"),
    os.path.expanduser("~/.fonts"),
)

# Come si chiamano i quattro stili nella tabella 'name' di un TTF.
_TTF_SUBFAMILY_TO_STYLE = {
    "regular": "regular", "book": "regular", "roman": "regular",
    "bold": "bold",
    "italic": "italic", "oblique": "italic",
    "bold italic": "bolditalic", "bolditalic": "bolditalic",
    "bold oblique": "bolditalic",
}


def read_ttf_names(path):
    """Nome della famiglia e dello stile di un file TTF, o (None, None).

    Legge SOLO l'intestazione e la tabella dei nomi, con due letture mirate:
    scorrere centinaia di font di sistema caricandoli interi sarebbe lento
    senza motivo."""
    try:
        with open(path, "rb") as f:
            testa = f.read(12)
            if len(testa) < 12 or testa[:4] not in (b"\x00\x01\x00\x00", b"true"):
                return (None, None)     # non e' un TrueType (potrebbe essere CFF)
            n_tab = struct.unpack(">H", testa[4:6])[0]
            elenco = f.read(16 * n_tab)
            offset = lunghezza = None
            for i in range(n_tab):
                voce = elenco[i * 16:(i + 1) * 16]
                if voce[:4] == b"name":
                    offset, lunghezza = struct.unpack(">II", voce[8:16])
                    break
            if offset is None:
                return (None, None)
            f.seek(offset)
            tabella = f.read(lunghezza)

        conteggio, area = struct.unpack(">HH", tabella[2:6])
        famiglia = stile = None
        for i in range(conteggio):
            rec = tabella[6 + i * 12:18 + i * 12]
            if len(rec) < 12:
                break
            plat, enc, _lang, nome_id, lung, off = struct.unpack(">HHHHHH", rec)
            if nome_id not in (1, 2):
                continue
            grezzo = tabella[area + off:area + off + lung]
            try:
                if plat == 3 or (plat == 0):        # Windows/Unicode: UTF-16BE
                    testo = grezzo.decode("utf-16-be", "ignore")
                else:                                # Macintosh: latin-1
                    testo = grezzo.decode("latin-1", "ignore")
            except Exception:
                continue
            testo = testo.strip()
            if not testo:
                continue
            if nome_id == 1 and famiglia is None:
                famiglia = testo
            elif nome_id == 2 and stile is None:
                stile = testo
        return (famiglia, stile)
    except Exception:
        return (None, None)


def system_font_families(dirs=None):
    """Famiglie TrueType installate sulla macchina.

    Restituisce {nome_famiglia: {stile: percorso}}, con stile fra 'regular',
    'bold', 'italic' e 'bolditalic'. Sono incluse solo le famiglie che hanno
    almeno il tondo: senza quello non si puo' impaginare niente.
    """
    trovate = {}
    for cartella in (dirs if dirs is not None else SYSTEM_FONT_DIRS):
        if not os.path.isdir(cartella):
            continue
        for radice, _sub, files in os.walk(cartella):
            for nome_file in files:
                if not nome_file.lower().endswith(".ttf"):
                    continue
                percorso = os.path.join(radice, nome_file)
                famiglia, sottofamiglia = read_ttf_names(percorso)
                if not famiglia:
                    continue
                stile = _TTF_SUBFAMILY_TO_STYLE.get(
                    (sottofamiglia or "regular").strip().lower())
                if stile is None:
                    continue
                trovate.setdefault(famiglia, {}).setdefault(stile, percorso)
    return {fam: stili for fam, stili in trovate.items() if "regular" in stili}


def font_files_for_family(famiglia, dirs=None):
    """Percorsi dei file di una famiglia di sistema, per stile. Dizionario
    vuoto se la famiglia non c'e' o non ha il tondo."""
    return system_font_families(dirs).get(famiglia, {})


def read_ttf_metrics(path):
    """Legge le metriche essenziali di un TTF (solo libreria standard).
    Restituisce un dict con i dati per incorporarlo in un PDF, oppure None.

    Per i font proporzionali (es. EB Garamond) estrae anche la larghezza di
    ogni carattere nell'intervallo WinAnsi 32..255, in 'widths_by_code', cosi'
    l'impaginazione del PDF e l'array /Widths usano la larghezza reale di ogni
    glifo invece di una larghezza fissa (che andrebbe bene solo per i
    monospace). 'advance1000' resta come ripiego."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        return None
    try:
        num_tables = struct.unpack(">H", data[4:6])[0]
        tables = {}
        off = 12
        for _ in range(num_tables):
            tag = data[off:off+4]
            t_off, t_len = struct.unpack(">II", data[off+8:off+16])
            tables[tag] = (t_off, t_len)
            off += 16

        def tbl(tag):
            o, l = tables[tag]
            return data[o:o+l]

        head = tbl(b"head")
        units_per_em = struct.unpack(">H", head[18:20])[0]
        x_min, y_min, x_max, y_max = struct.unpack(">hhhh", head[36:44])

        hhea = tbl(b"hhea")
        ascent, descent = struct.unpack(">hh", hhea[4:8])
        num_hmetrics = struct.unpack(">H", hhea[34:36])[0]

        hmtx = tbl(b"hmtx")
        # advance del primo glifo (per monospace e' la larghezza comune)
        adv0 = struct.unpack(">H", hmtx[0:2])[0]

        scale = 1000.0 / units_per_em

        # advance per ciascun glyph id: i primi num_hmetrics hanno valore
        # esplicito, gli altri ripetono l'ultimo (regola TrueType).
        def glyph_advance(gid):
            if gid < num_hmetrics:
                pos = gid * 4
            else:
                pos = (num_hmetrics - 1) * 4
            if pos + 2 > len(hmtx):
                return adv0
            return struct.unpack(">H", hmtx[pos:pos+2])[0]

        # larghezze per codice WinAnsi 32..255 tramite cmap (se disponibile)
        widths_by_code = None
        try:
            if b"cmap" in tables:
                cmap_off = tables[b"cmap"][0]
                uni2gid = _parse_cmap_unicode(data, cmap_off)
                if uni2gid:
                    wbc = {}
                    for code in range(32, 256):
                        # mappa il codice WinAnsi al suo codepoint Unicode
                        cp = _winansi_to_unicode(code)
                        gid = uni2gid.get(cp, 0)
                        adv = glyph_advance(gid) if gid else adv0
                        wbc[code] = int(round(adv * scale))
                    widths_by_code = wbc
        except Exception:
            widths_by_code = None

        result = {
            "data": data,
            "units_per_em": units_per_em,
            "bbox": [int(x_min*scale), int(y_min*scale),
                     int(x_max*scale), int(y_max*scale)],
            "ascent": int(ascent*scale),
            "descent": int(descent*scale),
            "advance1000": int(round(adv0*scale)),
        }
        if widths_by_code is not None:
            result["widths_by_code"] = widths_by_code
        return result
    except Exception:
        return None


def _wrap_line(line, font_size, max_width, advance1000=None, widths_by_code=None):
    """Spezza una riga in più righe che entrano in max_width (in punti)."""
    if not line.strip():
        return [""]
    def tw(s):
        return _text_width(s, font_size, advance1000, widths_by_code)
    words = line.split(" ")
    out, cur = [], ""
    for w in words:
        candidate = w if not cur else cur + " " + w
        if tw(candidate) <= max_width or not cur:
            # se una singola parola e' piu' larga della pagina, spezzala a forza
            if not cur and tw(w) > max_width:
                piece = ""
                for ch in w:
                    if tw(piece + ch) <= max_width or not piece:
                        piece += ch
                    else:
                        out.append(piece)
                        piece = ch
                cur = piece
            else:
                cur = candidate
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def _pdf_escape(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_escape_bytes(b):
    return (b.replace(b"\\", b"\\\\")
             .replace(b"(", b"\\(")
             .replace(b")", b"\\)"))


def _to_winansi(s):
    """Codifica una stringa in byte per WinAnsiEncoding (cp1252).
    I caratteri non rappresentabili vengono sostituiti con '?'."""
    return s.encode("cp1252", "replace")


def _winansi_to_unicode(code):
    """Converte un valore di byte WinAnsi (cp1252), 0..255, nel suo codepoint
    Unicode. Serve per mappare i codici dell'array /Widths del PDF ai glifi del
    font tramite la cmap Unicode. Per i codici non assegnati ripiega sul codice
    stesso."""
    try:
        return ord(bytes([code]).decode("cp1252"))
    except Exception:
        return code


# ---------------------------------------------------------------------------
# EN: THE MARKDOWN RULES, IN ONE PLACE.
#     Every part of the program that reads Markdown — the PDF typesetter, the
#     HTML and EPUB exports, the ODT and DOCX exports, the on-screen preview
#     and the live highlighting in the editor — asks these two functions:
#
#       classify_md_line(line)  what kind of line is this? (block level)
#       parse_inline(text)      where are bold, italic and code? (inline level)
#
#     Before, each of those six places carried its own copy of the rules, and
#     the copies had drifted apart: "#Title" without a space was a heading in
#     the PDF and a paragraph everywhere else, and "_italic_" was formatted on
#     export but not highlighted while typing. One source, one behaviour.
#
# IT: LE REGOLE DEL MARKDOWN, IN UN POSTO SOLO.
#     Ogni parte del programma che legge Markdown — l'impaginatore PDF, gli
#     export HTML ed EPUB, quelli ODT e DOCX, l'anteprima e l'evidenziazione
#     dal vivo nell'editor — interroga queste due funzioni:
#
#       classify_md_line(riga)  che tipo di riga e'? (livello blocco)
#       parse_inline(testo)     dove sono grassetto, corsivo e codice? (inline)
#
#     Prima ognuno di quei sei punti aveva la sua copia delle regole, e le
#     copie erano divergute: "#Titolo" senza spazio era un titolo nel PDF e un
#     paragrafo altrove, e "_corsivo_" veniva formattato in esportazione ma non
#     evidenziato mentre si scrive. Una fonte, un comportamento.
# ---------------------------------------------------------------------------

# Marcatori inline. Ogni alternativa richiede la coppia (apertura e chiusura):
# un asterisco solitario, come in "3 * 4", resta un asterisco e non fa
# scivolare in corsivo tutto il resto della riga.
_INLINE_RE = re.compile(
    r"(?P<bi>\*\*\*|___)(?P<bi_t>.+?)(?P=bi)"
    r"|(?P<b>\*\*|__)(?P<b_t>.+?)(?P=b)"
    r"|(?P<i>\*|_)(?P<i_t>.+?)(?P=i)"
    r"|`(?P<c_t>.+?)`"
)

# Link markdown [testo](indirizzo): del testo resta solo la parte leggibile.
_LINK_RE = re.compile(r"\[(.+?)\]\((.+?)\)")

# Regole di blocco: una riga per volta.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_NUMBER_RE = re.compile(r"^(\d+)\.\s+(.*)$")
_BULLET_PREFIXES = ("- ", "* ", "+ ")

# Stili inline possibili. 'code' e' un caso a se': dentro i backtick il testo
# resta letterale, senza altra formattazione.
INLINE_STYLES = ("regular", "bold", "italic", "bolditalic", "code")


def _style_name(bold, italic):
    if bold and italic:
        return "bolditalic"
    if bold:
        return "bold"
    if italic:
        return "italic"
    return "regular"


def _inline_tokens(s, bold=False, italic=False):
    """Percorre una stringa e produce i tratti formattati come (stile, testo),
    senza marcatori. La formattazione annidata funziona
    ("**grassetto con *corsivo* dentro**") perche' la funzione richiama se
    stessa sul contenuto."""
    pos = 0
    for m in _INLINE_RE.finditer(s):
        if m.start() > pos:
            yield (_style_name(bold, italic), s[pos:m.start()])
        if m.group("bi_t") is not None:
            yield from _inline_tokens(m.group("bi_t"), True, True)
        elif m.group("b_t") is not None:
            yield from _inline_tokens(m.group("b_t"), True, italic)
        elif m.group("i_t") is not None:
            yield from _inline_tokens(m.group("i_t"), bold, True)
        else:
            # codice: contenuto letterale, nessuna ricorsione
            yield ("code", m.group("c_t"))
        pos = m.end()
    if pos < len(s):
        yield (_style_name(bold, italic), s[pos:])


def link_display(etichetta, indirizzo):
    """Come si scrive un link in un libro: l'etichetta, poi l'indirizzo fra
    parentesi.

    NIENTE LINK CLICCABILI, e l'indirizzo SEMPRE IN CHIARO. Sono due facce
    della stessa scelta. Un link cliccabile puo' portare altrove da quel che
    l'etichetta promette, e in un documento che gira non e' un rischio da
    regalare a chi legge. Ma soprattutto: un libro si stampa, e su una pagina
    di carta nessuno clicca — se l'indirizzo non e' scritto, la fonte citata
    non e' raggiungibile. Prima veniva buttato via in silenzio.

    Se etichetta e indirizzo dicono gia' la stessa cosa non si ripete nulla.
    """
    etichetta = (etichetta or "").strip()
    indirizzo = (indirizzo or "").strip()
    if not indirizzo:
        return etichetta
    if not etichetta:
        return indirizzo
    # "vedi https://x.it" o "[https://x.it](https://x.it)": non raddoppiare
    nudo = indirizzo.split("://", 1)[-1].rstrip("/")
    if etichetta.rstrip("/").endswith(nudo) or nudo.endswith(etichetta.rstrip("/")):
        return etichetta
    return f"{etichetta} ({indirizzo})"


def parse_inline(text):
    """Spezza il testo in segmenti (testo, stile), stile in INLINE_STYLES.

    I link [testo](indirizzo) diventano "testo (indirizzo)": vedi
    link_display. Restituisce sempre almeno un segmento, così chi impagina non
    deve gestire la lista vuota."""
    text = _LINK_RE.sub(lambda m: link_display(m.group(1), m.group(2)), text)
    segments = [(t, st) for st, t in _inline_tokens(text) if t]
    return segments or [("", "regular")]


def inline_spans(text, base=0, bold=False, italic=False):
    """Posizioni dei tratti formattati nella riga così com'è scritta, marcatori
    compresi: (inizio, fine, stile).

    Serve all'evidenziazione nell'editor, che colora il testo sul posto e
    quindi ha bisogno delle posizioni vere, delimitatori inclusi: chi scrive
    "**forte**" si aspetta di vedere evidenziati anche gli asterischi. Un
    tratto annidato produce una voce propria, con lo stile combinato: chi
    colora sovrappone le due e ottiene, ad esempio, grassetto-corsivo."""
    spans = []
    for m in _INLINE_RE.finditer(text):
        if m.group("bi_t") is not None:
            inner, opener, nb, ni = m.group("bi_t"), m.group("bi"), True, True
        elif m.group("b_t") is not None:
            inner, opener, nb, ni = m.group("b_t"), m.group("b"), True, italic
        elif m.group("i_t") is not None:
            inner, opener, nb, ni = m.group("i_t"), m.group("i"), bold, True
        else:
            # codice: nessun annidamento da esplorare
            spans.append((base + m.start(), base + m.end(), "code"))
            continue
        spans.append((base + m.start(), base + m.end(), _style_name(nb, ni)))
        spans.extend(inline_spans(inner, base + m.start() + len(opener), nb, ni))
    return spans


def _parse_inline_md(text):
    """Come parse_inline, ma il codice viene reso in tondo: l'impaginatore PDF
    conosce solo tondo, grassetto, corsivo e grassetto-corsivo."""
    return [(t, "regular" if st == "code" else st) for t, st in parse_inline(text)]


def _strip_inline_md(text):
    """Restituisce il solo testo senza i marcatori inline markdown."""
    return "".join(seg for seg, _ in parse_inline(text))


def classify_md_line(raw_line):
    """Riconosce il tipo di una riga di Markdown.

    Restituisce (tipo, corpo, extra):

        ("blank",   "",          None)      riga vuota
        ("image",   didascalia,  nome)      ![didascalia](nome)
        ("heading", testo,       livello)   # ... ###### (lo spazio e' d'obbligo)
        ("bullet",  testo,       None)      - * +
        ("number",  testo,       "3")       3. testo
        ("quote",   testo,       None)      > testo
        ("text",    testo,       None)      tutto il resto

    Lo spazio dopo il cancelletto e' richiesto, come vuole il Markdown
    standard: senza, "#3 note a piè di pagina" diventerebbe un titolo.
    """
    s = raw_line.strip()
    if not s:
        return ("blank", "", None)
    mi = _IMG_LINE_RE.match(s)
    if mi:
        return ("image", mi.group("alt"), mi.group("src"))
    m = _HEADING_RE.match(s)
    if m:
        return ("heading", m.group(2), len(m.group(1)))
    if s[:2] in _BULLET_PREFIXES:
        return ("bullet", s[2:], None)
    m = _NUMBER_RE.match(s)
    if m:
        return ("number", m.group(2), m.group(1))
    if s.startswith(">"):
        return ("quote", s.lstrip(">").strip(), None)
    return ("text", s, None)


# EN/IT: the two machine-written lines Project Gutenberg wraps every book in.
# They are generated, not written, so matching them exactly is safe: no book
# opens a paragraph with three asterisks and that sentence.
# Le due righe scritte a macchina con cui Project Gutenberg avvolge ogni libro.
# Sono generate, non scritte: riconoscerle alla lettera e' sicuro, nessun libro
# comincia un paragrafo con tre asterischi e quella frase.
_PG_START_RE = re.compile(
    r"^\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK\b.*$", re.I)
_PG_END_RE = re.compile(
    r"^\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK\b.*$", re.I)


def strip_gutenberg_boilerplate(text):
    """Toglie l'intestazione e la licenza che Project Gutenberg aggiunge a ogni
    libro, lasciando solo l'opera.

    In un file tipico sono un'intestazione di una ventina di righe e una
    licenza finale di trecento: circa un decimo delle parole, che altrimenti
    finirebbero nel manoscritto e da li' nel PDF e nell'EPUB.

    Si taglia solo fra i due marcatori, e solo se ci sono entrambi e
    nell'ordine giusto: se il file non e' di Gutenberg, o e' stato modificato,
    il testo torna indietro intatto. Meglio non tagliare che tagliare a
    sproposito.
    """
    lines = (text or "").split("\n")
    start = end = None
    for i, line in enumerate(lines):
        if start is None and _PG_START_RE.match(line.strip()):
            start = i
        elif start is not None and _PG_END_RE.match(line.strip()):
            end = i
            break
    if start is None or end is None or end <= start + 1:
        return text
    return "\n".join(lines[start + 1:end]).strip("\n")


# ---------------------------------------------------------------------------
# EN: RE-JOINING HARD-WRAPPED PARAGRAPHS ON IMPORT.
#     Most literary .txt files — Project Gutenberg's above all — are wrapped by
#     hand at a fixed column, with a blank line between paragraphs. Taken
#     literally, every one of those newlines is a line break, so the text comes
#     out of the PDF unjustified and refuses to reflow on an e-reader.
#     The file is not at fault: that layout is the norm, and the importer has
#     to recognise it.
#
#     The decision is made one paragraph at a time, never on the whole file,
#     because a book can hold both prose and verse. A run of lines that are all
#     nearly as long as the longest was wrapped by a machine and gets rejoined;
#     a run of short, uneven lines is poetry and is left exactly as it is.
#
# IT: RICUCIRE I PARAGRAFI SPEZZATI ALL'IMPORTAZIONE.
#     Quasi tutti i .txt letterari — quelli di Project Gutenberg per primi —
#     hanno le righe spezzate a mano a una colonna fissa e i paragrafi separati
#     da una riga vuota. Presi alla lettera, quei ritorni a capo sono
#     interruzioni di riga: il testo esce dal PDF non giustificato e su un
#     e-reader non si riadatta. Non e' colpa del file: quel formato e' la
#     norma, ed e' l'importatore che deve saperlo leggere.
#
#     La decisione si prende un paragrafo per volta, mai sul file intero,
#     perche' un libro puo' contenere prosa e versi insieme. Un gruppo di righe
#     lunghe quasi quanto la piu' lunga e' stato spezzato a macchina e viene
#     ricucito; un gruppo di righe corte e irregolari e' poesia e resta com'e'.
# ---------------------------------------------------------------------------

# Sotto questa larghezza non si parla di spezzatura automatica: nessuno manda
# a capo a colonna 30. I .txt in circolazione vanno dalle 60 alle 80 colonne.
_WRAP_MIN_WIDTH = 50
# Quanto devono essere uniformi le righe: la piu' corta almeno il 60% della
# piu' lunga. La prosa spezzata a macchina sta ampiamente sopra; i versi no.
_WRAP_MIN_RATIO = 0.6


def _looks_machine_wrapped(lengths):
    """Vero se queste lunghezze di riga sembrano prodotte da una spezzatura
    automatica a colonna fissa, non da scelte di chi scrive."""
    if not lengths:
        return False
    width = max(lengths)
    if width < _WRAP_MIN_WIDTH:
        return False
    return min(lengths) >= width * _WRAP_MIN_RATIO


def wrapped_runs(text):
    """Trova i paragrafi spezzati a colonna fissa, senza modificare niente.

    Restituisce una lista di coppie (prima_riga, ultima_riga), indici a base
    zero ed estremi inclusi: sono esattamente i gruppi di righe che
    unwrap_hard_breaks ricucirebbe.

    Esiste perche' vedere e correggere devono seguire la STESSA regola:
    l'editor evidenzia queste righe e il comando "Ricuci i paragrafi" unisce
    queste righe. Se la regola cambia, cambiano insieme.
    """
    lines = (text or "").split("\n")
    runs = []
    start = None
    explicit = False
    for i, raw in enumerate(lines):
        if classify_md_line(raw)[0] == "text":
            if start is None:
                start, explicit = i, False
            stripped = raw.rstrip("\n")
            if stripped.endswith("  ") or stripped.rstrip().endswith("\\"):
                explicit = True
        else:
            if start is not None:
                runs.append((start, i - 1, explicit))
            start = None
    if start is not None:
        runs.append((start, len(lines) - 1, explicit))

    out = []
    for a, b, has_explicit in runs:
        if b <= a or has_explicit:
            continue
        # si guardano tutte le righe tranne l'ultima: e' l'unica che puo'
        # essere piu' corta senza che questo dica niente sulla spezzatura
        if _looks_machine_wrapped([len(lines[i].rstrip()) for i in range(a, b)]):
            out.append((a, b))
    return out


def unwrap_hard_breaks(text):
    """Ricuce i paragrafi spezzati a colonna fissa, lasciando intatto il resto.

    Non tocca mai: righe vuote, titoli, elenchi, citazioni, immagini (li
    riconosce con classify_md_line), i gruppi di righe corte o irregolari, e i
    paragrafi in cui compare un'interruzione esplicita del Markdown (riga che
    finisce con due spazi o con una barra rovesciata) — li' l'intenzione di chi
    scrive e' dichiarata e va rispettata.

    Quali paragrafi ricucire lo decide wrapped_runs: la stessa funzione che
    l'editor usa per evidenziarli.
    """
    lines = (text or "").split("\n")
    fino_a = dict(wrapped_runs(text))       # prima riga -> ultima riga
    out = []
    i = 0
    while i < len(lines):
        if i in fino_a:
            ultima = fino_a[i]
            out.append(" ".join(ln.strip() for ln in lines[i:ultima + 1]))
            i = ultima + 1
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


_HEADING_SCALE = {1: 1.6, 2: 1.4, 3: 1.25, 4: 1.15, 5: 1.07, 6: 1.0}


def parse_md_line(raw_line, base_size):
    """Interpreta una riga markdown per il PDF. Restituisce
    (segments, dimensione_font, rientro_punti, spazio_extra_sotto, force_style)
    dove segments e' una lista di (testo, stile).

    Il riconoscimento della riga arriva da classify_md_line: qui restano solo
    le scelte tipografiche, che sono l'unica cosa specifica del PDF."""
    kind, body, extra = classify_md_line(raw_line)
    if kind == "blank":
        return ([("", "regular")], base_size, 0.0, 0.0, None)
    if kind == "heading":
        return ([(_strip_inline_md(body), "bold")],
                base_size * _HEADING_SCALE[extra], 0.0, base_size * 0.4, "bold")
    if kind == "bullet":
        segs = [("\u2022 ", "regular")] + _parse_inline_md(body)
        return (segs, base_size, base_size * 1.2, 0.0, None)
    if kind == "number":
        segs = [(f"{extra}. ", "regular")] + _parse_inline_md(body)
        return (segs, base_size, base_size * 1.2, 0.0, None)
    if kind == "quote":
        segs = [(seg, "italic" if st == "regular" else st)
                for seg, st in _parse_inline_md(body)]
        return (segs, base_size, base_size * 1.2, 0.0, None)
    # riga normale (comprese le righe immagine, che l'impaginatore intercetta
    # prima di arrivare qui): si conserva il rientro originale
    return (_parse_inline_md(raw_line), base_size, 0.0, 0.0, None)


def fit_cover_title(parole, max_w, misura, start=13.5, floor=2.0,
                    max_lines=4, step=0.94):
    """Sceglie il corpo del titolo di copertina e la sua andata a capo.

    LE PAROLE NON SI SPEZZANO. Se una parola non ci sta, non la si taglia a
    meta': si rimpicciolisce il corpo finche' entra intera. Spezzare
    "INTRODUZIONE" in "INTRODUZ / IONE" e' un errore tipografico, non un
    ripiego accettabile.

    parole : le parole del titolo, gia' in maiuscolo
    max_w  : larghezza disponibile
    misura : funzione (testo, corpo) -> larghezza, spaziatura fra le lettere
             compresa. Passandola da fuori questa funzione non ha bisogno di
             font ne' di immagini, e si puo' verificare da sola.

    Restituisce (corpo, righe). Solo per un titolo assurdo — una parola sola
    piu' larga della copertina anche al corpo minimo — si arriva a spezzare,
    come ultima difesa perche' nulla esca dai bordi.
    """
    parole = [p for p in parole if p]
    if not parole:
        return (start, [])

    def manda_a_capo(corpo, spezza):
        righe, cur = [], ""
        for parola in parole:
            prova = (cur + " " + parola).strip()
            if misura(prova, corpo) <= max_w:
                cur = prova
                continue
            if cur:
                righe.append(cur)
                cur = ""
            if not spezza or misura(parola, corpo) <= max_w:
                cur = parola
                continue
            pezzo = ""
            for ch in parola:
                if not pezzo or misura(pezzo + ch, corpo) <= max_w:
                    pezzo += ch
                else:
                    righe.append(pezzo)
                    pezzo = ch
            cur = pezzo
        if cur:
            righe.append(cur)
        return righe

    corpo = start
    while True:
        intere = all(misura(p, corpo) <= max_w for p in parole)
        righe = manda_a_capo(corpo, spezza=False)
        if (intere and len(righe) <= max_lines) or corpo <= floor:
            break
        corpo *= step
    if not intere:
        # titolo impossibile: solo qui si spezza, per non debordare
        righe = manda_a_capo(corpo, spezza=True)
    return (corpo, righe)


def _cover_graphics_ops(page_w, page_h):
    """Operatori grafici vettoriali per una copertina sobria e seria.
    Disegna soltanto:
      - una cornice esterna a filetto singolo, sottile, color prugna scuro;
      - due brevi filetti orizzontali centrati, che incorniciano il blocco
        del titolo (uno appena sopra, uno appena sotto).
    Nessun ornamento dorato, nessun emblema. Restituisce una lista di byte
    (comandi del content stream) da anteporre al testo. Solo PDF nativo.
    """
    P = []

    plum_d = b"0.361 0.165 0.333"   # #5C2A55  unico colore, prugna scuro

    def rect_stroke(x, y, w, h, lw, col):
        P.append(col + b" RG")
        P.append(f"{lw:.2f} w".encode("latin-1"))
        P.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re S".encode("latin-1"))

    def line(x1, y1, x2, y2, lw, col):
        P.append(col + b" RG")
        P.append(f"{lw:.2f} w".encode("latin-1"))
        P.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S".encode("latin-1"))

    # --- cornice esterna sottile ----------------------------------------
    m_out = 40.0
    rect_stroke(m_out, m_out, page_w - 2 * m_out, page_h - 2 * m_out,
                0.8, plum_d)

    # --- due brevi filetti centrati attorno al titolo -------------------
    cx = page_w / 2.0
    half = page_w * 0.16        # mezza lunghezza del filetto (corto, centrato)
    y_top = page_h * 0.560      # appena sopra il blocco del titolo
    y_bot = page_h * 0.400      # appena sotto (sopra autore/data)
    line(cx - half, y_top, cx + half, y_top, 0.7, plum_d)
    line(cx - half, y_bot, cx + half, y_bot, 0.7, plum_d)

    return P


# --- Immagini / Images ------------------------------------------------------
# EN: Shared helpers for the "common image formats" the app accepts (PNG,
#     JPEG, WebP): format sniffing from magic bytes, pixel size reading
#     without external libraries, and conversion to JPEG for the PDF export
#     (PDF embeds JPEG natively via DCTDecode).
# IT: Helper condivisi per i "formati immagine comuni" accettati (PNG, JPEG,
#     WebP): riconoscimento del formato dai byte iniziali, lettura delle
#     dimensioni in pixel senza librerie esterne, e conversione in JPEG per
#     l'export PDF (il PDF incorpora i JPEG nativamente via DCTDecode).

# EN: canonical format name -> (file extension, MIME type)
# IT: nome canonico del formato -> (estensione file, tipo MIME)
IMAGE_FORMATS = {
    "png":  ("png",  "image/png"),
    "jpeg": ("jpg",  "image/jpeg"),
    "webp": ("webp", "image/webp"),
}


# --- generatore di copertine ------------------------------------------------
# EN: Formats offered by the cover generator, in centimetres. The keys match
#     PDF_PAGE_SIZES so a generated cover can follow the book's page size.
# IT: Formati offerti dal generatore di copertine, in centimetri. Le chiavi
#     coincidono con PDF_PAGE_SIZES cosi' la copertina generata puo' seguire
#     il formato pagina del libro.
COVER_FORMATS = {
    "A5":    {"w_cm": 14.8, "h_cm": 21.0},
    "6x9":   {"w_cm": 15.2, "h_cm": 22.9},
    "17x24": {"w_cm": 17.0, "h_cm": 24.0},
    "A4":    {"w_cm": 21.0, "h_cm": 29.7},
    "5x8":   {"w_cm": 12.7, "h_cm": 20.3},
}
COVER_DEFAULT_FORMAT = "A5"

# EN/IT: palette proposta dal generatore / palette offered by the generator
COVER_COLORS = [
    "#c98274", "#8d9e7e", "#7d8ba3", "#c4a94f", "#a2705f", "#6f6f78",
    "#d9c9a8", "#3f4a3c", "#8e5b6e", "#2e3440", "#e0ded6", "#b3462f",
]
COVER_DEFAULT_COLOR = "#c98274"
COVER_TEXT_COLORS = ["#111111", "#ffffff"]

# EN: preview vs final resolution (dots per inch). The preview stays small so
#     the GUI redraws instantly; the final image is print-quality.
# IT: risoluzione di anteprima e finale (punti per pollice). L'anteprima resta
#     piccola cosi' la GUI si ridisegna all'istante; l'immagine finale e' di
#     qualita' di stampa.
COVER_PREVIEW_DPI = 96
COVER_EXPORT_DPI = 300


def cover_generator_available():
    """EN: True if a cover can be generated. Drawing the text requires Pillow,
    so without it the generator is offered as unavailable (attaching a
    ready-made image keeps working).
    IT: True se e' possibile generare una copertina. Disegnare il testo
    richiede Pillow, quindi senza di esso il generatore risulta non disponibile
    (allegare un'immagine gia' pronta continua a funzionare)."""
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        return True
    except Exception:
        return False


def _hex_to_rgb(value, fallback=(201, 130, 116)):
    """EN/IT: '#rrggbb' (o '#rgb') -> (r, g, b); fallback se non valido."""
    s = (value or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return fallback
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return fallback


def render_cover_image(fmt_key=COVER_DEFAULT_FORMAT, dpi=COVER_EXPORT_DPI,
                       bg_color=COVER_DEFAULT_COLOR, text_color="#111111",
                       author="", title="", publisher="",
                       image_bytes=None, out_format="png", font_dir=None):
    """EN: Draw a book cover and return the image bytes (PNG by default).

    The layout follows a classic typographic scheme: a coloured ground, a
    double rule frame, the author in tracked capitals at the top, a picture
    box in the middle (cropped like CSS 'object-fit: cover'), the title in
    large capitals and the publisher at the foot under a short ornamental
    rule. Every measure is proportional to the cover width, so the result is
    identical at preview resolution and at print resolution.

    font_dir : folder holding the bundled EB Garamond .ttf files (the caller
    passes assets/, so this module keeps needing no path logic of its own).

    Returns None if Pillow is missing (see cover_generator_available()).

    IT: Disegna una copertina e restituisce i byte dell'immagine (PNG per
    impostazione predefinita).

    L'impaginazione segue uno schema tipografico classico: fondo colorato,
    cornice a doppio filetto, autore in maiuscoletto spaziato in alto,
    riquadro per l'immagine al centro (ritagliata come 'object-fit: cover'
    del CSS), titolo in maiuscole grandi ed editore in basso sotto un breve
    filetto ornamentale. Ogni misura e' proporzionale alla larghezza, cosi' il
    risultato e' identico in anteprima e in stampa.

    Restituisce None se Pillow non c'e' (vedi cover_generator_available())."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    spec = COVER_FORMATS.get(fmt_key) or COVER_FORMATS[COVER_DEFAULT_FORMAT]
    W = max(1, int(round(spec["w_cm"] / 2.54 * dpi)))
    H = max(1, int(round(spec["h_cm"] / 2.54 * dpi)))

    bg_rgb = _hex_to_rgb(bg_color)
    txt_rgb = _hex_to_rgb(text_color, (17, 17, 17))
    # filetti dello stesso colore del testo (bianchi su fondo scuro)
    rule_rgb = (255, 255, 255) if sum(txt_rgb) > 380 else (0, 0, 0)

    img = Image.new("RGB", (W, H), bg_rgb)
    d = ImageDraw.Draw(img)

    # unita' proporzionale: 1% della larghezza (il "cqw" dei CSS container)
    cqw = W / 100.0

    def _font(filename, size_px):
        """Carica un font del progetto; ripiega sul font di sistema."""
        try:
            path = os.path.join(font_dir, filename) if font_dir else filename
            return ImageFont.truetype(path, max(1, int(round(size_px))))
        except Exception:
            try:
                return ImageFont.load_default(max(1, int(round(size_px))))
            except Exception:
                return ImageFont.load_default()

    def _tracked(text_s, y, fnt, tracking, cx, fill):
        """Testo centrato con spaziatura tra le lettere (letter-spacing)."""
        if not text_s:
            return
        widths = [d.textlength(ch, font=fnt) for ch in text_s]
        total = sum(widths) + tracking * max(0, len(text_s) - 1)
        x = cx - total / 2.0
        for ch, w in zip(text_s, widths):
            d.text((x, y), ch, font=fnt, fill=fill)
            x += w + tracking

    # --- cornice a doppio filetto ---
    pad = 0.042 * W
    thick = max(1, int(round(0.42 * cqw)))
    thin = max(1, int(round(0.16 * cqw)))
    gap = 1.5 * cqw
    fx0, fy0, fx1, fy1 = pad, pad, W - pad, H - pad
    d.rectangle([fx0, fy0, fx1, fy1], outline=rule_rgb, width=thick)
    d.rectangle([fx0 + gap, fy0 + gap, fx1 - gap, fy1 - gap],
                outline=rule_rgb, width=thin)

    # --- area di testo interna ---
    inner_w = fx1 - fx0
    ix0 = fx0 + 0.065 * inner_w
    ix1 = fx1 - 0.065 * inner_w
    iy0 = fy0 + 0.060 * inner_w
    iy1 = fy1 - 0.055 * inner_w
    cx = (ix0 + ix1) / 2.0
    inner_h = iy1 - iy0

    # --- autore, in alto ---
    a_size = 4.0 * cqw
    fa = _font("EBGaramond-Regular.ttf", a_size)
    _tracked((author or "").upper(), iy0, fa, 0.18 * a_size, cx, txt_rgb)
    a_asc, a_desc = fa.getmetrics()
    author_bottom = iy0 + (a_asc + a_desc) * 1.2

    # --- editore, in basso, con filetto ornamentale ---
    e_size = 3.0 * cqw
    fe = _font("EBGaramond-Regular.ttf", e_size)
    e_asc, e_desc = fe.getmetrics()
    e_y = iy1 - (e_asc + e_desc) * 1.2
    _tracked((publisher or "").upper(), e_y, fe, 0.22 * e_size, cx, txt_rgb)
    rule_y = e_y - 0.035 * inner_h
    rule_half = 0.07 * (ix1 - ix0)
    if publisher:
        d.line([cx - rule_half, rule_y, cx + rule_half, rule_y],
               fill=rule_rgb, width=thin)

    # --- titolo: il corpo si MISURA, non si indovina --------------------------
    # Prima il corpo si sceglieva contando i caratteri: una parola sola e lunga
    # usciva dai bordi. La decisione sta ora in fit_cover_title, che scende di
    # corpo finche' ogni parola ci sta INTERA — le parole non si spezzano.
    t_text = (title or "").upper()
    max_w = ix1 - ix0

    def _misura(testo, corpo):
        """Larghezza reale del testo come lo disegna _tracked: la spaziatura
        fra le lettere va contata, o la misura mente."""
        if not testo:
            return 0.0
        fnt = _font("EBGaramond-Bold.ttf", corpo * cqw)
        tracking = 0.03 * corpo * cqw
        return (sum(d.textlength(ch, font=fnt) for ch in testo)
                + tracking * max(0, len(testo) - 1))

    corpo, lines = fit_cover_title(t_text.split(), max_w, _misura)
    t_size = corpo * cqw
    ft = _font("EBGaramond-Bold.ttf", t_size)

    line_h = t_size * 1.02
    title_top = rule_y - 0.025 * inner_h - line_h * len(lines)
    for i, ln in enumerate(lines):
        _tracked(ln, title_top + i * line_h, ft, 0.03 * t_size, cx, txt_rgb)

    # --- riquadro dell'immagine, tra autore e titolo ---
    box_top = int(round(author_bottom + 0.045 * inner_h))
    box_bottom = int(round(title_top - 0.045 * inner_h))
    bx0, bx1 = int(round(ix0)), int(round(ix1))
    if box_bottom > box_top and bx1 > bx0:
        bw, bh = bx1 - bx0, box_bottom - box_top
        placed = False
        if image_bytes:
            try:
                src = Image.open(io.BytesIO(image_bytes))
                if src.mode != "RGB":
                    src = src.convert("RGB")
                # ritaglio "cover": riempie il riquadro senza deformare
                src_ratio = src.width / max(1, src.height)
                box_ratio = bw / max(1, bh)
                if src_ratio > box_ratio:
                    nw = int(src.height * box_ratio)
                    left = max(0, (src.width - nw) // 2)
                    src = src.crop((left, 0, left + nw, src.height))
                else:
                    nh = int(src.width / max(0.0001, box_ratio))
                    top = max(0, (src.height - nh) // 2)
                    src = src.crop((0, top, src.width, top + nh))
                src = src.resize((bw, bh), Image.LANCZOS)
                img.paste(src, (bx0, box_top))
                placed = True
            except Exception:
                placed = False
        if not placed:
            # velo chiaro come segnaposto (CSS rgba(255,255,255,.22))
            base = img.crop((bx0, box_top, bx1, box_bottom))
            veil = Image.new("RGB", (bw, bh), (255, 255, 255))
            img.paste(Image.blend(base, veil, 0.22), (bx0, box_top))

    out = io.BytesIO()
    fmt = (out_format or "png").lower()
    if fmt in ("jpg", "jpeg"):
        img.save(out, format="JPEG", quality=95)
    elif fmt == "webp":
        img.save(out, format="WEBP", quality=95)
    else:
        img.save(out, format="PNG")
    return out.getvalue()


def image_format(data):
    """EN: Detect the image format from the magic bytes at the start of the
    file. Returns 'png', 'jpeg', 'webp' or None if unsupported. Sniffing the
    content (instead of trusting the file extension) makes attach robust.
    IT: Riconosce il formato dai byte iniziali del file. Restituisce 'png',
    'jpeg', 'webp' o None se non supportato. Annusare il contenuto (invece di
    fidarsi dell'estensione) rende l'allegato robusto."""
    if not data or len(data) < 12:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _png_dimensions(data):
    """EN: Read (width, height) from the PNG IHDR chunk (always first, big
    endian, at fixed offsets 16 and 20).
    IT: Legge (larghezza, altezza) dal chunk IHDR del PNG (sempre il primo,
    big endian, agli offset fissi 16 e 20)."""
    try:
        w, h = struct.unpack(">II", data[16:24])
        return (w, h) if w and h else None
    except Exception:
        return None


def _webp_dimensions(data):
    """EN: Read (width, height) from a WebP file. WebP is a RIFF container;
    the size lives in the first chunk, whose layout depends on the variant:
    VP8 (lossy), VP8L (lossless) or VP8X (extended).
    IT: Legge (larghezza, altezza) da un WebP. Il WebP e' un contenitore
    RIFF; la dimensione sta nel primo chunk, il cui formato dipende dalla
    variante: VP8 (lossy), VP8L (lossless) o VP8X (esteso)."""
    try:
        tag = data[12:16]
        if tag == b"VP8X":
            # EN: 24-bit little-endian fields store size minus one.
            # IT: campi a 24 bit little-endian con dimensione meno uno.
            w = int.from_bytes(data[24:27], "little") + 1
            h = int.from_bytes(data[27:30], "little") + 1
            return (w, h)
        if tag == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            w = (bits & 0x3FFF) + 1
            h = ((bits >> 14) & 0x3FFF) + 1
            return (w, h)
        if tag == b"VP8 ":
            # EN: lossy frame header: size at offset 26, 14 bits each.
            # IT: header del frame lossy: dimensioni all'offset 26, 14 bit.
            w = int.from_bytes(data[26:28], "little") & 0x3FFF
            h = int.from_bytes(data[28:30], "little") & 0x3FFF
            return (w, h) if w and h else None
        return None
    except Exception:
        return None


def image_dimensions(data, fmt=None):
    """EN: (width, height) in pixels for PNG/JPEG/WebP data, or None. Used to
    scale images in the exports without requiring Pillow.
    IT: (larghezza, altezza) in pixel per dati PNG/JPEG/WebP, o None. Usata
    per scalare le immagini negli export senza richiedere Pillow."""
    fmt = fmt or image_format(data)
    if fmt == "png":
        return _png_dimensions(data)
    if fmt == "jpeg":
        return _jpeg_dimensions(data)
    if fmt == "webp":
        return _webp_dimensions(data)
    return None


def _jpeg_dimensions(data):
    """Estrae (larghezza, altezza) da un JPEG leggendo i marker SOF (stdlib)."""
    try:
        i = 2; n = len(data)
        while i + 9 < n:
            if data[i] != 0xFF:
                i += 1; continue
            marker = data[i + 1]
            if marker in (0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF):
                h = (data[i+5] << 8) | data[i+6]
                w = (data[i+7] << 8) | data[i+8]
                return (w, h)
            seg_len = (data[i+2] << 8) | data[i+3]
            i += 2 + seg_len
        return None
    except Exception:
        return None


def _image_to_jpeg(data, fmt=None):
    """EN: Prepare an image (cover or chapter attachment) for embedding in
    the PDF. PDF embeds JPEG natively (DCTDecode) but not PNG/WebP. With
    Pillow any image is converted to RGB JPEG; without Pillow a JPEG passes
    through untouched; anything else returns None (the caller falls back).
    Returns (jpeg_bytes, width, height) or None.
    IT: Prepara un'immagine (copertina o allegato di capitolo) per
    l'incorporamento nel PDF. Il PDF incorpora i JPEG nativamente
    (DCTDecode) ma non PNG/WebP. Con Pillow ogni immagine viene convertita
    in JPEG RGB; senza Pillow un JPEG passa cosi' com'e'; altrimenti None
    (il chiamante ripiega). Ritorna (jpeg_bytes, width, height) o None."""
    if not data:
        return None
    fmt = fmt or image_format(data)
    try:
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(data))
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        buf = _io.BytesIO(); img.save(buf, format="JPEG", quality=90)
        return buf.getvalue(), w, h
    except Exception:
        pass
    if fmt == "jpeg":
        dims = _jpeg_dimensions(data)
        if dims:
            return data, dims[0], dims[1]
    return None


# EN: A chapter line that is ONLY a Markdown image, e.g. ![caption](img_001.png)
# IT: Riga di capitolo che e' SOLO un'immagine Markdown, es. ![didascalia](img_001.png)
_IMG_LINE_RE = re.compile(r"^!\[(?P<alt>.*?)\]\((?P<src>[^)\s]+)\)\s*$")


def write_pdf(path, chapters, title="",
              cover_paragraphs=None, cover_roles=None,
              chapter_titles=None, toc_label="Indice",
              font_size=12, leading=16,
              page_w=595.0, page_h=842.0,   # A4 in punti
              margin=72.0,                  # ~2.54 cm (margine uniforme di base)
              margin_inner=None,            # margine interno (lato rilegatura)
              margin_outer=None,            # margine esterno (lato taglio)
              page_break_per_chapter=True,
              embed_fonts=None, embed_font_name="CourierPrime",
              cover_image=None,
              chapter_images=None,
              frontispiece_paragraphs=None,
              colophon_paragraphs=None,
              blank_cover=False,
              justify=False,
              hyphenate=False,
              hyphen_lang="it"):
    """
    EN: Write a PDF using only the standard library, with basic Markdown.
      chapters : list of chapters; each chapter = list of paragraphs (str).
      cover_paragraphs : opening cover page (unnumbered).
      embed_fonts : dict {style: metrics} for regular/bold/italic/bolditalic
                    (from read_ttf_metrics). When present, the text uses the
                    embedded font and renders bold/italic.
      chapter_images : dict {internal_name: (jpeg_bytes, width, height)} of
                    the attached chapter images, already converted to JPEG;
                    a text line like ![caption](name) places the image.
      justify   : when True, body paragraphs are justified to the text width
                    (extra space is spread evenly between words); the LAST
                    line of each paragraph, headings and centered material stay
                    flush-left / centered as before.
      hyphenate : when True AND Pyphen is available, over-long words are broken
                    with a hyphen at a valid syllable point so justification
                    looks tidier and fewer words are stretched. Silently
                    ignored if Pyphen is missing.
      hyphen_lang : language code for the hyphenation dictionary (e.g. "it",
                    "en_US"); ignored when hyphenate is False.
    IT: Scrive un PDF usando solo la libreria standard, con markdown di base.
      chapters : lista di capitoli; ogni capitolo = lista di paragrafi (str).
      cover_paragraphs : pagina copertina iniziale (senza numero).
      embed_fonts : dict {stile: metrics} per stile in regular/bold/italic/
                    bolditalic (da read_ttf_metrics). Se presente, il testo usa
                    il font incorporato e rende grassetto/corsivo.
      chapter_images : dict {nome_interno: (jpeg_bytes, larg, alt)} delle
                    immagini allegate ai capitoli, gia' convertite in JPEG;
                    una riga di testo ![didascalia](nome) colloca l'immagine.
    """
    embed_fonts = embed_fonts or {}
    chapter_images = chapter_images or {}
    reg = embed_fonts.get("regular")
    # advance per glifo (monospace -> uguale per tutti gli stili)
    adv = reg["advance1000"] if reg else None
    # mappa larghezze per carattere (font proporzionali, es. EB Garamond):
    # se presente, l'impaginazione usa la larghezza reale di ogni glifo.
    widths_map = reg.get("widths_by_code") if reg else None
    # mappa stile -> chiave font PDF (/F1=regular, /F2=bold, ...)
    style_to_fid = {"regular": "F1", "bold": "F2",
                    "italic": "F3", "bolditalic": "F4"}

    def seg_w(s, size):
        return _text_width(s, size, adv, widths_map)

    # --- sillabazione (opzionale) ------------------------------------------
    # EN: the hyphenator is created only if requested AND Pyphen is present;
    #     otherwise it stays None and no word is ever broken with a hyphen.
    # IT: il sillabatore si crea solo se richiesto E Pyphen c'e'; altrimenti
    #     resta None e nessuna parola viene mai spezzata con un trattino.
    hyphenator = get_hyphenator(hyphen_lang) if hyphenate else None

    def _hyphenate_token(tok, style, size, first_max, next_max):
        """EN: Try to split an over-long word so its first piece fits in
        'first_max' points; the remainder is returned to be re-wrapped. Returns
        a list of (text, style) pieces where every piece but the last ends in a
        soft hyphen "-". If no valid split fits, returns [(tok, style)] intact.
        IT: Prova a spezzare una parola troppo lunga cosi' che il primo pezzo
        entri in 'first_max' punti; il resto viene restituito per essere
        re-impaginato. Restituisce una lista di pezzi (testo, stile) dove ogni
        pezzo tranne l'ultimo finisce con un trattino "-". Se nessuna divisione
        valida entra, restituisce [(tok, style)] intatto."""
        if hyphenator is None or len(tok) < 5:
            return [(tok, style)]
        # Pyphen.positions() da' gli indici di sillaba validi (crescenti).
        try:
            positions = hyphenator.positions(tok)
        except Exception:
            positions = []
        if not positions:
            return [(tok, style)]
        pieces = []
        rest = tok
        offset = 0
        avail = first_max
        while True:
            # posizioni valide relative a 'rest'
            rel = [p - offset for p in positions if 0 < p - offset < len(rest)]
            chosen = None
            for cut in reversed(rel):        # dal taglio piu' lungo che entra
                head = rest[:cut] + "-"
                if seg_w(head, size) <= avail:
                    chosen = cut
                    break
            if chosen is None:
                pieces.append((rest, style))
                break
            pieces.append((rest[:chosen] + "-", style))
            rest = rest[chosen:]
            offset += chosen
            avail = next_max
            if seg_w(rest, size) <= avail:
                pieces.append((rest, style))
                break
        return pieces

    # --- margini: interno (rilegatura) ed esterno (taglio) -----------------
    # Se non specificati, ripiegano sul margine uniforme 'margin', cosi' il
    # comportamento storico resta invariato. Quando differiscono, le pagine
    # dispari (recto) hanno il margine interno a SINISTRA e quelle pari (verso)
    # a DESTRA: il testo viene impaginato con un margine sinistro di base pari
    # al margine ESTERNO, e all'emissione viene traslato a destra del 'gutter'
    # (interno - esterno) sulle pagine recto. Cosi' i calcoli X esistenti
    # restano validi e basta spostare in blocco l'intera pagina.
    m_inner = margin if margin_inner is None else margin_inner
    m_outer = margin if margin_outer is None else margin_outer
    gutter = m_inner - m_outer          # spostamento extra del lato interno
    left_margin = m_outer               # margine sinistro di impaginazione (base)

    usable_w = page_w - (m_inner + m_outer)
    top_y = page_h - margin
    bottom_y = margin
    header_gap = leading * 1.6
    content_top_y = top_y - header_gap

    # ogni riga di pagina: (x, y, runs, size) dove runs = [(testo, stile), ...]
    pages = []
    cur_lines = []
    y = content_top_y

    def flush_page(kind=None):
        # kind: "cover" (grafica copertina), "plain" (senza numero, es. indice),
        #       None (pagina di contenuto, numerata)
        nonlocal cur_lines, y
        pages.append((cur_lines, kind))
        cur_lines = []
        y = content_top_y

    def wrap_segments(segments, size, maxw):
        """Manda a capo una sequenza di run (testo,stile) entro maxw.
        Restituisce una lista di righe, ciascuna lista di run.

        Se il sillabatore e' attivo, una parola che non entra nello spazio
        rimasto sulla riga corrente viene spezzata con un trattino nel punto
        di sillaba piu' conveniente, invece di essere mandata tutta a capo:
        cosi' le righe si riempiono meglio e la giustificazione risulta piu'
        uniforme (meno spazi dilatati)."""
        lines = []
        cur = []
        cur_w = 0.0
        for seg_text, style in segments:
            # spezza il run in parole conservando gli spazi
            tokens = re.split(r"(\s+)", seg_text)
            for tok in tokens:
                if tok == "":
                    continue
                w = seg_w(tok, size)
                if cur_w + w > maxw and cur:
                    if tok.strip() == "":
                        # lo spazio finisce la riga: a capo, senza riportarlo
                        lines.append(cur)
                        cur = []
                        cur_w = 0.0
                        continue
                    # la parola non entra nello spazio rimasto: prova a
                    # sillabarla in modo che un pezzo stia su questa riga.
                    if hyphenator is not None:
                        pieces = _hyphenate_token(
                            tok, style, size, maxw - cur_w, maxw)
                        if len(pieces) > 1:
                            head = pieces[0]
                            cur.append(head)
                            lines.append(cur)
                            cur = []
                            cur_w = 0.0
                            # i pezzi restanti (l'ultimo senza trattino) vanno
                            # sulle righe successive, ricontrollando la
                            # larghezza uno per uno
                            for pc_text, pc_style in pieces[1:]:
                                pw = seg_w(pc_text, size)
                                if cur_w + pw > maxw and cur:
                                    lines.append(cur)
                                    cur = []
                                    cur_w = 0.0
                                cur.append((pc_text, pc_style))
                                cur_w += pw
                            continue
                    # niente sillabazione: mando la parola intera a capo
                    lines.append(cur)
                    cur = []
                    cur_w = 0.0
                cur.append((tok, style))
                cur_w += w
        if cur:
            lines.append(cur)
        return lines or [[("", "regular")]]

    def _wrap_centered(text, size):
        """Spezza 'text' in righe centrabili che stanno in usable_w."""
        words = text.split()
        if not words:
            return [""]
        rows, cur = [], words[0]
        for w in words[1:]:
            if seg_w(cur + " " + w, size) <= usable_w:
                cur += " " + w
            else:
                rows.append(cur); cur = w
        rows.append(cur)
        return rows

    def _emit_centered(rows, size, style, yy, line_lead):
        for row in rows:
            lw = seg_w(row, size)
            cur_lines.append(((page_w - lw) / 2.0, yy, [(row, style)], size))
            yy -= line_lead
        return yy

    def add_front_page(styled_lines):
        """Frontespizio professionale: titolo grande nella parte alta-centrale,
        sottotitolo sotto, autore piu' in basso, e in fondo alla pagina i dati
        editoriali (editore, luogo/anno). styled_lines: lista (testo, ruolo)."""
        if not styled_lines:
            return
        title_sz = font_size * 2.1
        sub_sz = font_size * 1.25
        author_sz = font_size * 1.15
        meta_sz = font_size * 0.95
        # blocco principale (titolo/sottotitolo/autore) centrato verticalmente
        # nella meta' superiore; i meta vanno in fondo pagina.
        top = [(t, r) for (t, r) in styled_lines if r != "meta"]
        meta = [(t, r) for (t, r) in styled_lines if r == "meta"]

        # calcola altezza del blocco principale
        def size_of(role):
            return {"title": title_sz, "subtitle": sub_sz,
                    "author": author_sz}.get(role, font_size)
        block_h = 0
        for t, r in top:
            rows = _wrap_centered(t, size_of(r))
            lead = size_of(r) * 1.4
            block_h += lead * len(rows)
            if r == "title":
                block_h += font_size * 0.6   # spazio dopo il titolo
            if r == "author":
                block_h += font_size * 0.8   # spazio prima dell'autore
        # parti un po' sopra il centro, per un'aria piu' "da libro"
        yy = page_h * 0.66 + block_h / 2.0
        for t, r in top:
            sz = size_of(r)
            if r == "author":
                yy -= font_size * 0.8
            style = "bold" if r == "title" else ("italic" if r == "subtitle" else "regular")
            rows = _wrap_centered(t, sz)
            yy = _emit_centered(rows, sz, style, yy, sz * 1.4)
            if r == "title":
                yy -= font_size * 0.6
        # meta in fondo pagina
        if meta:
            my = margin + meta_sz * 1.6 * len(meta)
            for t, r in meta:
                rows = _wrap_centered(t, meta_sz)
                my = _emit_centered(rows, meta_sz, "regular", my, meta_sz * 1.4)
        flush_page("plain")

    def add_colophon_page(styled_lines):
        """Colophon professionale: blocco compatto e piccolo, centrato, nella
        parte bassa della pagina. styled_lines: lista (testo, ruolo)."""
        if not styled_lines:
            return
        copy_sz = font_size * 1.0
        small_sz = font_size * 0.85
        line_lead = small_sz * 1.5
        # altezza totale per posizionare il blocco nella meta' inferiore
        total = 0
        for t, r in styled_lines:
            sz = copy_sz if r == "copyright" else small_sz
            total += line_lead * len(_wrap_centered(t, sz))
        yy = page_h * 0.40 + total / 2.0
        for t, r in styled_lines:
            sz = copy_sz if r == "copyright" else small_sz
            rows = _wrap_centered(t, sz)
            yy = _emit_centered(rows, sz, "regular", yy, line_lead)
        flush_page("plain")

    # 0) copertina-immagine a piena pagina (precede ed esclude la grafica)
    if cover_image is not None:
        jpeg_bytes, img_w, img_h = cover_image
        pages.append(([], ("image", jpeg_bytes, img_w, img_h)))

    # 0-bis) copertina BIANCA e VUOTA: nessuna immagine e campi editoriali
    # vuoti. Si emette comunque una pagina (presente nel PDF) ma senza alcuna
    # grafica vettoriale e senza testo: pagina completamente bianca, senza
    # numero. Esclude la copertina stilizzata sottostante.
    blank_cover_now = blank_cover and cover_image is None
    if blank_cover_now:
        flush_page("plain")   # pagina vuota, senza cornice e senza numero

    # 1) pagina copertina stilizzata (grafica + testo) solo senza immagine
    if cover_paragraphs is not None and cover_image is None and not blank_cover_now:
        # raccoglie le righe non vuote della copertina conservando l'ordine.
        # convenzione del progetto: 1a riga = TITOLO, ultima = data,
        # le righe intermedie = autore (ed eventuale sottotitolo).
        raw_lines = []
        for para in cover_paragraphs:
            for raw_line in para.split("\n"):
                clean = _strip_inline_md(raw_line.lstrip("#").strip()
                                         if raw_line.strip().startswith("#")
                                         else raw_line)
                if clean.strip():
                    raw_lines.append(clean.strip())

        title_size  = font_size * 2.1
        author_size = font_size * 1.25
        date_size   = font_size * 0.95
        title_lead  = leading * 2.1
        author_lead = leading * 1.4

        def put_centered(text, size, cy_pos, style):
            lw = seg_w(text, size)
            cx = (page_w - lw) / 2.0
            cur_lines.append((cx, cy_pos, [(text, style)], size))

        def wrap_centered(text, size):
            """Spezza un testo troppo largo in piu' righe centrabili."""
            maxw = usable_w
            words = text.split()
            if not words:
                return [""]
            out, cur = [], words[0]
            for w in words[1:]:
                if seg_w(cur + " " + w, size) <= maxw:
                    cur += " " + w
                else:
                    out.append(cur); cur = w
            out.append(cur)
            return out

        # I ruoli arrivano dal progetto (cover_lines_with_roles): titolo,
        # sottotitolo, autore, editore. Non si deducono dalla posizione, o con
        # due sole righe la stessa finirebbe stampata due volte.
        if cover_roles and len(cover_roles) == len(raw_lines):
            title_line = next((t for t, r in zip(raw_lines, cover_roles)
                               if r == "title"), "")
            middle = [t for t, r in zip(raw_lines, cover_roles)
                      if r in ("subtitle", "author")]
            date_line = next((t for t, r in zip(raw_lines, cover_roles)
                              if r == "publisher"), "")
            raw_lines = [x for x in ([title_line] + middle + [date_line]) if x]
        elif raw_lines:
            # ripiego per chi chiama write_pdf senza ruoli
            title_line = raw_lines[0]
            date_line = raw_lines[-1] if len(raw_lines) > 2 else ""
            middle = raw_lines[1:-1] if len(raw_lines) > 2 else raw_lines[1:]

        if raw_lines:

            # TITOLO: centrato nella fascia tra i due filetti (0.585 e 0.375),
            # quindi attorno a ~0.48 dell'altezza pagina.
            band_mid = page_h * 0.48
            title_rows = wrap_centered(title_line, title_size)
            n_mid = len(middle)
            block_h = len(title_rows) * title_lead + n_mid * author_lead
            ty = band_mid + block_h / 2.0 - title_size * 0.30
            for trow in title_rows:
                put_centered(trow, title_size, ty, "bold")
                ty -= title_lead

            # AUTORE / sottotitolo: appena sotto il titolo
            ay = ty - (title_lead * 0.15)
            for line_txt in middle:
                put_centered(line_txt, author_size, ay, "regular")
                ay -= author_lead

            # DATA: ancorata appena sotto il filetto inferiore (0.400)
            if date_line:
                dy = page_h * 0.400 - date_size * 2.2
                put_centered(date_line, date_size, dy, "italic")

        flush_page("cover")

    # 1a) frontespizio (dopo la copertina, prima dell'indice)
    if frontispiece_paragraphs:
        add_front_page(frontispiece_paragraphs)

    # Per avere nell'indice i NUMERI DI PAGINA reali (non gli ordinali dei
    # capitoli) impaginiamo prima i capitoli in un elenco di pagine separato,
    # registrando la pagina di inizio di ciascun capitolo, e SOLO DOPO
    # costruiamo l'indice. I numeri di pagina visibili partono da 1 e contano
    # solo le pagine di contenuto (le pagine "plain" come copertina, indice e
    # colophon non sono numerate), quindi l'indice non altera la numerazione.
    pages_before_chapters = list(pages)   # cover + frontespizio
    pages = []                            # qui finiranno SOLO le pagine capitoli

    chapter_start_page = []   # numero di pagina visibile d'inizio per capitolo
    pages_so_far = 0          # pagine di contenuto gia' completate

    # 2) capitoli di contenuto (markdown)
    for ci, paragraphs in enumerate(chapters):
        if page_break_per_chapter and ci > 0:
            flush_page()
            pages_so_far += 1
        # all'inizio del capitolo, la sua prima pagina e' (pagine_finora + 1)
        chapter_start_page.append(pages_so_far + 1)
        for para in paragraphs:
            for raw_line in para.split("\n"):
                # EN: a line that is ONLY ![caption](name) places the
                #     attached image, centered and scaled to the text width
                #     (never upscaled), followed by an italic caption. If the
                #     image does not fit the remaining space, it moves to a
                #     new page first.
                # IT: una riga che e' SOLO ![didascalia](nome) colloca
                #     l'immagine allegata, centrata e scalata alla larghezza
                #     del testo (mai ingrandita), seguita dalla didascalia in
                #     corsivo. Se l'immagine non entra nello spazio rimasto,
                #     passa prima a una pagina nuova.
                mimg = _IMG_LINE_RE.match(raw_line.strip())
                if mimg and mimg.group("src") in chapter_images:
                    _jpg, iw, ih = chapter_images[mimg.group("src")]
                    max_h = (content_top_y - bottom_y) * 0.60
                    scale = min(usable_w / iw, max_h / ih, 1.0)
                    draw_w, draw_h = iw * scale, ih * scale
                    if y - draw_h < bottom_y and cur_lines:
                        flush_page()
                        pages_so_far += 1
                    ix = left_margin + (usable_w - draw_w) / 2.0
                    # EN/IT: special entry, handled at page-emission time /
                    # voce speciale, gestita al momento dell'emissione pagina
                    cur_lines.append(("img", mimg.group("src"),
                                      ix, y - draw_h, draw_w, draw_h))
                    y -= draw_h + leading * 0.5
                    alt = mimg.group("alt").strip()
                    if alt:
                        cap_sz = font_size * 0.85
                        for row in _wrap_centered(alt, cap_sz):
                            if y < bottom_y:
                                flush_page()
                                pages_so_far += 1
                            lw = seg_w(row, cap_sz)
                            cur_lines.append(((page_w - lw) / 2.0, y,
                                              [(row, "italic")], cap_sz))
                            y -= cap_sz * 1.4
                        y -= leading * 0.3
                    continue
                segments, sz, indent, extra, _force = parse_md_line(raw_line, font_size)
                line_leading = leading * (sz / font_size)
                avail = usable_w - indent
                # EN: the LAST wrapped line of a paragraph line is never
                #     justified (it would look stretched); headings (_force ==
                #     "bold") are never justified either.
                # IT: l'ULTIMA riga spezzata di una riga-paragrafo non si
                #     giustifica mai (apparirebbe dilatata); nemmeno le
                #     intestazioni (_force == "bold") si giustificano.
                wrapped = wrap_segments(segments, sz, avail)
                can_justify = justify and _force != "bold"
                for li, run_line in enumerate(wrapped):
                    if y < bottom_y:
                        flush_page()
                        pages_so_far += 1
                    is_last = (li == len(wrapped) - 1)
                    jw = avail if (can_justify and not is_last) else None
                    cur_lines.append((left_margin + indent, y, run_line, sz, jw))
                    y -= line_leading
                if extra:
                    y -= extra
            y -= leading * 0.5
    flush_page()
    pages_so_far += 1

    chapter_pages = pages        # le pagine dei capitoli appena impaginate
    pages = pages_before_chapters
    # Posizione in cui finira' l'indice stampato, da segnare ORA: 'pages' e
    # 'pages_before_chapters' sono da qui in poi la stessa lista, quindi
    # misurarla dopo aver impaginato l'indice restituirebbe la pagina
    # sbagliata.
    toc_page_index = len(pages)

    # Intestazione di pagina (running header): ogni pagina di capitolo mostra il
    # TITOLO DEL CAPITOLO a cui appartiene, non il titolo del progetto. La pagina
    # di capitolo in posizione j (0-based) ha numero visibile j+1; il suo
    # capitolo e' l'ultimo il cui chapter_start_page <= j+1.
    chapter_page_header = []
    for j in range(len(chapter_pages)):
        vis = j + 1
        title_for_page = title   # ripiego: titolo progetto
        for ci2, start in enumerate(chapter_start_page):
            if start <= vis and ci2 < len(chapter_titles):
                title_for_page = chapter_titles[ci2]
            else:
                break
        chapter_page_header.append(title_for_page)

    # 1b) pagina indice (sommario), senza numero, con i NUMERI DI PAGINA reali
    if chapter_titles:
        # titolo "Indice" centrato in alto
        tl_size = font_size * 1.7
        tw = seg_w(toc_label, tl_size)
        cur_lines.append(((page_w - tw) / 2.0, content_top_y,
                          [(toc_label, "bold")], tl_size))
        yy = content_top_y - leading * 2.4
        for idx_i, ct in enumerate(chapter_titles):
            page_no = (chapter_start_page[idx_i]
                       if idx_i < len(chapter_start_page) else idx_i + 1)
            left = f"{ct}"
            right = str(page_no)
            # titolo a sinistra, numero di pagina a destra, puntini di guida
            lw = seg_w(left, font_size)
            rw = seg_w(right, font_size)
            avail = usable_w - lw - rw - seg_w("  ", font_size)
            dots = ""
            dot_w = seg_w(".", font_size)
            if avail > dot_w and dot_w > 0:
                dots = "." * int(avail / dot_w)
            cur_lines.append((left_margin, yy, [(left + " ", "regular")], font_size))
            if dots:
                cur_lines.append((left_margin + lw + seg_w(" ", font_size), yy,
                                  [(dots, "regular")], font_size))
            cur_lines.append((page_w - m_outer - rw, yy,
                              [(right, "regular")], font_size))
            yy -= leading * 1.4
            if yy < bottom_y:
                flush_page("plain")
                yy = content_top_y
        flush_page("plain")

    # EN: bookmarks (the PDF outline) need the ABSOLUTE position of each
    #     chapter's first page inside the final page list — not the visible
    #     page number, which skips cover, index and colophon. We record it here,
    #     the one moment when both halves of the list are known.
    # IT: i segnalibri (l'indice di navigazione del PDF) vogliono la posizione
    #     ASSOLUTA della prima pagina di ogni capitolo nell'elenco finale, non
    #     il numero di pagina visibile, che salta copertina, indice e colophon.
    #     La registriamo qui, l'unico momento in cui si conoscono entrambe le
    #     meta' dell'elenco.
    outline_entries = []           # (titolo, indice assoluto di pagina)
    if chapter_titles:
        # la pagina dell'indice stampato e' la prima dopo copertina e
        # frontespizio: ci si mette un segnalibro, e' li' che si torna
        outline_entries.append((toc_label, toc_page_index))
    chapter_pages_offset = len(pages)
    for ci3, ct in enumerate(chapter_titles or []):
        if ci3 < len(chapter_start_page):
            outline_entries.append(
                (ct, chapter_pages_offset + chapter_start_page[ci3] - 1))

    # ora accodiamo le pagine dei capitoli (gia' impaginate sopra)
    pages.extend(chapter_pages)

    # 3) colophon (ultima pagina, senza numero)
    if colophon_paragraphs:
        add_colophon_page(colophon_paragraphs)

    if not pages:
        pages = [([], None)]

    total = len(pages)

    # costruisci gli oggetti PDF (come byte)
    objects = []

    def add_obj(body_bytes):
        objects.append(body_bytes)
        return len(objects)

    # mappa "F1".."F4" -> id oggetto font (per le Resources)
    font_ids = {}

    def make_embedded_font(metrics, psname, italic):
        ttf = metrics["data"]
        fontfile_id = add_obj(
            (f"<< /Length {len(ttf)} /Length1 {len(ttf)} >>\nstream\n").encode("latin-1")
            + ttf + b"\nendstream")
        bbox = metrics["bbox"]
        wbc = metrics.get("widths_by_code")
        # Flag del descrittore di font (PDF spec):
        #   1 = FixedPitch (solo monospace), 2 = Serif, 32 = Nonsymbolic, 64 = Italic
        # Per un font proporzionale (con widths_by_code) NON impostiamo FixedPitch,
        # altrimenti i visualizzatori assumono larghezza fissa.
        if wbc is not None:
            flags = 2 + 32 + (64 if italic else 0)      # Serif, Nonsymbolic
        else:
            flags = 1 + 32 + (64 if italic else 0)      # FixedPitch, Nonsymbolic
        ital_angle = -12 if italic else 0
        descriptor_id = add_obj(
            (f"<< /Type /FontDescriptor /FontName /{psname} /Flags {flags} "
             f"/FontBBox [{bbox[0]} {bbox[1]} {bbox[2]} {bbox[3]}] "
             f"/ItalicAngle {ital_angle} /Ascent {metrics['ascent']} "
             f"/Descent {metrics['descent']} /CapHeight {metrics['ascent']} "
             f"/StemV 80 /FontFile2 {fontfile_id} 0 R >>").encode("latin-1"))
        # Array /Widths: larghezza reale per ogni carattere se disponibile
        # (font proporzionale), altrimenti larghezza fissa (monospace).
        if wbc is not None:
            default = metrics.get("advance1000", 500)
            widths = " ".join(str(wbc.get(code, default))
                              for code in range(32, 256))
        else:
            widths = " ".join(str(metrics["advance1000"]) for _ in range(32, 256))
        return add_obj(
            (f"<< /Type /Font /Subtype /TrueType /BaseFont /{psname} "
             f"/FirstChar 32 /LastChar 255 /Widths [{widths}] "
             f"/FontDescriptor {descriptor_id} 0 R "
             f"/Encoding /WinAnsiEncoding >>").encode("latin-1"))

    if reg:
        defs = [("F1", "regular", False), ("F2", "bold", False),
                ("F3", "italic", True), ("F4", "bolditalic", True)]
        for fid, style, italic in defs:
            metrics = embed_fonts.get(style) or reg   # ripiego sul regular
            psname = f"{embed_font_name}-{style}"
            font_ids[fid] = make_embedded_font(metrics, psname, italic)
    else:
        # font core (fallback senza incorporamento)
        font_ids["F1"] = add_obj(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman "
            b"/Encoding /WinAnsiEncoding >>")
        font_ids["F2"] = add_obj(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold "
            b"/Encoding /WinAnsiEncoding >>")
        font_ids["F3"] = add_obj(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic "
            b"/Encoding /WinAnsiEncoding >>")
        font_ids["F4"] = add_obj(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-BoldItalic "
            b"/Encoding /WinAnsiEncoding >>")

    pages_obj_id = len(objects) + 1
    objects.append(None)

    # risorse font condivise (riferite da ogni pagina)
    font_res = " ".join(f"/{fid} {oid} 0 R" for fid, oid in font_ids.items())

    page_obj_ids = []
    visible_number = 0
    # EN: each distinct attached image becomes ONE shared PDF XObject, reused
    #     by every page that shows it: name -> object id.
    # IT: ogni immagine allegata distinta diventa UN solo XObject PDF,
    #     riutilizzato da ogni pagina che la mostra: nome -> id oggetto.
    image_obj_ids = {}
    for i, (lines, kind) in enumerate(pages):
        parts = []
        # pagina copertina-immagine: kind = ("image", jpeg_bytes, w, h)
        if isinstance(kind, tuple) and kind and kind[0] == "image":
            _, jpeg_bytes, img_w, img_h = kind
            img_stream = (f"<< /Type /XObject /Subtype /Image /Width {img_w} "
                          f"/Height {img_h} /ColorSpace /DeviceRGB "
                          f"/BitsPerComponent 8 /Filter /DCTDecode "
                          f"/Length {len(jpeg_bytes)} >>\nstream\n").encode("latin-1") \
                         + jpeg_bytes + b"\nendstream"
            img_id = add_obj(img_stream)
            scale = min(page_w / img_w, page_h / img_h)
            draw_w = img_w * scale; draw_h = img_h * scale
            off_x = (page_w - draw_w) / 2.0; off_y = (page_h - draw_h) / 2.0
            parts.append(b"q")
            parts.append(f"{draw_w:.2f} 0 0 {draw_h:.2f} {off_x:.2f} {off_y:.2f} cm".encode("latin-1"))
            parts.append(b"/Im0 Do")
            parts.append(b"Q")
            stream = b"\n".join(parts)
            body = (f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
                    + stream + b"\nendstream")
            cid = add_obj(body)
            pid = add_obj(
                (f"<< /Type /Page /Parent {pages_obj_id} 0 R "
                 f"/MediaBox [0 0 {page_w:.0f} {page_h:.0f}] "
                 f"/Resources << /Font << {font_res} >> "
                 f"/XObject << /Im0 {img_id} 0 R >> >> "
                 f"/Contents {cid} 0 R >>").encode("latin-1"))
            page_obj_ids.append(pid)
            continue
        if kind == "cover":
            # grafica vettoriale della copertina prima del testo
            parts.extend(_cover_graphics_ops(page_w, page_h))
        # spostamento orizzontale per la rilegatura: sulle pagine di contenuto
        # numerate, il recto (pagina fisica dispari) ha il margine interno a
        # sinistra, quindi il blocco di testo si sposta a destra del 'gutter';
        # il verso (pagina pari) resta al margine esterno. Header e numero di
        # pagina restano centrati sulla pagina fisica e NON vengono spostati.
        page_shift = 0.0
        if kind is None and gutter:
            physical_page = i + 1           # 1 = prima pagina fisica (recto)
            if physical_page % 2 == 1:      # recto: interno a sinistra
                page_shift = gutter
        # EN: attached chapter images: drawn BEFORE the text block (outside
        #     BT/ET, as required by the PDF graphics model). Each entry is
        #     ("img", name, x, y, w, h); the XObject is created once and its
        #     id is referenced by this page's /XObject resources.
        # IT: immagini allegate ai capitoli: disegnate PRIMA del blocco di
        #     testo (fuori da BT/ET, come richiede il modello grafico PDF).
        #     Ogni voce e' ("img", nome, x, y, w, h); l'XObject viene creato
        #     una sola volta e il suo id e' citato nelle risorse /XObject
        #     della pagina.
        page_xobjects = {}
        text_lines = []
        for entry in lines:
            if entry and entry[0] == "img":
                _tag, iname, ix, iy, dw, dh = entry
                oid = image_obj_ids.get(iname)
                if oid is None:
                    jpeg_b, iw, ih = chapter_images[iname]
                    oid = add_obj(
                        (f"<< /Type /XObject /Subtype /Image /Width {iw} "
                         f"/Height {ih} /ColorSpace /DeviceRGB "
                         f"/BitsPerComponent 8 /Filter /DCTDecode "
                         f"/Length {len(jpeg_b)} >>\nstream\n").encode("latin-1")
                        + jpeg_b + b"\nendstream")
                    image_obj_ids[iname] = oid
                res_name = f"ImA{oid}"
                page_xobjects[res_name] = oid
                parts.append(b"q")
                parts.append(f"{dw:.2f} 0 0 {dh:.2f} "
                             f"{ix + page_shift:.2f} {iy:.2f} cm"
                             .encode("latin-1"))
                parts.append(f"/{res_name} Do".encode("latin-1"))
                parts.append(b"Q")
            else:
                text_lines.append(entry)
        parts.append(b"BT")
        cur_fid = None
        cur_size = None
        cur_tw = 0.0   # word-spacing (Tw) attivo; 0 = normale (allineato a sx)
        for entry in text_lines:
            # EN: body lines may carry a 5th item, the justify target width
            #     (float) or None. Older 4-item lines (headings, centered,
            #     covers) are left flush as before.
            # IT: le righe di corpo possono portare un 5° elemento, la
            #     larghezza-obiettivo per la giustificazione (float) o None. Le
            #     righe a 4 elementi (intestazioni, centrate, copertine)
            #     restano allineate come prima.
            if len(entry) >= 5:
                x, ly, runs, sz, jw = entry[0], entry[1], entry[2], entry[3], entry[4]
            else:
                x, ly, runs, sz = entry
                jw = None
            # EN: compute word-spacing so the line reaches the target width:
            #     extra = target - natural, spread over the space characters.
            # IT: calcola lo spazio-parola perche' la riga raggiunga la
            #     larghezza-obiettivo: extra = obiettivo - naturale, diviso tra
            #     i caratteri di spazio.
            tw = 0.0
            if jw:
                natural = sum(seg_w(t, sz) for (t, _s) in runs if t)
                n_spaces = sum(t.count(" ") for (t, _s) in runs if t)
                if n_spaces > 0 and natural < jw:
                    extra = jw - natural
                    tw = extra / n_spaces
                    # non dilatare oltre misura: se servisse piu' di ~1 en per
                    # spazio la riga e' troppo corta (parole lunghissime),
                    # meglio lasciarla allineata a sinistra.
                    if tw > sz * 0.9:
                        tw = 0.0
            if tw != cur_tw:
                parts.append(f"{tw:.3f} Tw".encode("latin-1"))
                cur_tw = tw
            parts.append(f"1 0 0 1 {x + page_shift:.2f} {ly:.2f} Tm".encode("latin-1"))
            for (text, style) in runs:
                if text == "":
                    continue
                fid = style_to_fid.get(style, "F1")
                if fid != cur_fid or sz != cur_size:
                    parts.append(f"/{fid} {sz:.1f} Tf".encode("latin-1"))
                    cur_fid, cur_size = fid, sz
                parts.append(b"(" + _pdf_escape_bytes(_to_winansi(text)) + b") Tj")
        # ripristina lo spazio-parola normale prima di intestazione/numero
        if cur_tw != 0.0:
            parts.append(b"0 Tw")
            cur_tw = 0.0
        if kind is None:
            visible_number += 1
            head_txt = title
            if 0 <= visible_number - 1 < len(chapter_page_header):
                head_txt = chapter_page_header[visible_number - 1]
            if head_txt:
                hw = seg_w(head_txt, 10)
                hx = (page_w - hw) / 2.0
                hy = page_h - margin + leading * 0.4
                parts.append(b"ET BT")
                parts.append(b"/F1 10 Tf")
                parts.append(f"1 0 0 1 {hx:.2f} {hy:.2f} Tm".encode("latin-1"))
                parts.append(b"(" + _pdf_escape_bytes(_to_winansi(head_txt)) + b") Tj")
                cur_fid = cur_size = None
            label = str(visible_number)
            lw = seg_w(label, 10)
            nx = (page_w - lw) / 2.0
            ny = margin / 2.0
            parts.append(b"ET BT")
            parts.append(b"/F1 10 Tf")
            parts.append(f"1 0 0 1 {nx:.2f} {ny:.2f} Tm".encode("latin-1"))
            parts.append(b"(" + _pdf_escape_bytes(_to_winansi(label)) + b") Tj")
        parts.append(b"ET")
        stream = b"\n".join(parts)
        body = (f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
                + stream + b"\nendstream")
        cid = add_obj(body)
        # EN: page resources: shared fonts plus this page's image XObjects.
        # IT: risorse di pagina: font condivisi piu' gli XObject immagine
        #     di questa pagina.
        xres = ""
        if page_xobjects:
            xrefs = " ".join(f"/{n} {oid} 0 R"
                             for n, oid in page_xobjects.items())
            xres = f"/XObject << {xrefs} >> "
        pid = add_obj(
            (f"<< /Type /Page /Parent {pages_obj_id} 0 R "
             f"/MediaBox [0 0 {page_w:.0f} {page_h:.0f}] "
             f"/Resources << /Font << {font_res} >> {xres}>> "
             f"/Contents {cid} 0 R >>").encode("latin-1"))
        page_obj_ids.append(pid)

    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects[pages_obj_id - 1] = (
        f"<< /Type /Pages /Count {total} /Kids [{kids}] >>".encode("latin-1"))

    # EN: the outline — the clickable chapter tree in the reader's sidebar.
    #     Each item is an object pointing at a page; the items form a doubly
    #     linked list (/Prev, /Next) hanging off a single /Outlines root.
    #     Object ids must be known before the bodies are written, so we reserve
    #     empty slots first and fill them in afterwards.
    # IT: l'indice di navigazione: l'albero dei capitoli su cui si fa clic
    #     nella barra laterale del lettore. Ogni voce e' un oggetto che punta a
    #     una pagina; le voci formano una lista doppiamente concatenata
    #     (/Prev, /Next) appesa a un'unica radice /Outlines. Gli id degli
    #     oggetti servono prima dei contenuti, quindi si prenotano le caselle
    #     vuote e si riempiono dopo.
    voci = [(t, i) for t, i in outline_entries if 0 <= i < len(page_obj_ids)]
    outlines_id = None
    if voci:
        outlines_id = add_obj(None)
        voce_ids = [add_obj(None) for _ in voci]
        for k, (titolo, page_index) in enumerate(voci):
            pid = page_obj_ids[page_index]
            prev = f"/Prev {voce_ids[k - 1]} 0 R " if k > 0 else ""
            nxt = f"/Next {voce_ids[k + 1]} 0 R " if k < len(voci) - 1 else ""
            # /XYZ 0 altezza 0 = apri la pagina in cima, senza cambiare lo zoom
            objects[voce_ids[k] - 1] = (
                b"<< /Title ("
                + _pdf_escape_bytes(_to_winansi(titolo))
                + f") /Parent {outlines_id} 0 R {prev}{nxt}"
                  f"/Dest [{pid} 0 R /XYZ 0 {page_h:.0f} 0] >>".encode("latin-1"))
        objects[outlines_id - 1] = (
            f"<< /Type /Outlines /First {voce_ids[0]} 0 R "
            f"/Last {voce_ids[-1]} 0 R /Count {len(voce_ids)} >>").encode("latin-1")

    # /PageMode /UseOutlines chiede al lettore di aprire subito il pannello dei
    # segnalibri: senza, molti visualizzatori li tengono nascosti e sembra che
    # non ci siano.
    extra_cat = (f"/Outlines {outlines_id} 0 R /PageMode /UseOutlines "
                 if outlines_id else "")
    catalog_id = add_obj(
        (f"<< /Type /Catalog /Pages {pages_obj_id} 0 R "
         f"{extra_cat}>>").encode("latin-1"))

    # 3) serializza con tabella xref
    out = bytearray()
    out += b"%PDF-1.4\n"
    offsets = [0] * (len(objects) + 1)
    for num, body in enumerate(objects, start=1):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode("latin-1")
        out += body
        out += b"\nendobj\n"
    xref_pos = len(out)
    n_obj = len(objects) + 1
    out += f"xref\n0 {n_obj}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for num in range(1, n_obj):
        out += f"{offsets[num]:010d} 00000 n \n".encode("latin-1")
    out += (f"trailer\n<< /Size {n_obj} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF").encode("latin-1")

    with open(path, "wb") as f:
        f.write(out)


# ---- Colori: le due famiglie di tema ----------------------------------------
# L'interfaccia ha DUE famiglie di colori, ognuna con la sua versione chiara e
# la sua versione scura (quattro combinazioni in tutto):
#
#   "rusca"    — la famiglia prugna, abbinata alla distribuzione RuscaLinux.
#                E' il tema predefinito.
#   "standard" — famiglia neutra e classica (grafite, lino, blu ardesia),
#                ispirata all'abbinamento cromatico di Scrivener, per chi
#                preferisce un aspetto piu' sobrio e tradizionale.
#
# NB: "PLUM" qui e' il COLORE prugna ("plum" in inglese), il tema cromatico
# storico dell'applicazione — non un residuo del vecchio nome del programma.

# --- famiglia prugna (tema "rusca") ------------------------------------------
PLUM        = "#8E4585"   # prugna
PLUM_DARK   = "#5C2A55"   # prugna scuro (nomi file e note)
PLUM_LIGHT  = "#D9B8D4"   # prugna chiaro per le sfumature
WHITE       = "#FFFFFF"

# Tonalità aggiuntive per il tema scuro (sempre nella famiglia prugna)
PLUM_NIGHT  = "#2A1226"   # sfondo molto scuro, base del tema dark
PLUM_PANEL  = "#3A1A35"   # pannelli laterali nel tema dark
PLUM_INK    = "#241420"   # area di scrittura quasi nera, tono prugna
PLUM_GLOW   = "#E0A8D8"   # prugna chiaro luminoso per accenti su scuro
PAPER       = "#F7F2F5"   # testo principale su sfondo scuro (bianco caldo)
PLUM_CODE   = "#7A3B72"   # prugna media per il codice nel tema chiaro

# --- "Ametista": il prugna di RuscaLinux, rivisto per la vista ---------------
# Le fasce restano prugna piene: sono l'identita' della distribuzione e vanno
# tenute. Ma l'identita' sta nelle cornici, non nella pagina — e la pagina e'
# dove si guarda per ore. Prima erano nero pieno su bianco pieno, 21:1, il
# valore che affatica di piu': ora la carta ha un soffio di prugna e
# l'inchiostro e' grafite violacea, 13,8:1.
AMETISTA_HUES = {
    "paper":        "#FAF6F9",   # carta con un soffio di prugna
    "panel":        "#F1EAEF",   # pannelli
    "ink":          "#2E252C",   # grafite violacea, mai nero pieno
    "night":        "#20141D",   # notte prugna
    "night_panel":  "#2A1826",   # pannelli nel tema scuro
    "night_ink":    "#1B1017",   # area di scrittura scura
    "parchment":    "#DCD2DA",   # testo sul fondo scuro, non bianco pieno
    "accent":       PLUM,
    "dark":         PLUM_DARK,
    "light":        PLUM_LIGHT,
    "glow":         PLUM_GLOW,
    "code":         PLUM_CODE,
    "wrap_light":   "#F3E9F1",
    "wrap_dark":    "#2E1B2A",
    "text":         PLUM_DARK,
    # le fasce: qui il colore pieno resta, ed e' una scelta
    "chrome_a":     PLUM,
    "chrome_b":     PLUM_LIGHT,
    "menubar_a":    PLUM,
    "menubar_b":    PLUM_DARK,
    "on_chrome":    WHITE,
    "night_chrome_a":  PLUM_DARK,
    "night_chrome_b":  "#20141D",
    "night_menubar_a": PLUM,
    "night_menubar_b": PLUM_DARK,
    "night_on_chrome": WHITE,
}


# --- "Giada": verde salvia, la piu' riposante delle cinque ---------------------
# Il criterio non e' il contrasto massimo, e' il contrasto GIUSTO. Nero puro su
# bianco puro da' 21:1 e sembra la scelta piu' leggibile: non lo e'. Nel tema
# chiaro il bianco pieno e' una sorgente luminosa puntata negli occhi; nel tema
# scuro il bianco su nero produce alone, e le lettere sbordano sul fondo per
# chiunque abbia un po' di astigmatismo. La fascia buona per il corpo del testo
# sta fra 12:1 e 14:1, e i valori qui sotto ci stanno dentro.
PAPER_WHITE    = "#FAF8F4"   # carta: avorio appena accennato, non bianco pieno
CREAM_PANEL    = "#F0ECE4"   # pannelli: un gradino sotto la carta
INK            = "#2B2A28"   # inchiostro: grafite, mai nero pieno
NIGHT_WARM     = "#1B1D1C"   # fondo scuro: quasi nero, non nero
NIGHT_PANEL    = "#23262A"   # pannelli nel tema scuro
NIGHT_INK      = "#171918"   # area di scrittura scura
PARCHMENT      = "#D6D3CC"   # testo su fondo scuro: circa l'85% del bianco

# L'accento tende al verde perche' l'occhio mette a fuoco il centro dello
# spettro con il minimo sforzo: il blu saturo diffonde e sfoca i bordi, il
# rosso va a fuoco dietro la retina. Ma conta di piu' QUANTO POCO si usa: la
# selezione, i filetti, i pulsanti. Le fasce restano neutre, perche' un colore
# pieno su grandi superfici stanca qualunque tinta sia.
GIADA_HUES = {
    "accent":     "#3A6455",   # salvia: selezione e pulsanti
    "dark":       "#2C4C41",   # salvia profonda
    "light":      "#D7E4DD",   # verde polvere: sfumature
    "glow":       "#8FC4AE",   # salvia luminosa: accenti su fondo scuro
    "code":       "#3F6657",   # verde bosco: codice nel tema chiaro
    "wrap_light": "#EBF1ED",   # velo verde: paragrafi spezzati, tema chiaro
    "wrap_dark":  "#22302B",   # velo verde: paragrafi spezzati, tema scuro
    "text":       "#33574A",   # titoli, nomi dei capitoli, barra di stato
    # le fasce dell'interfaccia: neutre, con il testo scuro sopra
    "chrome_a":   "#F0ECE4",
    "chrome_b":   "#FAF8F4",
    "menubar_a":  "#F0ECE4",
    "menubar_b":  "#E6E1D8",
    "on_chrome":  "#2B2A28",
    # nel tema scuro le fasce sono grafite e il testo torna chiaro
    "night_chrome_a":  "#23262A",
    "night_chrome_b":  "#1B1D1C",
    "night_menubar_a": "#23262A",
    "night_menubar_b": "#191B1A",
    "night_on_chrome": "#D6D3CC",
}


# --- "Rubino": rosso profondo su carta con un velo rosato -------------------
RUBINO_HUES = {
    "paper":        "#FBF6F5", "panel":       "#F2E9E7",
    "ink":          "#2E2523",
    "night":        "#1E1516", "night_panel": "#2A1E1F",
    "night_ink":    "#191112", "parchment":   "#DED2D0",
    "accent":       "#8E3636", "dark":        "#6B2727",
    "light":        "#EBD4D2", "glow":        "#E8A6A0",
    "code":         "#7E3030",
    "wrap_light":   "#F6EAE8", "wrap_dark":   "#2C1E1F",
    "text":         "#6B2727",
    "chrome_a":     "#F2E9E7", "chrome_b":    "#FBF6F5",
    "menubar_a":    "#F2E9E7", "menubar_b":   "#E8DAD7",
    "on_chrome":    "#2E2523",
    "night_chrome_a":  "#2A1E1F", "night_chrome_b":  "#1E1516",
    "night_menubar_a": "#2A1E1F", "night_menubar_b": "#1A1213",
    "night_on_chrome": "#DED2D0",
}

# --- "Zaffiro": blu profondo, l'accento tenuto basso di saturazione ---------
# Il blu e' il colore che l'occhio mette a fuoco peggio: diffonde e sfoca i
# bordi. Per questo qui l'accento e' desaturato e resta sulla sola selezione,
# mentre le fasce restano neutre. E' il piu' delicato dei cinque, e va trattato
# con piu' prudenza degli altri, non con meno.
ZAFFIRO_HUES = {
    "paper":        "#F8F9FC", "panel":       "#ECEEF4",
    "ink":          "#262A33",
    "night":        "#141821", "night_panel": "#1D222D",
    "night_ink":    "#11141B", "parchment":   "#D2D7E0",
    "accent":       "#2E4F7E", "dark":        "#213A5E",
    "light":        "#D3DEEC", "glow":        "#9FBEE4",
    "code":         "#2B4A75",
    "wrap_light":   "#EDF1F7", "wrap_dark":   "#1C2331",
    "text":         "#213A5E",
    "chrome_a":     "#ECEEF4", "chrome_b":    "#F8F9FC",
    "menubar_a":    "#ECEEF4", "menubar_b":   "#DFE3EC",
    "on_chrome":    "#262A33",
    "night_chrome_a":  "#1D222D", "night_chrome_b":  "#141821",
    "night_menubar_a": "#1D222D", "night_menubar_b": "#12161E",
    "night_on_chrome": "#D2D7E0",
}

# --- "Ambra": miele e ottone, la piu' calda delle cinque ---------------------
AMBRA_HUES = {
    "paper":        "#FBF7EE", "panel":       "#F2EBDD",
    "ink":          "#2E2820",
    "night":        "#1E1A14", "night_panel": "#2A251C",
    "night_ink":    "#191612", "parchment":   "#DCD4C4",
    "accent":       "#7C5A20", "dark":        "#5C4216",
    "light":        "#EDDFC2", "glow":        "#E0BC7A",
    "code":         "#6E501C",
    "wrap_light":   "#F7F0E0", "wrap_dark":   "#2C261A",
    "text":         "#5C4216",
    "chrome_a":     "#F2EBDD", "chrome_b":    "#FBF7EE",
    "menubar_a":    "#F2EBDD", "menubar_b":   "#E8DEC9",
    "on_chrome":    "#2E2820",
    "night_chrome_a":  "#2A251C", "night_chrome_b":  "#1E1A14",
    "night_menubar_a": "#2A251C", "night_menubar_b": "#1A1712",
    "night_on_chrome": "#DCD4C4",
}


# Nomi delle famiglie. Il valore salvato nelle impostazioni ("theme_family") e'
# una di queste stringhe: qualunque altro valore ripiega sul predefinito.
USER_THEME_PREFIX  = "utente:"   # codice dei temi letti da disco
# Cinque gemme, cinque tavolozze. Cambia la pietra, non il criterio: nessun
# bianco pieno, nessun nero pieno, il corpo del testo fra 12:1 e 14:1.
THEME_AMETISTA = "ametista"   # prugna, il tema di RuscaLinux
THEME_RUBINO   = "rubino"     # rosso profondo
THEME_ZAFFIRO  = "zaffiro"    # blu, desaturato di proposito
THEME_GIADA    = "giada"      # verde salvia
THEME_AMBRA    = "ambra"      # miele e ottone
BUILTIN_THEMES = (THEME_AMETISTA, THEME_RUBINO, THEME_ZAFFIRO,
                  THEME_GIADA, THEME_AMBRA)
# nomi storici, tenuti perche' il codice esterno continui a funzionare
THEME_RUSCA, THEME_STANDARD, THEME_VELLUTO = (
    THEME_AMETISTA, THEME_GIADA, THEME_AMBRA)
# THEMES cresce a runtime con i temi trovati nella cartella dell'utente.
THEMES = BUILTIN_THEMES
DEFAULT_THEME = THEME_RUSCA

# Vecchi codici non piu' esistenti: chi li aveva salvati non deve ritrovarsi
# spedito al tema predefinito senza spiegazione.
THEME_ALIASES = {
    "standard_blue": THEME_GIADA,
    "standard_red":  THEME_GIADA,
    "rusca":         THEME_AMETISTA,
    "standard":      THEME_GIADA,
    "velluto":       THEME_AMBRA,
    "lapislazzuli":  THEME_ZAFFIRO,   # era mezzanotte e ottone: il blu resta
}

# Accento di ciascuna famiglia standard.
STANDARD_HUES = {
    THEME_AMETISTA: AMETISTA_HUES,
    THEME_RUBINO:   RUBINO_HUES,
    THEME_ZAFFIRO:  ZAFFIRO_HUES,
    THEME_GIADA:    GIADA_HUES,
    THEME_AMBRA:    AMBRA_HUES,
}

# I nomi delle gemme sono tradotti nelle lingue complete; le altre ripiegano
# sull'inglese, come per ogni altra stringa.
THEME_LABEL_KEYS = {
    THEME_AMETISTA: "theme_ametista",
    THEME_RUBINO:   "theme_rubino",
    THEME_ZAFFIRO:  "theme_zaffiro",
    THEME_GIADA:    "theme_giada",
    THEME_AMBRA:    "theme_ambra",
}

# EN/IT: a coloured dot beside each name, so the menu shows the theme's colour
# and not only its name. GTK menu labels are PLAIN TEXT — no markup, no per-item
# colour — so the dot is a character, not a painted label: it is the only way to
# get colour into a menu entry without replacing the menu with custom widgets.
# The emoji palette is fixed, so these are the nearest hues, not the exact ones.
# Un pallino colorato accanto a ogni nome, così il menu mostra il colore del
# tema e non solo il suo nome. Le etichette dei menu GTK sono TESTO SEMPLICE —
# niente markup, niente colore per singola voce — quindi il pallino e' un
# carattere, non un'etichetta dipinta: e' l'unico modo di portare colore in una
# voce di menu senza sostituire il menu con widget su misura. La tavolozza
# delle emoji e' fissa, quindi sono le tinte piu' vicine, non quelle esatte.
THEME_DOTS = {
    THEME_AMETISTA: "\U0001F7E3",   # pallino viola
    THEME_RUBINO:   "\U0001F534",   # pallino rosso
    THEME_ZAFFIRO:  "\U0001F535",   # pallino blu
    THEME_GIADA:    "\U0001F7E2",   # pallino verde
    THEME_AMBRA:    "\U0001F7E0",   # pallino arancio
}


def theme_dot(theme):
    """Pallino colorato di un tema, stringa vuota se non ne ha uno (i temi
    scritti dagli utenti non ne hanno)."""
    return THEME_DOTS.get(theme, "")
THEME_LABEL_FALLBACK = {
    THEME_AMETISTA: "Ametista",
    THEME_RUBINO:   "Rubino",
    THEME_ZAFFIRO:  "Zaffiro",
    THEME_GIADA:    "Giada",
    THEME_AMBRA:    "Ambra",
}


def resolve_theme(code):
    """Traduce un codice di tema salvato nelle impostazioni in uno valido,
    tenendo conto dei nomi vecchi. Ripiega sul predefinito se non esiste."""
    code = THEME_ALIASES.get(code, code)
    return code if code in THEMES else DEFAULT_THEME


def _rgba(hex_color, alpha):
    """Da #RRGGBB alla forma rgba() del CSS, per le superfici traslucide."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha:.2f})"


def _standard_palette(hues, dark):
    """Costruisce una tavolozza standard dai suoi soli colori d'accento.

    I neutri (bianco caldo, crema, bruno notte) sono identici per tutte le
    varianti: e' l'accento a distinguerle. Un tema nuovo vuol dire sette colori
    e nient'altro — ed e' esattamente cio' che scrive chi si fa il suo tema
    nella cartella themes/.
    """
    accent, accent_dark = hues["accent"], hues["dark"]
    accent_light, glow = hues["light"], hues["glow"]
    # Chiavi facoltative: un tema con accento CHIARO deve dire quale testo ci
    # va sopra e di che colore sono i titoli, altrimenti valgono i valori che
    # funzionano per un accento pieno — bianco sopra, accento scuro nei titoli.
    on_accent = hues.get("on_accent", WHITE)
    testo = hues.get("text", accent_dark)
    # I NEUTRI — carta, pannelli, inchiostro, fondo notte — sono la meta' del
    # carattere di un tema: un avorio caldo e un bianco freddo raccontano cose
    # diverse. Un tema puo' indicarli; se tace valgono quelli di Quiete, che
    # restano la scelta prudente per starci ore.
    carta = hues.get("paper", PAPER_WHITE)
    pannelli = hues.get("panel", CREAM_PANEL)
    inchiostro = hues.get("ink", INK)
    notte = hues.get("night", NIGHT_WARM)
    notte_pann = hues.get("night_panel", NIGHT_PANEL)
    notte_ink = hues.get("night_ink", NIGHT_INK)
    chiaro_su_scuro = hues.get("parchment", PARCHMENT)
    # Le FASCE dell'interfaccia (barra superiore, barra dei menu) sono un ruolo
    # a parte dall'accento. Un tema puo' volerle neutre e tenere il colore per
    # la sola selezione: un colore pieno steso su grandi superfici stanca
    # qualunque tinta sia. Se il tema non dice nulla, valgono l'accento e il
    # suo scuro, cioe' il comportamento di sempre.
    if dark:
        accent = hues.get("night_accent", accent)
        accent_dark = hues.get("night_accent_dark", accent_dark)
        chrome_a = hues.get("night_chrome_a", accent_dark)
        chrome_b = hues.get("night_chrome_b", NIGHT_WARM)
        menubar_a = hues.get("night_menubar_a", accent)
        menubar_b = hues.get("night_menubar_b", accent_dark)
        on_chrome = hues.get("night_on_chrome",
                             hues.get("on_accent_dark", WHITE))
        return dict(
            accent=accent, accent_dark=accent_dark, accent_light=accent_light,
            on_accent=hues.get("on_accent_dark", WHITE),
            menubar_a=menubar_a, menubar_b=menubar_b, on_chrome=on_chrome,
            bg_top=notte, bg_bottom=notte_pann,
            header_a=chrome_a, header_b=chrome_b,
            panel_bg=notte_pann,
            list_text=glow,
            editor_bg=notte_ink, editor_fg=chiaro_su_scuro,
            notes_fg=chiaro_su_scuro,
            title_fg=glow,
            status_a=accent_dark, status_b=notte,
            status_fg=glow,
            findbar_bg="rgba(20,22,26,0.95)",
            dialog_fg=chiaro_su_scuro,
            entry_bg=notte_ink, entry_fg=chiaro_su_scuro,
            head=glow, code=glow, marker=accent,
            wrapmark=hues["wrap_dark"],
        )
    return dict(
        accent=accent, accent_dark=accent_dark, accent_light=accent_light,
        on_accent=on_accent,
        menubar_a=hues.get("menubar_a", accent),
        menubar_b=hues.get("menubar_b", accent_dark),
        on_chrome=hues.get("on_chrome", on_accent),
        bg_top=accent_light, bg_bottom=carta,
        header_a=hues.get("chrome_a", accent),
        header_b=hues.get("chrome_b", accent_light),
        panel_bg=_rgba(pannelli, 0.90),
        list_text=testo,
        editor_bg=carta, editor_fg=inchiostro,
        notes_fg=testo,
        title_fg=testo,
        status_a=accent_light, status_b=carta,
        status_fg=testo,
        findbar_bg=_rgba(carta, 0.92),
        dialog_fg=inchiostro,
        entry_bg=carta, entry_fg=inchiostro,
        head=testo, code=hues["code"], marker=accent_light,
        wrapmark=hues["wrap_light"],
    )


# ---------------------------------------------------------------------------
# EN: USER THEMES ON DISK.
#     Beside the three built-in families, RuscaWriter reads themes from a
#     folder — one small text file each. A theme is seven colours and a name;
#     everything else (linen, ivory, graphite) is shared, so a person who wants
#     their own colours writes eight lines, not a stylesheet.
# IT: TEMI DELL'UTENTE SU DISCO.
#     Oltre alle tre famiglie incorporate, RuscaWriter legge i temi da una
#     cartella: un piccolo file di testo ciascuno. Un tema e' sette colori e un
#     nome; tutto il resto (lino, avorio, grafite) e' in comune, così chi vuole
#     i propri colori scrive otto righe, non un foglio di stile.
# ---------------------------------------------------------------------------

# I sette colori di un tema, con il nome usato nei file. Sono in italiano e in
# inglese: chi scrive il file usa la lingua che preferisce.
THEME_FILE_KEYS = {
    "accento": "accent",          "accent": "accent",
    "accento-scuro": "dark",      "accent-dark": "dark",
    "accento-chiaro": "light",    "accent-light": "light",
    "accento-acceso": "glow",     "accent-glow": "glow",
    "codice": "code",             "code": "code",
    "velo-chiaro": "wrap_light",  "tint-light": "wrap_light",
    "velo-scuro": "wrap_dark",    "tint-dark": "wrap_dark",
}

# Chiavi facoltative: servono solo a chi sceglie un accento CHIARO, dove il
# bianco sopra le barre non si leggerebbe. Se mancano valgono i valori
# predefiniti (bianco sulle barre, titoli nel colore dell'accento scuro).
THEME_FILE_OPTIONAL_KEYS = {
    "testo-su-accento": "on_accent", "text-on-accent": "on_accent",
    "testo": "text",                 "text": "text",
    "barre-scure": "night_accent",   "dark-bars": "night_accent",
    "fasce": "chrome_a",             "bars": "chrome_a",
    "fasce-fondo": "chrome_b",       "bars-deep": "chrome_b",
    "menu": "menubar_a",             "menubar": "menubar_a",
    "menu-fondo": "menubar_b",       "menubar-deep": "menubar_b",
    "testo-fasce": "on_chrome",      "text-on-bars": "on_chrome",
    # i neutri: carta, pannelli, inchiostro e i loro corrispettivi notturni
    "carta": "paper",               "paper": "paper",
    "pannelli": "panel",            "panels": "panel",
    "inchiostro": "ink",            "ink": "ink",
    "fondo-scuro": "night",         "night": "night",
    "pannelli-scuri": "night_panel", "night-panels": "night_panel",
    "carta-scura": "night_ink",     "night-paper": "night_ink",
    "testo-scuro": "parchment",     "night-text": "parchment",
    "barre-scure-fondo": "night_accent_dark",
    "dark-bars-deep": "night_accent_dark",
}
THEME_FILE_NAME_KEYS = ("nome", "name")

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def parse_theme_file(text, fallback_name="Tema"):
    """Legge un tema da un file di testo. Restituisce (nome, colori, errori).

    Il formato e' volutamente elementare, una riga per colore:

        nome = Standard verde
        accento = #2E7D4F
        accento-scuro = #1B5233
        ...

    Le righe vuote e quelle che iniziano con # sono commenti. Se un colore
    manca o non e' scritto bene, viene segnalato e il tema NON viene caricato:
    meglio dirlo che mostrare un'interfaccia mezza rotta.
    """
    nome = fallback_name
    colori = {}
    errori = []
    for numero, riga in enumerate((text or "").split("\n"), start=1):
        pulita = riga.strip()
        if not pulita or pulita.startswith("#"):
            continue
        if "=" not in pulita:
            errori.append(f"riga {numero}: manca il segno = ({pulita[:30]})")
            continue
        chiave, valore = pulita.split("=", 1)
        chiave = chiave.strip().lower()
        valore = valore.strip()
        if chiave in THEME_FILE_NAME_KEYS:
            if valore:
                nome = valore
            continue
        ruolo = THEME_FILE_KEYS.get(chiave) or THEME_FILE_OPTIONAL_KEYS.get(chiave)
        if ruolo is None:
            errori.append(f"riga {numero}: colore sconosciuto '{chiave}'")
            continue
        if not _HEX_RE.match(valore):
            errori.append(
                f"riga {numero}: '{valore}' non e' un colore (serve #RRGGBB)")
            continue
        colori[ruolo] = valore.upper()

    mancanti = [k for k in ("accent", "dark", "light", "glow", "code",
                            "wrap_light", "wrap_dark") if k not in colori]
    if mancanti:
        errori.append("colori mancanti: " + ", ".join(sorted(mancanti)))
    return nome, colori, errori


def load_user_themes(folder):
    """Carica tutti i file *.theme di una cartella.

    Restituisce (temi, errori): 'temi' e' un dizionario
    codice -> {"nome": ..., "hues": {...}}, dove il codice e' il nome del file
    preceduto da "utente:" per non collidere mai con i temi incorporati.
    'errori' elenca i file scartati, con il motivo, perche' chi ha sbagliato
    una riga possa correggerla invece di chiedersi perche' non succede nulla.
    """
    temi, errori = {}, []
    try:
        nomi = sorted(n for n in os.listdir(folder) if n.endswith(".theme"))
    except Exception:
        return temi, errori
    for nome_file in nomi:
        percorso = os.path.join(folder, nome_file)
        try:
            with open(percorso, "r", encoding="utf-8", errors="replace") as f:
                testo = f.read()
        except Exception as exc:
            errori.append(f"{nome_file}: non si riesce a leggerlo ({exc})")
            continue
        base = os.path.splitext(nome_file)[0]
        nome, colori, problemi = parse_theme_file(testo, fallback_name=base)
        if problemi:
            errori.append(f"{nome_file}: " + "; ".join(problemi))
            continue
        temi[USER_THEME_PREFIX + base] = {"nome": nome, "hues": colori}
    return temi, errori



# Temi letti dalla cartella dell'utente. Riempito all'avvio da
# register_user_themes(); vuoto significa "solo i temi incorporati".
USER_THEMES = {}


def register_user_themes(temi):
    """Rende disponibili i temi letti da disco. Li aggiunge in coda a THEMES,
    così compaiono nel menu dopo quelli incorporati."""
    global USER_THEMES, THEMES
    USER_THEMES = dict(temi or {})
    THEMES = BUILTIN_THEMES + tuple(sorted(USER_THEMES))
    for codice, dati in USER_THEMES.items():
        THEME_LABEL_FALLBACK[codice] = dati.get("nome", codice)
    return THEMES


def theme_hues(theme):
    """Colori d'accento di una famiglia standard o di un tema dell'utente,
    None per il prugna di RuscaLinux (che ha una tavolozza tutta sua)."""
    if theme in STANDARD_HUES:
        return STANDARD_HUES[theme]
    dati = USER_THEMES.get(theme)
    return dati["hues"] if dati else None


def theme_label(theme, translate=None):
    """Nome da mostrare nel menu. I temi dell'utente portano il nome scritto
    nel loro file; quelli incorporati passano dalle traduzioni."""
    if theme in USER_THEMES:
        return USER_THEMES[theme].get("nome", theme)
    chiave = THEME_LABEL_KEYS.get(theme)
    ripiego = THEME_LABEL_FALLBACK.get(theme, theme)
    if translate and chiave:
        return translate(chiave, ripiego)
    return ripiego


def theme_palette(theme=DEFAULT_THEME, dark=False):
    """Restituisce la tavolozza completa di una combinazione tema + luminosità.

    E' l'UNICO posto in cui si decide quale colore svolge quale ruolo. Il
    foglio di stile (build_css) e i colori del testo Markdown nell'editor
    leggono entrambi da qui, così le quattro combinazioni — prugna chiaro,
    prugna scuro, standard chiaro, standard scuro — restano coerenti.

    Le chiavi sono ruoli, non colori: 'accent' è l'accento del tema, non
    "prugna"; 'editor_bg' è lo sfondo dell'area di scrittura, non "bianco".
    Per aggiungere una terza famiglia basta aggiungere un ramo qui e il nome
    in THEMES.
    """
    if theme not in THEMES:
        theme = DEFAULT_THEME

    # Ogni tema — compreso l'Ametista di RuscaLinux — e' una tavolozza
    # costruita dai suoi colori. Non ci sono piu' rami speciali: aggiungerne
    # uno vuol dire scrivere i colori e nient'altro.
    p = _standard_palette(theme_hues(theme), dark)

    # comuni a tutte le combinazioni: la selezione usa sempre l'accento
    p["sel_bg"] = p["accent"]
    p["sel_fg"] = p["on_accent"]
    return p


def build_css(dark=False, theme=DEFAULT_THEME):
    """Genera il foglio di stile dell'interfaccia.

    Il tema è costruito da una piccola tavolozza (theme_palette): cambiando
    famiglia si ottiene il prugna di RuscaLinux o lo Standard ispirato a
    Scrivener, e per ciascuna la versione chiara o quella scura. Questo è il
    modo tipico in GTK di gestire più temi: un unico CSS parametrizzato invece
    di quattro fogli separati.
    """
    p = theme_palette(theme, dark)

    accent      = p["accent"]
    accent_dark = p["accent_dark"]
    on_accent   = p["on_accent"]
    bg_top, bg_bottom   = p["bg_top"], p["bg_bottom"]
    header_a, header_b  = p["header_a"], p["header_b"]
    panel_bg            = p["panel_bg"]
    list_text           = p["list_text"]
    editor_bg, editor_fg = p["editor_bg"], p["editor_fg"]
    notes_fg            = p["notes_fg"]
    title_fg            = p["title_fg"]
    status_a, status_b  = p["status_a"], p["status_b"]
    status_fg           = p["status_fg"]
    findbar_bg          = p["findbar_bg"]
    sel_bg, sel_fg      = p["sel_bg"], p["sel_fg"]
    dialog_fg           = p["dialog_fg"]
    entry_bg, entry_fg  = p["entry_bg"], p["entry_fg"]
    menubar_a, menubar_b = p["menubar_a"], p["menubar_b"]
    on_chrome           = p["on_chrome"]

    return f"""
/* Interfaccia generale: sfondo a sfumatura */
window, .rusca-bg {{
    background-image: linear-gradient(to bottom, {bg_top}, {bg_bottom});
}}

/* Testo dei dialoghi personalizzati (Informazioni, Obiettivo, Nuovo, Rinomina,
   avvio). USIAMO UNA CLASSE DEDICATA (.rusca-dialog-text) invece di colpire
   tutte le "label": in GTK 4 anche le voci di menu e il testo dei pulsanti
   sono label, quindi una regola generica le renderebbe illeggibili. */
.rusca-dialog-text {{
    color: {dialog_fg};
}}
/* Campi di testo SOLO dentro i dialoghi (.rusca-dialog), per non toccare gli
   entry/menu della finestra principale. Cosi' il numero/voce digitata resta
   leggibile anche nel tema scuro. */
.rusca-dialog entry, .rusca-dialog spinbutton,
.rusca-dialog spinbutton text, .rusca-dialog entry text {{
    background-color: {entry_bg};
    color: {entry_fg};
    caret-color: {entry_fg};
}}

.rusca-header {{
    background-image: linear-gradient(to right, {header_a}, {header_b});
    padding: 6px;
}}

.rusca-toolbar button {{
    background-image: linear-gradient(to bottom, {accent}, {accent_dark});
    color: {on_accent};
    border-radius: 6px;
    padding: 6px 14px;
    margin: 2px;
    font-weight: bold;
    border: none;
}}
.rusca-toolbar button:hover {{
    background-image: linear-gradient(to bottom, {accent_dark}, {accent});
}}

/* Barra menu in stile Scrivener */
.rusca-menubar {{
    background-image: linear-gradient(to bottom, {menubar_a}, {menubar_b});
    color: {on_chrome};
    padding: 1px 4px;
}}
.rusca-menubar > menuitem {{
    color: {on_chrome};
    padding: 4px 10px;
    border-radius: 4px;
}}
.rusca-menubar > menuitem:hover {{
    background-color: {menubar_b};
}}
.rusca-menubar menuitem:disabled {{
    color: alpha({on_chrome}, 0.5);
}}

/* Colonna sinistra: titoli dei capitoli */
.chapter-list {{
    background-color: {panel_bg};
}}
.chapter-list text, .chapter-list {{
    color: {list_text};
    font-family: Sans;
    font-weight: bold;
}}
.chapter-list:selected, .chapter-list row:selected, .chapter-list text:selected {{
    background-color: {sel_bg};
    color: {sel_fg};
}}

/* Colonna centrale: area di scrittura */
.text-editor, .text-editor text {{
    background-color: {editor_bg};
    color: {editor_fg};
    caret-color: {editor_fg};
}}
.text-editor text {{
    font-family: Serif;
    font-size: 13pt;
}}
textview.text-editor, textview.text-editor text {{
    color: {editor_fg};
    caret-color: {editor_fg};
}}
.text-editor text selection {{
    background-color: {sel_bg};
    color: {sel_fg};
}}

/* Colonna destra: note */
.notes-editor, .notes-editor text {{
    background-color: {panel_bg};
    color: {notes_fg};
    caret-color: {notes_fg};
}}
.notes-editor text {{
    font-family: Sans;
    font-size: 11pt;
}}
textview.notes-editor, textview.notes-editor text {{
    color: {notes_fg};
    caret-color: {notes_fg};
}}

.column-title {{
    color: {title_fg};
    font-family: Sans;
    font-weight: bold;
    padding: 4px 8px;
}}

.rusca-statusbar {{
    background-image: linear-gradient(to right, {status_a}, {status_b});
    border-top: 1px solid {accent};
}}
.statusbar-label {{
    color: {status_fg};
    font-family: Sans;
    font-size: 9pt;
    padding: 3px 6px;
}}
.rusca-findbar {{
    background-color: {findbar_bg};
    border-bottom: 1px solid {accent};
}}
.rusca-fontlabel {{
    color: {on_chrome};
    font-family: Serif;
    font-weight: bold;
    padding: 0 2px;
}}
/* Pulsante hamburger (☰) nella barra superiore: stesso stile dell'accento dei
   pulsanti della toolbar, leggibile su sfondo scuro e chiaro. */
.rusca-menubtn {{
    color: {on_accent};
    background-image: linear-gradient(to bottom, {accent}, {accent_dark});
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
    margin: 2px;
}}
.rusca-menubtn:hover {{
    background-image: linear-gradient(to bottom, {accent_dark}, {accent});
}}
"""


# CSS predefinito (tema RuscaLinux chiaro), per compatibilità con codice esistente
CSS = build_css(dark=False, theme=DEFAULT_THEME)


class Chapter:
    """Un capitolo: testo + nota. Indice 1-based -> 01.txt / 01n.txt.
    La copertina (is_cover) usa indice 0 -> 00.txt e non e' spostabile/cancellabile."""
    def __init__(self, index, text="", note="", is_cover=False, custom_title=""):
        self.index = index
        self.text = text
        self.note = note
        self.is_cover = is_cover
        self.custom_title = custom_title or ""   # titolo scelto dall'utente

    @property
    def base(self):
        return f"{self.index:02d}"

    @property
    def text_name(self):
        return f"{self.base}.md"

    @property
    def note_name(self):
        return f"{self.base}n.md"

    def title_with_fallback(self, fallback_template="Capitolo {n}", cover_label="Copertina"):
        """Titolo del capitolo. Priorita': titolo personalizzato dell'utente,
        poi intestazione markdown (# Titolo), poi prima riga tutta in MAIUSCOLO;
        altrimenti il fallback. La copertina mostra sempre l'etichetta dedicata."""
        if self.is_cover:
            return cover_label
        if self.custom_title.strip():
            return self.custom_title.strip()
        for line in self.text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # intestazione markdown: # Titolo, ## Titolo, ...
            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
                if heading:
                    return heading
            # prima riga interamente maiuscola
            if stripped == stripped.upper() and any(c.isalpha() for c in stripped):
                return stripped
            # se la prima riga non vuota non e' un titolo, fermati comunque
            break
        return fallback_template.format(n=self.index)

    @property
    def title(self):
        return self.title_with_fallback()


class Project:
    def __init__(self):
        self.path = None          # percorso del file .rwr
        self.chapters = []        # lista di Chapter
        self.title = "Senza titolo"
        self.meta = {}            # preferenze salvate nel documento (es. font)
        self._lang = "it"         # lingua per le etichette degli export
        # --- sezioni editoriali opzionali -----------------------------------
        self.cover_image = None
        self.cover_image_fmt = None      # "png" | "jpeg" | "webp"
        # EN: images attached inside chapters: name -> raw bytes. Names are
        #     img_001.png, img_002.webp, ... and are referenced from the text
        #     with standard Markdown: ![caption](img_001.png)
        # IT: immagini allegate nei capitoli: nome -> byte grezzi. I nomi sono
        #     img_001.png, img_002.webp, ... e sono richiamati dal testo con
        #     Markdown standard: ![didascalia](img_001.png)
        self.images = {}
        # frontespizio e colophon come CAMPI strutturati (formattazione
        # professionale decisa dal programma). Vedi FRONT_FIELDS / COLO_FIELDS.
        self.frontispiece_fields = {k: "" for k in FRONT_FIELDS}
        self.colophon_fields = {k: "" for k in COLO_FIELDS}

    def set_cover_image(self, data, fmt):
        """EN: Set the cover image. fmt: 'png', 'jpeg' or 'webp'.
        IT: Imposta l'immagine di copertina. fmt: 'png', 'jpeg' o 'webp'."""
        self.cover_image = data
        self.cover_image_fmt = fmt

    def clear_cover_image(self):
        self.cover_image = None
        self.cover_image_fmt = None

    def has_cover_image(self):
        return bool(self.cover_image)

    # ---- immagini nei capitoli / chapter images ----------------------------
    def add_image(self, data):
        """EN: Store an attached image (PNG/JPEG/WebP, detected from the
        content) and return its internal name (e.g. 'img_001.png'), ready to
        be referenced from the text as ![caption](img_001.png).
        Raises ValueError for unsupported formats.
        IT: Registra un'immagine allegata (PNG/JPEG/WebP, riconosciuta dal
        contenuto) e restituisce il suo nome interno (es. 'img_001.png'),
        pronto per essere richiamato dal testo come ![didascalia](img_001.png).
        Solleva ValueError per i formati non supportati."""
        fmt = image_format(data)
        if fmt is None:
            raise ValueError("Formato immagine non supportato "
                             "(usa PNG, JPEG o WebP). / Unsupported image "
                             "format (use PNG, JPEG or WebP).")
        ext = IMAGE_FORMATS[fmt][0]
        # EN: first free progressive number, so deleting one image never
        #     breaks the names of the others.
        # IT: primo numero progressivo libero, cosi' eliminare un'immagine
        #     non rompe mai i nomi delle altre.
        n = 1
        while any(name.startswith(f"img_{n:03d}.") for name in self.images):
            n += 1
        name = f"img_{n:03d}.{ext}"
        self.images[name] = data
        return name

    def image_mime(self, name):
        """EN: MIME type of an attached image (from its content).
        IT: Tipo MIME di un'immagine allegata (dal suo contenuto)."""
        fmt = image_format(self.images.get(name, b""))
        return IMAGE_FORMATS[fmt][1] if fmt else "application/octet-stream"

    def _image_data_uri(self, name):
        """EN: base64 data URI of an attached image (single-file HTML export).
        IT: data URI base64 di un'immagine allegata (export HTML a file unico)."""
        data = self.images.get(name)
        if not data:
            return None
        import base64
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{self.image_mime(name)};base64,{b64}"

    def used_images(self):
        """EN: Names of the attached images actually referenced by at least
        one chapter, in first-appearance order (exports only ship these).
        IT: Nomi delle immagini allegate effettivamente richiamate da almeno
        un capitolo, in ordine di prima apparizione (gli export includono
        solo queste)."""
        seen = []
        for ch in self.chapters:
            for line in ch.text.split("\n"):
                m = _IMG_LINE_RE.match(line.strip())
                if m and m.group("src") in self.images \
                        and m.group("src") not in seen:
                    seen.append(m.group("src"))
        return seen

    # ---- creazione / caricamento -------------------------------------------
    def _make_cover_text(self, title):
        """Testo predefinito della copertina interna: solo NOME OPERA e DATA.
        L'autore NON viene inserito qui: l'autore dell'opera e' quello indicato
        nei campi del frontespizio (File -> Sezioni editoriali), non lo
        sviluppatore dell'applicazione."""
        import datetime
        oggi = datetime.date.today().strftime("%d/%m/%Y")
        return f"{title.upper()}\n\n{oggi}"

    def new(self, title="Nuovo progetto"):
        self.title = title
        self.path = None
        self.cover_image = None
        self.cover_image_fmt = None
        self.images = {}
        self.frontispiece_fields = {k: "" for k in FRONT_FIELDS}
        self.colophon_fields = {k: "" for k in COLO_FIELDS}
        cover = Chapter(0, self._make_cover_text(title), "", is_cover=True)
        # Nessun capitolo creato in automatico: il progetto parte vuoto e
        # l'utente aggiunge i capitoli che vuole (Capitolo -> Aggiungi capitolo).
        self.chapters = [cover]

    def import_text_file(self, path):
        """Crea un nuovo progetto importando un file di testo (.txt) o
        Markdown (.md). Il titolo dell'opera viene dal nome del file. Per il
        Markdown, il documento viene suddiviso in capitoli usando le
        intestazioni di primo o secondo livello (# / ##) come punti di taglio;
        per il TXT, se ci sono righe di separazione tipo capitolo le usa,
        altrimenti tiene tutto in un unico capitolo."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        # Via l'intestazione e la licenza di Project Gutenberg, se ci sono:
        # sono righe generate a macchina, riconosciute alla lettera.
        # I paragrafi spezzati a colonna fissa, invece, NON si toccano qui:
        # e' una scelta di chi scrive, e la fa dal menu quando vuole
        # (vedi wrapped_runs e rejoin_paragraphs).
        raw = strip_gutenberg_boilerplate(raw)

        title = os.path.splitext(os.path.basename(path))[0]
        is_md = path.lower().endswith((".md", ".markdown"))

        self.title = title
        self.path = None        # importato: nessun .rwr associato finché non si salva
        self.meta = {}
        self.cover_image = None
        self.cover_image_fmt = None
        self.images = {}
        self.frontispiece_fields = {k: "" for k in FRONT_FIELDS}
        self.colophon_fields = {k: "" for k in COLO_FIELDS}
        cover = Chapter(0, self._make_cover_text(title), "", is_cover=True)
        self.chapters = [cover]

        # suddivisione in capitoli
        chunks = []   # lista di (titolo_opzionale, testo)
        if is_md:
            # taglia ad ogni intestazione di livello 1 o 2 mantenendola nel testo
            lines = raw.split("\n")
            current = []
            current_title = ""
            def flush():
                if current and any(l.strip() for l in current):
                    chunks.append((current_title, "\n".join(current).strip("\n")))
            for line in lines:
                m = re.match(r"^(#{1,2})\s+(.*)$", line.strip())
                if m:
                    # nuova sezione: salva la precedente e inizia
                    flush()
                    current = [line]
                    current_title = m.group(2).strip()
                else:
                    current.append(line)
            flush()
        if not chunks:
            # TXT, o MD senza intestazioni: prova a spezzare su separatori tipici
            # (righe con soli '***', '---' o '* * *'); altrimenti capitolo unico
            parts = re.split(r"\n\s*(?:\*\s*\*\s*\*|-{3,}|\*{3,})\s*\n", raw)
            parts = [p.strip("\n") for p in parts if p.strip()]
            if len(parts) > 1:
                chunks = [("", p) for p in parts]
            else:
                chunks = [("", raw.strip("\n"))]

        idx = 1
        for _ttl, body in chunks:
            self.chapters.append(Chapter(idx, body, ""))
            idx += 1
        self._renumber()

    def load(self, path):
        self.path = path
        self.title = os.path.splitext(os.path.basename(path))[0]
        self.chapters = []
        self.meta = {}
        contents = {}        # nome file -> bytes
        with tarfile.open(path, "r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                name = os.path.basename(member.name)
                f = tar.extractfile(member)
                if f is not None:
                    contents[name] = f.read()
        names = set(contents)
        if "meta.json" in names:
            try:
                self.meta = json.loads(contents["meta.json"].decode("utf-8"))
            except Exception:
                self.meta = {}
        # riconosce i file dei capitoli sia .md sia (per progetti vecchi) .txt
        def chapter_index(fname):
            for ext in (".md", ".txt"):
                if fname.endswith(ext) and not fname.endswith("n" + ext):
                    stem = fname[:-len(ext)]
                    if stem.isdigit():
                        return int(stem)
            return None

        idx_to_files = {}    # idx -> (text_name, note_name)
        for n in names:
            idx = chapter_index(n)
            if idx is not None:
                ext = ".md" if n.endswith(".md") else ".txt"
                idx_to_files[idx] = (f"{idx:02d}{ext}", f"{idx:02d}n{ext}")

        for idx in sorted(idx_to_files):
            text_name, note_name = idx_to_files[idx]
            ch = Chapter(idx, is_cover=(idx == 0))
            ch.text = contents[text_name].decode("utf-8")
            if note_name in names:
                ch.note = contents[note_name].decode("utf-8")
            self.chapters.append(ch)
        # titoli personalizzati salvati nei metadati (mappa indice->titolo)
        titles = self.meta.get("titles") or {}
        if isinstance(titles, dict):
            for ch in self.chapters:
                ct = titles.get(str(ch.index))
                if ct:
                    ch.custom_title = ct
        # garantisci la presenza della copertina come primo elemento
        if not self.chapters or not self.chapters[0].is_cover:
            cover = Chapter(0, self._make_cover_text(self.title), "", is_cover=True)
            self.chapters.insert(0, cover)
        # NB: nessun capitolo creato in automatico se il progetto e' vuoto:
        # un progetto senza capitoli e' uno stato legittimo.
        self._renumber()

        # --- sezioni editoriali opzionali ----------------------------------
        self.frontispiece_fields = {k: "" for k in FRONT_FIELDS}
        self.colophon_fields = {k: "" for k in COLO_FIELDS}
        self.cover_image = None
        self.cover_image_fmt = None
        # EN: attached chapter images travel inside the archive as img_*.<ext>
        # IT: le immagini allegate viaggiano nell'archivio come img_*.<ext>
        self.images = {n: b for n, b in contents.items()
                       if re.match(r"^img_\d+\.(png|jpe?g|webp)$", n)}
        # nuovo formato: campi strutturati in JSON
        if "frontispiece.json" in names:
            try:
                d = json.loads(contents["frontispiece.json"].decode("utf-8"))
                for k in FRONT_FIELDS:
                    self.frontispiece_fields[k] = str(d.get(k, "") or "")
            except Exception:
                pass
        elif "frontispiece.md" in names:
            # vecchio formato a testo libero: lo conserviamo nel sottotitolo,
            # cosi' non si perde nulla nella transizione
            try:
                old = contents["frontispiece.md"].decode("utf-8").strip()
                if old:
                    self.frontispiece_fields["subtitle"] = old
            except Exception:
                pass
        if "colophon.json" in names:
            try:
                d = json.loads(contents["colophon.json"].decode("utf-8"))
                for k in COLO_FIELDS:
                    self.colophon_fields[k] = str(d.get(k, "") or "")
            except Exception:
                pass
        elif "colophon.md" in names:
            try:
                old = contents["colophon.md"].decode("utf-8").strip()
                if old:
                    self.colophon_fields["notes"] = old
            except Exception:
                pass
        # EN: cover image, in any of the accepted formats.
        # IT: immagine di copertina, in uno qualsiasi dei formati accettati.
        for cname, cfmt in (("cover.jpg", "jpeg"), ("cover.jpeg", "jpeg"),
                            ("cover.png", "png"), ("cover.webp", "webp")):
            if cname in names:
                self.cover_image = contents[cname]
                self.cover_image_fmt = cfmt
                break

    def _renumber(self):
        """Copertina = 0, capitoli di contenuto = 1,2,3..."""
        n = 1
        for ch in self.chapters:
            if ch.is_cover:
                ch.index = 0
            else:
                ch.index = n
                n += 1

    def save(self, path=None, update_path=True):
        """Scrive il progetto. Se update_path è False, salva nel percorso dato
        (es. autosave) senza modificare self.path/self.title del progetto."""
        if path and update_path:
            self.path = path
            self.title = os.path.splitext(os.path.basename(path))[0]
        dest = path if (path and not update_path) else self.path
        if not dest:
            raise ValueError("Nessun percorso di salvataggio impostato.")
        self._renumber()
        # registra i titoli personalizzati nei metadati prima di scrivere
        titles = {str(ch.index): ch.custom_title
                  for ch in self.chapters if ch.custom_title.strip()}
        if titles:
            self.meta["titles"] = titles
        elif "titles" in self.meta:
            del self.meta["titles"]
        fd, tmp = tempfile.mkstemp(suffix=".rwr")
        os.close(fd)
        try:
            with tarfile.open(tmp, "w:gz") as tar:
                def add(name, data_bytes):
                    info = tarfile.TarInfo(name=name)
                    info.size = len(data_bytes)
                    tar.addfile(info, io.BytesIO(data_bytes))
                if self.meta:
                    add("meta.json",
                        json.dumps(self.meta, ensure_ascii=False, indent=2)
                        .encode("utf-8"))
                for ch in self.chapters:
                    add(ch.text_name, ch.text.encode("utf-8"))
                    add(ch.note_name, ch.note.encode("utf-8"))
                if any(v.strip() for v in self.frontispiece_fields.values()):
                    add("frontispiece.json",
                        json.dumps(self.frontispiece_fields,
                                   ensure_ascii=False, indent=2).encode("utf-8"))
                if any(v.strip() for v in self.colophon_fields.values()):
                    add("colophon.json",
                        json.dumps(self.colophon_fields,
                                   ensure_ascii=False, indent=2).encode("utf-8"))
                # EN: attached chapter images, each as its own archive entry.
                # IT: immagini allegate ai capitoli, una voce d'archivio ciascuna.
                for iname, idata in self.images.items():
                    add(iname, idata)
                if self.cover_image and self.cover_image_fmt:
                    ext = IMAGE_FORMATS.get(self.cover_image_fmt,
                                            ("png",))[0]
                    add(f"cover.{ext}", self.cover_image)
            shutil.move(tmp, dest)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def export_txt(self, path):
        """Concatena i capitoli in un unico file ordinato. La testata iniziale
        (titolo, autore, editore) viene dai CAMPI del frontespizio, non dal
        capitolo-copertina interno; seguono frontespizio, capitoli e colophon.
        L'immagine di copertina non ha senso nel testo semplice ed e' omessa."""
        with open(path, "w", encoding="utf-8") as out:
            wrote = False

            def sep():
                nonlocal wrote
                if wrote:
                    out.write("\n\n")
                wrote = True

            cov = self._cover_lines()
            if cov:
                sep()
                out.write("\n".join(cov))
                out.write("\n")
            front = self._front_paragraphs()
            if front:
                sep()
                out.write("\n".join(front))
                out.write("\n")
            for ch in self.chapters:
                if ch.is_cover:
                    continue
                sep()
                # EN: plain text cannot embed pictures: each attached image
                #     becomes a bracketed line with its caption (or name).
                # IT: il testo semplice non incorpora figure: ogni immagine
                #     allegata diventa una riga tra parentesi con la sua
                #     didascalia (o il nome).
                body = "\n".join(
                    f"[{(m.group('alt') or m.group('src')).strip()}]"
                    if (m := _IMG_LINE_RE.match(ln.strip())) else ln
                    for ln in ch.text.split("\n"))
                out.write(body.rstrip("\n"))
                out.write("\n")
            colo = self._colophon_paragraphs()
            if colo:
                sep()
                out.write("\n".join(colo))
                out.write("\n")

    # --- helper comuni agli export documentali ----------------------------
    def cover_lines_with_roles(self):
        """Righe della copertina grafica con il loro RUOLO tipografico.

        Restituisce una lista di (testo, ruolo) con ruolo fra "title",
        "subtitle", "author" e "publisher".

        Il ruolo si dichiara, non si indovina. Prima gli export lo deducevano
        dalla posizione — prima riga il titolo, ultima l'editore, il resto
        l'autore — e con DUE sole righe gli intervalli si sovrapponevano: lo
        stesso nome finiva stampato due volte, una come autore e una in coda.
        I campi del frontespizio sanno gia' cos'e' cosa: basta chiederglielo.
        """
        f = getattr(self, "frontispiece_fields", {}) or {}
        voci = []
        for campo, ruolo in (("title", "title"), ("subtitle", "subtitle"),
                             ("author", "author"), ("publisher", "publisher")):
            valore = (f.get(campo) or "").strip()
            if valore:
                voci.append((valore, ruolo))
        if voci:
            return voci

        # Ripiego per i progetti vecchi, dove la copertina era testo libero in
        # un capitolo: li' il ruolo si puo' solo dedurre dalla posizione, ma
        # senza mai usare due volte la stessa riga.
        righe = []
        cover = self.cover()
        if cover is not None:
            for ln in cover.text.splitlines():
                s = _strip_inline_md(ln.lstrip("#").strip()
                                     if ln.strip().startswith("#") else ln).strip()
                if s:
                    righe.append(s)
        if not righe and self.title:
            righe.append(self.title)
        if not righe:
            return []
        voci = [(righe[0], "title")]
        if len(righe) > 2:
            voci += [(r, "author") for r in righe[1:-1]]
            voci.append((righe[-1], "publisher"))
        elif len(righe) == 2:
            voci.append((righe[1], "author"))
        return voci

    def _cover_lines(self):
        """Solo i testi della copertina, nell'ordine. Per chi non ha bisogno
        dei ruoli; chi li vuole usa cover_lines_with_roles()."""
        return [testo for testo, _ruolo in self.cover_lines_with_roles()]

    def _ordered_chapters(self):
        """Capitoli di contenuto (esclusa la copertina) con titolo risolto."""
        out = []
        n = 0
        for ch in self.chapters:
            if ch.is_cover:
                continue
            n += 1
            title = ch.title_with_fallback(
                fallback_template="Capitolo {n}".replace("{n}", str(n)))
            out.append((title, ch.text))
        return out

    # --- sezioni editoriali: helper condivisi dagli export ----------------
    def has_frontispiece(self):
        return any(v.strip() for v in self.frontispiece_fields.values())

    def cover_is_blank(self):
        """True se la copertina esportata deve risultare BIANCA e VUOTA:
        nessuna immagine di copertina E tutti i campi delle Sezioni editoriali
        del frontespizio (titolo, sottotitolo, autore, editore) vuoti.
        In questo caso l'export non disegna la grafica della copertina ne'
        ripiega sul titolo del progetto: la pagina resta completamente bianca."""
        if self.has_cover_image():
            return False
        f = getattr(self, "frontispiece_fields", {}) or {}
        return not any(str(v).strip() for v in f.values())

    def has_colophon(self):
        return any(v.strip() for v in self.colophon_fields.values())

    def _front_lines(self):
        """Frontespizio come lista di righe con stile: (testo, ruolo).
        Ruoli: 'title', 'subtitle', 'author', 'meta'. La formattazione vera
        (font, dimensioni, spaziatura) la decide ogni export in base al ruolo.
        Lista vuota se non c'e' nessun campo."""
        f = self.frontispiece_fields
        lines = []
        if f.get("title", "").strip():
            lines.append((f["title"].strip(), "title"))
        if f.get("subtitle", "").strip():
            # il sottotitolo puo' contenere piu' righe (es. vecchio testo libero)
            for i, ln in enumerate(f["subtitle"].strip().split("\n")):
                if ln.strip():
                    lines.append((ln.strip(), "subtitle"))
        if f.get("author", "").strip():
            lines.append((f["author"].strip(), "author"))
        if f.get("publisher", "").strip():
            lines.append((f["publisher"].strip(), "meta"))
        if f.get("place_year", "").strip():
            lines.append((f["place_year"].strip(), "meta"))
        return lines

    def _colophon_lines(self):
        """Colophon come lista di righe con stile: (testo, ruolo).
        Ruoli: 'copyright', 'small'. Lista vuota se non c'e' nessun campo."""
        c = self.colophon_fields
        lines = []
        if c.get("copyright", "").strip():
            lines.append((c["copyright"].strip(), "copyright"))
        if c.get("publisher", "").strip():
            lines.append((c["publisher"].strip(), "small"))
        if c.get("isbn", "").strip():
            lines.append(("ISBN " + c["isbn"].strip(), "small"))
        if c.get("edition", "").strip():
            lines.append((c["edition"].strip(), "small"))
        if c.get("notes", "").strip():
            for ln in c["notes"].strip().split("\n"):
                if ln.strip():
                    lines.append((ln.strip(), "small"))
        if c.get("license", "").strip():
            lines.append((c["license"].strip(), "small"))
        return lines

    # compatibilita': vecchi nomi usati altrove, ora derivati dai campi
    def _front_paragraphs(self):
        return [t for (t, _r) in self._front_lines()]

    def _colophon_paragraphs(self):
        return [t for (t, _r) in self._colophon_lines()]

    def _cover_image_mime(self):
        """EN: MIME type of the cover image ('image/png' fallback).
        IT: Tipo MIME dell'immagine di copertina (ripiego 'image/png')."""
        return IMAGE_FORMATS.get(self.cover_image_fmt,
                                 (None, "image/png"))[1]

    def _cover_image_data_uri(self):
        """Data URI base64 dell'immagine di copertina, per incorporarla inline
        nell'HTML a file unico. None se non c'e' immagine."""
        if not self.cover_image:
            return None
        import base64
        b64 = base64.b64encode(self.cover_image).decode("ascii")
        return f"data:{self._cover_image_mime()};base64,{b64}"

    def export_markdown(self, path):
        """EN: Export the whole project to a single Markdown file. Title as
        H1, cover as the opening block, each chapter with its own H2 heading
        (unless the text already starts with one). Attached images are copied
        to a sibling '<name>_img/' folder and the ![..](..) references are
        rewritten to point there, so the exported file works anywhere.
        IT: Esporta tutto il progetto in un unico file Markdown. Titolo come
        H1, copertina come blocco iniziale, ogni capitolo con la propria
        intestazione H2 (se il testo non ne ha già una). Le immagini allegate
        vengono copiate in una cartella affiancata '<nome>_img/' e i
        riferimenti ![..](..) riscritti verso di essa, così il file esportato
        funziona ovunque."""
        cover_lines = self._cover_lines()
        title = cover_lines[0] if cover_lines else self.title

        # EN/IT: images folder next to the .md / cartella immagini accanto al .md
        used = self.used_images()
        img_dir_name = os.path.splitext(os.path.basename(path))[0] + "_img"
        if used:
            img_dir = os.path.join(os.path.dirname(path) or ".", img_dir_name)
            os.makedirs(img_dir, exist_ok=True)
            for n in used:
                with open(os.path.join(img_dir, n), "wb") as imgf:
                    imgf.write(self.images[n])

        def rewrite_refs(text):
            # EN: only the internal names get the folder prefix; any other
            #     Markdown image the author wrote is left untouched.
            # IT: solo i nomi interni ricevono il prefisso cartella; ogni
            #     altra immagine Markdown scritta dall'autore resta intatta.
            return "\n".join(
                f"![{m.group('alt')}]({img_dir_name}/{m.group('src')})"
                if (m := _IMG_LINE_RE.match(ln.strip()))
                and m.group("src") in self.images else ln
                for ln in text.split("\n"))

        with open(path, "w", encoding="utf-8") as out:
            out.write(f"# {title}\n\n")
            # autore e data della copertina, in corsivo
            for extra in cover_lines[1:]:
                out.write(f"*{extra}*\n\n")
            out.write("---\n\n")
            # frontespizio (dopo la copertina), se presente
            front = self._front_paragraphs()
            if front:
                for j, ln in enumerate(front):
                    if j == 0:
                        out.write(f"## {ln}\n\n")
                    else:
                        out.write(f"*{ln}*\n\n")
                out.write("---\n\n")
            for ch_title, text in self._ordered_chapters():
                body = rewrite_refs(text.rstrip("\n"))
                # EN: if the text already opens with a Markdown heading we do
                #     not add a duplicate title.
                # IT: se il testo inizia già con un'intestazione markdown, non
                #     aggiungiamo un titolo doppio.
                first = body.lstrip().split("\n", 1)[0] if body else ""
                if not first.startswith("#"):
                    out.write(f"## {ch_title}\n\n")
                out.write(body)
                out.write("\n\n")
            # colophon in fondo, se presente
            colo = self._colophon_paragraphs()
            if colo:
                out.write("---\n\n")
                for ln in colo:
                    out.write(f"*{ln}*\n\n")

    def _doc_blocks(self, text):
        """EN: Turn a chapter's Markdown into a list of (kind, content)
        blocks shared by the ODT and DOCX exports. Kinds: h1/h2/h3, bullet,
        quote, p, and image (content = (caption, internal_name)). Inline
        formatting is stripped (plain text) to stay simple and robust.
        IT: Trasforma il markdown di un capitolo in una lista di blocchi
        (tipo, contenuto) usata sia da ODT sia da DOCX. Tipi: h1/h2/h3,
        bullet, quote, p e image (contenuto = (didascalia, nome_interno)).
        La formattazione inline viene rimossa (testo piano) per restare
        semplice e robusta."""
        blocks = []
        for raw in text.split("\n"):
            kind, body, extra = classify_md_line(raw)
            if kind == "blank":
                continue
            if kind == "image":
                # un riferimento rotto (immagine non piu' nel progetto) non e'
                # una figura: resta un paragrafo con la sola didascalia
                if extra in self.images:
                    blocks.append(("image", (body, extra)))
                else:
                    blocks.append(("p", _strip_inline_md(body)))
            elif kind == "heading":
                blocks.append((f"h{min(3, extra)}", _strip_inline_md(body)))
            elif kind in ("bullet", "number"):
                blocks.append(("bullet", _strip_inline_md(body)))
            elif kind == "quote":
                blocks.append(("quote", _strip_inline_md(body)))
            else:
                blocks.append(("p", _strip_inline_md(body)))
        return blocks

    def _blocks_to_html(self, text, image_html=None):
        """EN: Convert a chapter's Markdown to HTML (list of strings),
        recognizing headings, lists, quotes, attached images and inline
        formatting (bold, italic, code). Used by the HTML and EPUB exports.
        image_html(caption, name) returns the markup for an attached image
        (or None to skip it); the default emits a <figure> whose <img>
        embeds the bytes as a base64 data URI (self-contained single file).
        IT: Converte il markdown di un capitolo in HTML (lista di stringhe),
        riconoscendo titoli, elenchi, citazioni, immagini allegate e
        formattazione inline (grassetto, corsivo, codice). Usato dagli
        export HTML ed EPUB. image_html(didascalia, nome) restituisce il
        markup per un'immagine allegata (o None per ometterla); il default
        emette un <figure> il cui <img> incorpora i byte come data URI
        base64 (file unico autosufficiente)."""
        from xml.sax.saxutils import escape as esc

        def default_image_html(alt, name):
            # EN: one image per <figure>, caption below when present.
            # IT: un'immagine per <figure>, didascalia sotto se presente.
            src = self._image_data_uri(name)
            if not src:
                return None
            cap = f"<figcaption>{esc(alt)}</figcaption>" if alt.strip() else ""
            return (f'<figure class="attached"><img src="{esc(src)}" '
                    f'alt="{esc(alt)}"/>{cap}</figure>')

        figure = image_html or default_image_html

        # marcatura HTML di ogni stile inline riconosciuto dal parser comune
        _WRAP = {
            "bold": ("<strong>", "</strong>"),
            "italic": ("<em>", "</em>"),
            "bolditalic": ("<strong><em>", "</em></strong>"),
            "code": ("<code>", "</code>"),
            "regular": ("", ""),
        }

        def inline(s):
            parts = []
            for seg, style in parse_inline(s):
                open_t, close_t = _WRAP[style]
                parts.append(f"{open_t}{esc(seg)}{close_t}")
            return "".join(parts)

        out = []
        lines = text.split("\n")
        kinds = [classify_md_line(ln) for ln in lines]
        i = 0
        while i < len(lines):
            kind, body, extra = kinds[i]
            if kind == "blank":
                i += 1
                continue
            if kind == "image":
                # EN: attached image; if the reference is broken (image not in
                #     the project) fall back to showing the caption only.
                # IT: immagine allegata; se il riferimento e' rotto (immagine
                #     assente dal progetto) ripiega sulla sola didascalia.
                fig = figure(body, extra) if extra in self.images else None
                out.append(fig if fig else f"<p><em>{esc(body)}</em></p>")
                i += 1
            elif kind == "heading":
                out.append(f"<h{extra}>{inline(body)}</h{extra}>")
                i += 1
            elif kind in ("bullet", "number"):
                # elenco: accorpa le righe contigue dello stesso tipo
                tag = "ul" if kind == "bullet" else "ol"
                items = []
                while i < len(lines) and kinds[i][0] == kind:
                    items.append(f"<li>{inline(kinds[i][1])}</li>")
                    i += 1
                out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            elif kind == "quote":
                out.append(f"<blockquote>{inline(body)}</blockquote>")
                i += 1
            else:
                # EN: plain paragraph: merge contiguous lines, but stop at any
                #     block starter (heading, list, quote, attached image).
                # IT: paragrafo semplice: accorpa righe contigue, ma si ferma
                #     a ogni inizio blocco (titolo, elenco, citazione,
                #     immagine allegata).
                buf = []
                while i < len(lines) and kinds[i][0] == "text":
                    buf.append(inline(kinds[i][1]))
                    i += 1
                out.append("<p>" + "<br/>".join(buf) + "</p>")
        return out

    # foglio di stile condiviso dalle pagine HTML esportate
    _HTML_CSS = (
        "body{font-family:'EB Garamond',Georgia,'Times New Roman',serif;line-height:1.6;"
        "max-width:42em;margin:2em auto;padding:0 1em;color:#222;}"
        "h1,h2,h3{font-family:'Helvetica Neue',Arial,sans-serif;color:#5C2A55;}"
        "h1.title{text-align:center;border-bottom:2px solid #8E4585;"
        "padding-bottom:0.3em;}"
        ".cover{text-align:center;margin:3em 0;}"
        ".cover .author{font-size:1.1em;color:#555;}"
        ".cover .date{font-style:italic;color:#777;}"
        ".cover-image{text-align:center;margin:0 0 2em 0;}"
        ".cover-image img{max-width:100%;height:auto;}"
        # EN/IT: attached chapter images / immagini allegate ai capitoli
        "figure.attached{text-align:center;margin:2em 0;}"
        "figure.attached img{max-width:100%;height:auto;}"
        "figure.attached figcaption{font-style:italic;color:#666;"
        "font-size:0.9em;margin-top:0.5em;}"
        ".frontispiece{text-align:center;margin:3em 0;}"
        ".frontispiece .ftitle{font-size:1.6em;font-weight:bold;color:#5C2A55;}"
        ".colophon{margin-top:3em;border-top:1px solid #d9b8d4;padding-top:1em;"
        "font-size:0.9em;color:#555;text-align:center;}"
        "blockquote{border-left:3px solid #8E4585;margin-left:0;padding-left:1em;"
        "font-style:italic;color:#444;}"
        "nav.toc{background:#f6eef4;border:1px solid #d9b8d4;border-radius:6px;"
        "padding:1em 1.5em;}"
        "nav.toc a{color:#5C2A55;text-decoration:none;}"
        "nav.toc a:hover{text-decoration:underline;}"
        "code{background:#f0e6ee;padding:0 0.2em;border-radius:3px;}"
        ".chapter-nav{margin-top:3em;border-top:1px solid #d9b8d4;"
        "padding-top:1em;font-size:0.9em;}"
    )

    def export_html(self, path, multifile=False):
        """Esporta in HTML.

        - multifile=False: un unico file .html con copertina, indice interno
          (link agli #ancore) e tutti i capitoli in sequenza.
        - multifile=True: crea una cartella accanto a 'path' con un index.html
          (copertina + indice) e un file per ogni capitolo, collegati tra loro.
        """
        from xml.sax.saxutils import escape as esc

        cover_lines = self._cover_lines()
        title = cover_lines[0] if cover_lines else self.title
        chapters = self._ordered_chapters()

        def page(title_txt, body_html):
            return (
                "<!DOCTYPE html>\n<html lang=\"it\">\n<head>\n"
                "<meta charset=\"utf-8\"/>\n"
                "<meta name=\"viewport\" content=\"width=device-width, "
                "initial-scale=1\"/>\n"
                f"<title>{esc(title_txt)}</title>\n"
                f"<style>{self._HTML_CSS}</style>\n</head>\n<body>\n"
                + body_html +
                "\n</body>\n</html>\n")

        def cover_html(image_src=None):
            h = ['<div class="cover">']
            if image_src:
                # con immagine di copertina: mostra l'immagine a piena larghezza
                h.append(f'<div class="cover-image"><img src="{esc(image_src)}" '
                         f'alt="{esc(title)}"/></div>')
            elif self.cover_is_blank():
                # campi Sezioni editoriali vuoti e nessuna immagine:
                # copertina bianca e vuota
                pass
            else:
                # ogni riga sa gia' che ruolo ha: nessuna deduzione
                h.append(f'<h1 class="title">{esc(title)}</h1>')
                for testo, ruolo in self.cover_lines_with_roles():
                    if ruolo in ("subtitle", "author"):
                        h.append(f'<p class="author">{esc(testo)}</p>')
                    elif ruolo == "publisher":
                        h.append(f'<p class="date">{esc(testo)}</p>')
            h.append('</div>')
            return "\n".join(h)

        def frontispiece_html():
            front = self._front_paragraphs()
            if not front:
                return ""
            h = ['<div class="frontispiece">']
            for j, ln in enumerate(front):
                cls = "ftitle" if j == 0 else "fline"
                h.append(f'<p class="{cls}">{esc(ln)}</p>')
            h.append('</div>')
            return "\n".join(h)

        def colophon_html():
            colo = self._colophon_paragraphs()
            if not colo:
                return ""
            h = ['<div class="colophon">']
            for ln in colo:
                h.append(f'<p>{esc(ln)}</p>')
            h.append('</div>')
            return "\n".join(h)

        if not multifile:
            # ---- file unico ----
            data_uri = self._cover_image_data_uri()
            parts = [cover_html(data_uri)]
            fr = frontispiece_html()
            if fr:
                parts.append(fr)
            # indice con ancore interne
            toc = ['<nav class="toc"><h2>' + esc(self.t_index_label())
                   + '</h2><ol>']
            for n, (ct, _t) in enumerate(chapters, 1):
                toc.append(f'<li><a href="#cap{n}">{esc(ct)}</a></li>')
            toc.append('</ol></nav>')
            parts.append("\n".join(toc))
            # capitoli
            for n, (ct, text) in enumerate(chapters, 1):
                parts.append(f'<section id="cap{n}">')
                blocks = self._blocks_to_html(text)
                starts_h = bool(blocks) and blocks[0].startswith("<h")
                if not starts_h:
                    parts.append(f"<h2>{esc(ct)}</h2>")
                parts.extend(blocks)
                parts.append('</section>')
            colo = colophon_html()
            if colo:
                parts.append(colo)
            with open(path, "w", encoding="utf-8") as f:
                f.write(page(title, "\n".join(parts)))
            return path

        # ---- multifile: una cartella con index + un file per capitolo ----
        base = os.path.splitext(path)[0]            # toglie .html se presente
        folder = base                                # la cartella di output
        os.makedirs(folder, exist_ok=True)

        filenames = [f"cap{n:02d}.html" for n in range(1, len(chapters) + 1)]

        # salva l'immagine di copertina come file nella cartella, se presente
        cover_src = None
        if self.cover_image:
            ext = IMAGE_FORMATS.get(self.cover_image_fmt, ("png",))[0]
            cover_name = f"cover.{ext}"
            with open(os.path.join(folder, cover_name), "wb") as imgf:
                imgf.write(self.cover_image)
            cover_src = cover_name

        # index.html: copertina + frontespizio + indice con link ai file
        idx = [cover_html(cover_src)]
        fr = frontispiece_html()
        if fr:
            idx.append(fr)
        idx.append('<nav class="toc"><h2>'
                   + esc(self.t_index_label()) + '</h2><ol>')
        for fn, (ct, _t) in zip(filenames, chapters):
            idx.append(f'<li><a href="{fn}">{esc(ct)}</a></li>')
        idx.append('</ol></nav>')
        colo = colophon_html()
        if colo:
            idx.append(colo)
        with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
            f.write(page(title, "\n".join(idx)))

        # un file per capitolo, con navigazione avanti/indietro
        for i, (fn, (ct, text)) in enumerate(zip(filenames, chapters)):
            body = []
            blocks = self._blocks_to_html(text)
            starts_h = bool(blocks) and blocks[0].startswith("<h")
            if not starts_h:
                body.append(f"<h2>{esc(ct)}</h2>")
            body.extend(blocks)
            # barra di navigazione tra capitoli
            nav = ['<div class="chapter-nav">']
            if i > 0:
                nav.append(f'<a href="{filenames[i-1]}">&larr; precedente</a> · ')
            nav.append('<a href="index.html">indice</a>')
            if i < len(filenames) - 1:
                nav.append(f' · <a href="{filenames[i+1]}">successivo &rarr;</a>')
            nav.append('</div>')
            body.append("\n".join(nav))
            with open(os.path.join(folder, fn), "w", encoding="utf-8") as f:
                f.write(page(ct, "\n".join(body)))
        return folder

    def export_odt(self, path):
        """Esporta in OpenDocument Text (.odt) usando solo la libreria standard.
        Un .odt è un archivio ZIP con dentro dei file XML; lo costruiamo a mano,
        come facciamo per l'EPUB."""
        import zipfile
        from xml.sax.saxutils import escape

        cover_lines = self._cover_lines()
        title = cover_lines[0] if cover_lines else self.title

        # corpo del documento in formato Open Document
        body = []
        # EN: every picture shipped in the archive: (zip path, MIME, bytes).
        #     Holds the cover (if any) plus the attached chapter images.
        # IT: tutte le immagini incluse nell'archivio: (percorso zip, MIME,
        #     byte). Contiene la copertina (se c'e') e le immagini allegate.
        img_entries = []
        # immagine di copertina (se presente) come frame a piena larghezza
        if self.cover_image:
            ext = IMAGE_FORMATS.get(self.cover_image_fmt, ("png",))[0]
            img_path = f"Pictures/cover.{ext}"
            img_entries.append((img_path, self._cover_image_mime(),
                                self.cover_image))
            # dimensioni in cm: stima per stare nella pagina (~16cm larghezza)
            from_w, from_h = 16.0, 22.0
            try:
                from PIL import Image as _PILImage
                import io as _io
                _im = _PILImage.open(_io.BytesIO(self.cover_image))
                iw, ih = _im.size
                from_h = min(24.0, 16.0 * ih / iw)
            except Exception:
                pass
            body.append(
                '<text:p text:style-name="Author">'
                f'<draw:frame draw:name="cover" text:anchor-type="paragraph" '
                f'svg:width="{from_w:.2f}cm" svg:height="{from_h:.2f}cm" '
                f'draw:z-index="0">'
                f'<draw:image xlink:href="{img_path}" '
                f'xlink:type="simple" xlink:show="embed" '
                f'xlink:actuate="onLoad"/></draw:frame></text:p>')
        else:
            # copertina testuale: titolo grande e dati centrati
            body.append(f'<text:h text:style-name="Title" '
                        f'text:outline-level="1">{escape(title)}</text:h>')
            for extra in cover_lines[1:]:
                body.append(f'<text:p text:style-name="Author">{escape(extra)}</text:p>')
        # frontespizio (dopo la copertina)
        for j, ln in enumerate(self._front_paragraphs()):
            style = "Title" if j == 0 else "Author"
            body.append(f'<text:p text:style-name="{style}">{escape(ln)}</text:p>')
        for ch_title, text in self._ordered_chapters():
            body_blocks = self._doc_blocks(text)
            # se il capitolo inizia gia' con un'intestazione, non duplicare
            starts_with_heading = bool(body_blocks) and body_blocks[0][0].startswith("h")
            if not starts_with_heading:
                body.append(f'<text:h text:style-name="Heading_20_1" '
                            f'text:outline-level="1">{escape(ch_title)}</text:h>')
            for kind, content in body_blocks:
                if kind == "image":
                    # EN: attached image as a centered frame + italic caption.
                    #     Width fits the page (max 14 cm), height keeps the
                    #     aspect ratio read from the file itself.
                    # IT: immagine allegata come cornice centrata + didascalia
                    #     in corsivo. Larghezza entro la pagina (max 14 cm),
                    #     altezza con le proporzioni lette dal file stesso.
                    alt, iname = content
                    data = self.images[iname]
                    dims = image_dimensions(data) or (1400, 1000)
                    w_cm = 14.0
                    h_cm = min(20.0, w_cm * dims[1] / dims[0])
                    ipath = f"Pictures/{iname}"
                    img_entries.append((ipath, self.image_mime(iname), data))
                    body.append(
                        '<text:p text:style-name="Author">'
                        f'<draw:frame draw:name="{iname}" '
                        'text:anchor-type="as-char" '
                        f'svg:width="{w_cm:.2f}cm" svg:height="{h_cm:.2f}cm" '
                        'draw:z-index="0">'
                        f'<draw:image xlink:href="{ipath}" '
                        'xlink:type="simple" xlink:show="embed" '
                        'xlink:actuate="onLoad"/></draw:frame></text:p>')
                    if alt.strip():
                        body.append(f'<text:p text:style-name="Caption">'
                                    f'{escape(alt)}</text:p>')
                    continue
                c = escape(content)
                if kind.startswith("h"):
                    lvl = kind[1]
                    body.append(f'<text:h text:style-name="Heading_20_{lvl}" '
                                f'text:outline-level="{lvl}">{c}</text:h>')
                elif kind == "bullet":
                    body.append('<text:list text:style-name="L1"><text:list-item>'
                                f'<text:p text:style-name="Standard">{c}</text:p>'
                                '</text:list-item></text:list>')
                elif kind == "quote":
                    body.append(f'<text:p text:style-name="Quote">{c}</text:p>')
                else:
                    body.append(f'<text:p text:style-name="Standard">{c}</text:p>')

        # colophon in fondo, se presente
        for ln in self._colophon_paragraphs():
            body.append(f'<text:p text:style-name="Author">{escape(ln)}</text:p>')

        content_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<office:document-content '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
            'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
            'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
            'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
            'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            'office:version="1.2">\n'
            '<office:automatic-styles>\n'
            '<style:style style:name="Title" style:family="paragraph">'
            '<style:paragraph-properties fo:text-align="center"/>'
            '<style:text-properties fo:font-size="24pt" fo:font-weight="bold" '
            'fo:color="#5C2A55"/></style:style>\n'
            '<style:style style:name="Author" style:family="paragraph">'
            '<style:paragraph-properties fo:text-align="center"/>'
            '<style:text-properties fo:font-size="13pt"/></style:style>\n'
            '<style:style style:name="Quote" style:family="paragraph">'
            '<style:paragraph-properties fo:margin-left="1cm"/>'
            '<style:text-properties fo:font-style="italic"/></style:style>\n'
            '<style:style style:name="Caption" style:family="paragraph">'
            '<style:paragraph-properties fo:text-align="center"/>'
            '<style:text-properties fo:font-size="10pt" fo:font-style="italic"/></style:style>\n'
            '</office:automatic-styles>\n'
            '<office:body><office:text>\n'
            + "\n".join(body) +
            '\n</office:text></office:body>\n'
            '</office:document-content>\n')

        styles_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<office:document-styles '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
            'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
            'office:version="1.2"><office:styles>\n'
            '<style:style style:name="Standard" style:family="paragraph"/>\n'
            '<style:style style:name="Heading_20_1" style:family="paragraph" '
            'style:display-name="Heading 1">'
            '<style:text-properties fo:font-size="18pt" fo:font-weight="bold" '
            'fo:color="#5C2A55"/></style:style>\n'
            '<style:style style:name="Heading_20_2" style:family="paragraph" '
            'style:display-name="Heading 2">'
            '<style:text-properties fo:font-size="15pt" fo:font-weight="bold"/>'
            '</style:style>\n'
            '<style:style style:name="Heading_20_3" style:family="paragraph" '
            'style:display-name="Heading 3">'
            '<style:text-properties fo:font-size="13pt" fo:font-weight="bold"/>'
            '</style:style>\n'
            '</office:styles></office:document-styles>\n')

        # EN/IT: one manifest entry per picture / una voce per immagine
        img_manifest = "".join(
            f'<manifest:file-entry manifest:full-path="{ipath}" '
            f'manifest:media-type="{imime}"/>\n'
            for (ipath, imime, _d) in img_entries)
        manifest = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<manifest:manifest '
            'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
            'manifest:version="1.2">\n'
            '<manifest:file-entry manifest:full-path="/" '
            'manifest:media-type="application/vnd.oasis.opendocument.text"/>\n'
            '<manifest:file-entry manifest:full-path="content.xml" '
            'manifest:media-type="text/xml"/>\n'
            '<manifest:file-entry manifest:full-path="styles.xml" '
            'manifest:media-type="text/xml"/>\n'
            + img_manifest +
            '</manifest:manifest>\n')

        with zipfile.ZipFile(path, "w") as z:
            # come per l'EPUB, il mimetype va per primo e non compresso
            z.writestr("mimetype", "application/vnd.oasis.opendocument.text",
                       compress_type=zipfile.ZIP_STORED)
            z.writestr("content.xml", content_xml, zipfile.ZIP_DEFLATED)
            z.writestr("styles.xml", styles_xml, zipfile.ZIP_DEFLATED)
            z.writestr("META-INF/manifest.xml", manifest, zipfile.ZIP_DEFLATED)
            for (ipath, _m, idata) in img_entries:
                z.writestr(ipath, idata, zipfile.ZIP_STORED)

    def export_docx(self, path):
        """Esporta in Word (.docx) usando solo la libreria standard.
        Anche il .docx è un archivio ZIP con XML (Office Open XML)."""
        import zipfile
        from xml.sax.saxutils import escape

        cover_lines = self._cover_lines()
        title = cover_lines[0] if cover_lines else self.title

        def para(text, style=None, bold=False, size=None, align=None,
                 color=None):
            ppr = []
            if style:
                ppr.append(f'<w:pStyle w:val="{style}"/>')
            if align:
                ppr.append(f'<w:jc w:val="{align}"/>')
            ppr_xml = f'<w:pPr>{"".join(ppr)}</w:pPr>' if ppr else ""
            rpr = []
            if bold:
                rpr.append('<w:b/>')
            if size:
                rpr.append(f'<w:sz w:val="{size*2}"/>')  # half-points
            if color:
                rpr.append(f'<w:color w:val="{color}"/>')
            rpr_xml = f'<w:rPr>{"".join(rpr)}</w:rPr>' if rpr else ""
            return (f'<w:p>{ppr_xml}<w:r>{rpr_xml}'
                    f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')

        # EN: pictures shipped inside word/media/: (relationship id,
        #     file name, bytes). Word cannot display WebP, so WebP data is
        #     converted to JPEG with Pillow when possible; if the conversion
        #     is unavailable the image is skipped (caption only).
        # IT: immagini incluse in word/media/: (id relazione, nome file,
        #     byte). Word non visualizza il WebP, quindi i dati WebP vengono
        #     convertiti in JPEG con Pillow quando possibile; se la
        #     conversione non e' disponibile l'immagine viene omessa (resta
        #     la didascalia).
        media = []
        CM = 360000       # EN/IT: 1 cm in EMU / 1 cm in EMU (unita' di Word)

        def docx_ready(data, fmt):
            """EN: (bytes, ext, w_px, h_px) suitable for Word, or None.
            IT: (byte, estensione, larg_px, alt_px) adatti a Word, o None."""
            fmt = fmt or image_format(data)
            if fmt in ("png", "jpeg"):
                dims = image_dimensions(data, fmt) or (1600, 1000)
                return data, IMAGE_FORMATS[fmt][0], dims[0], dims[1]
            jpg = _image_to_jpeg(data, fmt)     # WebP -> JPEG (con Pillow)
            if jpg:
                return jpg[0], "jpg", jpg[1], jpg[2]
            return None

        def drawing(rid, name, w_emu, h_emu, num):
            """EN: minimal Office Open XML inline picture block.
            IT: blocco minimo Office Open XML per un'immagine inline."""
            return (
                '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
                f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
                f'<wp:extent cx="{w_emu}" cy="{h_emu}"/>'
                f'<wp:docPr id="{num}" name="{name}"/>'
                '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                f'<pic:nvPicPr><pic:cNvPr id="{num}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
                f'<pic:blipFill><a:blip r:embed="{rid}" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
                '<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
                f'<a:ext cx="{w_emu}" cy="{h_emu}"/></a:xfrm>'
                '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')

        def add_picture(data, fmt, base_name, max_w_cm=16.0, max_h_cm=24.0):
            """EN: register a picture and return its <w:drawing> paragraph,
            or None when the image cannot be embedded.
            IT: registra un'immagine e restituisce il suo paragrafo
            <w:drawing>, o None quando non puo' essere incorporata."""
            ready = docx_ready(data, fmt)
            if not ready:
                return None
            bts, ext, iw, ih = ready
            num = len(media) + 1
            rid = f"rIdImg{num}"
            fname = f"{base_name}.{ext}"
            media.append((rid, fname, bts))
            w_cm = max_w_cm
            h_cm = min(max_h_cm, w_cm * ih / iw)
            return drawing(rid, base_name, int(w_cm * CM), int(h_cm * CM), num)

        # immagine di copertina (se presente) come primo paragrafo
        cover_drawing = None
        if self.cover_image:
            cover_drawing = add_picture(self.cover_image,
                                        self.cover_image_fmt, "cover")

        paras = []
        # copertina: immagine se presente, altrimenti testo
        if cover_drawing:
            paras.append(cover_drawing)
        else:
            paras.append(para(title, bold=True, size=24, align="center",
                              color="5C2A55"))
            for extra in cover_lines[1:]:
                paras.append(para(extra, size=13, align="center"))
        paras.append(para(""))   # spazio
        # frontespizio (dopo la copertina)
        front = self._front_paragraphs()
        for j, ln in enumerate(front):
            if j == 0:
                paras.append(para(ln, bold=True, size=20, align="center",
                                  color="5C2A55"))
            else:
                paras.append(para(ln, size=13, align="center"))
        if front:
            paras.append(para(""))
        # capitoli
        for ch_title, text in self._ordered_chapters():
            body_blocks = self._doc_blocks(text)
            starts_with_heading = bool(body_blocks) and body_blocks[0][0].startswith("h")
            if not starts_with_heading:
                paras.append(para(ch_title, bold=True, size=18, color="5C2A55"))
            for kind, content in body_blocks:
                if kind == "image":
                    # EN: attached image + optional italic caption below.
                    # IT: immagine allegata + eventuale didascalia in corsivo.
                    alt, iname = content
                    d = add_picture(self.images[iname], None,
                                    os.path.splitext(iname)[0],
                                    max_w_cm=14.0, max_h_cm=20.0)
                    if d:
                        paras.append(d)
                    if alt.strip():
                        paras.append(para(alt, size=10, align="center",
                                          color="666666"))
                    continue
                if kind == "h1":
                    paras.append(para(content, bold=True, size=18, color="5C2A55"))
                elif kind == "h2":
                    paras.append(para(content, bold=True, size=15))
                elif kind == "h3":
                    paras.append(para(content, bold=True, size=13))
                elif kind == "bullet":
                    paras.append(para("• " + content))
                elif kind == "quote":
                    paras.append(para(content, style="Quote"))
                else:
                    paras.append(para(content))

        # colophon in fondo, se presente
        colo = self._colophon_paragraphs()
        if colo:
            paras.append(para(""))
            for ln in colo:
                paras.append(para(ln, size=11, align="center", color="555555"))

        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
            '<w:body>'
            + "".join(paras) +
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>'
            '</w:sectPr>'
            '</w:body></w:document>')

        # EN: declare the MIME type once per extension actually used.
        # IT: dichiara il tipo MIME una volta per estensione davvero usata.
        exts = {fname.rsplit(".", 1)[1] for (_r, fname, _b) in media}
        img_ct = ""
        if "jpg" in exts:
            img_ct += ('<Default Extension="jpg" ContentType="image/jpeg"/>'
                       '<Default Extension="jpeg" ContentType="image/jpeg"/>')
        if "png" in exts:
            img_ct += '<Default Extension="png" ContentType="image/png"/>'
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            + img_ct +
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document.main+xml"/>'
            '</Types>')

        rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships '
            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')

        # EN: document relationships: one entry per embedded picture.
        # IT: relazioni del documento: una voce per ogni immagine incorporata.
        doc_rels = None
        if media:
            rel_items = "".join(
                f'<Relationship Id="{rid}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                f'relationships/image" Target="media/{fname}"/>'
                for (rid, fname, _b) in media)
            doc_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships '
                'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + rel_items + '</Relationships>')

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types)
            z.writestr("_rels/.rels", rels)
            z.writestr("word/document.xml", document)
            if media:
                z.writestr("word/_rels/document.xml.rels", doc_rels)
                for (_rid, fname, bts) in media:
                    z.writestr(f"word/media/{fname}", bts)


    def export_pdf(self, path, font_size=12, embed_fonts=None,
                   embed_font_name="CourierPrime", page_size="A4",
                   justify=False, hyphenate=False, hyphen_lang="it"):
        """Salva in PDF con markdown di base. Se embed_fonts e' fornito (dict
        stile->metrics), il testo usa il font del documento incorporato e rende
        grassetto/corsivo. La copertina e' una pagina senza numero; la
        numerazione parte da 1 dalla pagina successiva.

        page_size sceglie il formato pagina: "A4" (predefinito) o "A5". Le
        dimensioni e il margine vengono presi da PDF_PAGE_SIZES; un valore non
        riconosciuto ripiega su A4.

        justify   : se True, i paragrafi del corpo sono giustificati alla
                    larghezza del testo (l'ultima riga resta allineata a
                    sinistra; le intestazioni non si giustificano).
        hyphenate : se True e Pyphen e' disponibile, le parole lunghe vengono
                    sillabate con un trattino per una giustificazione piu'
                    ordinata; ignorato se Pyphen manca.
        hyphen_lang : codice lingua del dizionario di sillabazione (es. "it")."""
        cover_paragraphs = None
        cover_roles = None
        chapters_paragraphs = []
        chapter_titles = []
        n = 0
        for ch in self.chapters:
            text = ch.text.rstrip("\n")
            paras = list(text.split("\n\n")) if text else [""]
            if ch.is_cover:
                # la copertina grafica ora si costruisce dai CAMPI del
                # frontespizio (titolo, autore, editore), non dal testo del
                # vecchio capitolo-copertina. _cover_lines() gestisce anche il
                # ripiego per i progetti vecchi.
                voci_cop = self.cover_lines_with_roles()
                cover_paragraphs = [t for t, _r in voci_cop] or paras
                cover_roles = [r for _t, r in voci_cop] or None
            else:
                n += 1
                chapters_paragraphs.append(paras)
                chapter_titles.append(ch.title_with_fallback(
                    fallback_template="Capitolo {n}".replace("{n}", str(n))))
        leading = int(round(font_size * 1.45))
        cover_img = None
        if self.cover_image:
            cover_img = _image_to_jpeg(self.cover_image, self.cover_image_fmt)
        # EN: attached chapter images, converted to JPEG for embedding (the
        #     PDF stream uses DCTDecode). Images that cannot be converted
        #     (e.g. WebP without Pillow) are skipped: their caption remains.
        # IT: immagini allegate ai capitoli, convertite in JPEG per
        #     l'incorporamento (lo stream PDF usa DCTDecode). Le immagini non
        #     convertibili (es. WebP senza Pillow) vengono omesse: resta la
        #     loro didascalia.
        chapter_images = {}
        for iname in self.used_images():
            prepared = _image_to_jpeg(self.images[iname])
            if prepared:
                chapter_images[iname] = prepared
        # copertina bianca e vuota se non c'e' immagine e i campi delle
        # Sezioni editoriali del frontespizio sono tutti vuoti
        blank_cover = self.cover_is_blank()
        # frontespizio/colophon come righe con stile (testo, ruolo)
        front = self._front_lines() or None
        colo = self._colophon_lines() or None
        # dimensioni e margini del formato pagina scelto (ripiego su default)
        spec = PDF_PAGE_SIZES.get(page_size, PDF_PAGE_SIZES[PDF_DEFAULT_PAGE_SIZE])
        write_pdf(path, chapters_paragraphs, title=self.title,
                  cover_paragraphs=cover_paragraphs,
                  cover_roles=cover_roles,
                  chapter_titles=chapter_titles,
                  toc_label=self.t_index_label(),
                  font_size=font_size, leading=leading,
                  page_w=spec["w"], page_h=spec["h"], margin=spec["margin"],
                  margin_inner=spec.get("inner"), margin_outer=spec.get("outer"),
                  page_break_per_chapter=True,
                  embed_fonts=embed_fonts, embed_font_name=embed_font_name,
                  cover_image=cover_img,
                  chapter_images=chapter_images,
                  frontispiece_paragraphs=front,
                  colophon_paragraphs=colo,
                  blank_cover=blank_cover,
                  justify=justify, hyphenate=hyphenate, hyphen_lang=hyphen_lang)

    def _make_cover_png(self, cover_lines, width=600, height=900):
        """Genera i byte di un'immagine PNG di copertina (raster), necessaria
        perché i generatori di miniature come gnome-epub-thumbnailer mostrino
        l'anteprima: questi strumenti vogliono un'immagine raster (PNG/JPEG),
        non un SVG. Se Pillow è disponibile, disegna anche titolo e autore;
        altrimenti produce con la sola libreria standard un PNG con sfondo,
        cornice e filetti (senza testo), comunque valido come anteprima."""
        voci = self.cover_lines_with_roles()
        title = next((t for t, r in voci if r == "title"),
                     cover_lines[0] if cover_lines else self.title)
        middle = [t for t, r in voci if r in ("subtitle", "author")]
        date = next((t for t, r in voci if r == "publisher"), "")

        # --- tentativo con Pillow (testo nitido) --------------------------
        try:
            from PIL import Image, ImageDraw, ImageFont
            import io as _io

            img = Image.new("RGB", (width, height), "#FFFFFF")
            d = ImageDraw.Draw(img)
            plum = (92, 42, 85)
            # cornice
            d.rectangle([4, 4, width - 5, height - 5], outline=plum, width=3)

            def font(sz, bold=False):
                # prova alcuni font di sistema comuni; ripiego sul font interno
                for n in (["DejaVuSerif-Bold.ttf"] if bold else
                          ["DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf"]):
                    try:
                        return ImageFont.truetype(n, sz)
                    except Exception:
                        pass
                try:
                    return ImageFont.truetype(
                        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", sz)
                except Exception:
                    return ImageFont.load_default()

            def text_width(text, f):
                try:
                    bbox = d.textbbox((0, 0), text, font=f)
                    return bbox[2] - bbox[0]
                except Exception:
                    return len(text) * 20

            def centered(text, y, sz, bold=False, fill=(58, 18, 48)):
                f = font(sz, bold)
                tw = text_width(text, f)
                d.text(((width - tw) / 2, y), text, font=f, fill=fill)

            def wrap(text, f, maxw):
                words = text.split()
                if not words:
                    return [""]
                rows, cur = [], words[0]
                for w in words[1:]:
                    if text_width(cur + " " + w, f) <= maxw:
                        cur += " " + w
                    else:
                        rows.append(cur); cur = w
                rows.append(cur)
                return rows

            # filetti sopra/sotto il titolo
            d.line([180, 330, 420, 330], fill=plum, width=2)
            # titolo: riduci il corpo finché non sta, poi vai a capo se serve
            maxw = width - 120
            tsize = 40
            tfont = font(tsize, True)
            while tsize > 22 and text_width(title, tfont) > maxw:
                tsize -= 2
                tfont = font(tsize, True)
            rows = wrap(title, tfont, maxw)
            ty = 400 - (len(rows) - 1) * (tsize + 6) // 2
            for r in rows:
                tw = text_width(r, tfont)
                d.text(((width - tw) / 2, ty), r, font=tfont, fill=(58, 18, 48))
                ty += tsize + 6
            yy = 470
            for m in middle:
                centered(m, yy, 24)
                yy += 40
            d.line([180, 560, 420, 560], fill=plum, width=2)
            if date:
                centered(date, 600, 18, fill=(110, 110, 110))

            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            pass

        # --- ripiego senza dipendenze: PNG di sola grafica (stdlib) -------
        return self._simple_png(width, height)

    @staticmethod
    def _simple_png(width, height):
        """Crea un PNG (sfondo bianco + cornice prugna + due filetti) usando
        solo zlib e struct. Serve come anteprima quando Pillow non c'è."""
        import zlib, struct

        # immagine RGB: lista di righe, ogni pixel 3 byte
        white = (255, 255, 255)
        plum = (92, 42, 85)

        # buffer pixel
        raw = bytearray()
        # disegniamo: cornice spessa 3px e due filetti orizzontali
        def px(x, y):
            # bordo cornice
            if x < 4 or x >= width - 4 or y < 4 or y >= height - 4:
                if x < 7 or x >= width - 7 or y < 7 or y >= height - 7:
                    return plum
            # filetti a y=330 e y=560, da x=180 a x=420
            if (330 <= y <= 332 or 560 <= y <= 562) and 180 <= x <= 420:
                return plum
            return white

        for y in range(height):
            raw.append(0)  # filtro 'None' a inizio riga
            for x in range(width):
                r, g, b = px(x, y)
                raw += bytes((r, g, b))

        def chunk(typ, data):
            c = struct.pack(">I", len(data)) + typ + data
            c += struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff)
            return c

        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
        idat = zlib.compress(bytes(raw), 9)
        return (sig + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", idat) + chunk(b"IEND", b""))

    @staticmethod
    def _make_blank_cover_png(width=600, height=900):
        """Crea un PNG completamente BIANCO (nessuna cornice, nessun filetto,
        nessun testo), usando solo zlib e struct. Usato come copertina
        e-book quando i campi delle Sezioni editoriali sono vuoti e non c'e'
        un'immagine di copertina: il risultato e' una copertina bianca e vuota."""
        import zlib, struct

        # ogni riga: 1 byte di filtro 'None' + width pixel RGB bianchi
        white_row = b"\x00" + (b"\xff\xff\xff" * width)
        raw = white_row * height

        def chunk(typ, data):
            c = struct.pack(">I", len(data)) + typ + data
            c += struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff)
            return c

        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
        idat = zlib.compress(raw, 9)
        return (sig + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", idat) + chunk(b"IEND", b""))

    def export_epub(self, path, author=None):
        """Esporta il progetto in un file EPUB 2 valido usando solo la
        libreria standard. La copertina diventa la prima sezione; ogni
        capitolo una sezione XHTML separata. Il markdown di base
        (intestazioni, grassetto, corsivo, liste, citazioni) viene reso in
        HTML semplice. Titolo e autore provengono dal progetto/copertina."""
        import zipfile, html, uuid, datetime

        # --- titolo e autore: prima di tutto dai CAMPI del frontespizio ----
        # (File -> Sezioni editoriali). _cover_lines() usa i campi e ripiega
        # sul vecchio capitolo-copertina solo per i progetti datati.
        title = self.title or "Senza titolo"
        cover_lines = self._cover_lines()
        if cover_lines:
            title = cover_lines[0]
        if author is None:
            author = (self.frontispiece_fields.get("author", "") or "").strip()
        author = author or ""

        book_id = "urn:uuid:" + str(uuid.uuid4())

        def esc(s):
            return html.escape(s, quote=False)

        # EN: attached images referenced by the chapters: they are shipped in
        #     OEBPS/images/ and listed in the manifest with their MIME type.
        # IT: immagini allegate richiamate dai capitoli: vengono incluse in
        #     OEBPS/images/ ed elencate nel manifest con il loro tipo MIME.
        used_imgs = self.used_images()

        def epub_image_html(alt, name):
            # EN: XHTML 1.1 has no <figure>: a plain <div> + caption <p>.
            # IT: XHTML 1.1 non ha <figure>: un semplice <div> + <p> didascalia.
            cap = (f'<p style="text-align:center;font-style:italic;">'
                   f'{esc(alt)}</p>' if alt.strip() else "")
            return (f'<div style="text-align:center;">'
                    f'<img src="images/{name}" alt="{esc(alt)}" '
                    f'style="max-width:100%;"/></div>{cap}')

        def md_to_html(text):
            """EN: chapter Markdown -> XHTML body, via the shared converter.
            IT: markdown del capitolo -> corpo XHTML, tramite il convertitore
            condiviso."""
            out = self._blocks_to_html(text, image_html=epub_image_html)
            return "\n".join(out) if out else "<p></p>"

        XHTML = ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
                 '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
                 '<html xmlns="http://www.w3.org/1999/xhtml">\n'
                 '<head><meta http-equiv="Content-Type" '
                 'content="text/html; charset=utf-8"/>\n'
                 '<title>{t}</title>\n'
                 '<link rel="stylesheet" type="text/css" href="style.css"/>\n'
                 '</head>\n<body>\n{body}\n</body>\n</html>\n')

        CSS = ("body{font-family:'EB Garamond',Georgia,serif;line-height:1.5;margin:5%;}"
               "h1,h2,h3{font-family:sans-serif;color:#5C2A55;}"
               "blockquote{font-style:italic;border-left:3px solid #8E4585;"
               "padding-left:1em;color:#444;}"
               ".cover{text-align:center;margin-top:30%;}"
               ".cover .title{font-size:2em;font-weight:bold;color:#5C2A55;}"
               ".cover .author{font-size:1.2em;margin-top:1em;}"
               ".cover .date{font-style:italic;margin-top:2em;color:#666;}"
               "nav.toc ol{list-style:none;padding-left:0;}"
               "nav.toc li{margin:0.4em 0;}"
               "nav.toc a{color:#5C2A55;text-decoration:none;}"
               "code{font-family:monospace;}")

        # --- immagine di copertina (SVG, sobria come il PDF) --------------
        cl = cover_lines or [title]
        ctitle = esc(cl[0])
        cmiddle = [esc(x) for x in cl[1:-1]] if len(cl) > 2 else (
            [esc(cl[1])] if len(cl) == 2 else [])
        cdate = esc(cl[-1]) if len(cl) > 1 else ""

        def svg_text(y, size, weight, txt, style=""):
            return (f'<text x="300" y="{y}" text-anchor="middle" '
                    f'font-family="serif" font-size="{size}" '
                    f'font-weight="{weight}" {style} fill="#3A1230">{txt}</text>')

        svg_lines = [
            '<rect x="2" y="2" width="596" height="896" fill="#FFFFFF" '
            'stroke="#5C2A55" stroke-width="2"/>',
            '<line x1="180" y1="330" x2="420" y2="330" stroke="#5C2A55" '
            'stroke-width="1.2"/>',
            svg_text(420, 38, "bold", ctitle),
        ]
        yy = 470
        for mid in cmiddle:
            svg_lines.append(svg_text(yy, 24, "normal", mid))
            yy += 40
        svg_lines.append('<line x1="180" y1="560" x2="420" y2="560" '
                         'stroke="#5C2A55" stroke-width="1.2"/>')
        if cdate:
            svg_lines.append(svg_text(610, 18, "normal", cdate,
                                      'font-style="italic"'))
        cover_svg = ('<?xml version="1.0" encoding="utf-8"?>\n'
                     '<svg xmlns="http://www.w3.org/2000/svg" '
                     'width="600" height="900" viewBox="0 0 600 900">\n'
                     + "\n".join(svg_lines) + '\n</svg>\n')

        # immagine di copertina RASTER: se l'utente ne ha caricata una usiamo
        # quella, altrimenti generiamo il PNG sobrio. I generatori di miniature
        # (gnome-epub-thumbnailer, Calibre) richiedono un raster.
        if self.cover_image:
            cover_img_bytes = self.cover_image
            cover_ext = IMAGE_FORMATS.get(self.cover_image_fmt, ("png",))[0]
            cover_img_name = f"cover.{cover_ext}"
            cover_img_mime = self._cover_image_mime()
        elif self.cover_is_blank():
            # campi Sezioni editoriali vuoti e nessuna immagine: copertina
            # bianca e vuota (PNG completamente bianco, senza testo ne' grafica)
            cover_img_bytes = self._make_blank_cover_png()
            cover_img_name = "cover.png"
            cover_img_mime = "image/png"
        else:
            cover_img_bytes = self._make_cover_png(cl)
            cover_img_name = "cover.png"
            cover_img_mime = "image/png"

        # --- costruisci le sezioni XHTML ----------------------------------
        sections = []   # (id, filename, title, xhtml_body, in_toc)

        # pagina copertina che mostra l'immagine raster
        cover_page = ('<div style="text-align:center;margin:0;padding:0;">'
                      '<img src="%s" alt="%s" '
                      'style="max-width:100%%;height:auto;"/></div>'
                      % (cover_img_name, ctitle))
        sections.append(("coverpage", "cover.xhtml", title, cover_page, False))

        # frontespizio (dopo la copertina), se presente
        front = self._front_paragraphs()
        if front:
            fr_html = ['<div class="frontispiece">']
            for j, ln in enumerate(front):
                if j == 0:
                    fr_html.append(f'<h1 style="text-align:center">{esc(ln)}</h1>')
                else:
                    fr_html.append(f'<p style="text-align:center">{esc(ln)}</p>')
            fr_html.append('</div>')
            sections.append(("frontispiece", "frontispiece.xhtml",
                             "Frontispiece", "\n".join(fr_html), False))

        # capitoli
        chap_entries = []   # (filename, titolo) per l'indice
        n = 0
        for ch in self.chapters:
            if ch.is_cover:
                continue
            n += 1
            ch_title = ch.title_with_fallback(
                fallback_template="Capitolo {n}".replace("{n}", str(n)))
            fname = f"chap{n:02d}.xhtml"
            sections.append((f"chap{n:02d}", fname, ch_title,
                             md_to_html(ch.text), True))
            chap_entries.append((fname, ch_title))

        # colophon (ultima sezione), se presente
        colo = self._colophon_paragraphs()
        if colo:
            co_html = ['<div class="colophon">']
            for ln in colo:
                co_html.append(f'<p style="text-align:center">{esc(ln)}</p>')
            co_html.append('</div>')
            sections.append(("colophon", "colophon.xhtml",
                             "Colophon", "\n".join(co_html), False))

        # pagina indice (sommario navigabile)
        toc_items = "".join(
            f'<li><a href="{fn}">{esc(tt)}</a></li>' for fn, tt in chap_entries)
        toc_body = (f'<h1>{esc(self.t_index_label())}</h1>'
                    f'<nav class="toc"><ol>{toc_items}</ol></nav>')
        # inserisci l'indice subito dopo la copertina
        sections.insert(1, ("nav", "index.xhtml",
                            self.t_index_label(), toc_body, False))

        # --- file di struttura --------------------------------------------
        manifest, spine, navpoints = [], [], []
        play = 1
        for (iid, fname, sec_title, _body, in_toc) in sections:
            manifest.append(f'<item id="{iid}" href="{fname}" '
                            f'media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="{iid}"/>')
            if in_toc:
                navpoints.append(
                    f'<navPoint id="np{play}" playOrder="{play}">'
                    f'<navLabel><text>{esc(sec_title)}</text></navLabel>'
                    f'<content src="{fname}"/></navPoint>')
                play += 1

        opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<package xmlns="http://www.idpf.org/2007/opf" '
               'unique-identifier="bookid" version="2.0">\n'
               '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" '
               'xmlns:opf="http://www.idpf.org/2007/opf">\n'
               f'<dc:title>{esc(title)}</dc:title>\n'
               + (f'<dc:creator opf:role="aut">{esc(author)}</dc:creator>\n'
                  if author else '') +
               '<dc:language>it</dc:language>\n'
               f'<dc:identifier id="bookid">{book_id}</dc:identifier>\n'
               f'<dc:date>{datetime.date.today().isoformat()}</dc:date>\n'
               '<meta name="cover" content="cover-image"/>\n'
               '</metadata>\n<manifest>\n'
               '<item id="ncx" href="toc.ncx" '
               'media-type="application/x-dtbncx+xml"/>\n'
               '<item id="css" href="style.css" media-type="text/css"/>\n'
               f'<item id="cover-image" href="{cover_img_name}" '
               f'media-type="{cover_img_mime}"/>\n'
               '<item id="cover-svg" href="cover.svg" '
               'media-type="image/svg+xml"/>\n'
               + "".join(f'<item id="att{k}" href="images/{n}" '
                         f'media-type="{self.image_mime(n)}"/>\n'
                         for k, n in enumerate(used_imgs, 1))
               + "\n".join(manifest) +
               '\n</manifest>\n<spine toc="ncx">\n'
               + "\n".join(spine) +
               '\n</spine>\n<guide>\n'
               '<reference type="cover" title="Copertina" href="cover.xhtml"/>\n'
               '<reference type="toc" title="Indice" href="index.xhtml"/>\n'
               '</guide>\n</package>\n')

        ncx = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
               f'<head><meta name="dtb:uid" content="{book_id}"/>'
               '<meta name="dtb:depth" content="1"/>'
               '<meta name="dtb:totalPageCount" content="0"/>'
               '<meta name="dtb:maxPageNumber" content="0"/></head>\n'
               f'<docTitle><text>{esc(title)}</text></docTitle>\n'
               '<navMap>\n' + "\n".join(navpoints) + '\n</navMap>\n</ncx>\n')

        container = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                     '<container version="1.0" '
                     'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
                     '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                     'media-type="application/oebps-package+xml"/></rootfiles>\n'
                     '</container>\n')

        # --- scrivi lo ZIP EPUB (mimetype non compresso, per primo) -------
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("mimetype", "application/epub+zip",
                       compress_type=zipfile.ZIP_STORED)
            z.writestr("META-INF/container.xml", container,
                       compress_type=zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/toc.ncx", ncx, zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/style.css", CSS, zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/" + cover_img_name, cover_img_bytes,
                       zipfile.ZIP_DEFLATED)
            z.writestr("OEBPS/cover.svg", cover_svg, zipfile.ZIP_DEFLATED)
            # EN: attached chapter images (only the ones actually used).
            # IT: immagini allegate ai capitoli (solo quelle davvero usate).
            for n in used_imgs:
                z.writestr("OEBPS/images/" + n, self.images[n],
                           zipfile.ZIP_STORED)
            for (iid, fname, sec_title, body, in_toc) in sections:
                z.writestr("OEBPS/" + fname,
                           XHTML.format(t=esc(sec_title), body=body),
                           zipfile.ZIP_DEFLATED)

    def t_index_label(self):
        """Etichetta 'Indice' nella lingua del progetto (fallback IT/EN)."""
        return "Indice" if getattr(self, "_lang", "it") == "it" else "Contents"

    @staticmethod
    def _find_calibre_converter():
        """Cerca l'eseguibile 'ebook-convert' di Calibre nel sistema.
        Restituisce il percorso o None se Calibre non è installato."""
        # nel PATH
        exe = shutil.which("ebook-convert")
        if exe:
            return exe
        # percorsi tipici (Linux, macOS, Windows)
        candidates = [
            "/usr/bin/ebook-convert",
            "/opt/calibre/ebook-convert",
            "/Applications/calibre.app/Contents/MacOS/ebook-convert",
            r"C:\Program Files\Calibre2\ebook-convert.exe",
            r"C:\Program Files (x86)\Calibre2\ebook-convert.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def export_azw3(self, path, author=None):
        """Esporta in AZW3 (Kindle). L'AZW3 è un formato proprietario Amazon:
        per ottenere un file affidabile generiamo prima un EPUB (che sappiamo
        produrre bene) e lo convertiamo con Calibre ('ebook-convert'), se
        installato. Se Calibre non c'è, solleviamo un errore esplicativo.

        Restituisce il percorso prodotto. Solleva RuntimeError con istruzioni
        se la conversione non è possibile."""
        import subprocess

        converter = self._find_calibre_converter()
        if not converter:
            raise RuntimeError(
                "Per esportare in AZW3 serve Calibre (comando 'ebook-convert').\n"
                "Installa Calibre da https://calibre-ebook.com/ e riprova.\n"
                "In alternativa esporta in EPUB e converti con Calibre o "
                "'Invia a Kindle' di Amazon.")

        # 1) genera un EPUB temporaneo accanto alla destinazione
        tmpdir = tempfile.mkdtemp()
        epub_tmp = os.path.join(tmpdir, "book.epub")
        self.export_epub(epub_tmp, author=author)

        # 2) converti EPUB -> AZW3 con Calibre, passando i metadati principali
        cover_lines = self._cover_lines()
        book_title = cover_lines[0] if cover_lines else self.title
        book_author = author or (self.frontispiece_fields.get("author", "") or "").strip()
        cmd = [converter, epub_tmp, path,
               "--title", book_title]
        if book_author:
            cmd += ["--authors", book_author]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError("La conversione AZW3 ha impiegato troppo tempo.")
        except FileNotFoundError:
            raise RuntimeError(
                "Calibre non trovato. Installa Calibre da "
                "https://calibre-ebook.com/ e riprova.")
        finally:
            # pulizia del file temporaneo
            try:
                os.remove(epub_tmp)
                os.rmdir(tmpdir)
            except OSError:
                pass

        if result.returncode != 0 or not os.path.exists(path):
            msg = (result.stderr or result.stdout or "").strip()
            raise RuntimeError("Calibre non è riuscito a creare l'AZW3.\n" + msg[:500])
        return path

    def add_chapter(self):
        idx = (max((c.index for c in self.chapters if not c.is_cover), default=0)) + 1
        ch = Chapter(idx, "", "")
        self.chapters.append(ch)
        self._renumber()
        return ch

    def add_chapter_from_text(self, text, title=""):
        """Aggiunge UN nuovo capitolo in fondo al progetto con il contenuto
        passato (es. importato da un file .txt/.md). Il progetto e gli altri
        capitoli restano invariati. Se 'title' e' dato, diventa il titolo
        personalizzato del capitolo. Restituisce il Chapter creato."""
        idx = (max((c.index for c in self.chapters if not c.is_cover), default=0)) + 1
        body = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        ch = Chapter(idx, body, "", custom_title=(title or "").strip())
        self.chapters.append(ch)
        self._renumber()
        return ch

    def count_wrapped_runs(self):
        """Quanti paragrafi spezzati a colonna fissa ci sono in tutto il
        progetto, e su quante righe. Serve a CHIEDERE, non a decidere."""
        paragrafi = righe = 0
        for ch in self.chapters:
            for first, last in wrapped_runs(ch.text):
                paragrafi += 1
                righe += last - first
        return paragrafi, righe

    def rejoin_paragraphs(self):
        """Ricuce i paragrafi spezzati di TUTTI i capitoli. Restituisce
        (paragrafi, righe) effettivamente sistemati. Da chiamare solo dopo un
        assenso esplicito: la ricucitura cambia il testo di chi scrive."""
        paragrafi = righe = 0
        for ch in self.chapters:
            runs = wrapped_runs(ch.text)
            if not runs:
                continue
            paragrafi += len(runs)
            righe += sum(last - first for first, last in runs)
            ch.text = unwrap_hard_breaks(ch.text)
        return paragrafi, righe

    def delete_chapter(self, row):
        """Rimuove il capitolo alla posizione 'row'. La copertina e' protetta."""
        if 0 <= row < len(self.chapters) and not self.chapters[row].is_cover:
            del self.chapters[row]
            self._renumber()

    def move_chapter(self, row, direction):
        """Sposta il capitolo su (-1) o giu (+1). La copertina resta in cima
        e nessun capitolo puo' finire prima della copertina."""
        if not (0 <= row < len(self.chapters)):
            return row
        ch = self.chapters[row]
        if ch.is_cover:
            return row                      # la copertina non si sposta
        target = row + direction
        # non oltre i limiti e non sopra la copertina (posizione 0)
        if target < 1 or target >= len(self.chapters):
            return row
        if self.chapters[target].is_cover:
            return row
        self.chapters[row], self.chapters[target] = \
            self.chapters[target], self.chapters[row]
        self._renumber()
        return target

    def cover(self):
        """Restituisce il capitolo copertina, o None."""
        for ch in self.chapters:
            if ch.is_cover:
                return ch
        return None


