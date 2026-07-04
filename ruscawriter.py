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
