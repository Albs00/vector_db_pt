# Audit Product Category / Product Role Resolution

```json
{
  "audit": "Product Category / Product Role Resolution",
  "execution_mode": "READ_ONLY",
  "code_modified": false,
  "datasets_modified": false,
  "cases": 4,
  "observed_product_scope": "GENERAL",
  "expected_product_scope": "UI_ONLY",
  "categories_exist": "SI",
  "ui_ue_role_exists": "SI",
  "primary_diagnosis": "SCOPE PROPAGATION BUG",
  "category_routing_diagnosis": "OK: all four cases resolve to CLIMA",
  "role_retention_diagnosis": "OK: is_ui=true/is_ue=false survives exact matching and role=UI is materialized in the BOM",
  "secondary_data_gap": "PT 50224067 is absent from catalog_table_context.json and LanceDB, but is present in unified_catalog_master.json, exact_code_lookup.json, the climate compatibility master, and runtime candidates"
}
```

## 1. Esito esecutivo

Il difetto non è causato dall'assenza della categoria o del ruolo UI. Nei quattro casi il router seleziona correttamente il dominio `CLIMA`; il candidato prodotto conserva `is_ui=true`, `is_ue=false` e `tipo_unita=UI`, e la BOM materializza `role=UI`.

La perdita avviene nella risoluzione dello **scope globale**: `ClimateCategoryAdapter.extract_query_context()` ricava `product_scope` esclusivamente dal testo della query. Le query `PT ... MFG ...` non contengono espressioni come “unità interna” o “solo UI”, quindi producono `GENERAL`. Dopo l'exact match non esiste un passaggio che promuova lo scope a `UI_ONLY` usando `is_ui`, `is_ue` o `tipo_unita` del prodotto identificato.

Verdetto primario: **SCOPE PROPAGATION BUG**.

## 2. Tabella anagrafica consolidata

| PT | MODELLO richiesto / MPN anagrafico | CATEGORY | ROLE | UI/UE | FAMILY | TABLE | DATI PRESENTI |
|---|---|---|---|---|---|---|---|
| 50224067 | `AS42XCAHRA-MB` / `2501304F2` | `CONDIZIONAMENTO > CONDIZIONAMENTO > RESIDENZIALI`; root `CONDIZIONAMENTO`; runtime domain `CLIMA` | `UI` (`role` non serializzato nel candidate payload, derivato da `is_ui`) | `is_ui=true`, `is_ue=false`, `tipo_unita=UI` | `EXPERT (WHITE / BLACK)`; `HAIER_EXPERT_WHITE_BLACK` | Nessun `table_id`; nessun table context | master ✓; exact lookup ✓; climate compatibility master ✓; runtime candidate ✓; table context ✗; LanceDB ✗ |
| 99718206 | `FFA25A9` / `FFA25A9` | `CONDIZIONAMENTO > CONDIZIONAMENTO > COMMERCIALI`; root `CONDIZIONAMENTO`; runtime domain `CLIMA` | `UI` | `is_ui=true`, `is_ue=false`, `tipo_unita=UI` | `CASSETTA A 4 VIE FFA-A (9) 60X60`; `DAIKIN_CASSETTA_A_4_VIE_FFA_A_9_60X60` | `CASSETTA A 4 VIE FFA-A (9) 60x60`; `PDF_P0473_84E198812D`; section `CONDIZIONATORI RESIDENZIALI UNITA’ INTERNE MULTI` | master ✓; exact lookup ✓; table context ✓; LanceDB ✓; runtime candidate ✓ |
| 99759971 | `FCAG71B` / `FCAG71B` | `CONDIZIONAMENTO > CONDIZIONAMENTO > COMMERCIALI`; root `CONDIZIONAMENTO`; runtime domain `CLIMA` | `UI` | `is_ui=true`, `is_ue=false`, `tipo_unita=UI` | `CASSETTA DA INCASSO ROUND FLOW FCAG-B 90X90`; `DAIKIN_CASSETTA_DA_INCASSO_ROUND_FLOW_FCAG_B_90X90` | `CASSETTA DA INCASSO ROUND FLOW FCAG-B 90X90`; `PDF_P0481_F8FD9D34C3`; section `CONDIZIONATORI COMMERCIALI SKY AIR ACTIVE R32` | master ✓; exact lookup ✓; table context ✓; LanceDB ✓; runtime candidate ✓ |
| 50307791 | `FTXM25A` / `FTXM25A` | `CONDIZIONAMENTO > CONDIZIONAMENTO > RESIDENZIALI`; root `CONDIZIONAMENTO`; runtime domain `CLIMA` | `UI` | `is_ui=true`, `is_ue=false`, `tipo_unita=UI` | `PERFERA ALL SEASONS`; `DAIKIN_PERFERA_ALL_SEASONS` | `PERFERA ALL SEASONS`; `PDF_P0468_648746C190`; section `CONDIZIONATORI RESIDENZIALI R32` | master ✓; exact lookup ✓; table context ✓; LanceDB ✓; runtime candidate ✓ |

