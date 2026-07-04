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
============================================================================
 MINI RUSCAWRITER — heavily commented teaching version (GTK 4)
                     versione didattica super-commentata (GTK 4)
============================================================================

EN: This is NOT the full program: it is a stripped-to-the-bone version, made
    for LEARNING. It does only a few things (write text, count words, save and
    open a file, switch theme) but it uses exactly the same concepts as the
    big RuscaWriter. Every important part is explained in the comments.
IT: Questo NON è il programma completo: è una versione ridotta all'osso,
    pensata per IMPARARE. Fa poche cose (scrivere testo, contare le parole,
    salvare e aprire un file, cambiare tema) ma usa esattamente gli stessi
    concetti del RuscaWriter grande. Ogni parte importante è spiegata nei
    commenti.

EN/IT: To run it, from a terminal / Per eseguirlo, da terminale:
    python3 mini_ruscawriter.py

EN: Requires PyGObject and GTK 4. On Debian/Ubuntu:
IT: Richiede PyGObject e GTK 4. Su Debian/Ubuntu:
    sudo apt install python3-gi gir1.2-gtk-4.0

----------------------------------------------------------------------------
 EN: NOTE ON VERSIONS (GTK 3 -> GTK 4)
 IT: NOTA SULLE VERSIONI (GTK 3 -> GTK 4)
----------------------------------------------------------------------------
EN: The big RuscaWriter uses GTK 4, and so does this mini-editor. Compared to
    many older guides (written for GTK 3) some basic things change; we flag
    them in the comments where they occur:
IT: Il RuscaWriter grande usa GTK 4, e così questo mini-editor. Rispetto a
    tante guide più vecchie (scritte per GTK 3) cambiano alcune cose di base;
    le segnaliamo nei commenti dove capitano:
  - EN startup / IT avvio: Gtk.Application  ->  (instead of / al posto di) Gtk.main();
  - EN show the window / IT mostrare la finestra: present()  ->  show_all();
  - EN fill the boxes / IT riempire le scatole: append()  ->  pack_start();
  - EN put a child in a container / IT mettere un figlio in un contenitore:
    set_child()  ->  add();
  - EN dialogs are ASYNCHRONOUS (callbacks), no more dialog.run();
    IT i dialoghi sono ASINCRONI (con callback), niente più dialogo.run().
