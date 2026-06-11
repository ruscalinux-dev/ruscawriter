#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modello dati e generazione documenti di RuscaWriter.

Questo modulo è INDIPENDENTE dall'interfaccia grafica (non importa GTK):
contiene la struttura del progetto (Chapter, Project), il generatore PDF
nativo (write_pdf) e tutti gli export (TXT, Markdown, PDF, EPUB, ODT, DOCX,
HTML, AZW3). Essendo separato dalla GUI, può essere testato da solo ed essere
riusato da altri strumenti (script, conversioni batch, ecc.).
"""
import os
import io
import re
import json
import struct
import shutil
import tarfile
import tempfile

# --- costanti applicative condivise -----------------------------------------
APP_NAME = "RuscaWriter"
APP_VERSION = "0.1"
APP_AUTHOR = "ruscalinux-dev"

# Campi strutturati del frontespizio e del colophon. L'ordine e' anche l'ordine
# di impaginazione. Tutti i campi sono opzionali: quelli vuoti non compaiono.
FRONT_FIELDS = ["title", "subtitle", "author", "publisher", "place_year"]
COLO_FIELDS = ["copyright", "publisher", "isbn", "edition", "notes", "license"]
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
    import struct
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


def read_ttf_metrics(path):
    """Legge le metriche essenziali di un TTF (solo libreria standard).
    Restituisce un dict con i dati per incorporarlo in un PDF, oppure None.

    Per i font proporzionali (es. EB Garamond) estrae anche la larghezza di
    ogni carattere nell'intervallo WinAnsi 32..255, in 'widths_by_code', cosi'
    l'impaginazione del PDF e l'array /Widths usano la larghezza reale di ogni
    glifo invece di una larghezza fissa (che andrebbe bene solo per i
    monospace). 'advance1000' resta come ripiego."""
    import struct
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


def _parse_inline_md(text):
    """Spezza il testo in segmenti (testo, stile) interpretando il markdown
    inline. stile in {'regular','bold','italic','bolditalic'}.
    Gestisce **grassetto**, *corsivo*, ***entrambi***, __..__, _.._, `codice`,
    e link [testo](url) -> testo."""
    import re
    # prima normalizza i link in solo testo
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", text)
    # token: ***  ** * ___ __ _ `  (in ordine di lunghezza per il match)
    pattern = re.compile(r"(\*\*\*|___|\*\*|__|\*|_|`)")
    bold = False
    italic = False
    code = False
    segments = []
    buf = []

    def flush():
        if buf:
            if code:
                style = "regular"   # il codice resta a larghezza fissa, regolare
            elif bold and italic:
                style = "bolditalic"
            elif bold:
                style = "bold"
            elif italic:
                style = "italic"
            else:
                style = "regular"
            segments.append(("".join(buf), style))
            buf.clear()

    pos = 0
    for mtok in pattern.finditer(text):
        buf.append(text[pos:mtok.start()])
        tok = mtok.group(1)
        pos = mtok.end()
        if tok == "`":
            flush(); code = not code
        elif tok in ("***", "___"):
            flush(); bold = not bold; italic = not italic
        elif tok in ("**", "__"):
            flush(); bold = not bold
        elif tok in ("*", "_"):
            flush(); italic = not italic
    buf.append(text[pos:])
    flush()
    if not segments:
        segments = [("", "regular")]
    return segments


def _strip_inline_md(text):
    """Restituisce il solo testo senza i marcatori inline markdown."""
    return "".join(seg for seg, _ in _parse_inline_md(text))


def parse_md_line(raw_line, base_size):
    """Interpreta una riga markdown per il PDF. Restituisce
    (segments, dimensione_font, rientro_punti, spazio_extra_sotto, force_style)
    dove segments e' una lista di (testo, stile)."""
    stripped = raw_line.strip()
    if not stripped:
        return ([("", "regular")], base_size, 0.0, 0.0, None)
    # intestazioni: # .. ######  (rese in grassetto, dimensione crescente)
    if stripped.startswith("#"):
        level = len(stripped) - len(stripped.lstrip("#"))
        level = max(1, min(level, 6))
        heading = stripped.lstrip("#").strip()
        factor = {1: 1.6, 2: 1.4, 3: 1.25, 4: 1.15, 5: 1.07, 6: 1.0}[level]
        return ([(_strip_inline_md(heading), "bold")],
                base_size * factor, 0.0, base_size * 0.4, "bold")
    # liste puntate: -, *, +
    if stripped[:2] in ("- ", "* ", "+ "):
        segs = [("\u2022 ", "regular")] + _parse_inline_md(stripped[2:])
        return (segs, base_size, base_size * 1.2, 0.0, None)
    # liste numerate: "1. testo"
    import re
    mnum = re.match(r"^(\d+)\.\s+(.*)$", stripped)
    if mnum:
        segs = [(f"{mnum.group(1)}. ", "regular")] + _parse_inline_md(mnum.group(2))
        return (segs, base_size, base_size * 1.2, 0.0, None)
    # citazione: > testo (resa in corsivo)
    if stripped.startswith(">"):
        body = stripped.lstrip(">").strip()
        segs = [(seg, "italic" if st == "regular" else st)
                for seg, st in _parse_inline_md(body)]
        return (segs, base_size, base_size * 1.2, 0.0, None)
    # riga normale
    return (_parse_inline_md(raw_line), base_size, 0.0, 0.0, None)


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