Note sui nomi dei campi:

- nei dataset non esiste un campo letterale `category`; il dato è `category_path`, con `category_root` nel master e in LanceDB;
- `domain` non è serializzato nell'anagrafica: è il risultato runtime del router (`CLIMA` per tutti e quattro);
- `role` non è serializzato nel master/LanceDB e resta `null` nel payload per il component lookup, ma il ruolo è inequivocabilmente disponibile tramite `tipo_unita=UI` e `is_ui=true`; la BOM lo materializza come `role=UI`;
- `product_type` non è un dato anagrafico: con accessori abilitati viene derivato a runtime come `AC` per tutti e quattro. Non va confuso con `product_scope`, che risulta `GENERAL`.

## 3. Presenza per fonte

### 3.1 `unified_catalog_master.json`

Tutti i prodotti sono presenti e hanno categoria e ruolo UI:

| PT | category_path | category_root | tipo_unita | is_ui | is_ue |
|---|---|---|---|---:|---:|
| 50224067 | `CONDIZIONAMENTO > CONDIZIONAMENTO > RESIDENZIALI` | `CONDIZIONAMENTO` | `UI` | true | false |
| 99718206 | `CONDIZIONAMENTO > CONDIZIONAMENTO > COMMERCIALI` | `CONDIZIONAMENTO` | `UI` | true | false |
| 99759971 | `CONDIZIONAMENTO > CONDIZIONAMENTO > COMMERCIALI` | `CONDIZIONAMENTO` | `UI` | true | false |
| 50307791 | `CONDIZIONAMENTO > CONDIZIONAMENTO > RESIDENZIALI` | `CONDIZIONAMENTO` | `UI` | true | false |

### 3.2 `catalog_table_context.json`

- `99718206`, `99759971` e `50307791`: contesto completo con `catalog_family`, `family_key`, `table_title`, `table_id`, `page`, `section_title`, `model` e `mpn`.
- `50224067`: nessuna entry. La famiglia osservata nel candidate runtime arriva dal climate compatibility master, non dal PDF table context.

### 3.3 Vector index metadata (LanceDB `catalog_products`)

Lo schema vettoriale contiene `category_path`, `category_root`, `catalog_family`, `family_key`, `table_title`, `table_id`, `table_page` e `table_section_title`. Non contiene `role`, `is_ui`, `is_ue`, `tipo_unita`, `domain` o `product_type`.

- righe presenti e complete per `99718206`, `99759971`, `50307791`;
- nessuna riga LanceDB per `50224067`.

Questa differenza non è la causa comune del difetto: anche i tre record con metadati vettoriali e table context completi terminano con `product_scope=GENERAL`.

### 3.4 Exact lookup e candidate objects

L'exact lookup contiene tutti e quattro i PT con `category_path`, `is_ui=true` e `is_ue=false`. Il campo `tipo_unita` non è serializzato nell'exact lookup corrente, ma è presente nel master e viene ricostruito/confermato durante l'enrichment clima.

Nei candidate objects osservati end-to-end:

