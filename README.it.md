# RuscaWriter

🇬🇧 [Read it in English](README.md)


Editor di scrittura a tre colonne (capitoli · testo · note) del progetto
**RuscaLinux**. Pensato per testi e saggistica divulgativa, con esportazione in
molti formati e interfaccia in 40 lingue. Software libero sotto licenza GNU
GPL v3+.

## Avvio

Dalla cartella del progetto:

```
python3 ruscawriter.py
```

Requisiti: Python 3, PyGObject e GTK 4. Su Debian/Ubuntu:

```
sudo apt install python3-gi gir1.2-gtk-4.0
```

Per il controllo ortografico (opzionale ma consigliato), su GTK 4 serve
**libspelling** (la stessa libreria di GNOME Text Editor); Gspell 1.x e
GtkSpell NON funzionano con GTK 4 perché legati a GTK 3:

```
sudo apt install gir1.2-spelling-1 gir1.2-gtksource-5 hunspell-it hunspell-en-us
```

libspelling lavora su un editor `GtkSource.View`, quindi serve anche
**GtkSourceView 5** (`gir1.2-gtksource-5`): se è presente, l'area di scrittura
lo usa automaticamente; se manca, l'editor funziona lo stesso ma senza
controllo ortografico.

**Elisione (it/fr).** Il controllo ortografico di GTK 4 (libspelling/ICU)
spezza le parole sull'apostrofo, perciò forme come *dell'anima* o *l'uomo*
verrebbero segnalate come errore (il frammento *dell*, *l*, ecc. non è una
parola). Per evitarlo, all'avvio RuscaWriter aggiunge automaticamente i
frammenti di elisione di italiano e francese alle liste personali di Enchant
in `~/.config/enchant/<locale>.dic`, senza toccare le parole che hai aggiunto
tu. È trasparente: non devi fare nulla.

Aggiungi i pacchetti `hunspell-<lingua>` per le lingue che ti servono
(es. `hunspell-fr`, `hunspell-de`): l'editor mostrerà automaticamente nel
selettore le lingue per cui è installato un dizionario.

## Struttura del progetto

```
ruscawriter/
├── ruscawriter.py            avvio dell'applicazione
├── ruscawriter.desktop       voce per il menu applicazioni di GNOME
├── README.md
├── src/ruscawriter/          codice sorgente (pacchetto Python)
│   ├── __init__.py          espone main()
│   ├── editor.py            interfaccia grafica GTK 4
│   ├── model.py             modello dati ed export (indipendente da GTK)
│   ├── i18n.py              traduzioni e lingue
│   └── paths.py             individua le cartelle lang/ e assets/
├── lang/                    40 file di traduzione (.json)
├── assets/                  font CourierPrime e icone
│   └── icons/hicolor/        icona in tutte le dimensioni (16…512 px + SVG)
├── install-icons.sh         installa le icone nel tema del sistema
├── tests/                   test automatici
│   └── test_ruscawriter.py
└── docs/                    materiale didattico
    ├── GUIDA_DIDATTICA.md
    └── mini_ruscawriter.py
```

## Test

```
python3 tests/test_ruscawriter.py
```

## Icona nel menu applicazioni

L'icona (la stilografica bordeaux e oro) è fornita come SVG scalabile e come
PNG in tutte le dimensioni standard (16, 22, 24, 32, 48, 64, 128, 256, 512 px),
nella struttura `assets/icons/hicolor/`. Per installarla nel sistema, così
appare accanto al programma nel menu e nella dock:

```
sh install-icons.sh
```

Poi copia `ruscawriter.desktop` in `~/.local/share/applications/` (il file usa
`Icon=ruscawriter`, che il sistema risolverà con l'icona appena installata).

## Lingue

L'interfaccia è disponibile in 40 lingue, selezionabili al volo da
**Visualizza → Lingua**. Sono tradotte completamente sette lingue: italiano,
inglese, spagnolo, francese, tedesco, portoghese e russo. Le altre lingue
partono come "scheletri" che usano l'inglese come ripiego: nel menu sono
raccolte in una sezione separata e contrassegnate come "non tradotto", così è
chiaro che l'interfaccia resterà in inglese finché non vengono completate.
Per tradurne una basta editare il file corrispondente in `lang/` (e, volendo,
aggiungere il suo codice a `COMPLETE_LANGUAGES` in `src/ruscawriter/i18n.py`) —
senza toccare il resto del codice.

**Sezioni editoriali.** Da **File → Sezioni editoriali…** puoi aggiungere
un'immagine di copertina (PNG o JPEG), un frontespizio e un colophon. Vengono
impaginati insieme al testo nell'ordine copertina → frontespizio → capitoli →
colophon. L'immagine di copertina compare in PDF, EPUB, HTML, DOCX e ODT (negli
altri formati, e in TXT/Markdown, restano le sole sezioni testuali); se non
carichi un'immagine viene usata la copertina grafica generata. Tutto è
incorporato nel file `.rwr`, che resta autoportante.

