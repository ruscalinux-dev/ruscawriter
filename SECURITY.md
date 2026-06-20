# Security Policy

RuscaWriter is a local desktop writing editor. It does not connect to the
network, run a server, or handle user accounts, so its attack surface is
small. Still, we take security seriously and welcome responsible reports.

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

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| older   | :x:                |

## Scope

Because RuscaWriter is an offline desktop application, the most realistic
risk is **opening a malicious project file** (a `.rwr` archive or an imported
image) crafted by a third party. Reports about how such files could crash the
app, exhaust resources, or write outside the intended location are especially
welcome.

Thank you for helping keep RuscaWriter and its users safe.
