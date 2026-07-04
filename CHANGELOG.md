# Changelog — RuscaWriter

All notable changes to this project are listed here.
Tutte le modifiche degne di nota a questo progetto sono elencate qui.

*Each release lists the English section first, followed by the Italian one.*
*Ogni versione riporta prima la sezione in inglese, poi quella in italiano.*

---

## [0.3] — 2026-07-04

### 🇬🇧 English

#### Added
- **Images inside chapters.** New Edit → “Insert image…” entry
  (Ctrl+Shift+I): the chosen picture (PNG, JPEG or WebP) is copied *into*
  the project — it travels inside the `.rwr` archive — and a standard
  Markdown line `![caption](img_001.png)` appears in the text. The caption
  is freely editable. Every export renders it as a real figure: PDF
  (centered, italic caption, automatic page break), EPUB, ODT, DOCX and
  HTML; the exported Markdown copies the images to a sibling folder; TXT
  shows the caption in square brackets.
- **WebP covers.** The cover image now accepts PNG, JPEG and WebP; the
  format is detected from the file content, not from its extension. For
  Word (which cannot display WebP) and for the PDF, conversion to JPEG
  happens automatically when Pillow is available.

#### Removed
- **“Update date” button and menu entry.** The feature, tied to the old
  cover chapter, had become redundant: the cover is managed from the
  Editorial sections.

#### Internal
- **Bilingual (EN + IT) comments and docstrings** for all new or touched
  code, with bilingual headers for the five modules.
- Deduplicated the Markdown→HTML converter: EPUB now reuses the same
  `_blocks_to_html` as the HTML export (≈55 fewer lines).
- Unified image-format handling (`IMAGE_FORMATS` table, `image_format()`,
  `image_dimensions()` for PNG/JPEG/WebP, stdlib only).
- New automated tests for attached images (24 more checks); the suite
  passes both with and without Pillow.

#### Documentation
- **English is now the default language for all repository documents**, with
  the Italian version alongside where useful (`README.md` / `README.it.md`,
  `SECURITY.md` / `SECURITY.it.md`, `CONTRIBUTING.md` / `CONTRIBUTING.it.md`),
  and cross-links between each pair.
- `CONTRIBUTING.md` is now in English (the Italian text moved to
  `CONTRIBUTING.it.md`).
- The `docs/mini_ruscawriter.py` teaching mini-editor is now fully bilingual
  (English first, then Italian).
- Each `CHANGELOG` release lists the English section first, then the Italian.
- Removed the Italian-only `docs/GUIDA_DIDATTICA.md` guide.

---

### 🇮🇹 Italiano

#### Aggiunto
- **Immagini nei capitoli.** Nuova voce Modifica → «Inserisci immagine…»
  (Ctrl+Maiusc+I): l'immagine scelta (PNG, JPEG o WebP) viene copiata
  *dentro* il progetto — viaggia nell'archivio `.rwr` — e nel testo compare
  una riga Markdown standard `![didascalia](img_001.png)`. La didascalia si
  modifica liberamente. Tutti gli export la rendono come figura vera e
  propria: PDF (centrata, con didascalia in corsivo e salto pagina
  automatico), EPUB, ODT, DOCX e HTML; il Markdown esportato copia le
  immagini in una cartella affiancata; il TXT mostra la didascalia tra
  parentesi quadre.
- **Copertina anche in WebP.** L'immagine di copertina ora accetta PNG,
  JPEG e WebP; il formato è riconosciuto dal contenuto del file, non
  dall'estensione. Per Word (che non visualizza il WebP) e per il PDF la
  conversione in JPEG avviene automaticamente quando Pillow è presente.

#### Rimosso
- **Pulsante e voce di menu «Aggiorna data».** La funzione, legata al
  vecchio capitolo-copertina, era ormai superflua: la copertina si
  gestisce dalle Sezioni editoriali.

#### Interno
- Commenti e docstring dei moduli in **doppia lingua (EN + IT)** per tutto
  il codice nuovo o toccato, con intestazioni bilingue dei cinque moduli.
- Deduplicato il convertitore Markdown→HTML: l'EPUB riusa ora lo stesso
  `_blocks_to_html` dell'export HTML (≈55 righe in meno).
- Gestione unificata dei formati immagine (tabella `IMAGE_FORMATS`,
  `image_format()`, `image_dimensions()` per PNG/JPEG/WebP, solo stdlib).
- Nuovi test automatici per le immagini allegate (24 verifiche in più);
  la suite passa sia con sia senza Pillow.

#### Documentazione
- **L'inglese è ora la lingua predefinita di tutti i documenti del
  repository**, con la versione italiana affiancata dove utile
  (`README.md` / `README.it.md`, `SECURITY.md` / `SECURITY.it.md`,
  `CONTRIBUTING.md` / `CONTRIBUTING.it.md`), con link incrociati tra ogni
  coppia.
- `CONTRIBUTING.md` è ora in inglese (il testo italiano è stato spostato in
  `CONTRIBUTING.it.md`).
- Il mini-editor didattico `docs/mini_ruscawriter.py` è ora completamente
  bilingue (prima l'inglese, poi l'italiano).
- In ogni versione del `CHANGELOG` la sezione inglese precede quella italiana.
- Rimossa la guida `docs/GUIDA_DIDATTICA.md`, che era solo in italiano.

## [0.2] — 2026-06-14

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

## [0.1] — 2026-06-11

First public release. / Prima versione pubblica.

**English** — A three-column writing editor (chapters, text, notes) in
Python/GTK 4, exporting to PDF, EPUB, DOCX, ODT, HTML, Markdown and TXT, with
spell checking, a 40-language interface and a light/dark theme.

**Italiano** — Editor di scrittura a tre colonne (capitoli, testo, note) in
Python/GTK 4, con esportazione verso PDF, EPUB, DOCX, ODT, HTML, Markdown e
TXT, controllo ortografico, interfaccia in 40 lingue e tema chiaro/scuro.
