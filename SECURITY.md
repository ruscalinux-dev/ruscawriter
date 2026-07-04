# Security Policy

RuscaWriter is a local desktop writing editor. It does not connect to the
network, run a server, or handle user accounts, so its attack surface is
small. Still, we take security seriously and welcome responsible reports.

*Ultimo aggiornamento / last updated: version 0.3 (July 2026). Una versione
italiana di questo documento è disponibile in [SECURITY.it.md](SECURITY.it.md).*

## Reporting a vulnerability

**Please do not open a public issue for security problems.** Public issues
expose the flaw to everyone — including potential attackers — before a fix is
available.

Instead, report it privately through GitHub:

1. Go to the **[Security tab](https://github.com/ruscalinux-dev/ruscawriter/security)**
   of this repository.
2. Click **"Report a vulnerability"** to open a private advisory visible only
   to the maintainers.

If you cannot use GitHub's private reporting, you may also email
**<info@ruscalinux.org>**.

When reporting, it helps to include:

- a description of the issue and why it is a security concern;
- the steps to reproduce it (a sample `.rwr` file or image, if relevant);
- the affected version and your operating system;
- any suggested fix, if you have one.

## What to expect

- We aim to acknowledge a report within **7 days**.
- We will keep you informed about our assessment and the fix timeline.
- Once a fix is released, we are happy to credit you in the advisory unless
  you prefer to stay anonymous.

## Supported versions

RuscaWriter is in early development. Security fixes are applied to the
**latest release** only. Please make sure you are on the most recent version
before reporting.

| Version        | Supported          |
| -------------- | ------------------ |
| 0.3 (latest)   | :white_check_mark: |
| 0.2.x and older| :x:                |

## Scope

Because RuscaWriter is an offline desktop application, the most realistic
risk is **opening a malicious file** crafted by a third party. As of version
0.3 the untrusted inputs are:

- **`.rwr` project files** (tar.gz archives) received from someone else;
- **image files** attached to chapters or set as cover
  (PNG, JPEG, WebP — a feature introduced in 0.3);
- **text/Markdown files** imported as chapters.

Reports about how such files could crash the app, execute code, exhaust
resources (memory/CPU via decompression or oversized images), or write
outside the intended location are especially welcome.

## Security posture of version 0.3

This section summarizes the properties verified by static analysis of the
0.3 source and by the automated test suite. It describes what we checked —
it is not a claim of absolute security.

**No network, no telemetry.** The source contains no networking code
(`urllib`, `socket`, `requests`, `http.client`): the application never opens
connections, checks for updates, or transmits data.

**No dynamic code execution or unsafe deserialization.** There is no
`eval`, `exec`, `pickle`, `marshal` or `shelve` anywhere in the code base.
All persistent data uses passive formats: JSON, Markdown, plain text.

**Careful archive handling.** When loading a `.rwr` archive, only regular
file members are accepted (symlinks, devices and directories are skipped),
member names are reduced to their base name (`os.path.basename`), contents
are read into memory rather than extracted to disk, and only names matching
strict patterns (`NN.md`, `NNn.md`, `img_NNN.png/jpg/webp`,
`cover.*`, `*.json`) are actually used. There is no call to `extractall`.

**Image validation by content.** Attached and cover images (new in 0.3) are
identified by their magic bytes, never by file extension; unsupported or
malformed headers are rejected before the data enters the project.

**Constrained use of external programs.** The only `subprocess` call in the
code base is the optional AZW3 export, which invokes Calibre's
`ebook-convert` found in known system locations, as an argument list
(never `shell=True`), with a 300-second timeout.

**Atomic saves.** Projects are written to a temporary file and moved into
place only on success, so a crash mid-save cannot corrupt the previous copy.

**Minimal dependencies.** Everything runs on the Python standard library
plus PyGObject/GTK 4. Pillow is optional (image conversion for PDF/DOCX) and
its absence is handled gracefully; when Pillow is installed, image decoding
partly happens in Pillow, so keeping it updated matters.

**Writes are limited** to paths the user chooses in save/export dialogs,
the autosave file, the configuration folder, and Enchant's personal spelling
dictionaries under `~/.config/enchant/` (documented in the source; entries
are only added, never removed).

## Known considerations

Areas we consider residual risk within the current design, and where reports
or patches are particularly appreciated:

- **Resource exhaustion.** Archive contents and attached images are loaded
  into memory without an explicit size ceiling; a maliciously large or
  highly compressed `.rwr` could exhaust RAM ("decompression bomb").
- **Third-party decoders.** When present, Pillow (image conversion) and
  Calibre (AZW3 export) process untrusted data; vulnerabilities in those
  projects affect the corresponding optional features.

## Verifying your download

Release archives ship with a `SHA256SUMS` file. After downloading, run:

```
sha256sum -c SHA256SUMS
```

and make sure every line reports `OK` before running the code.

Thank you for helping keep RuscaWriter and its users safe.
