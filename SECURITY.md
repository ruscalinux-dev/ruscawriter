# Security

RuscaWriter is a desktop editor. It never goes online, runs no server and has
no accounts, so there is not much surface to attack. What there is, we take
seriously.

## Reporting a problem

**Do not open a public issue.** That tells everyone about the flaw before there
is a fix.

Report it privately:

1. Go to the
   [Security tab](https://github.com/ruscalinux-dev/ruscawriter/security).
2. Click **Report a vulnerability**. Only the maintainers see it.

Or email **<info@ruscalinux.org>**.

It helps to include:

- what the problem is, and why it matters;
- how to make it happen again — a sample `.rwr` file or image, if that is what
  triggers it;
- your version and operating system;
- a fix, if you have one.

You should hear back within 7 days. Once it is fixed, we will credit you in the
advisory unless you would rather stay anonymous.

## Supported versions

Fixes go into the latest release.

| Version                    | Supported          |
| -------------------------- | ------------------ |
| latest release             | :white_check_mark: |
| the one before it          | :white_check_mark: |
| anything older             | :x:                |

Your version is in Help → About. Releases are on the
[Releases](https://github.com/ruscalinux-dev/ruscawriter/releases) page.

## What could go wrong

The program is offline, so the realistic risk is **opening a file someone else
made**. Those files are:

- `.rwr` projects;
- images attached to chapters or used as a cover (PNG, JPEG, WebP);
- text and Markdown files imported as chapters.

Reports about such a file crashing the program, running code, eating all the
memory, or writing somewhere it should not, are very welcome.

## What we have checked

Verified by reading the source and by the automated tests. It is a list of what
we looked at, not a promise that nothing is wrong.

**No network. No telemetry.** There is no networking code in the source — no
`urllib`, `socket`, `requests` or `http.client`. The program opens no
connections, checks for no updates and sends nothing anywhere.

**No code is generated or executed at runtime.** No `eval`, no `exec`, no
`pickle`, no `marshal`, no `shelve`. Everything saved is passive: JSON,
Markdown, plain text.

**Archives are opened carefully.** Loading a `.rwr` accepts regular files only
— symlinks, devices and directories are skipped. Member names are cut down to
their base name. Contents are read into memory, not unpacked to disk. Only
names matching strict patterns are used. `extractall` is never called.

**Images are identified by their bytes**, never by their file name. A bad or
unsupported header is rejected before the data gets into the project.

**One external program, tightly held.** The only `subprocess` call is the
optional AZW3 export. It runs Calibre's `ebook-convert` from known system
paths, as an argument list, never through a shell, with a 300-second timeout.

**Saves are atomic.** A project is written to a temporary file and moved into
place only once it is complete. A crash mid-save cannot damage the previous
copy.

**Few dependencies.** Python standard library plus PyGObject and GTK 4. Pillow
and Pyphen are optional; without them, the features that need them are simply
disabled.

**Writes are limited** to the paths you pick in a save or export dialog, the
autosave file, the configuration folder, and the personal spelling dictionaries
under `~/.config/enchant/` — where entries are only added, never removed.

## Known weak spots

Where we would most welcome a report or a patch:

- **Memory.** Archive contents and images are loaded without a size limit. A
  deliberately huge or heavily compressed `.rwr` could exhaust RAM.
- **Other people's decoders.** When installed, Pillow decodes images and
  Calibre converts to AZW3. Their bugs become bugs in those optional features.

## Checking your download

Releases ship a `SHA256SUMS` file:

```
sha256sum -c SHA256SUMS
```

Every line should say `OK` before you run anything.
