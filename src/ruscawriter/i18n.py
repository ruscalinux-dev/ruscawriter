#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Internazionalizzazione (i18n) di RuscaWriter.

Le traduzioni NON sono più scritte nel codice: vivono in file JSON nella
cartella 'lang/' (uno per lingua, es. it.json, en.json, ...). Questo rende
il programma modulare e traducibile senza toccare il Python: per aggiungere o
completare una lingua basta editare il suo file JSON.

- LANGUAGES elenca le 40 lingue più parlate al mondo (codice e nome nativo).
- load_language(code) carica il dizionario di una lingua, con fallback
  automatico all'inglese (e poi alla chiave stessa) per le voci mancanti.
- ensure_language_files() crea gli "scheletri" dei file mancanti, così il
  selettore mostra subito tutte le lingue anche se non ancora tradotte.
"""
import os
import json

# cartella dei file di lingua, accanto a questo modulo
from . import paths
LANG_DIR = paths.LANG_DIR

# Le 40 lingue più parlate al mondo (per numero totale di parlanti).
# Ogni voce: codice -> (nome nativo, nome inglese). Il nome nativo è ciò che
# vede l'utente nel selettore, così riconosce la propria lingua.
LANGUAGES = {
    "en": ("English", "English"),
    "zh": ("中文", "Chinese"),
    "hi": ("हिन्दी", "Hindi"),
    "es": ("Español", "Spanish"),
    "fr": ("Français", "French"),
    "ar": ("العربية", "Arabic"),
    "bn": ("বাংলা", "Bengali"),
    "pt": ("Português", "Portuguese"),
    "ru": ("Русский", "Russian"),
    "ur": ("اردو", "Urdu"),
    "id": ("Bahasa Indonesia", "Indonesian"),
    "de": ("Deutsch", "German"),
    "ja": ("日本語", "Japanese"),
    "sw": ("Kiswahili", "Swahili"),
    "mr": ("मराठी", "Marathi"),
    "te": ("తెలుగు", "Telugu"),
    "tr": ("Türkçe", "Turkish"),
    "ta": ("தமிழ்", "Tamil"),
    "vi": ("Tiếng Việt", "Vietnamese"),
    "ko": ("한국어", "Korean"),
    "it": ("Italiano", "Italian"),
    "fa": ("فارسی", "Persian"),
    "pl": ("Polski", "Polish"),
    "uk": ("Українська", "Ukrainian"),
    "ro": ("Română", "Romanian"),
    "nl": ("Nederlands", "Dutch"),
    "th": ("ไทย", "Thai"),
    "gu": ("ગુજરાતી", "Gujarati"),
    "pa": ("ਪੰਜਾਬੀ", "Punjabi"),
    "ms": ("Bahasa Melayu", "Malay"),
    "kn": ("ಕನ್ನಡ", "Kannada"),
    "ml": ("മലയാളം", "Malayalam"),
    "el": ("Ελληνικά", "Greek"),
    "he": ("עברית", "Hebrew"),
    "sv": ("Svenska", "Swedish"),
    "cs": ("Čeština", "Czech"),
    "hu": ("Magyar", "Hungarian"),
    "fi": ("Suomi", "Finnish"),
    "da": ("Dansk", "Danish"),
    "no": ("Norsk", "Norwegian"),
}

# lingue di destra-a-sinistra (per eventuale adattamento futuro dell'interfaccia)
RTL_LANGUAGES = {"ar", "ur", "fa", "he"}

# Locale predefinito del dizionario ortografico (Hunspell) per ciascuna lingua.
# I dizionari NON sono forniti dal programma: vanno installati nel sistema
# (es. su Debian/Ubuntu: "sudo apt install hunspell-fr" per il francese).
# Qui mappiamo solo il codice lingua al nome di locale più comune del dizionario.
SPELL_LOCALES = {
    "en": "en_US", "it": "it_IT", "es": "es_ES", "fr": "fr_FR",
    "de": "de_DE", "pt": "pt_PT", "ru": "ru_RU", "pl": "pl_PL",
    "nl": "nl_NL", "sv": "sv_SE", "da": "da_DK", "no": "nb_NO",
    "fi": "fi_FI", "cs": "cs_CZ", "hu": "hu_HU", "ro": "ro_RO",
    "el": "el_GR", "uk": "uk_UA", "tr": "tr_TR", "id": "id_ID",
    "ms": "ms_MY", "vi": "vi_VN", "he": "he_IL", "ar": "ar",
    "fa": "fa_IR", "ur": "ur_PK", "hi": "hi_IN", "bn": "bn_BD",
    "mr": "mr_IN", "pa": "pa_IN", "gu": "gu_IN", "ta": "ta_IN",
    "te": "te_IN", "kn": "kn_IN", "ml": "ml_IN", "th": "th_TH",
    "zh": "zh_CN", "ja": "ja_JP", "ko": "ko_KR", "sw": "sw_TZ",
}


def spell_locale_for(code):
    """Restituisce il nome del locale del dizionario per una lingua, o il
    codice stesso se non mappato (Gspell/GtkSpell tenteranno comunque)."""
    return SPELL_LOCALES.get(code, code)

# le lingue con traduzione completa e verificata
COMPLETE_LANGUAGES = {"it", "en", "es", "fr", "de", "pt", "ru"}


def available_languages():
    """Restituisce la lista (codice, nome_nativo) ordinata per nome nativo,
    con inglese e italiano in cima (le complete)."""
    items = []
    for code, (native, _eng) in LANGUAGES.items():
        items.append((code, native))
    # ordina: prima le complete, poi le altre per nome nativo
    items.sort(key=lambda x: (x[0] not in COMPLETE_LANGUAGES, x[1].lower()))
    return items


def _load_json(code):
    path = os.path.join(LANG_DIR, f"{code}.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def load_language(code):
    """Carica il dizionario della lingua richiesta, completato con l'inglese
    per le chiavi mancanti (fallback). Restituisce sempre un dizionario usabile.

    L'ordine di risoluzione di ogni chiave, gestito altrove da Translator, è:
    lingua scelta -> inglese -> la chiave stessa."""
    base = _load_json("en")           # base di fallback
    chosen = _load_json(code) if code != "en" else {}
    merged = dict(base)
    merged.update(chosen)             # le voci tradotte sovrascrivono il fallback
    return merged


class Translator:
    """Piccolo gestore di traduzioni con cambio lingua a runtime.

    Uso tipico:
        tr = Translator("it")
        tr.t("mi_save")          -> "Salva"
        tr.set_language("fr")    -> ricarica il francese
        tr.t("mi_save", x=3)     -> supporta i segnaposto {x} via str.format
    """

    def __init__(self, code="en"):
        self.code = code
        self._strings = load_language(code)

    def set_language(self, code):
        self.code = code
        self._strings = load_language(code)

    def t(self, key, **kwargs):
        s = self._strings.get(key, key)   # fallback finale: la chiave stessa
        if kwargs:
            try:
                return s.format(**kwargs)
            except Exception:
                return s
        return s

    def is_rtl(self):
        return self.code in RTL_LANGUAGES


def ensure_language_files():
    """Crea i file di lingua mancanti come 'scheletri': un JSON con le stesse
    chiavi dell'inglese ma con un commento che indica che vanno tradotte.
    In pratica copiamo l'inglese come punto di partenza, così l'app funziona
    e la lingua è selezionabile; chi traduce sostituisce i valori.

    I file esistenti NON vengono toccati (le traduzioni già fatte si conservano).
    """
    os.makedirs(LANG_DIR, exist_ok=True)
    base = _load_json("en")
    if not base:
        return
    for code in LANGUAGES:
        path = os.path.join(LANG_DIR, f"{code}.json")
        if os.path.exists(path):
            continue   # non sovrascrivere lingue già presenti/tradotte
        # scheletro: copia dell'inglese, da tradurre
        skeleton = {"__comment__": (
            f"Traduzione di RuscaWriter in "
            f"{LANGUAGES[code][1]} ({LANGUAGES[code][0]}). "
            f"Sostituisci i valori inglesi con la traduzione. "
            f"Le chiavi mancanti useranno l'inglese come ripiego.")}
        skeleton.update(base)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(skeleton, f, ensure_ascii=False, indent=2)