def _prepare_cover_jpeg(data, fmt):
    """Prepara l'immagine di copertina per l'incorporamento nel PDF.
    Il PDF incorpora i JPEG (DCTDecode); i PNG no. Con Pillow convertiamo
    qualsiasi immagine in JPEG RGB; senza Pillow usiamo il JPEG cosi' com'e';
    altrimenti None (ripiego sulla copertina grafica).
    Ritorna (jpeg_bytes, width, height) oppure None."""
    if not data:
        return None
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


def write_pdf(path, chapters, title="",
              cover_paragraphs=None,
              chapter_titles=None, toc_label="Indice",
              font_size=12, leading=16,
              page_w=595.0, page_h=842.0,   # A4 in punti
              margin=72.0,                  # ~2.54 cm
              page_break_per_chapter=True,
              embed_fonts=None, embed_font_name="CourierPrime",
              cover_image=None,
              frontispiece_paragraphs=None,
              colophon_paragraphs=None):
    """
    Scrive un PDF usando solo la libreria standard, con markdown di base.
      chapters : lista di capitoli; ogni capitolo = lista di paragrafi (str).
      cover_paragraphs : pagina copertina iniziale (senza numero).
      embed_fonts : dict {stile: metrics} per stile in regular/bold/italic/
                    bolditalic (da read_ttf_metrics). Se presente, il testo usa
                    il font incorporato e rende grassetto/corsivo.
    """
    embed_fonts = embed_fonts or {}
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

    usable_w = page_w - 2 * margin
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
        Restituisce una lista di righe, ciascuna lista di run."""
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
                    # a capo
                    lines.append(cur)
                    cur = []
                    cur_w = 0.0
                    if tok.strip() == "":
                        continue   # non iniziare una riga con spazi
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
        prev_role = None
        for t, r in top:
            sz = size_of(r)
            if r == "author":
                yy -= font_size * 0.8
            style = "bold" if r == "title" else ("italic" if r == "subtitle" else "regular")
            rows = _wrap_centered(t, sz)
            yy = _emit_centered(rows, sz, style, yy, sz * 1.4)
            if r == "title":
                yy -= font_size * 0.6
            prev_role = r
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

    # 1) pagina copertina stilizzata (grafica + testo) solo senza immagine
    if cover_paragraphs is not None and cover_image is None:
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

        if raw_lines:
            title_line = raw_lines[0]
            date_line = raw_lines[-1] if len(raw_lines) > 1 else ""
            middle = raw_lines[1:-1] if len(raw_lines) > 2 else (
                raw_lines[1:] if len(raw_lines) == 2 else [])

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

    import re
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
                segments, sz, indent, extra, _force = parse_md_line(raw_line, font_size)
                line_leading = leading * (sz / font_size)
                avail = usable_w - indent
                for run_line in wrap_segments(segments, sz, avail):
                    if y < bottom_y:
                        flush_page()
                        pages_so_far += 1
                    cur_lines.append((margin + indent, y, run_line, sz))
                    y -= line_leading
                if extra:
                    y -= extra
            y -= leading * 0.5
    flush_page()
    pages_so_far += 1

    chapter_pages = pages        # le pagine dei capitoli appena impaginate
    pages = pages_before_chapters

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
            cur_lines.append((margin, yy, [(left + " ", "regular")], font_size))
            if dots:
                cur_lines.append((margin + lw + seg_w(" ", font_size), yy,
                                  [(dots, "regular")], font_size))
            cur_lines.append((page_w - margin - rw, yy,
                              [(right, "regular")], font_size))
            yy -= leading * 1.4
            if yy < bottom_y:
                flush_page("plain")
                yy = content_top_y
        flush_page("plain")

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
        parts.append(b"BT")
        cur_fid = None
        cur_size = None
        for (x, ly, runs, sz) in lines:
            parts.append(f"1 0 0 1 {x:.2f} {ly:.2f} Tm".encode("latin-1"))
            for (text, style) in runs:
                if text == "":
                    continue
                fid = style_to_fid.get(style, "F1")
                if fid != cur_fid or sz != cur_size:
                    parts.append(f"/{fid} {sz:.1f} Tf".encode("latin-1"))
                    cur_fid, cur_size = fid, sz
                parts.append(b"(" + _pdf_escape_bytes(_to_winansi(text)) + b") Tj")
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
        pid = add_obj(
            (f"<< /Type /Page /Parent {pages_obj_id} 0 R "
             f"/MediaBox [0 0 {page_w:.0f} {page_h:.0f}] "
             f"/Resources << /Font << {font_res} >> >> "
             f"/Contents {cid} 0 R >>").encode("latin-1"))
        page_obj_ids.append(pid)

    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects[pages_obj_id - 1] = (
        f"<< /Type /Pages /Count {total} /Kids [{kids}] >>".encode("latin-1"))

    catalog_id = add_obj(
        f"<< /Type /Catalog /Pages {pages_obj_id} 0 R >>".encode("latin-1"))

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


# ---- Colori (color prugna / plum) -------------------------------------------
# --- palette del tema ------------------------------------------------------
# NB: "PLUM" qui e' il COLORE prugna ("plum" in inglese), il tema cromatico
# dell'applicazione — non un residuo del vecchio nome del programma.
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


def build_css(dark=False):
    """Genera il foglio di stile dell'interfaccia.

    Il tema è costruito da una piccola palette: cambiando i colori qui sotto
    si ottiene la versione chiara o quella scura, mantenendo in entrambi i
    casi gli accenti color prugna. Questo è il modo tipico in GTK di gestire
    più temi: un unico CSS parametrizzato invece di due fogli separati.
    """
    if dark:
        bg_top, bg_bottom = PLUM_NIGHT, PLUM_PANEL      # sfondo finestra
        header_a, header_b = PLUM_DARK, PLUM_NIGHT       # barra superiore
        panel_bg = PLUM_PANEL                            # pannelli laterali (pieno)
        list_text = PLUM_GLOW                            # titoli capitoli
        editor_bg = PLUM_INK                             # area di scrittura
        editor_fg = PAPER                                # testo scritto
        notes_fg = PLUM_GLOW
        title_fg = PLUM_GLOW
        status_a, status_b = PLUM_DARK, PLUM_NIGHT
        status_fg = PLUM_GLOW
        findbar_bg = "rgba(30,16,24,0.95)"
        sel_bg, sel_fg = PLUM, WHITE
        dialog_fg = PAPER          # testo dei dialoghi su sfondo scuro
        entry_bg, entry_fg = PLUM_INK, PAPER
    else:
        bg_top, bg_bottom = PLUM_LIGHT, WHITE
        header_a, header_b = PLUM, PLUM_LIGHT
        panel_bg = "rgba(255,255,255,0.55)"
        list_text = PLUM_DARK
        editor_bg = WHITE
        editor_fg = "#000000"
        notes_fg = PLUM_DARK
        title_fg = PLUM_DARK
        status_a, status_b = PLUM_LIGHT, WHITE
        status_fg = PLUM_DARK
        findbar_bg = "rgba(255,255,255,0.85)"
        sel_bg, sel_fg = PLUM, WHITE
        dialog_fg = PLUM_DARK       # testo dei dialoghi su sfondo chiaro
        entry_bg, entry_fg = WHITE, "#000000"

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
    background-image: linear-gradient(to bottom, {PLUM}, {PLUM_DARK});
    color: {WHITE};
    border-radius: 6px;
    padding: 6px 14px;
    margin: 2px;
    font-weight: bold;
    border: none;
}}
.rusca-toolbar button:hover {{
    background-image: linear-gradient(to bottom, {PLUM_DARK}, {PLUM});
}}

/* Barra menu in stile Scrivener */
.rusca-menubar {{
    background-image: linear-gradient(to bottom, {PLUM}, {PLUM_DARK});
    color: {WHITE};
    padding: 1px 4px;
}}
.rusca-menubar > menuitem {{
    color: {WHITE};
    padding: 4px 10px;
    border-radius: 4px;
}}
.rusca-menubar > menuitem:hover {{
    background-color: {PLUM_DARK};
}}
.rusca-menubar menuitem:disabled {{
    color: alpha({WHITE}, 0.5);
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
    background-color: {PLUM};
    color: {WHITE};
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
    border-top: 1px solid {PLUM};
}}
.statusbar-label {{
    color: {status_fg};
    font-family: Sans;
    font-size: 9pt;
    padding: 3px 6px;
}}
.rusca-findbar {{
    background-color: {findbar_bg};
    border-bottom: 1px solid {PLUM};
}}
.rusca-fontlabel {{
    color: {WHITE};
    font-family: Serif;
    font-weight: bold;
    padding: 0 2px;
}}
/* Pulsante hamburger (☰) nella barra superiore: stesso stile prugna dei
   pulsanti della toolbar, leggibile su sfondo scuro e chiaro. */
.rusca-menubtn {{
    color: {WHITE};
    background-image: linear-gradient(to bottom, {PLUM}, {PLUM_DARK});
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
    margin: 2px;
}}
.rusca-menubtn:hover {{
    background-image: linear-gradient(to bottom, {PLUM_DARK}, {PLUM});
}}
"""


