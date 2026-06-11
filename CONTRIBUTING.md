# Contributing to RuscaWriter

Thanks for your interest! Bug reports, ideas, translations and pull requests
are all welcome. RuscaWriter is free software under the **GNU GPL v3+**; by
contributing you agree that your contribution is released under the same
license.

## Reporting a bug

Open an issue and include:

- what you expected and what happened instead;
- steps to reproduce;
- your distribution (e.g. RuscaLinux, Debian 13), Python and GTK 4 versions;
- if possible, the full error message (run `python3 ruscawriter.py` from a
  terminal to see it).

## Pull requests

1. Fork the repository and create a focused branch (one topic per PR).
2. Make your changes, following the style of the file you're editing.
3. **Run the tests** (see below) — they must all pass.
4. Open the PR with a clear description; link the related issue if any.

## Development setup

```bash
sudo apt install python3-gi gir1.2-gtk-4.0
# optional, for spell checking:
sudo apt install gir1.2-gtksource-5 gir1.2-spelling-1 hunspell-it hunspell-en-us
python3 ruscawriter.py
```

## Tests

The data model and all export formats are covered by a GTK-free test suite:

```bash
python3 tests/test_ruscawriter.py
```

If you add a feature to the model or the exporters, add a test for it.

## Project layout

- `ruscawriter.py` — application entry point
- `src/ruscawriter/editor.py` — GTK 4 user interface
- `src/ruscawriter/model.py` — data model and exporters (GTK-free; this is
  what the tests exercise)
- `src/ruscawriter/i18n.py` + `lang/*.json` — translations
- `docs/` — learning guide and a minimal example editor

## Translating

Copy `lang/en.json` to `lang/<code>.json`, translate the values (keep keys
and placeholders like `{p}` or `{n}` intact), and — once complete — add the
language code to `COMPLETE_LANGUAGES` in `src/ruscawriter/i18n.py`.

## Questions

Open an issue, or write to <info@ruscalinux.org>.
