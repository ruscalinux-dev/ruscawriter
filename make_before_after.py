#!/usr/bin/env python3
# make_before_after.py — RuscaWriter
# Copyright (C) 2026  Nunzio Curcuruto — GNU GPL v3 or later
#
# EN: Composes the "before and after" presentation image from two pictures you
#     took yourself: the program at work, and the book that comes out of it.
#
#         python3 make_before_after.py interface.png result.png
#
#     Options worth knowing:
#         --out FILE     where to write (default ruscawriter_before_after.png)
#         --labels "Write the book" "Print the book"
#         --title "..."  a headline above the two panels; omit for none
#         --theme giada  which theme's colours to dress it in
#         --width 2800   width of the finished image
#
#     The two pictures may be any size and any proportion: each is scaled to
#     the same height and the canvas follows. Nothing is cropped, because a
#     screenshot cropped by a script is a screenshot ruined.
#
# IT: Compone l'immagine di presentazione "prima e dopo" a partire da due
#     immagini tue: il programma al lavoro e il libro che ne esce.
#
#         python3 make_before_after.py interfaccia.png risultato.png
#
#     Opzioni utili:
#         --out FILE     dove scriverlo (predefinito ruscawriter_before_after.png)
#         --labels "Scrivi il libro" "Stampa il libro"
#         --title "..."  un titolo sopra i due riquadri; senza, non compare
#         --theme giada  i colori di quale tema usare
#         --width 2800   larghezza dell'immagine finita
#
#     Le due immagini possono avere qualunque misura e proporzione: ciascuna
#     viene portata alla stessa altezza e la tela si adatta. Non si ritaglia
#     nulla, perche' una schermata ritagliata da uno script e' una schermata
#     rovinata.

import argparse
import os
import sys

# Il programma non serve: bastano i suoi colori e i suoi font, se ci sono.
QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(QUI, "src"))

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    sys.exit("Serve Pillow:  pip install pillow")


# --- colori e font: dal programma se e' accanto, altrimenti dei ripieghi ----
def tavolozza(nome_tema, scuro=True):
    """Colori con cui vestire l'immagine, presi dal tema del programma.

    Il fondo scuro fa risaltare le due tavole, che sono chiare: e' il motivo
    per cui l'immagine di presentazione storica era su prugna profondo. Se il
    programma non e' raggiungibile si usano valori equivalenti, così lo script
    resta utilizzabile da solo."""
    try:
        from ruscawriter.model import theme_palette
        p = theme_palette(nome_tema, dark=scuro)
        return {"fondo": _scurisci(_hx(p["accent_dark"]), 0.55),
                "titolo": (255, 255, 255),
                "accento": _hx(p["glow"] if scuro else p["accent"]),
                "piede": _hx(p["parchment"] if scuro else p["editor_fg"])}
    except Exception:
        return {"fondo": (63, 23, 56), "titolo": (255, 255, 255),
                "accento": (224, 168, 216), "piede": (237, 234, 229)}


def _scurisci(rgb, fattore):
    return tuple(max(0, int(c * fattore)) for c in rgb)


def _hx(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def carattere(corpo, grassetto=False):
    """Un sans per i titoli: in miniatura si legge meglio di un serif, e queste
    immagini saranno viste rimpicciolite."""
    suffisso = "-Bold" if grassetto else ""
    candidati = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffisso}.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans"
        + ("-Bold" if grassetto else "-Regular") + ".ttf",
        os.path.join(QUI, "assets",
                     "EBGaramond-Bold.ttf" if grassetto
                     else "EBGaramond-Regular.ttf"),
    ]
    for percorso in candidati:
        try:
            return ImageFont.truetype(percorso, corpo)
        except Exception:
            continue
    return ImageFont.load_default()


def ombra(tela, riquadro, raggio=22, opacita=80):
    """Un'ombra morbida, perche' i due riquadri sembrino appoggiati."""
    x0, y0, x1, y1 = riquadro
    velo = Image.new("RGBA", tela.size, (0, 0, 0, 0))
    ImageDraw.Draw(velo).rectangle((x0 + 8, y0 + 12, x1 + 8, y1 + 12),
                                   fill=(0, 0, 0, opacita))
    tela.alpha_composite(velo.filter(ImageFilter.GaussianBlur(raggio)))


def freccia(d, cx, cy, raggio, colore, fondo):
    """Un disco con dentro un triangolo: dice che il secondo riquadro viene
    dal primo. Un disco pieno regge la miniatura meglio di una linea sottile,
    che a 600 px sparisce."""
    d.ellipse((cx - raggio, cy - raggio, cx + raggio, cy + raggio), fill=colore)
    lato = raggio * 0.62
    d.polygon([(cx - lato * 0.45, cy - lato),
               (cx - lato * 0.45, cy + lato),
               (cx + lato * 0.85, cy)], fill=fondo)