| PT | match type | slot | is_ui | is_ue | famiglia dopo enrichment |
|---|---|---|---:|---:|---|
| 50224067 | `AMBIGUOUS_CATALOG_MODEL_LABEL` | `slot_ui_15000` | true | false | `HAIER_EXPERT_WHITE_BLACK` |
| 99718206 | `EXACT_RAW` | `slot_ui_9000` | true | false | `DAIKIN_CASSETTA_A_4_VIE_FFA_A_9_60X60` |
| 99759971 | `EXACT_RAW` | `slot_ui_24000` | true | false | `DAIKIN_CASSETTA_DA_INCASSO_ROUND_FLOW_FCAG_B_90X90` |
| 50307791 | `EXACT_CATALOG_MODEL_LABEL` | `slot_ui_9000` | true | false | `DAIKIN_PERFERA_ALL_SEASONS` |

Anomalia secondaria Haier: il valore fornito `AS42XCAHRA-MB` è una label commerciale nel `name`, mentre l'MPN anagrafico è `2501304F2`. La label commerciale è condivisa/ambigua nel parser e viene registrata prima che il token PT possa aggiornarne il match type. Il PT target `50224067` viene comunque mantenuto, classificato UI e inserito nella BOM; l'anomalia non causa lo scope `GENERAL`.

## 4. Simulazione exact match → category resolution → product scope

### PT 50224067 — AS42XCAHRA-MB

```text
exact match
  -> target PT 50224067 presente; candidate is_ui=true, is_ue=false
  -> la label AS42XCAHRA-MB produce anche un candidate commerciale ambiguo
category resolution
  -> CLIMA (evidenza AC master / category_root CONDIZIONAMENTO)
product scope
  -> extract_query_context("PT 50224067 MFG AS42XCAHRA-MB")
  -> nessun token esplicito UNITÀ INTERNA / SOLO UI
  -> GENERAL

CURRENT RESULT: GENERAL
EXPECTED: UI_ONLY
LOSS POINT: lo scope non viene derivato dal ruolo UI dell'exact product.
```

### PT 99718206 — FFA25A9

```text
exact match
  -> EXACT_RAW; PT 99718206; is_ui=true, is_ue=false
category resolution
  -> CLIMA (exact_token_in_ac_master; category CONDIZIONAMENTO)
product scope
  -> query-text-only resolution
  -> GENERAL

CURRENT RESULT: GENERAL
EXPECTED: UI_ONLY
LOSS POINT: il candidate ha già ruolo UI, ma product_scope non lo consulta.
```

### PT 99759971 — FCAG71B

```text
exact match
  -> EXACT_RAW; PT 99759971; is_ui=true, is_ue=false
category resolution
  -> CLIMA (exact_token_in_ac_master; category CONDIZIONAMENTO)
product scope
  -> query-text-only resolution
  -> GENERAL

CURRENT RESULT: GENERAL
EXPECTED: UI_ONLY
LOSS POINT: il candidate ha già ruolo UI, ma product_scope non lo consulta.
```

### PT 50307791 — FTXM25A

```text
exact match
  -> EXACT_CATALOG_MODEL_LABEL; PT 50307791; is_ui=true, is_ue=false
category resolution
  -> CLIMA (exact_token_in_ac_master; category CONDIZIONAMENTO)
product scope
  -> query-text-only resolution
  -> GENERAL

CURRENT RESULT: GENERAL
EXPECTED: UI_ONLY
LOSS POINT: il candidate ha già ruolo UI, ma product_scope non lo consulta.
```

Il ramo short-circuit usato da una query composta dal solo codice PT presenta lo stesso difetto di propagazione in altra forma: restituisce esplicitamente `product_scope: null`, non `UI_ONLY`.

## 5. Controllo `catalog_component_relations` dopo product match

Il runtime usa l'indice approvato `catalog_component_relations_safe_preview_v3_4.json`. Il lookup ha precedenza: contesto ottenuto dal PT → `table_id` → `family_key` + modello esatto. Il ruolo è ricavato da `is_ui`/`is_ue` anche quando il campo `role` del payload è `null`.

