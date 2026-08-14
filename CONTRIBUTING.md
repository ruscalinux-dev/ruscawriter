# Contributing

Bug reports, ideas, translations, fixes and new features are all welcome.

RuscaWriter is free software under the **GNU GPL v3 or later**. By
contributing, you agree your work is distributed under the same licence.

**On method:** the existing code was written with AI tools under step-by-step
human direction. Contributions made the same way are as welcome as those typed
by hand. Either way, review and test before opening a pull request.

## Reporting a bug

Open an issue and say:

- what you expected, and what happened instead;
- how to make it happen again;
- your distribution, and your Python and GTK 4 versions;
- the error message, if there is one. Start the program from a terminal with
  `python3 ruscawriter.py` to see it.

Check first whether someone has already reported it.

## Proposing a change

1. Fork, then branch: `git checkout -b fix-pdf-export`.
2. Keep the change focused. One pull request, one topic.
3. Run the tests. They must all pass.
4. Write the commit message as described below.
5. Open the pull request. If it closes an issue, link it.

## Commit messages

One commit, one thing, one line. The line starts with one of seven words.

| Start with   | For                                             | In the changelog |
| ------------ | ----------------------------------------------- | ---------------- |
| `added:`     | something new you can use                       | yes              |
| `changed:`   | something that existed and now works differently | yes             |
| `fixed:`     | a bug gone                                      | yes              |
| `removed:`   | something taken away                            | yes              |
| `internal:`  | refactoring, tests, cleanups                    | no               |
| `docs:`      | README, SECURITY, man page, comments            | no               |
| `packaging:` | build-deb.sh, icons, .desktop, dependencies     | no               |

```
added: LaTeX export
fixed: cover preview was blurry on HiDPI screens
internal: reworked the PDF writer
```

Lowercase after the colon. No full stop. Under 72 characters. If you need the
word "and", that is two commits. Anything longer goes in a paragraph below,
after a blank line.

The first four are the ones that end up in the changelog. A good commit line is
a changelog line already written.

To load the template with these reminders:

```
git config commit.template .gitmessage
```

## Running the tests

The data model and the exports are tested without GTK:

```
python3 tests/test_ruscawriter.py
```

They must all pass. If you add something to the model or to an export, add a
test for it.

## Where things are

- `ruscawriter.py` — launcher.
- `src/ruscawriter/editor.py` — the GTK 4 interface.
- `src/ruscawriter/model.py` — data model and exports. No GTK. This is what
  the tests run against.
- `src/ruscawriter/i18n.py` and `lang/*.json` — translations.
- `tests/` — the test suite.
- `docs/` — the images used by the README.

## Code style

Follow the style of the file you are editing. Prefer small readable changes to
large rewrites.

## Translating

Copy `lang/en.json` to `lang/<code>.json`. Translate the values, leave the keys
and the placeholders (`{p}`, `{n}`) alone. If the translation is complete, add
the code to `COMPLETE_LANGUAGES` in `src/ruscawriter/i18n.py`. Nothing else
changes.

## Making a release

For maintainers, by hand:

```
# 1. version and date — the only two lines to edit
#    APP_VERSION_SHORT and APP_RELEASE_DATE in src/ruscawriter/model.py

python3 tests/test_ruscawriter.py     # 2. must pass before anything else
                                      # 3. write the CHANGELOG entry
git add -A && git commit -m "RuscaWriter 1.0"
git tag -a v1.0 -m "RuscaWriter 1.0"
./build-deb.sh                        # 4. the .deb package
sha256sum ruscawriter_*.deb > SHA256SUMS
git push && git push --tags
```

The version and the release date live in one place: `APP_VERSION_SHORT` and
`APP_RELEASE_DATE` in `src/ruscawriter/model.py`. The About screen, the window
title, the `.deb` and the man page all follow from there — never edit them
anywhere else.

## Questions

Open an issue with the "discussion" label, or write to info@ruscalinux.org.