def componi(prima, dopo, destinazione, etichette, titolo, piede,
            nome_tema, larghezza):
    """Compone le due immagini su un fondo scuro, con le didascalie sopra
    ciascuna, il disco fra le due e una riga di chiusura in basso."""
    col = tavolozza(nome_tema)
    a = Image.open(prima).convert("RGBA")
    b = Image.open(dopo).convert("RGBA")

    margine = int(larghezza * 0.030)
    varco = int(larghezza * 0.055)          # spazio per il disco
    alt_titolo = int(larghezza * 0.052) if titolo else 0
    alt_didascalie = int(larghezza * 0.050) if etichette else 0
    alt_piede = int(larghezza * 0.048) if piede else 0

    # Le due immagini vanno alla STESSA altezza: e' quello che le fa leggere
    # come due momenti della stessa cosa. La larghezza segue le proporzioni.
    utile = larghezza - 2 * margine - varco
    quota_a = a.width / a.height
    quota_b = b.width / b.height
    altezza = int(utile / (quota_a + quota_b))
    a = a.resize((int(altezza * quota_a), altezza), Image.LANCZOS)
    b = b.resize((int(altezza * quota_b), altezza), Image.LANCZOS)

    alt_tela = (margine + alt_titolo + alt_didascalie + altezza
                + alt_piede + margine)
    tela = Image.new("RGBA", (larghezza, alt_tela), col["fondo"] + (255,))
    d = ImageDraw.Draw(tela)

    def centra(testo, x, w, y, corpo, colore, grassetto=False):
        """Scrive centrato, rimpicciolendo finche' il testo ci sta.

        Serve perche' i due riquadri hanno larghezze diverse: una pagina
        verticale e' molto piu' stretta di una schermata, e una didascalia
        pensata per la seconda sbordava dalla prima."""
        font = carattere(corpo, grassetto)
        while corpo > 8 and d.textlength(testo, font=font) > w - 12:
            corpo = int(corpo * 0.94)
            font = carattere(corpo, grassetto)
        d.text((x + (w - d.textlength(testo, font=font)) / 2, y),
               testo, font=font, fill=colore)

    y = margine
    if titolo:
        centra(titolo, 0, larghezza, y, int(larghezza * 0.030),
               col["titolo"], grassetto=True)
        y += alt_titolo

    x_a = margine
    x_b = margine + a.width + varco
    if etichette:
        corpo = int(larghezza * 0.024)
        centra(etichette[0], x_a, a.width, y, corpo, col["titolo"],
               grassetto=True)
        centra(etichette[1], x_b, b.width, y, corpo, col["accento"],
               grassetto=True)
        y += alt_didascalie

    for immagine, x in ((a, x_a), (b, x_b)):
        ombra(tela, (x, y, x + immagine.width, y + immagine.height))
        tela.alpha_composite(immagine, (x, y))
        d.rectangle((x - 2, y - 2, x + immagine.width + 1,
                     y + immagine.height + 1),
                    outline=(0, 0, 0, 210), width=3)

    freccia(d, margine + a.width + varco // 2, y + altezza // 2,
            int(varco * 0.30), col["accento"], col["fondo"])

    if piede:
        centra(piede, 0, larghezza, y + altezza + int(alt_piede * 0.28),
               int(larghezza * 0.021), col["piede"])

    tela.convert("RGB").save(destinazione, "PNG")
    return destinazione


def main():
    ap = argparse.ArgumentParser(
        description="Compone l'immagine 'prima e dopo' di RuscaWriter.")
    ap.add_argument("prima", help="schermata del programma al lavoro")
    ap.add_argument("dopo", help="immagine del risultato (pagine del PDF)")
    ap.add_argument("--out", default="ruscawriter_before_after.png")
    ap.add_argument("--labels", nargs=2, metavar=("PRIMA", "DOPO"),
                    default=["You write in Markdown",
                             "You get a finished book"],
                    help="le due didascalie; --labels '' '' per nessuna")
    ap.add_argument("--title", default="",
                    help="titolo sopra i riquadri (senza, non compare)")
    ap.add_argument("--footer",
                    default="RuscaWriter — three-column editor · "
                            "PDF · EPUB · DOCX · ODT · HTML",
                    help="riga di chiusura in basso ('' per nessuna)")
    ap.add_argument("--theme", default="ametista",
                    help="tema da cui prendere i colori")
    ap.add_argument("--width", type=int, default=2800,
                    help="larghezza dell'immagine finita")
    v = ap.parse_args()

    for percorso in (v.prima, v.dopo):
        if not os.path.exists(percorso):
            sys.exit(f"non trovo: {percorso}")

    etichette = [e for e in v.labels if e.strip()]
    etichette = v.labels if len(etichette) == 2 else None

    fatto = componi(v.prima, v.dopo, v.out, etichette, v.title,
                    v.footer.strip(), v.theme, v.width)
    misure = Image.open(fatto).size
    print(f"scritto: {fatto}  {misure[0]}×{misure[1]}  "
          f"({os.path.getsize(fatto) // 1024} KB)")


if __name__ == "__main__":
    main()
