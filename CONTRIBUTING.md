# Contributing to RuscaWriter

🇮🇹 [Leggilo in italiano](CONTRIBUTING.it.md)

Thank you for your interest in **RuscaWriter**, the three-column writing
editor of the RuscaLinux project. Contributions are welcome: bug reports,
ideas, translations, fixes and new features.

RuscaWriter is free software released under the **GNU GPL v3+** license. By
contributing, you agree that your contribution is distributed under the same
license.

**A note on method:** the existing RuscaWriter code was produced with the
help of AI under step-by-step human direction. Contributions written the same
way are as welcome as those written entirely by hand — in either case, review
and test your changes before opening a pull request, and make sure they are
compatible with the GPL v3+ license.

## How to report a problem (issue)

Open an *issue* on GitHub describing:

- what you expected and what happened instead;
- the steps to reproduce the problem;
- your distribution and version (e.g. RuscaLinux, Debian 13), the version of
  Python and of GTK 4;
- if possible, the full error message (start the program from a terminal with
  `python3 ruscawriter.py` to see it).

Before opening a new issue, check whether a similar one already exists.

## How to propose a change (pull request)

1. *Fork* the repository and create a dedicated branch
   (e.g. `git checkout -b fix-pdf-export`).
2. Make your changes, keeping them **focused**: one pull request per topic.
   It is easier to review and to accept.
3. **Run the tests** before submitting (see below): they must all stay green.
4. Write a clear commit message explaining *what* changes and *why*.
5. Open the pull request describing the change and, if it fixes an issue,
   link it.

## Development environment

RuscaWriter requires Python 3, PyGObject and GTK 4. On
Debian/Ubuntu/RuscaLinux:

```
sudo apt install python3-gi gir1.2-gtk-4.0
```

For spell checking (optional):

```
sudo apt install gir1.2-gtksource-5 gir1.2-spelling-1 hunspell-en-us hunspell-it
```

To run from source, from the project root:

```
python3 ruscawriter.py
```

## Running the tests

The data model and the exports are covered by a test suite that **does not
require GTK** (it imports only the package modules). From the project root:

```
python3 tests/test_ruscawriter.py
```

All tests must pass. If you add a feature to the model or to the exports,
add a test that covers it as well.

## Project structure

- `ruscawriter.py` — application launcher.
- `src/ruscawriter/editor.py` — graphical interface (GTK 4).
- `src/ruscawriter/model.py` — data model and exports (independent of GTK;
  this is where the tests run).
- `src/ruscawriter/i18n.py` + `lang/*.json` — translations.
- `tests/` — the test suite.
- `docs/` — a heavily commented example mini-editor (bilingual EN + IT).

## Code style

- Follow the style already present in the file you are editing.
- Prefer small, readable changes over large rewrites.
- Bilingual comments are fine: the project was born in Italian and is
  bilingual (English + Italian).

## Translating the interface

To add or complete a language, copy `lang/en.json` to `lang/<code>.json`,
translate the values (leaving the keys and placeholders such as `{p}` or
`{n}` untouched), and — if the translation is complete — add the language
code to `COMPLETE_LANGUAGES` in `src/ruscawriter/i18n.py`. No change to the
rest of the code is needed.

## Questions

For questions or broader proposals, open an issue with the "discussion" label
or write to info@ruscalinux.org.