| PT | PT disponibile | table_id | family_key | product role disponibile | lookup result |
|---|---:|---|---|---|---|
| 50224067 | sì | **no** | `HAIER_EXPERT_WHITE_BLACK` | sì: `is_ui=true` → `UI` | 0 relazioni; PT senza table context e nessun record per la famiglia nel dataset V3.4 |
| 99718206 | sì | `PDF_P0473_84E198812D` | `DAIKIN_CASSETTA_A_4_VIE_FFA_A_9_60X60` | sì: `is_ui=true` → `UI` | 7 relazioni, strategia `EXACT_PRODUCT_PT` |
| 99759971 | sì | `PDF_P0481_F8FD9D34C3` | `DAIKIN_CASSETTA_DA_INCASSO_ROUND_FLOW_FCAG_B_90X90` | sì: `is_ui=true` → `UI` | 14 relazioni, strategia `EXACT_PRODUCT_PT` |
| 50307791 | sì | `PDF_P0468_648746C190` | `DAIKIN_PERFERA_ALL_SEASONS` | sì: `is_ui=true` → `UI` | 0 relazioni; chiavi complete ma nessun record sorgente V3.4 per tabella/famiglia |

Conclusioni del controllo:

- FFA25A9 e FCAG71B dimostrano che PT, tabella, famiglia e ruolo sopravvivono all'exact match e sono realmente consumati dal lookup.
- FTXM25A dimostra che un risultato vuoto può significare “nessuna relazione registrata”, non perdita di contesto.
- AS42XCAHRA-MB ha un data gap limitato a PDF table context/vector metadata, ma mantiene categoria e ruolo; questo gap non può spiegare il medesimo `GENERAL` negli altri tre casi.

## 6. Risposte finali

**A) Le categorie esistono già? SI.** Tutti e quattro i prodotti hanno `category_path` e `category_root` nel master; il router usa tali dati/AC master e risolve `CLIMA`. Tre prodotti riportano gli stessi dati anche in LanceDB; Haier è l'unica eccezione nell'indice vettoriale.

**B) Il ruolo UI/UE esiste già? SI.** Tutti e quattro hanno `tipo_unita=UI`, `is_ui=true`, `is_ue=false` nel master/compatibility metadata; exact candidates e BOM conservano il ruolo. Il campo letterale `role` viene materializzato solo nella BOM, ma il lookup ricava correttamente `UI` dai flag.

**C) Il problema è: SCOPE PROPAGATION BUG.** Non è `DATA MISSING` come causa comune e non è un errore di category routing: la categoria viene risolta correttamente. La logica di scope non riceve/usa il ruolo del prodotto exact identificato e resta basata esclusivamente sul testo della query.

## 7. Evidenze e verifica

- Master records: `Knowledge/unified_catalog_master.json` — PT 50224067 riga 3446232; PT 99718206 riga 3394970; PT 99759971 riga 3402069; PT 50307791 riga 3512528.
- Table contexts: `Knowledge/catalog_table_context.json` — PT 50307791 riga 166908; PT 99718206 riga 484994; PT 99759971 riga 510700; nessuna entry per PT 50224067.
- Exact lookup records: `Knowledge/vector_db/exact_code_lookup.json` — PT 99718206 riga 4275130; PT 99759971 riga 4281220; PT 50224067 riga 4326223; PT 50307791 riga 4395592.
- Scope query-only: `src/adapters/climate.py`, funzione `extract_query_context`, riga 475; fallback `GENERAL`, riga 503.
- Scope letto senza riconciliazione col candidate exact: `catalog_search_engine.py`, righe 1406 e 1755.
- Component payload e lookup: `catalog_search_engine.py`, funzione `_component_product_payload`, e `src/core/component_relations.py`, funzione `lookup_product`, riga 240.
- Verifica runtime eseguita sulle quattro query con `limit=20`: dominio `CLIMA`, `product_scope=GENERAL`, prodotto target `product_type=AC`, flag UI intatti e BOM con `role=UI` in tutti i casi.
- Test diagnostici esistenti eseguiti senza modifiche: 16 test, tutti `OK` (`tests.test_product_scope_and_compatibility` e `tests.test_component_relations_lookup_after_product_match`). I test correnti verificano scope esplicito nella query e component lookup, ma non coprono l'inferenza `UI_ONLY` da un exact product privo delle parole “unità interna”.

Nessun fix applicato.
