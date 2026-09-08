# Architettura del Search Engine e Motore di Validazione Puglia Termica (PT)

Questo documento descrive l'architettura tecnica, le strutture dati, il funzionamento degli algoritmi di ricerca ibrida e le regole operative del motore di validazione per il catalogo Puglia Termica 2026.

---

## 1. Visione Generale e Struttura dei Dati

L'obiettivo del sistema è identificare, validare e riconciliare qualsiasi prodotto termoidraulico (Climatizzazione, Caldaie, Scaldabagni, Pompe di Calore, Fancoil, Componentistica) descritto in titoli commerciali e inserzioni e-commerce, associandolo in modo deterministico e con evidenze oggettive agli articoli del catalogo **Puglia Termica**.

```
                           ┌─────────────────────────────────────────────────────────┐
                           │                 INPUT (Titolo / Riferimento / MPN)      │
                           └────────────────────────────┬────────────────────────────┘
                                                        │
                      ┌─────────────────────────────────┴─────────────────────────────────┐
                      ▼                                                                   ▼
         [ SE MPN ORIGINALE ESISTE ]                                         [ SE MPN ASSENTE O DISCORDANTE ]
                      │                                                                   │
                      ▼                                                                   ▼
       ┌──────────────────────────────┐                                    ┌──────────────────────────────┐
       │   VALIDATION ENGINE          │                                    │   DYNAMIC SEARCH & RESOLVER  │
       │   (Multiset Verification)    │                                    │   (Catalog Querying)         │
       └──────────────┬───────────────┘                                    └──────────────┬───────────────┘
                      │                                                                   │
                      ▼                                                                   ▼
       ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
       │                                  DATA STORES DI RIFERIMENTO                                      │
       │                                                                                                  │
       │  1. exact_code_lookup.json        2. climatizzatori_compatibilita_master.json                    │
       │     (Hash Map O(1), <5ms)            (1.007 UE, 1.447 UI, porte, combinazioni)                   │
       │                                                                                                  │
       │  3. unified_catalog_master.json   4. lancedb_store (catalog_products)                            │
       │     (57.608 articoli ERP, prezzi)     (Embedding 384d MiniLM-L6-v2 + BM25 Tantivy)               │
       └──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### I 4 Data Store del Repository

1. **`Knowledge/vector_db/exact_code_lookup.json`**:
   - **Tecnologia**: Tabella hash in RAM con oltre 110.000 chiavi univoche.
   - **Contenuto**: Indicizzazione diretta di codici articolo PT a 8 cifre (es. `50418725`), codici fornitore / MPN alfanumerici (es. `7733703589`, `CL3200iU W26E`), e versioni stripped prive di punteggiatura.
   - **Prestazioni**: Risoluzione immediata O(1) in **< 5ms**.
   - **Metadati restituiti**: Taglia BTU, taglia kW, tipo unità (`UI` / `UE`), flag macchine, combustibile, camera, litri, accessori.

2. **`Knowledge/climatizzatori_compatibilita_master.json`**:
   - **Tecnologia**: Grafo relazionale estratto analiticamente dalle tabelle tecniche del catalogo cartaceo (pagine 468–628).
   - **Contenuto**:
     - **1.007 Unità Esterne (UE)**: con numero attacchi/porte (da 1 a 5), potenza nominale kW, serie di appartenenza, pagine catalogo e combinazioni ammesse.
     - **1.447 Unità Interne (UI)**: con taglia nominale BTU certificata (7k, 9k, 12k, 15k, 18k, 21k, 24k), tipologia (Parete, Pavimento, Cassetta, Canalizzato), serie/famiglia e finiture colore (Bianco, Nero, Silver).
     - **Tabelle combinazioni multisplit**: matrici ufficiali di abbinamento ammesse dal costruttore.

3. **`Knowledge/unified_catalog_master.json`**:
   - **Tecnologia**: Anagrafica unificata di **57.608 articoli**.
   - **Contenuto**: Anagrafica completa con codice PT, codice fornitore, descrizione estesa, marchio, albero categorie ERP (`category_root`, `category_path`), prezzo di listino lordo, prezzo netto riservato, pagina catalogo primaria e stato di presenza nel PDF.

4. **`Knowledge/vector_db/lancedb_store` (Tabella `catalog_products`)**:
   - **Tecnologia**: Vector Database moderno (LanceDB) con motore di ricerca ibrido (vettoriale denso + lessicale BM25 Tantivy).
   - **Contenuto**: 32.232 prodotti vettorializzati tramite modello ONNX `sentence-transformers/all-MiniLM-L6-v2` a 384 dimensioni.

---

## 2. Come Funziona il Search Engine (Pipeline a 7 Stadi)

Il motore di ricerca (`catalog_search_engine.py`) riceve una stringa di testo libero o un codice e applica una sequenza a più stadi ottimizzata per la termoidraulica:

```
[Query Utente]
      │
      ▼
