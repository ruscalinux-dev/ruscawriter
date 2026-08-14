# Changelog

What changed that you can see while using RuscaWriter. Internal changes stay
in the `git log`.

One line per change.

---

## [0.99] — 2026-08-13

Everything that changed since 0.3, the last published release.

### Writing and typesetting

- **Added** — View → Fonts: the screen font and the export font are chosen
  separately, from the two built-in faces or from any TrueType family installed
  on the machine. The export font is embedded in the PDF
- **Added** — PDF bookmarks: the exported PDF now carries a navigation tree of
  the chapters, which readers show in the sidebar and open by default
- **Added** — justified text in the PDF export, with optional hyphenation
- **Fixed** — a maximised window now reopens maximised. Its size was being
  saved while maximised and restored as an ordinary window the size of the
  screen, spilling under the taskbar every time
- **Fixed** — on the first run the text sat in a narrow column between two
  huge margins. The reading margins were measured before the side panels took
  their space, and nothing recalculated them afterwards
- **Fixed** — the writing column could be squeezed into a sliver, with the
  chapter list taking most of the window. The side columns were each capped at
  40% of the width, but independently, so together they could take 80%; and
  divider positions were being saved before the window had a real size, so a
  bad layout copied itself from one session to the next. The text now keeps a
  floor whatever the side columns ask for
- **Fixed** — View → Dark theme and Show line breaks now carry a tick when
  they are on. They are switches, and the menu used to read the same either way
- **Fixed** — on a cover with only a title and an author, the author was
  printed twice: the exports worked out each line's role from its position,
  and with two lines the ranges overlapped. Roles now come from the editorial
  fields themselves, in the PDF, HTML, EPUB and the thumbnail alike
- **Added** — cover generator: builds a typographic cover, with a live preview
- **Fixed** — on the generated cover, a long title no longer runs off the
  edges, and words are never split across lines: the type size is measured
  against the real text width, letter spacing included, and shrinks until every
  word fits whole
- **Added** — Markdown guide under Help (Shift+F1)
- **Added** — View → Show line breaks (`Ctrl+Shift+B`) tints the paragraphs that
  are broken at a fixed column, and Chapter → Rejoin paragraphs repairs them.
  Both follow the same rule, so what you see highlighted is what gets joined
- **Changed** — importing a hard-wrapped `.txt` no longer rejoins the
  paragraphs on its own: it is your text, so the choice is yours. Turn on
  Chapter → Rejoin imported text automatically and RuscaWriter will do it from
  then on
- **Fixed** — importing a Project Gutenberg `.txt` no longer drags the header
  and the licence into the manuscript: about a tenth of the words in a typical
  file. The cut is made between Gutenberg's own two marker lines, so a file
  that is not from Gutenberg comes through untouched
- **Added** — Chapter → Rejoin paragraphs repairs text that is hard-wrapped at
  a fixed column, the usual shape of literary plain text, so it justifies in the
  PDF and reflows in the EPUB. Verse, lists, quotes and explicit Markdown line
  breaks are left alone
- **Fixed** — a Markdown link lost its address on export: only the label came
  through, so a cited source became unreachable. The address is now printed in
  full beside the label, and never as a clickable link — a book gets printed,
  and on paper nobody can click
- **Fixed** — Markdown is now read the same way everywhere. A heading needs a
  space after the `#`, as the Markdown guide has always shown: `#Title` is body
  text in every format, where before it was a heading in the PDF only
- **Fixed** — `_italic_` and `__bold__` are highlighted while you type, not
  only formatted on export
- **Fixed** — a lone `*`, as in `3 * 4`, no longer turns the rest of the line
  italic in the PDF
- **Fixed** — nested formatting (`**bold with *italic* inside**`) now comes out
  right in HTML and EPUB too

### Look

- **Added** — custom themes: drop a small text file with a name and seven
  colours into `~/.config/ruscawriter/themes/` and it joins the theme menu,
  light and dark version included. The folder ships a commented example
- **Added** — a second interface theme beside the plum of RuscaLinux:
  **Quiet**, designed for comfort over long sessions — off-white paper,
  graphite ink, a sage accent kept to the selection and the rules, in a light
  and a dark version
- **Changed** — five themes, named after five gems: **Ametista**, **Rubino**,
  **Zaffiro**, **Giada**, **Ambra**. Each has its own paper, ink and night
  ground, and each keeps body text between 12:1 and 14:1 rather than at the
  21:1 of pure black on pure white. The names are translated, and each entry in
  the theme menu carries a dot in its own colour
- **Changed** — the RuscaLinux plum theme was reworked for the eyes. Its bars
  keep the full plum, but the page no longer is black on white at 21:1: paper
  with a whisper of plum, graphite ink, 13.8:1
- **Added** — themes can now set the interface bars separately from the accent,
  and choose their own paper, panels and ink. Custom themes in the folder can
  do the same
- **Changed** — the theme is now picked in two independent steps: the colour
  family under View → Theme, light or dark with `Ctrl+Shift+D`
- **Fixed** — the hint on the empty page named a menu command that did not
  exist ("New chapter" instead of "Add chapter")

### Under the hood

- **Changed** — the version and the date are now written in one place only

---

## [0.3] — 2026-07-04

- **Added** — images inside chapters (Ctrl+Shift+I). They travel inside the
  `.rwr` file and come out as real figures with captions in every export
- **Added** — WebP, alongside PNG and JPEG, for chapter images and covers
- **Removed** — the "update date" button, made redundant by editorial sections

---

## [0.2] — 2026-06-14

- **Added** — five page sizes for the PDF export: A5, 6×9″, 17×24 cm, A4, 5×8″
- **Added** — binding margins, so text does not disappear into the spine
- **Added** — cover, frontispiece and colophon, set from editorial sections
- **Changed** — the default PDF page size is now A5 instead of A4
- **Changed** — application icons redrawn at every size, up to 512 px

---

## [0.1] — 2026-06-11

- **Added** — first release. Three columns (chapters, text, notes), writing in
  Markdown, and export to TXT, Markdown, PDF, EPUB, ODT, DOCX and HTML
