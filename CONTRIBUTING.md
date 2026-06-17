# Contribuire a RuscaWriter

Grazie per l'interesse verso **RuscaWriter**, l'editor di scrittura a tre
colonne del progetto RuscaLinux. I contributi sono benvenuti: segnalazioni di
problemi, idee, traduzioni, correzioni e nuove funzionalità.

RuscaWriter è software libero rilasciato sotto licenza **GNU GPL v3+**.
Contribuendo, accetti che il tuo contributo sia distribuito con la stessa
licenza.

## Come segnalare un problema (issue)

Apri una *issue* su GitHub descrivendo:

- cosa ti aspettavi e cosa è successo invece;
- i passi per riprodurre il problema;
- la tua distribuzione e versione (es. RuscaLinux, Debian 13), la versione di
  Python e di GTK 4;
- se possibile, il messaggio d'errore completo (avvia il programma da terminale
  con `python3 ruscawriter.py` per vederlo).

Prima di aprire una nuova issue, controlla se ne esiste già una simile.

## Come proporre una modifica (pull request)

1. Fai un *fork* del repository e crea un ramo dedicato
   (es. `git checkout -b correzione-export-pdf`).
2. Fai le tue modifiche, mantenendole **mirate**: una pull request per un
   argomento. È più facile da rivedere e da accettare.
3. **Esegui i test** prima di inviare (vedi sotto): devono restare tutti verdi.
4. Scrivi un messaggio di commit chiaro che spieghi *cosa* cambia e *perché*.
5. Apri la pull request descrivendo la modifica e, se risolve una issue,
   collegala.

## Ambiente di sviluppo

RuscaWriter richiede Python 3, PyGObject e GTK 4. Su Debian/Ubuntu/RuscaLinux:

```
sudo apt install python3-gi gir1.2-gtk-4.0
```

Per il controllo ortografico (opzionale):

```
sudo apt install gir1.2-gtksource-5 gir1.2-spelling-1 hunspell-it hunspell-en-us
```

Per avviare dal sorgente, dalla radice del progetto:

```
python3 ruscawriter.py
```

## Eseguire i test

Il modello dati e l'esportazione sono coperti da una suite di test che **non
richiede GTK** (importa solo i moduli del pacchetto). Dalla radice del progetto:

```
python3 tests/test_ruscawriter.py
```

Tutti i test devono passare. Se aggiungi una funzionalità al modello o
all'esportazione, aggiungi anche un test che la copra.

## Struttura del progetto

- `ruscawriter.py` — avvio dell'applicazione.
- `src/ruscawriter/editor.py` — interfaccia grafica (GTK 4).
- `src/ruscawriter/model.py` — modello dati ed esportazione (indipendente da
  GTK; è qui che girano i test).
- `src/ruscawriter/i18n.py` + `lang/*.json` — traduzioni.
- `tests/` — la suite di test.
- `docs/` — guida didattica e mini editor d'esempio.

## Stile del codice

- Segui lo stile già presente nel file che stai modificando.
- Preferisci modifiche piccole e leggibili a grandi riscritture.
- I commenti in italiano vanno bene: il progetto nasce in italiano ed è
  bilingue.

## Tradurre l'interfaccia

Per aggiungere o completare una lingua, copia `lang/en.json` in
`lang/<codice>.json`, traduci i valori (lasciando intatte le chiavi e i
segnaposto come `{p}` o `{n}`), e — se la traduzione è completa — aggiungi il
codice lingua a `COMPLETE_LANGUAGES` in `src/ruscawriter/i18n.py`. Nessuna
modifica al resto del codice è necessaria.

## Domande

Per dubbi o proposte più ampie, apri una issue con l'etichetta "discussione"
oppure scrivi a info@ruscalinux.org.
