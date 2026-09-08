# Puglia Termica 2026 - AI Catalog Explorer & Audit Suite (Pacchetto Portable)

Pacchetto autonomo, pulito e portatile contenente:
1. **Puglia Termica 2026 AI Explorer**: motore di ricerca ibrido semantico + vettoriale + viewer PDF ad alta risoluzione.
2. **Audit & Verification Suite PrestaShop**: motore di verifica e riconciliazione automatica ad alta precisione per file CSV da 12.000+ prodotti, con abbinamento componenti kit clima (UE/UI), kit fumi caldaie e rimozione totale dei falsi positivi.

Questa cartella è 100% autonoma: può essere spostata, copiata su una chiavetta USB o su qualsiasi altro PC Windows o server.

---

## 🚀 Avvio Rapido (Windows 1-Click)

### 1. Interfaccia Web di Ricerca: `avvia_server.bat`
- Crea in automatico l'ambiente virtuale locale `.venv` (se non presente).
- Installa le librerie minime da `requirements.txt`.
- Avvia il server locale con rilevamento automatico collisioni di porta e **apre automaticamente il browser su `http://localhost:8085`** solo a inizializzazione completata (nessun errore di connessione rifiutata).

### 2. Audit Completo Catalogo PrestaShop: `avvia_audit.bat`
- Esegue in circa **14 secondi** la verifica rigorosa di tutti i **12.001 prodotti** di `Export_Prodotti_Verifica.csv`.
- Applica le regole aggiornate:
  * **Climatizzatori**: Monosplit (almeno 2 codici UE+UI), Dual-Split (almeno 3 codici), Trial-Split (almeno 4), Quadri-Split (almeno 5), Penta-Split (almeno 6).
  * **Serie Commerciali (es. LG DUALCOOL)**: Distingue i nomi di serie da veri Dual-Split, evitando falsi kit incompleti.
  * **Caldaie e Scaldabagni a Gas (es. Baxi Acquaprojet)**: 1 solo codice valido per il generatore + colonne dedicate per i **Kit Fumi Coassiale (60/100)** e **Sdoppiato (80/80)** compatibili di Puglia Termica.
  * **Query Retry & Abbreviazioni PT**: Mappatura intelligente dei suffissi e titoli abbreviati storici PT (`ACQUAPR`, `SCALD`, `CS`, `CA`, `COND`, etc.).
  * **Fallback Intelligente Codici Obsoleti (CASO 2D)**: Se un codice fornitore CSV è stato superato o non è più a listino, l'AI suggerisce in automatico il codice articolo PT attivo equivalente.
  * **Zero Falsi Positivi**: Priorità al titolo rispetto al campo brand CSV, gestione moltiplicatori (`x3`, `*5`), tolleranza caldaie commerciali HP.
  * **Zero Codici Errati Auto-Suggeriti**: Se un codice è incompatibile o inesistente, non viene mai riproposto nel campo suggerito.
- Genera i file di output:
  * `Report_Verifica_Kit_Completi_12000_Prodotti.xlsx` (Excel formattato a colori).
  * `Report_Verifica_Kit_Completi_12000_Prodotti.csv` (CSV delimitato da `;`).

### 3. Esecuzione Test di Verifica: `avvia_test.bat`
- Esegue la suite completa:
  * Benchmark di ricerca (7 test case: codici PT, MPN, semantica, filtri, bundle su pagina PDF, rendering visuale 0-RAM, query retry scaldabagni abbreviati).
  * Test combinazioni e compatibilità climatizzatori (5 test case con Unità Esterne multi-split e Unità Interne compatibili).

---

## 📁 Struttura della Cartella Portable

```
PugliaTermica_AI_Search/
│
├── avvia_server.bat             # Launcher interfaccia web di ricerca (http://localhost:8085)
├── avvia_audit.bat              # Launcher audit automatico 12.001 righe PrestaShop
├── avvia_test.bat               # Test automatico di integrità e performance
├── requirements.txt             # Dipendenze Python minime e pulite (lancedb, fastembed, tantivy, pymupdf, openpyxl)
├── README.md                    # Questo documento
│
├── server_ui.py                 # Server HTTP multi-threaded (porta 8085)
├── catalog_search_engine.py     # Motore di Ricerca Ibrido (LanceDB vettoriale + Tantivy BM25 + Short-circuit <5ms)
├── accessory_engine.py          # Motore di Compatibilità (Kit bundle, singole UI/UE, accessori tecnici, varianti)
├── catalog_page_viewer.py       # Visualizzatore PDF on-demand ad alta definizione
├── run_full_csv_audit.py        # Script di Audit e Normalizzazione ad alta precisione
│
├── test_search_benchmark.py     # Suite benchmark (ricerca esatta PT, MPN, semantica, filtri)
├── test_ac_combinations.py      # Suite combinazioni clima (Daikin, Haier, Aermec)
│
├── Export_Prodotti_Verifica.csv # File sorgente PrestaShop (12.001 prodotti)
├── Report_Verifica_Kit_Completi_12000_Prodotti.xlsx # Report finale Excel formattato
├── Report_Verifica_Kit_Completi_12000_Prodotti.csv  # Report finale CSV delimitato da ;
│
├── ui/                          # Frontend Web Moderno (Glassmorphism Dark Theme)
│   ├── index.html               # Struttura applicazione, viewer PDF e modale accessori
│   ├── style.css                # Stili CSS, animazioni, layout responsivo
│   └── app.js                   # Logica client, zoom/pan PDF, filtri categoria live
├── build_full_ac_matrix.py      # Generatore matrice compatibilità climatizzatori master JSON
│
└── Knowledge/                   # Dati e Database di Produzione
    ├── climatizzatori_compatibilita_master.json # Matrice Master Completa & Bidirezionale (UE, UI, Kit, Taglie BTU)
    ├── unified_catalog_master.json      # Anagrafica catalogo unificata con prezzi e codici
    ├── ac_outdoor_combinations.json     # Tabelle combinazioni e kit commerciali clima
    ├── catalog_accessory_rules.json     # Regole compatibilità accessori caldaie, pompe, etc.
    ├── CAT2600_CATALOGO_2026-V4pdf.pdf  # Catalogo PDF originale da 960MB (consultazione on-demand)
    └── vector_db/
        ├── exact_code_lookup.json       # Indice hash per short-circuit istantaneo (<5ms)
        └── lancedb_store/               # Database vettoriale LanceDB con embedding densi e BM25
```

---

## 🛠️ Requisiti di Sistema
- **Sistema Operativo**: Windows 10/11, Windows Server, Linux o macOS.
- **Python**: Versione 3.10, 3.11 o 3.12 installata nel sistema.
- **RAM**: ~1 GB libero.
