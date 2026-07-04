#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# RuscaWriter — three-column writing editor for non-fiction
# Copyright (C) 2026  Nunzio Curcuruto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
EN — RuscaWriter project paths.

Code modules live in src/ruscawriter/, while resources (languages, fonts,
icons) sit in dedicated folders at the project root. This module locates
those folders reliably, so the rest of the code never computes scattered
relative paths.

IT — Percorsi del progetto RuscaWriter.

I moduli del codice vivono in src/ruscawriter/, mentre le risorse (lingue,
font, icone) stanno in cartelle dedicate nella radice del progetto. Questo
modulo individua quelle cartelle in modo affidabile, così il resto del codice
non deve calcolare percorsi relativi sparsi qua e là.

Struttura attesa / Expected layout:
    <root>/
        src/ruscawriter/   (questo pacchetto / this package)
        lang/             (file di traduzione .json / .json translations)
        assets/           (font .ttf, icone, svg / fonts, icons, svg)
"""
import os

# EN: folder of this file / IT: cartella di questo file: <root>/src/ruscawriter
_HERE = os.path.dirname(os.path.abspath(__file__))
# EN: project root, two levels up / IT: radice del progetto, due livelli
# sopra (src/ruscawriter -> src -> root)
PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

LANG_DIR = os.path.join(PROJECT_ROOT, "lang")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")


def asset(*parts):
    """EN: path of a file inside assets/ (e.g. asset('pen.svg')).
    IT: percorso di un file dentro assets/ (es. asset('penna.svg'))."""
    return os.path.join(ASSETS_DIR, *parts)


def lang_file(code):
    """EN: path of the language file for a code (e.g. lang_file('it')).
    IT: percorso del file di lingua per un codice (es. lang_file('it'))."""
    return os.path.join(LANG_DIR, f"{code}.json")