Stadio 1: Exact Match Short-Circuit (<5ms su exact_code_lookup.json)
      │ (se non trovato)
      ▼
Stadio 2: Brand Detection & Normalizzazione Alias
      │
      ▼
Stadio 3: Espansione Lessicale Tecnica (BTU <-> kW, Abbreviazioni PT)
      │
      ▼
Stadio 4: Ricerca Ibrida LanceDB (Vettori Densi + Tantivy BM25)
      │
      ▼
Stadio 5: Token-Based Lexical Retry su Master Catalog (57.608 articoli)
      │
      ▼
Stadio 6: Reranking Multi-Campo Ponderato (Field-Aware Boost & Penalties)
      │
      ▼
Stadio 7: Accessory & Bundle Expander (Arricchimento da Pagina PDF)
```

### Dettaglio degli Stadi:

1. **Stadio 1 — Short-Circuit Esatto (<5ms)**:
   Se l'input è un codice PT a 8 cifre o un codice produttore MPN (anche con formattazioni sporche come trattini o spazi), il resolver accede istantaneamente a `exact_code_lookup.json` e restituisce il record completo senza overhead di calcolo.
2. **Stadio 2 — Brand Detection & Normalizzazione**:
   Rileva i marchi menzionati (Daikin, Bosch, Mitsubishi, Panasonic, Samsung, Midea, Haier, Ferroli, Ariston, Baxi, Riello, Vaillant, Hermann Saunier Duval, DAB, ecc.) mappando gli alias commerciali al marchio anagrafico standard.
3. **Stadio 3 — Espansione Lessicale Tecnica**:
   Espande automaticamente le grandezze fisiche e le abbreviazioni ufficiali del catalogo PT:
   - Taglie clima: `9000 btu` $\rightarrow$ `25 2.5 kw 9000`, `12000 btu` $\rightarrow$ `35 3.5 kw 12000`, `18000 btu` $\rightarrow$ `50 5.0 kw 18000`.
   - Abbreviazioni ERP: `ACQUAPROJET` $\rightarrow$ `ACQUAPR`, `CALDAIA` $\rightarrow$ `CALD`, `VENTILCONVETTORE` $\rightarrow$ `VENTILCONV`, `CONDENSAZIONE` $\rightarrow$ `COND`, `SDOPPIATO` $\rightarrow$ `SDOPP`.
4. **Stadio 4 — Ricerca Ibrida LanceDB**:
   Genera il vettore denso della query tramite FastEmbed e lo unisce all'indice lessicale Tantivy BM25, filtrando per marchio e categoria radice.
5. **Stadio 5 — Query Retry su Anagrafica Master**:
   Esegue un recupero lessicale deterministico su tutti i 57.608 record del catalogo master, assicurando che nessun articolo online o codice non presente nel PDF venga ignorato.
6. **Stadio 6 — Reranking Multi-Campo Ponderato**:
   Ricalcola lo score di rilevanza con pesi specifici:
   - Match codice fornitore (`mfg_code`): **+25.0**
   - Match esatto token modello nel nome: **+35.0**
   - Corrispondenza tipo macchina (es. Caldaia, Scaldabagno, Climatizzatore): **+40.0**
   - **Machine vs Accessory Penalty**: se la query cerca una macchina ma l'articolo è una dima, raccordo, staffa o filtro, viene applicata una penalità di **-35.0**.
7. **Stadio 7 — Accessory & Bundle Expander**:
   Se l'articolo appartiene a una pagina PDF del catalogo, recupera automaticamente le unità abbinate (UI + UE) e gli accessori co-presenti nella medesima tabella (staffe, comandi a filo, schede WiFi, kit scarico fumi).

---

## 3. Eliminazione dei Dizionari Hardcoded: Il Motore Dinamico

### Perché i Dizionari Hardcoded sono stati Eliminati

In precedenza, per risolvere rapidamente alcune famiglie di condizionatori (es. Samsung Avant, Panasonic BZ, Mitsubishi LN, Bosch Climate), erano stati inseriti nel codice Python dizionari statici con codici cablati a mano (es. `self.BOSCH_3000_UI = {9000: '50418718', ...}`).

Questo approccio presentava gravi criticità:
- **Fragilità e omissioni**: Se a catalogo esistono finiture alternative (Bianco, Nero, Silver), revisioni generazionali o serie equivalenti (es. Climate 3000i e 3200i a pagina 583), il dizionario statico fallisce perché non copre ciò che non è stato scritto a mano.
- **Mancanza di scalabilità**: Su 57.608 articoli non è concepibile mantenere migliaia di righe di mappe statiche.
- **Violazione del principio del DB reale**: I dati esistono già all'interno di `climatizzatori_compatibilita_master.json` e `unified_catalog_master.json`. Il motore deve **interrogare il database reale**, non duplicarlo in mappe cablate.

### Come Opera il Dynamic Catalog Resolver

Il risolutore dinamico converte la richiesta in una query strutturata su `climatizzatori_compatibilita_master.json`:

```
Titolo: "Bosch Climatizzatore Dual Split Climate 3000i 12+12 con 5000M 105/4 E"
                                │
                                ▼
