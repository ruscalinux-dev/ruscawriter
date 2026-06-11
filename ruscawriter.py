#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Avvio di RuscaWriter.

Esegui questo file per lanciare l'editor:
    python3 ruscawriter.py

Aggiunge la cartella src/ al percorso di importazione e avvia il pacchetto
'ruscawriter'. Tenere questo file nella radice del progetto, accanto alle
cartelle src/, lang/ e assets/.
"""
import os
import sys

# rendi importabile il pacchetto in src/ruscawriter
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from ruscawriter import main

if __name__ == "__main__":
    main()