# CSS predefinito (tema chiaro), per compatibilità con codice esistente
CSS = build_css(dark=False)


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
        self.cover_image_fmt = None      # "png" | "jpeg"
        # frontespizio e colophon come CAMPI strutturati (formattazione
        # professionale decisa dal programma). Vedi FRONT_FIELDS / COLO_FIELDS.
        self.frontispiece_fields = {k: "" for k in FRONT_FIELDS}
        self.colophon_fields = {k: "" for k in COLO_FIELDS}

    def set_cover_image(self, data, fmt):
        """Imposta l'immagine di copertina. fmt: 'png' o 'jpeg'."""
        self.cover_image = data
        self.cover_image_fmt = fmt

    def clear_cover_image(self):
        self.cover_image = None
        self.cover_image_fmt = None

    def has_cover_image(self):
        return bool(self.cover_image)

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
        self.frontispiece_fields = {k: "" for k in FRONT_FIELDS}
        self.colophon_fields = {k: "" for k in COLO_FIELDS}
        cover = Chapter(0, self._make_cover_text(title), "", is_cover=True)
        # Nessun capitolo creato in automatico: il progetto parte vuoto e
        # l'utente aggiunge i capitoli che vuole (Capitolo -> Nuovo capitolo).
        self.chapters = [cover]

    def import_text_file(self, path):
        """Crea un nuovo progetto importando un file di testo (.txt) o
        Markdown (.md). Il titolo dell'opera viene dal nome del file. Per il
        Markdown, il documento viene suddiviso in capitoli usando le
        intestazioni di primo o secondo livello (# / ##) come punti di taglio;
        per il TXT, se ci sono righe di separazione tipo capitolo le usa,
        altrimenti tiene tutto in un unico capitolo."""
        import re
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()

        title = os.path.splitext(os.path.basename(path))[0]
        is_md = path.lower().endswith((".md", ".markdown"))

        self.title = title
        self.path = None        # importato: nessun .rwr associato finché non si salva
        self.meta = {}
        self.cover_image = None
        self.cover_image_fmt = None
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
        if "cover.jpg" in names:
            self.cover_image = contents["cover.jpg"]; self.cover_image_fmt = "jpeg"
        elif "cover.jpeg" in names:
            self.cover_image = contents["cover.jpeg"]; self.cover_image_fmt = "jpeg"
        elif "cover.png" in names:
            self.cover_image = contents["cover.png"]; self.cover_image_fmt = "png"

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
                if self.cover_image and self.cover_image_fmt:
                    ext = "jpg" if self.cover_image_fmt == "jpeg" else "png"
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
                out.write(ch.text.rstrip("\n"))
                out.write("\n")
            colo = self._colophon_paragraphs()
            if colo:
                sep()
                out.write("\n".join(colo))
                out.write("\n")

    # --- helper comuni agli export documentali ----------------------------
    def _cover_lines(self):
        """Righe della copertina grafica (usata quando NON c'e' un'immagine).
        Le prende dai campi del frontespizio (titolo, autore, editore): la
        copertina non e' piu' un capitolo a se'. Per i progetti vecchi, se i
        campi sono tutti vuoti, ripiega sul testo del vecchio capitolo-copertina
        cosi' non si perde nulla."""
        f = getattr(self, "frontispiece_fields", {}) or {}
        lines = []
        if f.get("title", "").strip():
            lines.append(f["title"].strip())
        if f.get("subtitle", "").strip():
            lines.append(f["subtitle"].strip())
        if f.get("author", "").strip():
            lines.append(f["author"].strip())
        if f.get("publisher", "").strip():
            lines.append(f["publisher"].strip())
        if lines:
            return lines
        # ripiego: vecchio capitolo-copertina (compatibilita')
        cover = self.cover()
        if cover is not None:
            for ln in cover.text.splitlines():
                s = _strip_inline_md(ln.lstrip("#").strip()
                                     if ln.strip().startswith("#") else ln).strip()
                if s:
                    lines.append(s)
        if not lines and self.title:
            lines.append(self.title)
        return lines

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
        return "image/jpeg" if self.cover_image_fmt == "jpeg" else "image/png"

    def _cover_image_data_uri(self):
        """Data URI base64 dell'immagine di copertina, per incorporarla inline
        nell'HTML a file unico. None se non c'e' immagine."""
        if not self.cover_image:
            return None
        import base64
        b64 = base64.b64encode(self.cover_image).decode("ascii")
        return f"data:{self._cover_image_mime()};base64,{b64}"

    def export_markdown(self, path):
        """Esporta tutto il progetto in un unico file Markdown.
        Titolo come H1, copertina come blocco iniziale, ogni capitolo con la
        propria intestazione H2 (se il testo non ne ha già una)."""
        cover_lines = self._cover_lines()
        title = cover_lines[0] if cover_lines else self.title
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
                body = text.rstrip("\n")
                # se il testo inizia già con un'intestazione markdown, non
                # aggiungiamo un titolo doppio
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
        """Trasforma il markdown di un capitolo in una lista di blocchi
        (tipo, contenuto) usata sia da ODT sia da DOCX. Tipi: h1/h2/h3,
        bullet, quote, p. La formattazione inline viene rimossa (testo piano)
        per restare semplice e robusta."""
        import re
        blocks = []
        for raw in text.split("\n"):
            s = raw.strip()
            if not s:
                continue
            m = re.match(r"^(#{1,6})\s+(.*)$", s)
            if m:
                lvl = min(3, len(m.group(1)))
                blocks.append((f"h{lvl}", _strip_inline_md(m.group(2))))
            elif s[:2] in ("- ", "* ", "+ "):
                blocks.append(("bullet", _strip_inline_md(s[2:])))
            elif re.match(r"^\d+\.\s+", s):
                blocks.append(("bullet", _strip_inline_md(re.sub(r"^\d+\.\s+", "", s))))
            elif s.startswith(">"):
                blocks.append(("quote", _strip_inline_md(s.lstrip(">").strip())))
            else:
                blocks.append(("p", _strip_inline_md(s)))
        return blocks

    def _blocks_to_html(self, text):
        """Converte il markdown di un capitolo in HTML (lista di stringhe),
        riconoscendo titoli, elenchi, citazioni e formattazione inline
        (grassetto, corsivo, codice). Usato dall'export HTML."""
        import re
        from xml.sax.saxutils import escape as esc

        def inline(s):
            s = esc(s)
            s = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", s)
            s = re.sub(r"(\*\*\*|___)(.+?)\1", r"<strong><em>\2</em></strong>", s)
            s = re.sub(r"(\*\*|__)(.+?)\1", r"<strong>\2</strong>", s)
            s = re.sub(r"(\*|_)(.+?)\1", r"<em>\2</em>", s)
            s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
            return s

        out = []
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            if not s:
                i += 1
                continue
            m = re.match(r"^(#{1,6})\s+(.*)$", s)
            if m:
                lvl = min(6, len(m.group(1)))
                out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
                i += 1
            elif s[:2] in ("- ", "* ", "+ "):
                items = []
                while i < len(lines) and lines[i].strip()[:2] in ("- ", "* ", "+ "):
                    items.append(f"<li>{inline(lines[i].strip()[2:])}</li>")
                    i += 1
                out.append("<ul>" + "".join(items) + "</ul>")
            elif re.match(r"^\d+\.\s+", s):
                items = []
                while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                    body = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                    items.append(f"<li>{inline(body)}</li>")
                    i += 1
                out.append("<ol>" + "".join(items) + "</ol>")
            elif s.startswith(">"):
                out.append(f"<blockquote>{inline(s.lstrip('>').strip())}</blockquote>")
                i += 1
            else:
                buf = []
                while i < len(lines) and lines[i].strip() and not re.match(
                        r"^(#{1,6}\s|[-*+]\s|\d+\.\s|>)", lines[i].strip()):
                    buf.append(inline(lines[i].strip()))
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
        import os
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
            else:
                h.append(f'<h1 class="title">{esc(title)}</h1>')
                for mid in cover_lines[1:-1]:
                    h.append(f'<p class="author">{esc(mid)}</p>')
                if len(cover_lines) > 1:
                    h.append(f'<p class="date">{esc(cover_lines[-1])}</p>')
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
            ext = "jpg" if self.cover_image_fmt == "jpeg" else "png"
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
        # immagine di copertina (se presente) come frame a piena larghezza
        cover_img_entry = None
        if self.cover_image:
            ext = "jpg" if self.cover_image_fmt == "jpeg" else "png"
            img_path = f"Pictures/cover.{ext}"
            cover_img_entry = (img_path, self._cover_image_mime(), self.cover_image)
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

        img_manifest = ""
        if cover_img_entry:
            ipath, imime, _ = cover_img_entry
            img_manifest = (f'<manifest:file-entry manifest:full-path="{ipath}" '
                            f'manifest:media-type="{imime}"/>\n')
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
            if cover_img_entry:
                ipath, _, idata = cover_img_entry
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

        # immagine di copertina (se presente): preparo i dati e un blocco
        # <w:drawing> da inserire come primo paragrafo
        cover_img_data = None
        cover_img_ext = None
        cover_drawing = None
        if self.cover_image:
            cover_img_data = self.cover_image
            cover_img_ext = "jpg" if self.cover_image_fmt == "jpeg" else "png"
            # dimensioni in EMU (1 cm = 360000 EMU); larghezza ~16cm
            cm = 360000
            w_emu = int(16 * cm)
            h_emu = int(22 * cm)
            try:
                from PIL import Image as _PILImage
                import io as _io
                _im = _PILImage.open(_io.BytesIO(self.cover_image))
                iw, ih = _im.size
                h_emu = int(min(24, 16 * ih / iw) * cm)
            except Exception:
                pass
            cover_drawing = (
                '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
                f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
                f'<wp:extent cx="{w_emu}" cy="{h_emu}"/>'
                '<wp:docPr id="1" name="cover"/>'
                '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                '<pic:nvPicPr><pic:cNvPr id="1" name="cover"/><pic:cNvPicPr/></pic:nvPicPr>'
                '<pic:blipFill><a:blip r:embed="rIdImg" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
                '<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
                f'<a:ext cx="{w_emu}" cy="{h_emu}"/></a:xfrm>'
                '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')

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

        img_ct = ""
        if cover_img_data:
            if cover_img_ext == "jpg":
                img_ct = ('<Default Extension="jpg" ContentType="image/jpeg"/>'
                          '<Default Extension="jpeg" ContentType="image/jpeg"/>')
            else:
                img_ct = '<Default Extension="png" ContentType="image/png"/>'
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

        # relazioni del documento: collega l'immagine (rIdImg) se presente
        doc_rels = None
        if cover_img_data:
            img_target = f"media/cover.{cover_img_ext}"
            doc_rels = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships '
                'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rIdImg" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                f'relationships/image" Target="{img_target}"/>'
                '</Relationships>')

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types)
            z.writestr("_rels/.rels", rels)
            z.writestr("word/document.xml", document)
            if cover_img_data:
                z.writestr("word/_rels/document.xml.rels", doc_rels)
                z.writestr(f"word/media/cover.{cover_img_ext}", cover_img_data)


    def export_pdf(self, path, font_size=12, embed_fonts=None,
                   embed_font_name="CourierPrime"):
        """Salva in PDF con markdown di base. Se embed_fonts e' fornito (dict
        stile->metrics), il testo usa il font del documento incorporato e rende
        grassetto/corsivo. La copertina e' una pagina senza numero; la
        numerazione parte da 1 dalla pagina successiva."""
        cover_paragraphs = None
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
                cover_paragraphs = self._cover_lines() or paras
            else:
                n += 1
                chapters_paragraphs.append(paras)
                chapter_titles.append(ch.title_with_fallback(
                    fallback_template="Capitolo {n}".replace("{n}", str(n))))
        leading = int(round(font_size * 1.45))
        cover_img = None
        if self.cover_image:
            cover_img = _prepare_cover_jpeg(self.cover_image, self.cover_image_fmt)
        # frontespizio/colophon come righe con stile (testo, ruolo)
        front = self._front_lines() or None
        colo = self._colophon_lines() or None
        write_pdf(path, chapters_paragraphs, title=self.title,
                  cover_paragraphs=cover_paragraphs,
                  chapter_titles=chapter_titles,
                  toc_label=self.t_index_label(),
                  font_size=font_size, leading=leading,
                  page_break_per_chapter=True,
                  embed_fonts=embed_fonts, embed_font_name=embed_font_name,
                  cover_image=cover_img,
                  frontispiece_paragraphs=front,
                  colophon_paragraphs=colo)

    def _make_cover_png(self, cover_lines, width=600, height=900):
        """Genera i byte di un'immagine PNG di copertina (raster), necessaria
        perché i generatori di miniature come gnome-epub-thumbnailer mostrino
        l'anteprima: questi strumenti vogliono un'immagine raster (PNG/JPEG),
        non un SVG. Se Pillow è disponibile, disegna anche titolo e autore;
        altrimenti produce con la sola libreria standard un PNG con sfondo,
        cornice e filetti (senza testo), comunque valido come anteprima."""
        title = cover_lines[0] if cover_lines else self.title
        middle = cover_lines[1:-1] if len(cover_lines) > 2 else (
            [cover_lines[1]] if len(cover_lines) == 2 else [])
        date = cover_lines[-1] if len(cover_lines) > 1 else ""

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
                names = (["DejaVuSerif-Bold.ttf", "DejaVuSerif.ttf"] if not bold
                         else ["DejaVuSerif-Bold.ttf"])
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
        row_bytes = bytearray()
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

    def export_epub(self, path, author=None):
        """Esporta il progetto in un file EPUB 2 valido usando solo la
        libreria standard. La copertina diventa la prima sezione; ogni
        capitolo una sezione XHTML separata. Il markdown di base
        (intestazioni, grassetto, corsivo, liste, citazioni) viene reso in
        HTML semplice. Titolo e autore provengono dal progetto/copertina."""
        import zipfile, html, re, uuid, datetime

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

        def md_to_html(text):
            """Converte il markdown di base di un capitolo in XHTML."""
            def inline(s):
                s = esc(s)
                s = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", s)
                s = re.sub(r"(\*\*\*|___)(.+?)\1", r"<strong><em>\2</em></strong>", s)
                s = re.sub(r"(\*\*|__)(.+?)\1", r"<strong>\2</strong>", s)
                s = re.sub(r"(\*|_)(.+?)\1", r"<em>\2</em>", s)
                s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
                return s

            out = []
            lines = text.split("\n")
            i = 0
            while i < len(lines):
                raw = lines[i]
                st = raw.strip()
                if not st:
                    i += 1
                    continue
                m = re.match(r"^(#{1,6})\s+(.*)$", st)
                if m:
                    lvl = len(m.group(1))
                    out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
                    i += 1
                    continue
                if st[:2] in ("- ", "* ", "+ "):
                    items = []
                    while i < len(lines) and lines[i].strip()[:2] in ("- ", "* ", "+ "):
                        items.append(f"<li>{inline(lines[i].strip()[2:])}</li>")
                        i += 1
                    out.append("<ul>" + "".join(items) + "</ul>")
                    continue
                if re.match(r"^\d+\.\s+", st):
                    items = []
                    while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                        body = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                        items.append(f"<li>{inline(body)}</li>")
                        i += 1
                    out.append("<ol>" + "".join(items) + "</ol>")
                    continue
                if st.startswith(">"):
                    out.append(f"<blockquote>{inline(st.lstrip('>').strip())}</blockquote>")
                    i += 1
                    continue
                # paragrafo normale: accorpa righe contigue
                buf = []
                while i < len(lines) and lines[i].strip() and not re.match(
                        r"^(#{1,6}\s|[-*+]\s|\d+\.\s|>)", lines[i].strip()):
                    buf.append(inline(lines[i].strip()))
                    i += 1
                out.append("<p>" + "<br/>".join(buf) + "</p>")
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
            cover_img_name = "cover.jpg" if self.cover_image_fmt == "jpeg" else "cover.png"
            cover_img_mime = self._cover_image_mime()
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
        import shutil
        # nel PATH
        exe = shutil.which("ebook-convert")
        if exe:
            return exe
        # percorsi tipici (Linux, macOS, Windows)
        import os
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
        import os, tempfile, subprocess

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

    def update_cover_date(self):
        """Sostituisce l'ultima riga non vuota della copertina con la data odierna."""
        import datetime
        cover = self.cover()
        if cover is None:
            return None
        oggi = datetime.date.today().strftime("%d/%m/%Y")
        lines = cover.text.split("\n")
        # trova l'indice dell'ultima riga non vuota
        last = -1
        for i, ln in enumerate(lines):
            if ln.strip():
                last = i
        if last >= 0:
            lines[last] = oggi
        else:
            lines = [oggi]
        cover.text = "\n".join(lines)
        return oggi