1. ENTITY PARSING (Analisi dei parametri richiesti)
   • Brand: BOSCH
   • Serie/Famiglia: CLIMATE 3000I (alias catalogo: CLIMATE 3200I)
   • Split Count: 2 (Dual Split)
   • Taglie UI: [12000, 12000]
   • Modello UE: "5000M 105/4 E" (richiede 4 attacchi, soddisfa >= 2 split)
                                │
                                ▼
2. DYNAMIC DB QUERY (Interrogazione del Master DB)
   • Per ciascuna UI (12.000 BTU):
     QUERY unita_interne WHERE brand == 'BOSCH' 
                           AND famiglia IN ('CLIMATE 3000I', 'CLIMATE 3200I', 'CLIMATE 3000i / 3200i')
                           AND taglia_btu == 12000
     --> Restituisce dal DB: 50418725 ("UI PARETE CLIMATE 3200i 35 WE")
   • Per l'Unità Esterna:
     QUERY unita_esterne WHERE brand == 'BOSCH' 
                           AND '5000M' in nome AND '105/4' in nome
                           AND porte_attacchi >= 2
     --> Restituisce dal DB: 50250516 ("UE MULTI 4ATT CLIMATE 5000M 105/4 E R32")
                                │
                                ▼
3. MULTISET BOM ASSEMBLY (Assemblaggio certificato)
   • Componenti: 2x 50418725 + 1x 50250516
   • Stringa MPN: "50418725+50418725+50250516"
   • Confidence Score: 100% (Certificato DB)
   • Verifica Catalogo: Pagina 583 / 611 certificata
