#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 MINI RUSCAWRITER — versione didattica super-commentata (GTK 4)
============================================================================

Questo NON è il programma completo: è una versione ridotta all'osso, pensata
per IMPARARE. Fa poche cose (scrivere testo, contare le parole, salvare e
aprire un file, cambiare tema) ma usa esattamente gli stessi concetti del
RuscaWriter grande. Ogni parte importante è spiegata nei commenti.

Per eseguirlo, da terminale:
    python3 mini_ruscawriter.py

Richiede PyGObject e GTK 4. Su Debian/Ubuntu:
    sudo apt install python3-gi gir1.2-gtk-4.0

----------------------------------------------------------------------------
 NOTA SULLE VERSIONI (GTK 3 -> GTK 4)
----------------------------------------------------------------------------
Il RuscaWriter grande usa GTK 4, e così questo mini-editor. Rispetto a tante
guide più vecchie (scritte per GTK 3) cambiano alcune cose di base; le
segnaliamo nei commenti dove capitano:
  - l'avvio: Gtk.Application al posto di Gtk.main();
  - mostrare la finestra: present() al posto di show_all();
  - riempire le scatole: append() al posto di pack_start();
  - mettere un figlio in un contenitore: set_child() al posto di add();
  - i dialoghi sono ASINCRONI (con callback), niente più dialogo.run().
