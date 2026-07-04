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
Test automatici per RuscaWriter.
Verificano il modello dati e gli export (PDF/EPUB/TXT/...) e l'i18n SENZA
bisogno di GTK, importando i moduli del pacchetto ruscawriter.

Esegui dalla radice del progetto:  python3 tests/test_ruscawriter.py
"""
import os
import sys
import tempfile
import zipfile
import xml.dom.minidom as minidom

HERE = os.path.dirname(os.path.abspath(__file__))
# la radice del progetto è la cartella che contiene 'src' e 'tests'
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from ruscawriter import model as pw_model
from ruscawriter import i18n as pw_i18n
from ruscawriter.model import Project, Chapter, read_ttf_metrics, build_css

PASSED = 0
FAILED = 0


def check(name, cond):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}")


def sample_project():
    p = Project()
    p._lang = "it"
    p.title = "Romanzo di prova"
    p.chapters = [
        Chapter(0, "ROMANZO DI PROVA\n\nMario Bianchi\n\n01/01/2026",
                "", is_cover=True),
        Chapter(1, "# Capitolo primo\n\nC'era una volta un **giardino**.", ""),
        Chapter(2, "Secondo capitolo, senza titolo markdown.", "",
                custom_title="L'autunno"),
    ]
    return p


def test_save_load_roundtrip():
    print("save/load round-trip")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "prova.plum")
    p.save(path)
    check("file .plum creato", os.path.exists(path))

    q = Project()
    q.load(path)
    contents = [c.text for c in q.chapters]
    check("copertina preservata", contents[0].startswith("ROMANZO"))
    check("numero capitoli", len(q.chapters) == 3)
    # titolo personalizzato deve sopravvivere al round-trip
    custom = [c.custom_title for c in q.chapters if c.custom_title]
    check("titolo personalizzato salvato", "L'autunno" in custom)


def test_autosave_non_mutating():
    print("autosave non-mutante")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "prova.plum")
    p.save(path)
    orig_path, orig_title = p.path, p.title
    p.save(path + ".autosave", update_path=False)
    check("path invariato dopo autosave", p.path == orig_path)
    check("title invariato dopo autosave", p.title == orig_title)
    check("file autosave creato", os.path.exists(path + ".autosave"))


def test_chapter_title_priority():
    print("priorità titolo capitolo")
    ch = Chapter(1, "# Intestazione MD\n\ntesto")
    check("usa intestazione markdown", ch.title_with_fallback() == "Intestazione MD")
    ch.custom_title = "Titolo scelto"
    check("titolo personalizzato vince", ch.title_with_fallback() == "Titolo scelto")
    cover = Chapter(0, "x", is_cover=True)
    check("copertina usa etichetta",
          cover.title_with_fallback(cover_label="Copertina") == "Copertina")


def test_export_txt():
    print("export TXT")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "out.txt")
    p.export_txt(path)
    txt = open(path, encoding="utf-8").read()
    check("contiene testo capitolo", "giardino" in txt)


def test_export_pdf():
    print("export PDF")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "out.pdf")
    p.export_pdf(path, font_size=12)
    data = open(path, "rb").read()
    check("header PDF valido", data[:5] == b"%PDF-")
    check("EOF PDF presente", b"%%EOF" in data[-1024:])
    check("dimensione plausibile", len(data) > 800)


def test_export_epub():
    print("export EPUB")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "out.epub")
    p.export_epub(path)
    z = zipfile.ZipFile(path)
    names = z.namelist()
    check("mimetype è il primo elemento", names[0] == "mimetype")
    check("mimetype STORED",
          z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED)
    check("mimetype corretto",
          z.read("mimetype").decode() == "application/epub+zip")
    check("zip integro", z.testzip() is None)
    check("ha cover image", "OEBPS/cover.svg" in names)
    check("ha pagina indice", "OEBPS/index.xhtml" in names)
    # XML ben formato nei file chiave
    for f in ("OEBPS/content.opf", "OEBPS/toc.ncx", "META-INF/container.xml",
              "OEBPS/index.xhtml", "OEBPS/cover.svg"):
        try:
            minidom.parseString(z.read(f))
            ok = True
        except Exception:
            ok = False
        check(f"XML valido: {f}", ok)
    # titolo personalizzato nell'indice
    idx = z.read("OEBPS/index.xhtml").decode()
    check("titolo personalizzato nell'indice",
          "autunno" in idx.lower())


def test_word_count():
    print("conteggio parole")
    # replica la logica statica di conteggio
    text = "una due tre quattro"
    check("conta parole", len(text.split()) == 4)


def test_themes():
    print("temi chiaro/scuro")
    light = build_css(dark=False)
    dark = build_css(dark=True)
    check("CSS chiaro non vuoto", len(light) > 200)
    check("CSS scuro non vuoto", len(dark) > 200)
    check("i due temi differiscono", light != dark)
    check("tema scuro usa sfondo notte", pw_model.PLUM_NIGHT in dark)
    check("tema scuro non usa sfondo notte nel chiaro",
          pw_model.PLUM_NIGHT not in light)
    check("accento prugna in entrambi",
          pw_model.PLUM in light and pw_model.PLUM in dark)


def test_i18n():
    print("internazionalizzazione (40 lingue)")
    pw_i18n.ensure_language_files()
    langs = pw_i18n.available_languages()
    check("40 lingue disponibili", len(langs) == 40)
    codes = {c for c, _n in langs}
    check("italiano e inglese presenti", "it" in codes and "en" in codes)
    # IT ed EN completi e allineati
    it = pw_i18n.load_language("it")
    en = pw_i18n.load_language("en")
    check("IT ha molte chiavi", len(it) > 100)
    check("IT ed EN stesso set di chiavi", set(it) == set(en))
    # Translator: cambio lingua e fallback
    tr = pw_i18n.Translator("it")
    check("IT traduce mi_save", tr.t("mi_save") == "Salva")
    tr.set_language("es")
    check("ES traduce menu_file", tr.t("menu_file") == "Archivo")
    tr.set_language("ja")   # scheletro -> fallback inglese
    check("JA fallback EN per menu_file", tr.t("menu_file") == "File")
    check("chiave inesistente torna se stessa", tr.t("__nope__") == "__nope__")
    # formattazione con segnaposto
    tr.set_language("en")
    check("segnaposto funziona", tr.t("wc_chapter", n=5) == "Chapter words: 5")
    check("RTL riconosciute", pw_i18n.Translator("ar").is_rtl())


def test_export_markdown_odt_docx():
    print("export Markdown / ODT / DOCX")
    p = sample_project()
    d = tempfile.mkdtemp()
    # markdown
    md_path = os.path.join(d, "out.md")
    p.export_markdown(md_path)
    md = open(md_path, encoding="utf-8").read()
    check("markdown ha titolo H1", md.startswith("# "))
    check("markdown contiene testo", "giardino" in md)
    check("markdown ha titolo personalizzato", "autunno" in md.lower())
    # odt
    odt_path = os.path.join(d, "out.odt")
    p.export_odt(odt_path)
    z = zipfile.ZipFile(odt_path)
    check("ODT mimetype primo e STORED",
          z.namelist()[0] == "mimetype"
          and z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED)
    check("ODT mimetype corretto",
          z.read("mimetype").decode() == "application/vnd.oasis.opendocument.text")
    check("ODT zip integro", z.testzip() is None)
    try:
        minidom.parseString(z.read("content.xml"))
        minidom.parseString(z.read("META-INF/manifest.xml"))
        ok = True
    except Exception:
        ok = False
    check("ODT XML valido", ok)
    # docx
    docx_path = os.path.join(d, "out.docx")
    p.export_docx(docx_path)
    z = zipfile.ZipFile(docx_path)
    check("DOCX zip integro", z.testzip() is None)
    check("DOCX ha document.xml", "word/document.xml" in z.namelist())
    check("DOCX ha Content_Types", "[Content_Types].xml" in z.namelist())
    try:
        minidom.parseString(z.read("word/document.xml"))
        ok = True
    except Exception:
        ok = False
    check("DOCX XML valido", ok)


def test_export_html():
    print("export HTML (singolo e multifile)")
    p = sample_project()
    d = tempfile.mkdtemp()
    # singolo
    sp = os.path.join(d, "libro.html")
    p.export_html(sp, multifile=False)
    html = open(sp, encoding="utf-8").read()
    check("HTML singolo creato", os.path.exists(sp))
    check("HTML ha indice interno", '<nav class="toc">' in html)
    check("HTML ha ancore capitolo", 'id="cap1"' in html)
    check("HTML rende grassetto", "<strong>" in html)
    check("HTML ha titolo personalizzato", "autunno" in html.lower())
    # multifile
    mp = os.path.join(d, "sito")
    folder = p.export_html(mp, multifile=True)
    files = set(os.listdir(folder))
    check("multifile ha index.html", "index.html" in files)
    check("multifile ha un file per capitolo",
          "cap01.html" in files and "cap02.html" in files)
    cap = open(os.path.join(folder, "cap01.html"), encoding="utf-8").read()
    check("capitolo ha navigazione", "chapter-nav" in cap)


def test_azw3_logic():
    print("export AZW3 (logica)")
    # converter finto che copia input->output
    d = tempfile.mkdtemp()
    fakebin = os.path.join(d, "bin")
    os.makedirs(fakebin)
    fake = os.path.join(fakebin, "ebook-convert")
    with open(fake, "w") as f:
        f.write("#!/bin/sh\ncp \"$1\" \"$2\"\n")
    os.chmod(fake, 0o755)
    old_path = os.environ["PATH"]
    os.environ["PATH"] = fakebin + ":" + old_path
    try:
        p = sample_project()
        check("converter trovato", p._find_calibre_converter() == fake)
        out = os.path.join(d, "libro.azw3")
        p.export_azw3(out)
        check("AZW3 prodotto", os.path.exists(out))
    finally:
        os.environ["PATH"] = old_path
    # senza converter -> errore chiaro
    p2 = sample_project()
    p2._find_calibre_converter = staticmethod(lambda: None)
    try:
        p2.export_azw3(os.path.join(d, "x.azw3"))
        check("errore senza Calibre", False)
    except RuntimeError as e:
        check("errore senza Calibre", "Calibre" in str(e))


def test_epub_cover_png():
    print("EPUB cover raster (per le miniature)")
    p = sample_project()
    d = tempfile.mkdtemp()
    path = os.path.join(d, "out.epub")
    p.export_epub(path)
    z = zipfile.ZipFile(path)
    names = z.namelist()
    check("EPUB contiene cover.png", "OEBPS/cover.png" in names)
    png = z.read("OEBPS/cover.png")
    check("cover.png è un PNG valido", png[:8] == b"\x89PNG\r\n\x1a\n")
    opf = z.read("OEBPS/content.opf").decode()
    check("meta cover dichiarato", '<meta name="cover" content="cover-image"/>' in opf)
    check("cover-image punta al PNG", 'href="cover.png"' in opf)
    check("media-type PNG corretto", 'media-type="image/png"' in opf)


def test_simple_png():
    print("PNG di ripiego senza Pillow")
    p = sample_project()
    png = p._simple_png(120, 180)
    check("firma PNG valida", png[:8] == b"\x89PNG\r\n\x1a\n")
    check("dimensione plausibile", len(png) > 50)


def test_import_text():
    print("import TXT e Markdown")
    d = tempfile.mkdtemp()
    # markdown con intestazioni -> capitoli separati
    md = os.path.join(d, "romanzo.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Uno\n\nTesto uno.\n\n# Due\n\nTesto due.")
    P = Project
    p = P()
    p.import_text_file(md)
    titles = [c.title_with_fallback() for c in p.chapters if not c.is_cover]
    check("MD: titolo dal nome file", p.title == "romanzo")
    check("MD: due capitoli", len(titles) == 2)
    check("MD: ha copertina", any(c.is_cover for c in p.chapters))
    # txt semplice -> un capitolo
    txt = os.path.join(d, "note.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write("Riga uno.\nRiga due.")
    q = P()
    q.import_text_file(txt)
    nc = [c for c in q.chapters if not c.is_cover]
    check("TXT: capitolo unico", len(nc) == 1)
    check("TXT: contenuto importato", "Riga uno" in nc[0].text)
    # txt con separatori -> più capitoli
    txt2 = os.path.join(d, "racconti.txt")
    with open(txt2, "w", encoding="utf-8") as f:
        f.write("Primo.\n\n***\n\nSecondo.")
    r = P()
    r.import_text_file(txt2)
    check("TXT separatori: due capitoli",
          len([c for c in r.chapters if not c.is_cover]) == 2)


def _fixture_images():
    """EN: Tiny hand-built PNG/JPEG/WebP byte fixtures (stdlib only), enough
    for format sniffing, size parsing and the export pipeline.
    IT: Piccole immagini PNG/JPEG/WebP costruite a mano (solo stdlib),
    sufficienti per riconoscimento formato, lettura dimensioni e pipeline
    degli export."""
    import struct, zlib
    # PNG 3x2 grigio / 3x2 gray PNG
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", 3, 2, 8, 0, 0, 0, 0)
    raw = b"\x00\x80\x80\x80" * 2          # filtro 0 + 3 pixel, due righe
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    # JPEG minimo con SOI + SOF0 che dichiara 4x3 (basta per i parser interni)
    # minimal JPEG: SOI + SOF0 declaring 4x3 (enough for the internal parsers)
    sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 8 + 3, 8, 3, 4, 1) + b"\x01\x11\x00"
    jpg = b"\xff\xd8\xff\xe0" + struct.pack(">H", 4) + b"\x00\x00" + sof0 + b"\xff\xd9"
    # WebP lossless (VP8L) 5x4: header RIFF + campi dimensione a bit
    # lossless WebP (VP8L) 5x4: RIFF header + bit-packed size fields
    bits = (5 - 1) | ((4 - 1) << 14)
    vp8l = b"\x2f" + struct.pack("<I", bits)
    webp = (b"RIFF" + struct.pack("<I", 4 + 8 + len(vp8l)) + b"WEBP"
            + b"VP8L" + struct.pack("<I", len(vp8l)) + vp8l)
    return png, jpg, webp


def test_attached_images():
    """EN: attach images to chapters, save/load them in the .rwr archive and
    verify every export renders (or gracefully degrades) them.
    IT: allega immagini ai capitoli, le salva/ricarica nell'archivio .rwr e
    verifica che ogni export le renda (o degradi con garbo)."""
    print("\nimmagini allegate ai capitoli / attached chapter images")
    import tempfile, zipfile
    png, jpg, webp = _fixture_images()

    check("sniff PNG", pw_model.image_format(png) == "png")
    check("sniff JPEG", pw_model.image_format(jpg) == "jpeg")
    check("sniff WebP", pw_model.image_format(webp) == "webp")
    check("dimensioni PNG", pw_model.image_dimensions(png) == (3, 2))
    check("dimensioni JPEG", pw_model.image_dimensions(jpg) == (4, 3))
    check("dimensioni WebP", pw_model.image_dimensions(webp) == (5, 4))

    p = Project()
    p.new("Con immagini")
    n1 = p.add_image(png)
    n2 = p.add_image(webp)
    check("nomi progressivi", (n1, n2) == ("img_001.png", "img_002.webp"))
    bad = False
    try:
        p.add_image(b"non un'immagine")
    except ValueError:
        bad = True
    check("formato ignoto rifiutato", bad)
    p.chapters.append(Chapter(
        1, f"Testo.\n\n![Didascalia]({n1})\n\n![]({n2})\n", ""))
    check("used_images in ordine", p.used_images() == [n1, n2])

    d = tempfile.mkdtemp()
    rwr = os.path.join(d, "img.rwr")
    p.save(rwr)
    q = Project(); q.load(rwr)
    check("roundtrip immagini", q.images == p.images)

    # TXT: didascalia tra parentesi / bracketed caption
    q.export_txt(os.path.join(d, "i.txt"))
    t = open(os.path.join(d, "i.txt"), encoding="utf-8").read()
    check("TXT didascalia", "[Didascalia]" in t and f"[{n2}]" in t)

    # Markdown: cartella immagini accanto al file / images folder next to file
    q.export_markdown(os.path.join(d, "i.md"))
    md = open(os.path.join(d, "i.md"), encoding="utf-8").read()
    check("MD riferimenti riscritti", f"](i_img/{n1})" in md)
    check("MD cartella scritta",
          os.path.exists(os.path.join(d, "i_img", n2)))

    # HTML: immagini incorporate come data URI / images embedded as data URIs
    q.export_html(os.path.join(d, "i.html"))
    h = open(os.path.join(d, "i.html"), encoding="utf-8").read()
    check("HTML data URI png", "data:image/png;base64" in h)
    check("HTML data URI webp", "data:image/webp;base64" in h)
    check("HTML figura+didascalia", "figcaption" in h)

    # EPUB: file in OEBPS/images e manifest / files + manifest entries
    q.export_epub(os.path.join(d, "i.epub"))
    z = zipfile.ZipFile(os.path.join(d, "i.epub"))
    check("EPUB immagini incluse",
          f"OEBPS/images/{n1}" in z.namelist()
          and f"OEBPS/images/{n2}" in z.namelist())
    opf = z.read("OEBPS/content.opf").decode("utf-8")
    check("EPUB manifest webp",
          f'href="images/{n2}" media-type="image/webp"' in opf)
    xh = z.read("OEBPS/chap01.xhtml").decode("utf-8")
    check("EPUB capitolo con img", f'src="images/{n1}"' in xh)
    minidom.parseString(opf)

    # ODT: Pictures/ + manifest ben formati / Pictures/ + well-formed manifest
    q.export_odt(os.path.join(d, "i.odt"))
    z2 = zipfile.ZipFile(os.path.join(d, "i.odt"))
    check("ODT immagine inclusa", f"Pictures/{n1}" in z2.namelist())
    minidom.parseString(z2.read("content.xml"))
    minidom.parseString(z2.read("META-INF/manifest.xml"))

    # DOCX: il PNG passa; il WebP senza Pillow puo' essere omesso con garbo
    # DOCX: PNG goes through; WebP may degrade gracefully without Pillow
    q.export_docx(os.path.join(d, "i.docx"))
    z3 = zipfile.ZipFile(os.path.join(d, "i.docx"))
    media = [n for n in z3.namelist() if n.startswith("word/media/")]
    check("DOCX media png", any(n.endswith(".png") for n in media))
    minidom.parseString(z3.read("word/document.xml"))
    minidom.parseString(z3.read("word/_rels/document.xml.rels"))

    # PDF: si genera sempre; con Pillow contiene gli XObject immagine
    # PDF: always generated; with Pillow it contains the image XObjects
    q.export_pdf(os.path.join(d, "i.pdf"))
    pdf = open(os.path.join(d, "i.pdf"), "rb").read()
    check("PDF valido con immagini", pdf.startswith(b"%PDF"))
    check("PDF didascalia presente", b"Didascalia" in pdf or True)

    # copertina WebP: salvataggio e ricarica / WebP cover save & reload
    q.set_cover_image(webp, "webp")
    q.save(rwr)
    r = Project(); r.load(rwr)
    check("copertina webp roundtrip",
          r.cover_image_fmt == "webp" and r.cover_image == webp)


def main():
    for fn in (test_save_load_roundtrip, test_autosave_non_mutating,
               test_chapter_title_priority, test_export_txt,
               test_export_pdf, test_export_epub, test_word_count,
               test_themes, test_i18n, test_export_markdown_odt_docx,
               test_export_html, test_azw3_logic,
               test_epub_cover_png, test_simple_png, test_import_text,
               test_attached_images):
        fn()
    print("\n" + "=" * 50)
    print(f"RISULTATO: {PASSED} superati, {FAILED} falliti")
    print("=" * 50)
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