```

Questo meccanismo funziona in modo universale per **qualsiasi costruttore e serie**, interrogando i metadati del DB e garantendo l'assenza totale di codici allucinati o cablati a mano.

---

## 4. Il Validation Engine: Principi, Regole e Hard Gates

Il motore di validazione (`ClimaMatchingEngine` in `src/clima_matching_engine.py`) esegue la verifica riga per riga confrontando l'MPN esistente con la configurazione attesa.

### 1. Ricostruzione Analitica della BOM Attesa (`ExpectedBOM`)
Dal titolo e riferimento commerciale vengono estratti:
- **Brand**: Rilevamento esatto da anagrafica produttori.
- **Split Count**: 
  - Monosplit: 1 UI + 1 UE.
  - Multisplit: 2 (Dual), 3 (Trial), 4 (Quadri), 5 (Penta).
  - Solo Unità Esterna: `split_count = 0` (es. prodotti outlet o offerte solo macchina esterna).
- **Taglie UI (Multiset)**: Elenco ordinato delle potenze richieste (es. `9+12` $\rightarrow$ `[9000, 12000]`).
- **Colori UI**: Riconoscimento finiture specifiche (Bianco, Nero, Silver, Dark).
- **Modello UE**: Token identificativo dell'unità esterna specificata (es. `5000M 79/3`, `2Z50`, `3AMW62`).
- **Generazione / Revisione**: Token generazionali (es. `FTXM-A` vs `FTXM-R`, `ZKE` vs `XKE`, `S2`).
- **Accessori**: Rilevamento di staffe di supporto o kit WiFi optional citati.

### 2. Barriera Categorica di Non-Contaminazione
Prima di qualsiasi valutazione, ogni codice presente nell'MPN viene verificato contro l'anagrafica master unificata:
- Se un codice appartiene alle categorie radice **`UTENSILI ED ATTREZZATURA`** o **`FERRAMENTA`** (es. morse, frese, chiavi, ganasce):
  - Viene classificato come **DISCORDANZA CRITICA**.
  - Lo score scende a **0%**.
  - Viene **bloccato l'inserimento** ed espulso dal set di climatizzazione.

### 3. Multiset Matching (Verifica Quantità e Taglie Duplicate)
La validazione non si limita a verificare la presenza di una taglia, ma confronta il conteggio esatto tramite `Counter`:
- Se il titolo richiede un Dual Split `9+9`:
  - Richiede: `{9000: 2}` (due unità da 9k distinte o con codice ripetuto).
  - Se l'MPN contiene solo `50207572+99675233` (una sola UI 9k + UE), il multiset check rileva la discrepanza quantitativa (`presenti 1 UI vs attese 2 UI`) e rifiuta il match.

### 4. Hard Gates per il Blocco dell'Autocorrezione

> [!IMPORTANT]
> **Regola Fondamentale di Sicurezza Dati**:
> La colonna originale **D (`MPN`) NON VIENE MAI SOVRASCRITTA**.
> Qualsiasi proposta o correzione viene scritta esclusivamente nella colonna **E (`MPN_Suggerito`)**.
> Inoltre, la presenza di un Confidence Score elevato ($\ge 80\%$) **NON** autorizza l'autocorrezione se scatta un Hard Gate.

Gli Hard Gates bloccano tassativamente la compilazione di `MPN_Suggerito` (che rimane vuoto `""` per richiedere l'intervento dell'operatore umano):

| Hard Gate | Descrizione | Azione su Colonna E | Score |
| :--- | :--- | :---: | :---: |
| **`DA_VERIFICARE_VERSIONE`** | Rileva discordanza tra generazioni/revisioni simili (es. titolo richiede Daikin serie *A* o Panasonic *XKE*, mentre a catalogo è presente la serie *R* o *ZKE*). | **BLOCCATA** (`""`) | 85% |
| **`CONFIGURAZIONE_NON_CONFERMATA`** | Per impianti multisplit dove l'unità esterna non è specificata nel titolo/riferimento o gli attacchi sono incerti. L'UE non viene MAI inferita o inventata senza riscontro nel catalogo PT. | **BLOCCATA** (`""`) | 75% |
| **`DISCORDANZA`** | Marca errata, quantità UI/UE errata, serie incompatibile o codice non appartenente al condizionamento. | **BLOCCATA** (`""`) | 0% |
| **`DA VERIFICARE`** | Accessorio specificato nel titolo (es. staffa a parete) non presente nei codici MPN. | **NON BLOCCATA** (propone la macchina) | 90% |
| **`COERENTE`** | Tutti i componenti (UI, UE, taglie multiset, marca, modello e serie) corrispondono perfettamente al catalogo PT. | **INSERITO** | 95% - 100% |

### 5. Fall-Through Logic per MPN Errati o Assenti
Se un MPN preesistente in Colonna D risulta non coerente (`DISCORDANZA`):
1. Il vecchio match errato viene completamente scartato.
2. Si attiva il **Dynamic Catalog Resolver** che riesegue l'identificazione da zero sul catalogo master come se la riga fosse priva di MPN.
3. Se il catalogo master individua la combinazione ufficiale univoca con evidenze oggettive, la nuova distinta base viene proposta in Colonna E (`MPN_Suggerito`) accompagnata dal feedback analitico che spiega l'errore dell'MPN originale.

---

## 5. Casi Reali e Riscontri su Catalogo Ufficiale (Esempio Bosch Pagina 583)

A titolo esemplificativo della precisione del motore, la pagina **583** del catalogo ufficiale Puglia Termica raccoglie la gamma residenziale R32 Bosch:

```
PAGINA 583 CATALOGO PUGLIA TERMICA — GAMMA RESIDENZIALE R32 BOSCH
─────────────────────────────────────────────────────────────────────────────
• Tabella "CLIMATE 3000i / 3200i":
  - UI 7k  (2,0 kW):  Codice 50416219 (Climate 3200i 20 WE)
  - UI 9k  (2,6 kW):  Codice 50418718 (Climate 3200i 26 WE) [o 50009381 3000i F.E.S.]
  - UE 9k  (2,9 kW):  Codice 50009398 (Climate 3000i 26 WE)
  - UI 12k (3,5 kW):  Codice 50418725 (Climate 3200i 35 WE)
  - UE 12k (3,8 kW):  Codice 50009411 (Climate 3000i 35 WE)
  - UI 18k (5,3 kW):  Codice 50410330 (Climate 3200i 53 WE)
  - UE 18k (5,6 kW):  Codice 50009435 (Climate 3000i 53 WE)
  - UI 24k (7,0 kW):  Codice 50009442 (Climate 3000i 70 WE)
  - UE 24k (7,3 kW):  Codice 50009459 (Climate 3000i 70 WE)

