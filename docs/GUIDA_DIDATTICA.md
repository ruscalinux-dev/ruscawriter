# Imparare Python e GTK con RuscaWriter

Questa guida usa l'editor **RuscaWriter** come esempio reale per insegnarti
Python e la creazione di interfacce grafiche con **GTK 4** (tramite
**PyGObject**). Non serve essere esperti: si parte dalle basi e si arriva, passo
dopo passo, a capire come è fatto un programma vero.

L'idea è semplice: invece di esercizi finti, guardiamo un programma che fa
qualcosa di utile (scrivere romanzi e racconti, e impaginarli in PDF, EPUB e
altri formati) e lo smontiamo pezzo per pezzo.

> Nota sulle versioni: RuscaWriter usa **GTK 4**. Molte guide più vecchie parlano
> di GTK 3, che funziona in modo simile ma con alcune differenze importanti
> (l'avvio dell'applicazione, i menu, l'apertura delle finestre di dialogo). In
> questa guida segnaliamo le differenze quando contano.

---

## Indice

1. Cos'è un'interfaccia grafica e cos'è GTK
2. Come si avvia il programma: `Gtk.Application`
3. Le finestre: la classe `RuscaWriterWindow`
4. I widget e i contenitori
5. I segnali: come il programma "reagisce"
6. I menu e le azioni
7. Organizzare i dati: le classi `Chapter` e `Project`
8. Salvare e caricare: il formato `.rwr`
9. Esportare: PDF, EPUB e gli altri formati
10. Il controllo ortografico
11. I temi e il CSS
12. Le traduzioni (internazionalizzazione)
13. Esercizi proposti

---

## 1. Cos'è un'interfaccia grafica e cos'è GTK

Un programma può comunicare in due modi: scrivendo testo in un terminale,
oppure mostrando finestre con bottoni e menu (un'interfaccia grafica, o GUI).

**GTK** è una libreria che disegna queste finestre. È scritta in C, ma grazie
a **PyGObject** possiamo usarla da Python. Quando scrivi `import gi`, stai
caricando il ponte tra Python e GTK.

```python
import gi
gi.require_version("Gtk", "4.0")   # vogliamo GTK versione 4
from gi.repository import Gtk, Gio, GLib
```

La riga `gi.require_version` serve a dire "voglio proprio la versione 4",
perché ne esistono anche altre. È come specificare l'edizione di un libro. Se
chiedessi la 3.0 e poi importassi widget della 4.0 otterresti errori: le due
versioni non si mescolano nello stesso programma.

Oltre a `Gtk` importiamo spesso `Gio` (azioni, menu, file) e `GLib` (utilità di
base come i timer). Sono tutte parte della stessa famiglia di librerie.

---

## 2. Come si avvia il programma: `Gtk.Application`

In GTK 4 un programma non si avvia più con il vecchio `Gtk.main()`. Si usa
invece la classe `Gtk.Application`, che gestisce per noi il ciclo di vita
dell'applicazione. Apri `src/ruscawriter/editor.py` e vai in fondo:

```python
class RuscaWriterApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.ruscalinux.RuscaWriter")
        self.win = None

    def do_activate(self):
        if self.win is None:
            self.win = RuscaWriterWindow(self)
        self.win.present()

def main():
    app = RuscaWriterApp()
    return app.run(None)
```

Concetti fondamentali:

- **`application_id`** è un identificatore unico dell'app, scritto come un
  nome di dominio al contrario (`org.ruscalinux.RuscaWriter`). Serve al sistema
  per riconoscere il programma.
- **`do_activate`** è il metodo che GTK chiama quando l'applicazione viene
  attivata (di solito all'avvio). Qui creiamo la finestra e la mostriamo con
  `present()` (in GTK 4 si usa `present()`, non più `show_all()`).
- **`app.run(None)`** avvia tutto e resta in ascolto finché non chiudi la
  finestra.

> **Differenza con GTK 3:** prima si scriveva `win.show_all(); Gtk.main()`. In
> GTK 4 `show_all()` non esiste più (i widget sono visibili per impostazione
> predefinita) e il loop è gestito da `Gtk.Application`.

La riga `if __name__ == "__main__":` è un modo standard in Python per dire
"esegui `main()` solo se lancio direttamente questo file, non se lo importo da
un altro programma". È una convenzione che vedrai ovunque.

---

## 3. Le finestre: la classe `RuscaWriterWindow`

In Python una **classe** è un modo di raggruppare dati e funzioni che vanno
insieme. La finestra del programma è una classe:

```python
class RuscaWriterWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="RuscaWriter")
        ...
```

Cosa significa:

- **`class RuscaWriterWindow(Gtk.ApplicationWindow)`**: creiamo una nostra
  finestra che *eredita* da `Gtk.ApplicationWindow`. L'ereditarietà vuol dire
  "prendi tutto ciò che sa fare una finestra GTK, e aggiungi le mie cose". È
  come ricevere una cucina già attrezzata e aggiungerci i tuoi utensili.
- **`def __init__(self, app)`**: è il *costruttore*, la funzione eseguita
  quando crei l'oggetto. Qui si preparano tutti i pezzi.
- **`super().__init__(...)`**: chiama il costruttore della finestra GTK
  originale, così erediti il comportamento di base.
- **`self`**: rappresenta "questo specifico oggetto". Quando scrivi
  `self.font_size = 14`, memorizzi un dato dentro la finestra, disponibile in
  tutte le altre funzioni della classe.

Dentro `__init__` il programma legge le impostazioni salvate, prepara i colori,
poi chiama una serie di metodi per costruire l'interfaccia: `_apply_css()`,
`_build_actions()`, `_build_ui()`, `_setup_spell()`, `_retranslate()`. Spezzare
il lavoro in tante piccole funzioni rende il codice leggibile: ogni funzione fa
una cosa sola e ha un nome che dice cosa fa.

---

## 4. I widget e i contenitori

Ogni elemento dell'interfaccia è un **widget**. Qualche esempio dal codice:

```python
self.text_view = GtkSource.View()      # area dove si scrive (vedi cap. 10)
self.font_size_spin = Gtk.SpinButton() # selettore numerico (dimensione font)
self.menu_button = Gtk.MenuButton()    # il pulsante hamburger del menu
```

I widget vanno *messi dentro contenitori*, perché GTK non posiziona le cose con
coordinate fisse (x, y) ma con scatole che si adattano alla finestra. Il
contenitore più comune è `Gtk.Box`:

```python
# una scatola orizzontale: i widget si dispongono in fila
bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
bar.append(self.font_size_spin)
```

> **Differenza con GTK 3:** prima si usava `bar.pack_start(widget, expand, fill,
> padding)`. In GTK 4 si usa semplicemente **`append()`** (e `prepend()`), e
> l'espansione si controlla sul widget con `set_hexpand(True)` /
> `set_vexpand(True)`. È più semplice e meno criptico.

L'editor ha tre colonne (capitoli | testo | note) realizzate con `Gtk.Paned`,
un contenitore speciale con un divisore trascinabile. Due `Paned` annidati
danno le tre colonne. La larghezza di lettura del testo centrale viene limitata
e centrata con i margini del `TextView`, così le righe non diventano lunghissime
su uno schermo largo (lo fa il metodo `_update_reading_margins`).

La lista dei capitoli a sinistra usa `Gtk.ListView` con un `Gtk.StringList` (i
titoli) e una `Gtk.SingleSelection` (quale riga è selezionata). È il modo
moderno di GTK 4 per mostrare elenchi.

---

## 5. I segnali: come il programma reagisce

Questo è il cuore della programmazione a interfaccia grafica. Un widget *emette
segnali* quando succede qualcosa, e noi *colleghiamo* una funzione a quel
segnale. Esempio dal codice:

```python
self.btn_up.connect("clicked", self.on_move_up)
```

Si legge così: "quando il bottone `btn_up` emette il segnale `clicked`, chiama
la funzione `self.on_move_up`". La funzione collegata si chiama *callback*
(richiamata).

```python
def on_move_up(self, *_):
    self._move(-1)
```

Nota `*_`: è un modo per dire "questa funzione potrebbe ricevere altri
argomenti da GTK, ma non mi interessano". L'underscore è una convenzione per
"valore che ignoro".

La chiusura della finestra è anch'essa un segnale, ed è interessante perché
permette di intervenire *prima* che la finestra si chiuda:

```python
self.connect("close-request", self.on_close_request)
```

Se nel progetto ci sono modifiche non salvate, `on_close_request` mostra una
finestra di conferma e restituisce `True`, che significa "per ora non chiudere":
la chiusura avverrà solo dopo che l'utente ha scelto Salva o Scarta.

Capito questo schema — *widget → segnale → callback* — hai capito gran parte di
come funziona qualsiasi programma GTK.

---

## 6. I menu e le azioni

In GTK 4 i menu non si costruiscono più "a mano" aggiungendo voci una a una con
i loro callback. Si separano due cose: il **modello del menu** (cosa contiene) e
le **azioni** (cosa fa ogni voce). È più ordinato e permette di assegnare
scorciatoie da tastiera con facilità.

Un'azione si registra così (versione semplificata dal codice):

```python
action = Gio.SimpleAction.new("save", None)
action.connect("activate", self.on_save)
self.add_action(action)
self.app.set_accels_for_action("win.save", ["<Control>s"])
```

Il modello del menu si costruisce con `Gio.Menu`:

```python
m_file = Gio.Menu()
m_file.append("Salva", "win.save")   # la voce punta all'azione "win.save"
```

RuscaWriter mostra questo modello in due modi: come barra dei menu in alto
(`Gtk.PopoverMenuBar`) e, a schermo intero, come pulsante hamburger
(`Gtk.MenuButton`) — entrambi usano lo *stesso* modello, così non c'è
duplicazione. Questo è un esempio concreto del vantaggio di separare il modello
dalla sua visualizzazione.

---

## 7. Organizzare i dati: `Chapter` e `Project`

Finora abbiamo parlato di interfaccia. Ma un programma serio separa
l'interfaccia dai *dati*. RuscaWriter ha due classi (nel file `model.py`) che non
sanno nulla di bottoni e finestre: rappresentano solo l'opera che stai
scrivendo. Infatti `model.py` non importa nemmeno GTK — e questo permette di
testarlo senza aprire finestre.

```python
class Chapter:
    def __init__(self, index, text="", note="", is_cover=False, custom_title=""):
        self.index = index          # numero del capitolo (0 = copertina)
        self.text = text            # il testo vero e proprio
        self.note = note            # le note a margine
        self.is_cover = is_cover    # è la copertina?
        self.custom_title = custom_title
```

Un `Chapter` è un contenitore di dati: numero, testo, nota. Il `Project` è la
lista di tutti i capitoli, più il titolo e le sezioni editoriali:

```python
class Project:
    def __init__(self):
        self.path = None          # dove è salvato il file .rwr
        self.chapters = []        # lista di oggetti Chapter
        self.title = "Senza titolo"
        # sezioni editoriali opzionali:
        self.cover_image = None   # immagine di copertina (PNG/JPEG)
        self.frontispiece = ""    # frontespizio
        self.colophon = ""        # colophon
```

Questa separazione (dati da una parte, interfaccia dall'altra) è una buona
abitudine: puoi testare i dati senza aprire nessuna finestra. Il file
`tests/test_ruscawriter.py` fa proprio questo, e nessuno dei suoi test ha bisogno
di GTK.

I valori con il segno `=` nella definizione (`text=""`, `is_cover=False`) sono
*valori predefiniti*: se non li passi, Python usa quelli. Così puoi scrivere
`Chapter(1)` oppure `Chapter(1, "del testo")`.

---

## 8. Salvare e caricare: il formato `.rwr`

Un progetto `.rwr` è in realtà un archivio compresso (un `tar.gz`) che contiene
i vari pezzi del progetto come file separati: i capitoli come file di testo
Markdown, eventualmente l'immagine di copertina, il frontespizio e il colophon.
Salvare significa scrivere quei file nell'archivio:

```python
import tarfile, io
with tarfile.open(percorso, "w:gz") as tar:
    def add(name, data_bytes):
        info = tarfile.TarInfo(name=name)
        info.size = len(data_bytes)
        tar.addfile(info, io.BytesIO(data_bytes))
    add("01.md", capitolo.text.encode("utf-8"))
    # ...e così via per note, copertina, frontespizio, colophon
```

Il costrutto `with ... as ...` è importante: apre il file e garantisce che
venga chiuso correttamente alla fine, anche se succede un errore nel mezzo. È il
modo giusto di lavorare con i file in Python.

Una tecnica usata nel codice è il **salvataggio sicuro**: invece di scrivere
direttamente sul file dell'utente (rischiando di rovinarlo se il programma si
blocca a metà), si scrive prima su un file temporaneo e poi lo si sposta al
posto giusto con `shutil.move`. Se qualcosa va storto, il file originale resta
intatto.

Caricare fa il percorso inverso: apre l'archivio, legge i file dei capitoli
(riconoscendoli dal nome, es. `01.md`, `02.md`) e ricostruisce gli oggetti
`Chapter`, più le sezioni editoriali se presenti.

> Curiosità: l'immagine di copertina viene salvata *dentro* l'archivio (come
> `cover.png` o `cover.jpg`). Così il file `.rwr` resta "autoportante": lo
> copi o lo mandi a qualcuno e l'immagine viaggia con esso, senza riferimenti a
> file esterni che si romperebbero.

---

## 9. Esportare: PDF, EPUB e gli altri formati

RuscaWriter esporta in TXT, Markdown, PDF, EPUB, HTML, DOCX e ODT, e tutto questo
**senza dipendenze esterne**: usa solo la libreria standard di Python. Questa è
una parte istruttiva perché mostra che molti formati "complicati" sono, sotto
sotto, cose semplici:

- un **DOCX** e un **ODT** sono archivi ZIP che contengono file XML;
- un **EPUB** è anch'esso uno ZIP con XHTML e un po' di file di struttura;
- un **PDF** è un file di testo con una struttura precisa di "oggetti".

Per esempio, il PDF viene costruito scrivendo a mano gli oggetti che lo
compongono e tenendo traccia delle loro posizioni (la "xref table"). Il testo
del documento usa un font serif libero, **EB Garamond**, che viene incorporato
nel PDF: così il documento appare identico ovunque, anche su un computer che
quel font non ce l'ha. (L'editor, invece, usa a schermo un font monospace,
Courier Prime, più adatto alla scrittura.)

Le tre sezioni editoriali — copertina, frontespizio, colophon — vengono
impaginate insieme al testo nell'ordine: copertina → frontespizio → capitoli →
colophon. Nei formati che le supportano (PDF, EPUB, HTML, DOCX, ODT) compare
anche l'immagine di copertina; in TXT e Markdown restano solo le sezioni
testuali, perché un file di testo non può contenere un'immagine.

Non serve capire ogni dettaglio di questi formati per usarli: l'importante è
afferrare l'idea che un formato di file è solo una *convenzione* su come
disporre dei dati, e che con pazienza la si può rispettare.

---

## 10. Il controllo ortografico

L'ortografia è un buon esempio di come il passaggio da GTK 3 a GTK 4 cambi le
librerie disponibili. In GTK 3 si usavano GtkSpell o Gspell; in GTK 4 quelle
versioni non funzionano più, e si usa **libspelling** (la stessa libreria di
GNOME Text Editor).

Un dettaglio tecnico interessante: libspelling richiede che l'area di scrittura
sia un `GtkSource.View` (di GtkSourceView), non un semplice `Gtk.TextView`. Per
questo RuscaWriter costruisce l'editor come `GtkSource.View` quando la libreria è
disponibile.

C'è anche un problema linguistico curioso: in italiano e francese l'apostrofo
dell'elisione (`dell'anima`, `l'uomo`) verrebbe interpretato come confine di
parola, e frammenti come `dell` risulterebbero "errori". RuscaWriter lo risolve
aggiungendo quei frammenti al dizionario personale del correttore. È un esempio
di come, programmando, spesso il problema vero non sia il codice ma capire bene
il comportamento di una libreria.

---

## 11. I temi e il CSS

GTK permette di colorare i widget con il **CSS**, lo stesso linguaggio dei siti
web. Nel codice (`model.py`) c'è una funzione `build_css(dark)` che genera lo
stile:

```python
def build_css(dark=False):
    if dark:
        editor_bg = PLUM_INK      # sfondo scuro
        editor_fg = PAPER         # testo chiaro
    else:
        editor_bg = WHITE         # sfondo chiaro
        editor_fg = "#000000"     # testo nero
    return f"... .text-editor {{ background-color: {editor_bg}; }} ..."
```

Nota la **f-string** (`f"..."`): le parentesi graffe `{editor_bg}` vengono
sostituite con il valore della variabile. È il modo moderno in Python per
costruire testo con dei valori dentro. Attenzione: nel CSS le graffe vere vanno
raddoppiate `{{ }}` per non confonderle con quelle delle f-string.

Cambiare tema a programma in esecuzione significa semplicemente rigenerare il
CSS e ricaricarlo. Ecco perché il tema è una *funzione* e non un testo fisso.

Una lezione appresa "sul campo" e annotata nel codice: le regole CSS troppo
generiche fanno danni. Una regola come "colora tutte le etichette" finisce per
colpire anche le voci di menu e il testo dei pulsanti (che in GTK sono anch'essi
etichette), rendendoli illeggibili. La soluzione è usare **classi CSS dedicate**
(es. `.rusca-dialog-text`) e applicarle solo dove servono.

---

## 12. Le traduzioni (internazionalizzazione)

RuscaWriter parla diverse lingue. Il meccanismo (nel file `i18n.py`) è semplice:
ogni testo dell'interfaccia ha una *chiave* (per esempio `mi_save`), e per ogni
lingua c'è un file JSON nella cartella `lang/` che associa la chiave al testo
tradotto.

Nel codice non si scrive mai il testo direttamente, ma si chiede la traduzione:

```python
self.t("mi_save")    # restituisce "Salva" in italiano, "Save" in inglese, ...
```

Se una lingua non ha tradotto una certa chiave, il sistema *ripiega*
sull'inglese, così non resta mai un buco. Questo spiega perché alcune lingue
sono complete e altre, ancora da tradurre, mostrano l'inglese: il menu le segnala
come "non tradotto".

I testi con valori variabili usano i segnaposto, che vanno preservati nelle
traduzioni:

```python
self.t("exported", p=percorso)   # "Esportato in:\n{p}" -> {p} diventa il percorso
```

Tradurre il programma in una nuova lingua significa quindi solo compilare un
file JSON: nessuna modifica al codice.

---

## 13. Esercizi proposti

Prova a modificare il codice. È il modo migliore per imparare. Dal più facile:

1. **Cambia i colori.** In cima a `model.py` trovi `PLUM = "#8E4585"` e simili.
   Cambia i codici colore e riavvia: vedrai l'interfaccia cambiare aspetto.
2. **Cambia l'intervallo di autosave.** Cerca `timeout_add_seconds(60, ...)` e
   prova con 30 secondi.
3. **Aggiungi un conteggio.** Nella barra di stato si contano parole e
   caratteri. Prova ad aggiungere il numero di paragrafi (suggerimento: conta
   quante righe vuote separano i blocchi di testo).
4. **Una nuova scorciatoia.** Trova dove vengono registrate le azioni e le loro
   scorciatoie (`set_accels_for_action`) e assegna una combinazione di tasti a
   una voce che non ce l'ha.
5. **Una nuova lingua.** Copia `lang/en.json` in `lang/xx.json` (con il codice
   della tua lingua), traduci qualche chiave e avvia il programma: nel menu
   Lingua vedrai comparire la tua versione.
6. **Un nuovo formato di esportazione.** Guarda `export_markdown` in `model.py`:
   è il più semplice. Prova a scrivere un `export_bbcode` o simile, partendo da
   quello come modello.

Quando modifichi, tieni aperto un terminale e lancia il programma da lì con
`python3 ruscawriter.py`: se commetti un errore, Python ti scriverà dove e
perché. Leggere i messaggi d'errore è una competenza, non una sconfitta.

E prima di toccare il codice, lancia i test:

```
python3 tests/test_ruscawriter.py
```

Se dopo una modifica restano tutti verdi, è un buon segno; se qualcuno diventa
rosso, hai cambiato un comportamento che qualcosa si aspettava.

---

## Come continuare

- La documentazione ufficiale di PyGObject (in inglese) è su
  `https://pygobject.readthedocs.io/`.
- Per GTK 4 e i suoi widget, cerca la documentazione delle API di GTK 4 e gli
  esempi di PyGObject per GTK 4 (attento a non seguire esempi per GTK 3, che
  usano `pack_start`, `show_all` e `Gtk.main`).
- Per capire i formati di file, apri un `.docx` o un `.epub` con un programma di
  archiviazione (sono ZIP) e guarda cosa c'è dentro: è il modo migliore per
  demistificarli.

Buon divertimento, e ricorda: ogni programmatore ha iniziato non capendo niente
di quello che vedeva. La differenza la fa la curiosità di smontare le cose.
