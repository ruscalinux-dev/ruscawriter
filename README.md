# RuscaWriter

*A focused, three-column writing editor for non-fiction — part of the [RuscaLinux](https://www.ruscalinux.org/) project.*

🇮🇹 [Leggilo in italiano](README.it.md)

[![License: GPL v3+](https://img.shields.io/badge/License-GPL%20v3%2B-blue.svg)](LICENSE)
[![Website](https://img.shields.io/badge/Website-ruscalinux.org-8E4585)](https://www.ruscalinux.org/ruscawriter/)
[![Ko-fi](https://img.shields.io/badge/Support-Ko--fi-FF5E5B)](https://ko-fi.com/ruscalinuxdev)

![RuscaWriter screenshot](docs/screenshot.png)

Chapters, text and notes side by side. Write in plain Markdown, then export
a finished book — no plugins, no external converters.

## Features

- **Three columns**: chapter list, your text, and per-chapter notes in one view
- **Export** to PDF (typeset, embedded fonts, automatic index), EPUB, DOCX, ODT, HTML, Markdown, TXT
- **Title page & colophon** built from simple editorial fields
- **Spell checking** with proper handling of Italian/French elisions (*dell'anima*, *l'uomo*)
- **40-language interface**, light & dark plum theme
- **Plain-text projects**: a `.rwr` file is just a tar.gz of Markdown — yours forever

## Install & run

Requires Python 3, PyGObject and GTK 4. On Debian / Ubuntu / RuscaLinux:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0
# optional, for spell checking:
sudo apt install gir1.2-gtksource-5 gir1.2-spelling-1 hunspell-it hunspell-en-us
```

Run from source:

```bash
python3 ruscawriter.py
```

Or grab the `.deb` package from the [Releases](https://github.com/ruscalinux-dev/ruscawriter/releases) page.

## Links

- 🏠 **Website**: <https://www.ruscalinux.org/ruscawriter/>
- ☕ **Support the project**: <https://ko-fi.com/ruscalinuxdev>

## Contributing

Bug reports, translations and pull requests are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md). Run the test suite with
`python3 tests/test_ruscawriter.py`.

## License

Free software under the **GNU GPL v3 or later** — see [LICENSE](LICENSE).
Bundled fonts (EB Garamond, Courier Prime) are under the SIL Open Font
License 1.1 (texts in `assets/`).