============================================================================
"""

# ---------------------------------------------------------------------------
# EN: 1) IMPORTS
# IT: 1) IMPORTAZIONI
# ---------------------------------------------------------------------------
# EN: "import gi" loads the bridge between Python and GTK. Before using GTK we
#     must state which version we want, otherwise Python does not know which
#     one to load.
# IT: "import gi" carica il ponte tra Python e GTK. Prima di usare GTK dobbiamo
#     dire quale versione vogliamo, altrimenti Python non sa quale caricare.
import gi
gi.require_version("Gtk", "4.0")
# EN: Besides Gtk we import Gdk, needed to get the "display" on which to apply
#     the CSS. They belong to the same family of libraries.
# IT: Oltre a Gtk importiamo Gdk, che ci serve per ottenere il "display" su cui
#     applicare il CSS. Sono parte della stessa famiglia di librerie.
from gi.repository import Gtk, Gdk


# ---------------------------------------------------------------------------
# EN: 2) THE STYLE SHEET (CSS)
# IT: 2) IL FOGLIO DI STILE (CSS)
# ---------------------------------------------------------------------------
# EN: GTK colors its widgets with CSS, the same language used by websites.
#     We put the style inside a FUNCTION so we can generate two versions: a
#     light one and a dark one. The function returns a CSS string.
# IT: GTK colora i widget con il CSS, lo stesso linguaggio dei siti web.
#     Mettiamo lo stile dentro una FUNZIONE così possiamo generarne due
#     versioni: una chiara e una scura. La funzione restituisce una stringa CSS.
def costruisci_css(scuro=False):
    if scuro:
        sfondo = "#241420"   # EN: very dark plum / IT: prugna molto scuro
        testo = "#F7F2F5"    # EN: almost white   / IT: quasi bianco
    else:
        sfondo = "#FFFFFF"   # EN: white / IT: bianco
        testo = "#000000"    # EN: black / IT: nero

    # EN: This is an "f-string": the text between curly braces { } is replaced
    #     with the value of the variable. In CSS the REAL braces must be
    #     doubled {{ }} so they are not confused with the f-string ones.
    # IT: Questa è una "f-string": il testo tra parentesi graffe { } viene
    #     sostituito con il valore della variabile. Nel CSS le graffe VERE
    #     vanno raddoppiate {{ }} per non confonderle con quelle della f-string.
    return f"""
    .area-testo, .area-testo text {{
        background-color: {sfondo};
        color: {testo};
        font-family: Serif;
        font-size: 13pt;
    }}
    .barra {{
        background-color: #8E4585;   /* EN plum accent, same in both themes
                                        IT prugna: l'accento, uguale nei due temi */
        padding: 4px;
    }}
    /* EN: Buttons have their own background: to make the white text readable
           we must give the button a background TOO, not only the text color.
           We color both the button and its inner label.
       IT: I bottoni hanno un loro sfondo: per rendere leggibile il testo
           bianco dobbiamo dare ANCHE uno sfondo al bottone, non solo il
           colore del testo. Coloriamo sia il bottone sia l'etichetta (label). */
    .barra button {{
        background-image: none;          /* EN removes default gradient
                                            IT toglie il gradiente di default */
        background-color: #6E3268;       /* EN darker than the accent
                                            IT prugna piu' scuro dell'accento */
        color: #FFFFFF;
        border: none;
        padding: 4px 10px;
    }}
    .barra button label {{
        color: #FFFFFF;                  /* EN label follows the white text
                                            IT l'etichetta segue il testo bianco */
    }}
    .barra button:hover {{
        background-color: #7E3A77;       /* EN slightly lighter on hover
                                            IT leggermente piu' chiaro al passaggio */
    }}
    """


# ---------------------------------------------------------------------------
# EN: 3) THE MAIN WINDOW
# IT: 3) LA FINESTRA PRINCIPALE
# ---------------------------------------------------------------------------
# EN: We create our own window that INHERITS from Gtk.ApplicationWindow. To
#     inherit means: "start from a ready-made GTK window and add your own
#     things". In GTK 4 the window is tied to a Gtk.Application (see the bottom
#     of the file).
# IT: Creiamo una nostra finestra che EREDITA da Gtk.ApplicationWindow.
#     Ereditare significa: "parti da una finestra GTK già pronta e aggiungici
#     le tue cose". In GTK 4 la finestra è legata a una Gtk.Application (vedi
#     in fondo al file).
class MiniEditor(Gtk.ApplicationWindow):

    def __init__(self, app):
        # EN: super().__init__ calls the constructor of the original GTK
        #     window. We pass it the application (application=app): that is what
        #     ties this window to the program and manages its life cycle.
        # IT: super().__init__ chiama il costruttore della finestra GTK
        #     originale. Le passiamo l'applicazione (application=app): è ciò che
        #     lega questa finestra al programma e ne gestisce il ciclo di vita.
        super().__init__(application=app, title="Mini RuscaWriter")
        self.set_default_size(700, 500)   # EN: initial width, height
                                          # IT: larghezza, altezza iniziali

        # EN: "self.something" stores a value INSIDE the window, available in
        #     every method of the class. Here we track the current theme and
        #     the path of the open file.
        # IT: "self.qualcosa" memorizza un dato DENTRO la finestra, disponibile
        #     in tutte le funzioni della classe. Qui teniamo traccia del tema
        #     corrente e del percorso del file aperto.
        self.scuro = False
        self.percorso_file = None

        # EN: We prepare the style provider (CSS) and register it on the
        #     display. NB (GTK 3 -> 4): use add_provider_for_display, no longer
        #     add_provider_for_screen.
        # IT: Prepariamo il fornitore di stile (CSS) e lo registriamo sul
        #     display. NB (GTK 3 -> 4): si usa add_provider_for_display, non più
        #     add_provider_for_screen.
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self.applica_tema()   # EN: load the light CSS the first time
                              # IT: carica il CSS chiaro la prima volta

        # EN: Build the interface (see the method below).
        # IT: Costruiamo l'interfaccia (vedi la funzione qui sotto).
        self.costruisci_interfaccia()

    # -----------------------------------------------------------------------
    # EN: Building the interface / IT: Costruzione dell'interfaccia
    # -----------------------------------------------------------------------
    def costruisci_interfaccia(self):
        # EN: In GTK you do not place widgets with fixed coordinates: you use
        #     "boxes" (Box) that adapt. A vertical box stacks widgets from top
        #     to bottom.
        # IT: In GTK non si posizionano i widget con coordinate fisse: si usano
        #     delle "scatole" (Box) che si adattano. Una scatola verticale
        #     impila i widget dall'alto verso il basso.
        colonna = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # EN: NB (GTK 3 -> 4): to put a widget inside the window use
        #     set_child(), no longer add(). The window has ONE single child.
        # IT: NB (GTK 3 -> 4): per mettere un widget dentro la finestra si usa
        #     set_child(), non più add(). La finestra ha UN solo figlio.
        self.set_child(colonna)

        # EN: --- Top button bar (horizontal box) ---
        # IT: --- Barra dei bottoni in alto (scatola orizzontale) ---
        barra = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        barra.add_css_class("barra")   # EN: give it the CSS class
                                       # IT: le diamo la classe CSS

        # EN: Create the buttons. Each has a label.
        # IT: Creiamo i bottoni. Ognuno ha un'etichetta.
        btn_apri = Gtk.Button(label="Apri")
        btn_salva = Gtk.Button(label="Salva")
        btn_tema = Gtk.Button(label="Tema chiaro/scuro")

        # EN: CONNECTING SIGNALS — the most important concept.
        #     "when the button emits 'clicked', call this method of mine".
        #     The connected function is called a callback.
        # IT: COLLEGAMENTO DEI SEGNALI — il concetto più importante.
        #     "quando il bottone emette 'clicked', chiama questa mia funzione".
        #     La funzione collegata si chiama callback (richiamata).
        btn_apri.connect("clicked", self.on_apri)
        btn_salva.connect("clicked", self.on_salva)
        btn_tema.connect("clicked", self.on_cambia_tema)

        # EN: NB (GTK 3 -> 4): to fill a box use append(), no longer
        #     pack_start(expand, fill, padding).
        # IT: NB (GTK 3 -> 4): per riempire una scatola si usa append(), non più
        #     pack_start(expand, fill, padding).
        barra.append(btn_apri)
        barra.append(btn_salva)
        barra.append(btn_tema)
        colonna.append(barra)

        # EN: --- Writing area ---
        # IT: --- Area di scrittura ---
        # EN: The TextView shows and edits the text. Its real content lives in a
        #     "buffer" (Gtk.TextBuffer), separate from the visual part.
        # IT: Il TextView mostra e modifica il testo. Il suo contenuto vero vive
        #     in un "buffer" (Gtk.TextBuffer), separato dalla parte visiva.
        self.area = Gtk.TextView()
        self.area.set_wrap_mode(Gtk.WrapMode.WORD)   # EN: wrap on words
                                                     # IT: va a capo sulle parole
        self.area.add_css_class("area-testo")
        self.buffer = self.area.get_buffer()

        # EN: Every time the text changes, we update the word count.
        # IT: Ogni volta che il testo cambia, aggiorniamo il conteggio parole.
        self.buffer.connect("changed", self.on_testo_cambiato)

        # EN: Put the area inside a scrolled window, so that if the text is long
        #     the scrollbars appear. We tell the scrolled area to expand
        #     vertically to fill the available space.
        # IT: Mettiamo l'area dentro una finestra scorrevole, così se il testo è
        #     lungo compaiono le barre di scorrimento. Diciamo all'area
        #     scorrevole di espandersi in verticale per occupare lo spazio.
        scorrevole = Gtk.ScrolledWindow()
        scorrevole.set_child(self.area)
        scorrevole.set_vexpand(True)
        colonna.append(scorrevole)

        # EN: --- Bottom status bar: word count ---
        # IT: --- Barra di stato in basso: conteggio parole ---
        self.stato = Gtk.Label(label="Parole: 0")
        self.stato.set_xalign(0)   # EN: align text to the left
                                   # IT: allinea il testo a sinistra
        self.stato.set_margin_top(2)
        self.stato.set_margin_bottom(2)
        colonna.append(self.stato)

    # -----------------------------------------------------------------------
    # EN: The callbacks: methods called when the user does something
    # IT: Le callback: le funzioni chiamate quando l'utente fa qualcosa
    # -----------------------------------------------------------------------

    # EN: The "*_" means: "GTK might pass me more arguments, but I ignore them".
    # IT: Il "*_" significa: "GTK potrebbe passarmi altri argomenti, ma li
    #     ignoro".
    def on_testo_cambiato(self, *_):
        # EN: Grab the whole text from the buffer. get_bounds() returns the
        #     start and the end; get_text reads what is in between.
        # IT: Prendiamo tutto il testo dal buffer. get_bounds() restituisce
        #     l'inizio e la fine; get_text legge ciò che c'è in mezzo.
        inizio, fine = self.buffer.get_bounds()
        testo = self.buffer.get_text(inizio, fine, True)
        # EN: .split() breaks the text on spaces: the number of pieces is the
        #     number of words. We update the bottom label.
        # IT: .split() spezza il testo sugli spazi: il numero di pezzi è il
        #     numero di parole. Aggiorniamo l'etichetta in basso.
        n_parole = len(testo.split())
        self.stato.set_text(f"Parole: {n_parole}")

    def on_cambia_tema(self, *_):
        # EN: Flip the boolean and re-apply the CSS. That's all.
        # IT: Invertiamo il booleano e riapplichiamo il CSS. Tutto qui.
        self.scuro = not self.scuro
        self.applica_tema()

    def applica_tema(self):
        # EN: Regenerate the CSS based on the current theme and load it.
        #     NB (GTK 3 -> 4): use load_from_string(text), no longer
        #     load_from_data(bytes).
        # IT: Rigeneriamo il CSS in base al tema corrente e lo carichiamo.
        #     NB (GTK 3 -> 4): si usa load_from_string(testo), non più
        #     load_from_data(byte).
        css = costruisci_css(self.scuro)
        self.css.load_from_string(css)

    # -- EN: SAVING / IT: SALVATAGGIO ---------------------------------------
    # EN: NB (GTK 3 -> 4): dialogs no longer "stop" to wait with dialog.run().
    #     You use Gtk.FileDialog, which works ASYNCHRONOUSLY: we give it a
    #     callback that GTK will call once the user has chosen. Meanwhile the
    #     program does not freeze.
    # IT: NB (GTK 3 -> 4): i dialoghi non si "fermano" più ad aspettare con
    #     dialogo.run(). Si usa Gtk.FileDialog, che lavora in modo ASINCRONO:
    #     gli diamo una funzione di callback che GTK chiamerà quando l'utente
    #     avrà scelto. Il programma intanto non si blocca.
    def on_salva(self, *_):
        dialogo = Gtk.FileDialog()
        dialogo.set_title("Salva")
        # EN: dialog.save(...) opens the window and, on choice, calls
        #     _salva_finito.
        # IT: dialogo.save(...) apre la finestra e, alla scelta, chiama
        #     _salva_finito.
        dialogo.save(self, None, self._salva_finito)

    def _salva_finito(self, dialogo, risultato):
        # EN: save_finish can raise an error if the user cancels: we handle it
        #     with try/except, so cancelling does no harm.
        # IT: save_finish può sollevare un errore se l'utente annulla: lo
        #     gestiamo con try/except, così l'annullamento non fa nulla di male.
        try:
            gfile = dialogo.save_finish(risultato)
        except Exception:
            return   # EN: user cancelled: do nothing
                     # IT: l'utente ha annullato: non facciamo nulla
        percorso = gfile.get_path()
        inizio, fine = self.buffer.get_bounds()
        testo = self.buffer.get_text(inizio, fine, True)
        # EN: "with open(...)" opens the file and closes it automatically at the
        #     end. "w" = write, encoding utf-8 to handle accented letters.
        # IT: "with open(...)" apre il file e lo chiude in automatico alla fine.
        #     "w" = scrittura, encoding utf-8 per gestire le lettere accentate.
        with open(percorso, "w", encoding="utf-8") as f:
            f.write(testo)
        self.percorso_file = percorso

    # -- EN: OPENING / IT: APERTURA -----------------------------------------
    def on_apri(self, *_):
        dialogo = Gtk.FileDialog()
        dialogo.set_title("Apri")
        dialogo.open(self, None, self._apri_finito)

    def _apri_finito(self, dialogo, risultato):
        try:
            gfile = dialogo.open_finish(risultato)
        except Exception:
            return   # EN: cancelled / IT: annullato
        percorso = gfile.get_path()
        # EN: "r" = read. We read the whole content and put it in the buffer.
        # IT: "r" = lettura. Leggiamo tutto il contenuto e lo mettiamo nel buffer.
        with open(percorso, "r", encoding="utf-8") as f:
            testo = f.read()
        self.buffer.set_text(testo)
        self.percorso_file = percorso


# ---------------------------------------------------------------------------
# EN: 4) THE APPLICATION AND THE STARTUP
# IT: 4) L'APPLICAZIONE E L'AVVIO
# ---------------------------------------------------------------------------
# EN: NB (GTK 3 -> 4): Gtk.main() is no longer used. You create a
#     Gtk.Application, which manages the event loop for us (the loop that
#     listens for clicks and keys). The do_activate method is called by GTK at
#     startup: there we create the window and show it with present().
# IT: NB (GTK 3 -> 4): non si usa più Gtk.main(). Si crea una Gtk.Application,
#     che gestisce per noi il ciclo degli eventi (il loop che ascolta clic e
#     tasti). Il metodo do_activate viene chiamato da GTK all'avvio: lì creiamo
#     la finestra e la mostriamo con present().
class MiniApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.ruscalinux.MiniRuscaWriter")

    def do_activate(self):
        finestra = MiniEditor(self)
        finestra.present()   # EN: show the window (no show_all in GTK 4)
                             # IT: mostra la finestra (in GTK 4 niente show_all)


def main():
    app = MiniApp()
    return app.run(None)


# EN: This line starts main() ONLY if you run this file directly. If you
#     imported it from another program, main() would not start by itself.
# IT: Questa riga fa partire main() SOLO se lanci direttamente questo file.
#     Se invece lo importassi da un altro programma, main() non partirebbe
#     da solo.
if __name__ == "__main__":
    main()
