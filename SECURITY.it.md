# Politica di sicurezza

RuscaWriter è un editor di scrittura desktop locale. Non si collega alla
rete, non esegue un server e non gestisce account utente, quindi la sua
superficie d'attacco è ridotta. Prendiamo comunque la sicurezza sul serio e
accogliamo con favore le segnalazioni responsabili.

*Ultimo aggiornamento: versione 0.3 (luglio 2026). The English version of
this document is available in [SECURITY.md](SECURITY.md).*

## Segnalare una vulnerabilità

**Per i problemi di sicurezza, non aprire una issue pubblica.** Una issue
pubblica espone la falla a tutti — potenziali aggressori compresi — prima che
sia disponibile una correzione.

Segnala invece il problema in modo privato tramite GitHub:

1. Vai alla **[scheda Security](https://github.com/ruscalinux-dev/ruscawriter/security)**
   di questo repository.
2. Fai clic su **"Report a vulnerability"** per aprire un advisory privato,
   visibile solo ai manutentori.

Se non puoi usare la segnalazione privata di GitHub, puoi anche scrivere a
**<info@ruscalinux.org>**.

Nella segnalazione è utile includere:

- una descrizione del problema e del perché riguarda la sicurezza;
- i passaggi per riprodurlo (un file `.rwr` o un'immagine di esempio, se
  pertinenti);
- la versione interessata e il tuo sistema operativo;
- una proposta di correzione, se ne hai una.

## Cosa aspettarsi

- Puntiamo a confermare la ricezione di una segnalazione entro **7 giorni**.
- Ti terremo informato sulla nostra valutazione e sui tempi della correzione.
- Alla pubblicazione della correzione saremo lieti di citarti
  nell'advisory, a meno che tu non preferisca restare anonimo.

## Versioni supportate

RuscaWriter è in fase di sviluppo iniziale. Le correzioni di sicurezza si
applicano solo all'**ultima versione rilasciata**. Prima di segnalare,
assicurati di usare la versione più recente.

| Versione         | Supportata         |
| ---------------- | ------------------ |
| 0.3 (ultima)     | :white_check_mark: |
| 0.2.x e anteriori| :x:                |

## Ambito

Essendo RuscaWriter un'applicazione desktop offline, il rischio più
realistico è **l'apertura di un file malevolo** confezionato da terzi. Nella
versione 0.3 gli ingressi non fidati sono:

- **file di progetto `.rwr`** (archivi tar.gz) ricevuti da altri;
- **file immagine** allegati ai capitoli o impostati come copertina
  (PNG, JPEG, WebP — funzionalità introdotta nella 0.3);
- **file di testo/Markdown** importati come capitoli.

Sono particolarmente gradite le segnalazioni su come tali file possano far
crollare l'applicazione, eseguire codice, esaurire le risorse (memoria/CPU
tramite decompressione o immagini enormi) o scrivere fuori dalla
destinazione prevista.

## Stato della sicurezza della versione 0.3

Questa sezione riassume le proprietà verificate con l'analisi statica del
sorgente 0.3 e con la suite di test automatici. Descrive ciò che abbiamo
controllato: non è una dichiarazione di sicurezza assoluta.

**Niente rete, niente telemetria.** Il sorgente non contiene codice di rete
(`urllib`, `socket`, `requests`, `http.client`): l'applicazione non apre mai
connessioni, non controlla aggiornamenti e non trasmette dati.

**Nessuna esecuzione dinamica di codice né deserializzazione insicura.** In
tutto il codice non compaiono `eval`, `exec`, `pickle`, `marshal` o
`shelve`. Tutti i dati persistenti usano formati passivi: JSON, Markdown,
testo semplice.

**Gestione prudente degli archivi.** Nel caricamento di un archivio `.rwr`
vengono accettati solo i membri che sono file regolari (link simbolici,
dispositivi e cartelle sono scartati), dei nomi si tiene solo l'ultima
componente (`os.path.basename`), i contenuti sono letti in memoria e mai
estratti su disco, e vengono usati soltanto i nomi conformi a schemi rigidi
(`NN.md`, `NNn.md`, `img_NNN.png/jpg/webp`, `cover.*`, `*.json`). Non esiste
alcuna chiamata a `extractall`.

**Validazione delle immagini dal contenuto.** Le immagini allegate e di
copertina (novità della 0.3) sono riconosciute dai byte iniziali (magic
bytes), mai dall'estensione del file; intestazioni non supportate o
malformate vengono rifiutate prima che i dati entrino nel progetto.

**Uso vincolato di programmi esterni.** L'unica chiamata `subprocess` del
codice è l'export AZW3 opzionale, che invoca `ebook-convert` di Calibre
cercato in posizioni note del sistema, come lista di argomenti (mai
`shell=True`), con un timeout di 300 secondi.

**Salvataggi atomici.** I progetti vengono scritti su un file temporaneo e
spostati a destinazione solo a operazione riuscita: un crollo a metà
salvataggio non può corrompere la copia precedente.

**Dipendenze minime.** Tutto funziona con la libreria standard di Python più
PyGObject/GTK 4. Pillow è opzionale (conversione immagini per PDF/DOCX) e la
sua assenza è gestita con garbo; quando Pillow è installato, parte della
decodifica delle immagini avviene in Pillow, quindi tenerlo aggiornato è
importante.

**Le scritture sono limitate** ai percorsi scelti dall'utente nei dialoghi
di salvataggio/esportazione, al file di salvataggio automatico, alla
cartella di configurazione e ai dizionari personali di Enchant in
`~/.config/enchant/` (documentati nel sorgente; le voci vengono solo
aggiunte, mai rimosse).

## Considerazioni note

Aree che consideriamo rischio residuo nel progetto attuale, e dove
segnalazioni o patch sono particolarmente apprezzate:

- **Esaurimento delle risorse.** I contenuti degli archivi e le immagini
  allegate vengono caricati in memoria senza un tetto esplicito di
  dimensione; un `.rwr` malevolo molto grande o molto compresso potrebbe
  esaurire la RAM ("bomba di decompressione").
- **Decodificatori di terze parti.** Quando presenti, Pillow (conversione
  immagini) e Calibre (export AZW3) elaborano dati non fidati; le
  vulnerabilità di quei progetti si riflettono sulle rispettive funzionalità
  opzionali.

## Verificare il proprio download

Gli archivi di rilascio includono un file `SHA256SUMS`. Dopo il download,
esegui:

```
sha256sum -c SHA256SUMS
```

e assicurati che ogni riga riporti `OK` prima di eseguire il codice.

Grazie per contribuire alla sicurezza di RuscaWriter e dei suoi utenti.
