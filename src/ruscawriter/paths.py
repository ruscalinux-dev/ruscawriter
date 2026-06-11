#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Percorsi del progetto RuscaWriter.

I moduli del codice vivono in src/ruscawriter/, mentre le risorse (lingue,
font, icone) stanno in cartelle dedicate nella radice del progetto. Questo
modulo individua quelle cartelle in modo affidabile, così il resto del codice
non deve calcolare percorsi relativi sparsi qua e là.

Struttura attesa:
    <root>/
        src/ruscawriter/   (questo pacchetto)
        lang/             (file di traduzione .json)
        assets/           (font .ttf, icone, svg)
"""
import os

# cartella di questo file: <root>/src/ruscawriter
_HERE = os.path.dirname(os.path.abspath(__file__))
# radice del progetto: due livelli sopra (src/ruscawriter -> src -> root)
PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

LANG_DIR = os.path.join(PROJECT_ROOT, "lang")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")


def asset(*parts):
    """Percorso di un file dentro assets/ (es. asset('penna.svg'))."""
    return os.path.join(ASSETS_DIR, *parts)


def lang_file(code):
    """Percorso del file di lingua per un codice (es. lang_file('it'))."""
    return os.path.join(LANG_DIR, f"{code}.json")
