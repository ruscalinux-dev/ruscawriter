# Changelog — RuscaWriter

Tutte le modifiche degne di nota a questo progetto sono elencate qui.
All notable changes to this project are listed here.

---

## [0.2] — 2026-06-14

### 🇮🇹 Italiano

#### Aggiunto
- **Formati di pagina per l'esportazione PDF.** Oltre all'A4 ora si può
  scegliere tra cinque formati editoriali pensati per la stampa di libri:
  A5 (14,8 × 21 cm), 6×9″ (15,2 × 22,9 cm), 17 × 24 cm, A4 (21 × 29,7 cm)
  e 5×8″ (12,7 × 20,3 cm). Un dialogo dedicato mostra un'anteprima grafica
  di ciascun formato; la scelta viene ricordata tra una sessione e l'altra.
  Le voci del selettore sono tradotte in tutte e 40 le lingue.
- **Margini di rilegatura (gutter).** Ogni formato distingue il margine
  *interno* (lato della piega, più largo perché il testo non sparisca nella
  rilegatura) da quello *esterno* (lato del taglio). Nelle pagine recto e
  verso il blocco di testo si sposta automaticamente verso la rilegatura,
  mentre intestazione e numero di pagina restano centrati sulla pagina fisica.
- **Copertina bianca.** Se un progetto non ha né immagine di copertina né
  alcun campo del frontespizio compilato, l'esportazione produce una pagina
  iniziale completamente bianca (senza cornice e senza numero) invece della
  copertina grafica automatica. Comportamento coerente tra PDF ed EPUB.

#### Modificato
- Il formato pagina PDF predefinito passa da A4 ad **A5**, più adatto a
  narrativa e saggistica.
- La schermata «Informazioni» mostra il numero di versione e la data di
  rilascio separati, per maggiore leggibilità.
- **Icone dell'applicazione rigenerate ad alta risoluzione** per tutte le
  dimensioni (16px → 512px) e logo SVG aggiornato.
- **Documentazione ampliata**: README e linee guida per i contributi
  (CONTRIBUTING) riviste ed estese.

#### Interno
- Nuovo helper di traduzione con testo di ripiego (`_t_or`): le voci di
  interfaccia non ancora presenti in una lingua mostrano comunque un testo
  sensato senza interrompere il flusso.
- Pulizia dei file di lingua (newline finale uniformato su tutti i JSON).

#### Compatibilità
- I progetti `.rwr` della 0.1 si aprono senza modifiche. Nessun cambiamento
  al formato file. L'intera suite di test (78 controlli su modello dati ed
  esportazioni PDF/EPUB/ODT/DOCX/HTML/AZW3/TXT/Markdown) viene superata.

---

### 🇬🇧 English

#### Added
- **Page sizes for PDF export.** Beyond A4, you can now choose among five
  book-oriented page formats: A5 (14.8 × 21 cm), 6×9″ (15.2 × 22.9 cm),
  17 × 24 cm, A4 (21 × 29.7 cm), and 5×8″ (12.7 × 20.3 cm). A dedicated
  dialog shows a graphical preview of each format, and your choice is
  remembered between sessions. The selector strings are translated across
  all 40 languages.
- **Binding margins (gutter).** Each format separates the *inner* margin
  (the spine side, made wider so text doesn't disappear into the binding)
  from the *outer* margin (the trim side). On recto and verso pages the text
  block shifts toward the spine automatically, while the running header and
  page number stay centred on the physical page.
- **Blank cover.** When a project has neither a cover image nor any
  frontispiece field filled in, export now produces a fully blank opening
  page (no frame, no page number) instead of the automatic graphic cover.
  Consistent behaviour across PDF and EPUB.

#### Changed
- The default PDF page size moves from A4 to **A5**, a better fit for
  fiction and non-fiction.
- The "About" screen shows the version number and release date separately
  for readability.
- **Application icons regenerated at high resolution** across all sizes
  (16px → 512px), with an updated SVG logo.
- **Expanded documentation**: README and contribution guidelines
  (CONTRIBUTING) revised and extended.

#### Internal
- New translation helper with fallback text (`_t_or`): interface strings not
  yet present in a given language still display sensible text without
  breaking the flow.
- Language-file cleanup (trailing newline normalised across all JSON files).

#### Compatibility
- Projects (`.rwr`) from 0.1 open unchanged. No file-format changes. The full
  test suite (78 checks across the data model and the PDF/EPUB/ODT/DOCX/HTML/
  AZW3/TXT/Markdown exports) passes.

---

## [0.1] — 2026-06-11

Prima versione pubblica. / First public release.

Editor di scrittura a tre colonne (capitoli, testo, note) in Python/GTK 4,
con esportazione verso PDF, EPUB, DOCX, ODT, HTML, Markdown e TXT, controllo
ortografico, interfaccia in 40 lingue e tema chiaro/scuro.