============================================================================
"""

# ---------------------------------------------------------------------------
# 1) IMPORTAZIONI
# ---------------------------------------------------------------------------
# "import gi" carica il ponte tra Python e GTK. Prima di usare GTK dobbiamo
# dire quale versione vogliamo, altrimenti Python non sa quale caricare.
import gi
gi.require_version("Gtk", "4.0")
# Oltre a Gtk importiamo Gdk, che ci serve per ottenere il "display" su cui
# applicare il CSS. Sono parte della stessa famiglia di librerie.
from gi.repository import Gtk, Gdk


# ---------------------------------------------------------------------------
# 2) IL FOGLIO DI STILE (CSS)
# ---------------------------------------------------------------------------
# GTK colora i widget con il CSS, lo stesso linguaggio dei siti web.
# Mettiamo lo stile dentro una FUNZIONE così possiamo generarne due versioni:
# una chiara e una scura. La funzione restituisce una stringa di CSS.
def costruisci_css(scuro=False):
    if scuro:
        sfondo = "#241420"   # prugna molto scuro
        testo = "#F7F2F5"    # quasi bianco
    else:
        sfondo = "#FFFFFF"   # bianco
        testo = "#000000"    # nero

    # Questa è una "f-string": il testo tra parentesi graffe { } viene
    # sostituito con il valore della variabile. Nel CSS le graffe VERE vanno
    # raddoppiate {{ }} per non confonderle con quelle della f-string.
    return f"""
    .area-testo, .area-testo text {{
        background-color: {sfondo};
        color: {testo};
        font-family: Serif;
        font-size: 13pt;
    }}
    .barra {{
        background-color: #8E4585;   /* prugna: l'accento, uguale nei due temi */
        padding: 4px;
    }}
    /* I bottoni hanno un loro sfondo: per rendere leggibile il testo bianco
       dobbiamo dare ANCHE uno sfondo al bottone, non solo il colore del testo.
       Coloriamo sia il bottone sia la sua etichetta interna (label). */
    .barra button {{
        background-image: none;          /* toglie il gradiente di default */
        background-color: #6E3268;       /* prugna piu' scuro dell'accento */
        color: #FFFFFF;
        border: none;
        padding: 4px 10px;
    }}
    .barra button label {{
        color: #FFFFFF;                  /* l'etichetta segue il testo bianco */
    }}
    .barra button:hover {{
        background-color: #7E3A77;       /* leggermente piu' chiaro al passaggio */
    }}
    """


# ---------------------------------------------------------------------------
# 3) LA FINESTRA PRINCIPALE
# ---------------------------------------------------------------------------
# Creiamo una nostra finestra che EREDITA da Gtk.ApplicationWindow. Ereditare
# significa: "parti da una finestra GTK già pronta e aggiungici le tue cose".
# In GTK 4 la finestra è legata a una Gtk.Application (vedi in fondo al file).
class MiniEditor(Gtk.ApplicationWindow):

    def __init__(self, app):
        # super().__init__ chiama il costruttore della finestra GTK originale.
        # Le passiamo l'applicazione (application=app): è ciò che lega questa
        # finestra al programma e ne gestisce il ciclo di vita.
        super().__init__(application=app, title="Mini RuscaWriter")
        self.set_default_size(700, 500)   # larghezza, altezza iniziali

        # "self.qualcosa" memorizza un dato DENTRO la finestra, disponibile in
        # tutte le funzioni della classe. Qui teniamo traccia del tema corrente
        # e del percorso del file aperto.
        self.scuro = False
        self.percorso_file = None

        # Prepariamo il fornitore di stile (CSS) e lo registriamo sul display.
        # NB (GTK 3 -> 4): si usa add_provider_for_display, non più
        # add_provider_for_screen.
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self.applica_tema()   # carica il CSS chiaro la prima volta

        # Costruiamo l'interfaccia (vedi la funzione qui sotto).
        self.costruisci_interfaccia()

    # -----------------------------------------------------------------------
    # Costruzione dell'interfaccia
    # -----------------------------------------------------------------------
    def costruisci_interfaccia(self):
        # In GTK non si posizionano i widget con coordinate fisse: si usano
        # delle "scatole" (Box) che si adattano. Una scatola verticale impila
        # i widget dall'alto verso il basso.
        colonna = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # NB (GTK 3 -> 4): per mettere un widget dentro la finestra si usa
        # set_child(), non più add(). La finestra ha UN solo figlio.
        self.set_child(colonna)

        # --- Barra dei bottoni in alto (scatola orizzontale) ---
        barra = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        barra.add_css_class("barra")   # le diamo la classe CSS

        # Creiamo i bottoni. Ognuno ha un'etichetta.
        btn_apri = Gtk.Button(label="Apri")
        btn_salva = Gtk.Button(label="Salva")
        btn_tema = Gtk.Button(label="Tema chiaro/scuro")

        # COLLEGAMENTO DEI SEGNALI — il concetto più importante.
        # "quando il bottone emette 'clicked', chiama questa mia funzione".
        # La funzione collegata si chiama callback (richiamata).
        btn_apri.connect("clicked", self.on_apri)
        btn_salva.connect("clicked", self.on_salva)
        btn_tema.connect("clicked", self.on_cambia_tema)

        # NB (GTK 3 -> 4): per riempire una scatola si usa append(), non più
        # pack_start(expand, fill, padding).
        barra.append(btn_apri)
        barra.append(btn_salva)
        barra.append(btn_tema)
        colonna.append(barra)

        # --- Area di scrittura ---
        # Il TextView mostra e modifica il testo. Il suo contenuto vero vive in
        # un "buffer" (Gtk.TextBuffer), che è separato dalla parte visiva.
        self.area = Gtk.TextView()
        self.area.set_wrap_mode(Gtk.WrapMode.WORD)   # va a capo sulle parole
        self.area.add_css_class("area-testo")
        self.buffer = self.area.get_buffer()

        # Ogni volta che il testo cambia, aggiorniamo il conteggio parole.
        self.buffer.connect("changed", self.on_testo_cambiato)

        # Mettiamo l'area dentro una finestra scorrevole, così se il testo è
        # lungo compaiono le barre di scorrimento. Diciamo all'area scorrevole
        # di espandersi in verticale per occupare lo spazio disponibile.
        scorrevole = Gtk.ScrolledWindow()
        scorrevole.set_child(self.area)
        scorrevole.set_vexpand(True)
        colonna.append(scorrevole)

        # --- Barra di stato in basso: conteggio parole ---
        self.stato = Gtk.Label(label="Parole: 0")
        self.stato.set_xalign(0)   # allinea il testo a sinistra
        self.stato.set_margin_top(2)
        self.stato.set_margin_bottom(2)
        colonna.append(self.stato)

    # -----------------------------------------------------------------------
    # Le callback: le funzioni chiamate quando l'utente fa qualcosa
    # -----------------------------------------------------------------------

    # Il "*_" significa: "GTK potrebbe passarmi altri argomenti, ma li ignoro".
    def on_testo_cambiato(self, *_):
        # Prendiamo tutto il testo dal buffer. get_bounds() restituisce
        # l'inizio e la fine; get_text legge ciò che c'è in mezzo.
        inizio, fine = self.buffer.get_bounds()
        testo = self.buffer.get_text(inizio, fine, True)
        # .split() spezza il testo sugli spazi: il numero di pezzi è il numero
        # di parole. Aggiorniamo l'etichetta in basso.
        n_parole = len(testo.split())
        self.stato.set_text(f"Parole: {n_parole}")

    def on_cambia_tema(self, *_):
        # Invertiamo il booleano e riapplichiamo il CSS. Tutto qui.
        self.scuro = not self.scuro
        self.applica_tema()

    def applica_tema(self):
        # Rigeneriamo il CSS in base al tema corrente e lo carichiamo.
        # NB (GTK 3 -> 4): si usa load_from_string(testo), non più
        # load_from_data(byte).
        css = costruisci_css(self.scuro)
        self.css.load_from_string(css)

    # -- SALVATAGGIO ---------------------------------------------------------
    # NB (GTK 3 -> 4): i dialoghi non si "fermano" più ad aspettare con
    # dialogo.run(). Si usa Gtk.FileDialog, che lavora in modo ASINCRONO: gli
    # diamo una funzione di callback che GTK chiamerà quando l'utente avrà
    # scelto. Il programma intanto non si blocca.
    def on_salva(self, *_):
        dialogo = Gtk.FileDialog()
        dialogo.set_title("Salva")
        # dialogo.save(...) apre la finestra e, alla scelta, chiama _salva_finito
        dialogo.save(self, None, self._salva_finito)

    def _salva_finito(self, dialogo, risultato):
        # save_finish può sollevare un errore se l'utente annulla: lo gestiamo
        # con try/except, così l'annullamento non fa nulla di male.
        try:
            gfile = dialogo.save_finish(risultato)
        except Exception:
            return   # l'utente ha annullato: non facciamo nulla
        percorso = gfile.get_path()
        inizio, fine = self.buffer.get_bounds()
        testo = self.buffer.get_text(inizio, fine, True)
        # "with open(...)" apre il file e lo chiude in automatico alla fine.
        # "w" = scrittura, encoding utf-8 per gestire le lettere accentate.
        with open(percorso, "w", encoding="utf-8") as f:
            f.write(testo)
        self.percorso_file = percorso

    # -- APERTURA ------------------------------------------------------------
    def on_apri(self, *_):
        dialogo = Gtk.FileDialog()
        dialogo.set_title("Apri")
        dialogo.open(self, None, self._apri_finito)

    def _apri_finito(self, dialogo, risultato):
        try:
            gfile = dialogo.open_finish(risultato)
        except Exception:
            return   # annullato
        percorso = gfile.get_path()
        # "r" = lettura. Leggiamo tutto il contenuto e lo mettiamo nel buffer.
        with open(percorso, "r", encoding="utf-8") as f:
            testo = f.read()
        self.buffer.set_text(testo)
        self.percorso_file = percorso


# ---------------------------------------------------------------------------
# 4) L'APPLICAZIONE E L'AVVIO
# ---------------------------------------------------------------------------
# NB (GTK 3 -> 4): non si usa più Gtk.main(). Si crea una Gtk.Application, che
# gestisce per noi il ciclo degli eventi (il loop che ascolta clic e tasti).
# Il metodo do_activate viene chiamato da GTK all'avvio: lì creiamo la finestra
# e la mostriamo con present().
class MiniApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.ruscalinux.MiniRuscaWriter")

    def do_activate(self):
        finestra = MiniEditor(self)
        finestra.present()   # mostra la finestra (in GTK 4 niente show_all)


def main():
    app = MiniApp()
    return app.run(None)


# Questa riga fa partire main() SOLO se lanci direttamente questo file.
# Se invece lo importassi da un altro programma, main() non partirebbe da solo.
if __name__ == "__main__":
    main()