• Tabella "CLIMATE 7000i":
  - Finiture UI: Bianco (BCO), Silver (ES), Nero (EB)
  - Taglie: 20 (7k), 26 (9k), 35 (12k), 41 (15k), 53 (18k)
  - UE Monosplit dedicate: 50276431 (20), 50276479 (26), 50276493 (35), 50276516 (41), 50276530 (53)

• Tabella "CLIMATE 5000M MULTISPLIT" (Pagina 611):
  - 41/2 E (2 attacchi): Codice 50195626
  - 53/2 E (2 attacchi): Codice 50195633
  - 62/3 E (3 attacchi): Codice 50195640
  - 79/3 E (3 attacchi): Codice 50252343
  - 82/4 E (4 attacchi): Codice 50195657
  - 105/4 E (4 attacchi): Codice 50250516
  - 125/5 E (5 attacchi): Codice 50252374
─────────────────────────────────────────────────────────────────────────────
```

Grazie al risolutore dinamico:
1. **Equivalenza Serie 3000i / 3200i**: Il motore riconosce che `Climate 3000i` e `Climate 3200i` appartengono alla stessa famiglia commerciale certificata a pag. 583. Una richiesta di `Climate 3000i 12k` riceve `50418725` con esito `COERENTE` (100%).
2. **Parsing Disambiguato Taglia vs Serie**: In stringhe come `Climate 7000i da 9000 btu`, il parser esclude il numero serie `7000` dal conteggio BTU, identificando correttamente la taglia richiesta come 9.000 BTU ed evitando false discordanze.
3. **Unità Esterne Singole (UE-Only)**: Nelle righe outlet/offerta destinate solo a unità esterne (es. `Bosch UE Multisplit Climate 5000M 41/2 E`), il motore imposta `split_count = 0` validando la sola UE senza pretendere unità interne.

---

## 6. Riepilogo Struttura Output Excel (`VERIFICA_CLIMA.xlsx`)

La tabella finale conserva intatta l'anagrafica e appende i risultati di verifica:

| Colonna | Nome Campo | Descrizione |
| :---: | :--- | :--- |
| **A** | `ID` | Identificativo univoco della riga originale. |
| **B** | `Riferimento` | Codice o riferimento gestionale originario. |
| **C** | `Titolo` | Titolo esteso dell'inserzione commerciale. |
| **D** | `MPN` *(Originale)* | **INVARIATO AL 100%** — Codice originale da validare. |
| **E** | `MPN_Suggerito` | Codice certificato proposto dal motore (vuoto se scatta un Hard Gate o se non raggiunge l'80%). |
| **F** | `Confidence_Score` | Punteggio evidence-based con etichetta descrittiva (es. `100% (Certificato DB)`). |
| **G** | `Esito_validazione` | Esito: `COERENTE`, `DA VERIFICARE`, `DA_VERIFICARE_VERSIONE`, `CONFIGURAZIONE_NON_CONFERMATA`, `DISCORDANZA`, `SENZA CODICI`. |
| **H** | `Feedback_match` | Spiegazione tecnica dettagliata delle verifiche eseguite o dei motivi di disallineamento. |
| **I** | `Componenti_DB` | Descrizione completa di ciascun componente individuato nel catalogo master PT. |
| **J** | `Confronto_titolo_DB` | Sintesi comparativa tra la richiesta del titolo e la distinta trovata a catalogo. |
| **K** | `Fonte_verifica` | Origine del dato (`LanceDB / Catalogo Master PT / Pagina 583`). |
| **L** | `Tua_verifica` | Campo di stato per l'operatore (`Confermato` o `Da rivedere`). |
| **M** | `Note_revisione` | Eventuali annotazioni tecniche per la gestione commerciale. |