**Importare testo come capitoli.** Da **File → Importa come capitoli…** (o
`Ctrl+I`) puoi scegliere uno o più file `.txt`/`.md`: ognuno viene aggiunto come
un nuovo capitolo in fondo al progetto corrente (un file = un capitolo), senza
toccare gli altri capitoli. Lo stesso effetto si ottiene **trascinando** i file
sull'area di scrittura. Il titolo del capitolo viene preso dal nome del file.

## Formati di esportazione

TXT, Markdown, PDF, EPUB, ODT, DOCX, HTML (file unico o multi-file con indice)
e AZW3 (Kindle, tramite Calibre se installato). PDF, EPUB, ODT e DOCX sono
generati senza dipendenze esterne, con la sola libreria standard di Python.

**Font.** L'editor usa Courier Prime (monospace, in stile macchina da scrivere)
per la scrittura. I documenti esportati usano invece un serif da lettura,
**EB Garamond**, più adatto a un libro: nel PDF il font viene incorporato (con
le larghezze reali di ogni glifo, trattandosi di un font proporzionale), mentre
EPUB e HTML lo richiedono per nome con ripiego sui serif di sistema. Entrambi i
font sono liberi, rilasciati sotto la **SIL Open Font License 1.1**, e i
rispettivi testi di licenza si trovano in `assets/` accanto ai file `.ttf`.

## Scorciatoie da tastiera

Le funzioni principali hanno una scorciatoia, utili soprattutto a schermo
intero (F11), dove i menu a tendina possono non aprirsi a causa di limitazioni
note dei popover GTK con alcuni window manager:

- `Ctrl+N` nuovo, `Ctrl+O` apri, `Ctrl+S` salva, `Ctrl+I` importa come capitoli
- `Ctrl+Maiusc+N` aggiungi capitolo, `F2` rinomina capitolo
- `Ctrl+F` cerca e sostituisci
- `Ctrl++` / `Ctrl+-` ingrandisci/riduci il testo
- `Ctrl+E` anteprima, `Ctrl+Maiusc+E` anteprima documento intero
- `Ctrl+L` / `Ctrl+R` mostra/nascondi colonna capitoli/note
- `F11` schermo intero
- `Ctrl+Maiusc+D` tema scuro
- `F1` Informazioni

## Come è stato realizzato

RuscaWriter è stato progettato e diretto dal progetto RuscaLinux: l'idea, il
layout a tre colonne, il design visivo e l'interfaccia, il tema plum chiaro e
scuro, le funzionalità, il sistema di esportazione e le scelte editoriali sono
tutto lavoro umano. L'implementazione in Python è stata poi realizzata con
l'aiuto di strumenti di intelligenza artificiale, seguendo indicazioni umane
dettagliate passo dopo passo, e rivista e testata da una persona a ogni stadio.

Lo diciamo apertamente perché crediamo sia il modo onesto di descrivere come è
stato costruito il software: una persona che decide cosa fare, che aspetto deve
avere e come deve funzionare, e l'IA usata come strumento per scrivere il codice.

## Contribuire

I contributi sono benvenuti: segnalazioni, traduzioni, correzioni e nuove
funzionalità. Vedi [CONTRIBUTING.md](CONTRIBUTING.md) per come segnalare un
problema, far girare i test e proporre una modifica.

## Licenza

Copyright © 2026 Nunzio Curcuruto.

RuscaWriter è software libero rilasciato sotto licenza **GNU General Public
License v3 o successiva (GPL-3.0-or-later)**. Il testo completo è nel file
[LICENSE](LICENSE).

RuscaWriter è stato progettato — interfaccia e design visivo compresi — e
diretto dal progetto RuscaLinux. L'implementazione in Python è stata realizzata
con strumenti di intelligenza artificiale seguendo indicazioni umane
dettagliate, passo dopo passo, con revisione e test.

I font inclusi (EB Garamond, Courier Prime) sono rilasciati sotto la **SIL Open
Font License 1.1**; i rispettivi testi si trovano in `assets/`.
