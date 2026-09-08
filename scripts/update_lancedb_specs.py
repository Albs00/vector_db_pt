import os, time, json, lancedb
from fastembed import TextEmbedding

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "Knowledge", "vector_db", "lancedb_store")
MASTER_PATH = os.path.join(BASE_DIR, "Knowledge", "unified_catalog_master.json")
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

print("Caricamento master catalog...")
with open(MASTER_PATH, "r", encoding="utf-8") as f:
    master = json.load(f)

changed_items = [
    it for it in master 
    if it.get("in_catalog_pdf") and "SPECIFICHE TECNICHE CATALOGO:" in (it.get("search_text") or "")
]
print(f"Articoli con specifiche aggiornate: {len(changed_items)}")

texts = [it["search_text"] for it in changed_items]

print("Generazione embedding FastEmbed MiniLM-L6-v2...")
t0 = time.time()
embed_model = TextEmbedding(model_name=MODEL_NAME)
vectors = list(embed_model.embed(texts, batch_size=256))
print(f"Embedding generati in {time.time() - t0:.2f}s ({len(vectors)} vettori)")

records = []
for it, vec in zip(changed_items, vectors):
    records.append({
        "id": it.get("id"),
        "code": it.get("code"),
        "mfg_code": it.get("mfg_code"),
        "name": it.get("name"),
        "brand": it.get("brand"),
        "category_path": it.get("category_path"),
        "category_root": it.get("category_root"),
        "gross_price": it.get("gross_price"),
        "net_price": it.get("net_price"),
        "image_url": it.get("image_url"),
        "in_catalog_pdf": it.get("in_catalog_pdf"),
        "primary_page": it.get("primary_page"),
        "catalog_pages": it.get("catalog_pages", []),
        "related_accessories_count": it.get("related_accessories_count", 0),
        "search_text": it.get("search_text"),
        "vector": vec.tolist()
    })

print("Connessione a LanceDB...")
db = lancedb.connect(DB_DIR)
tbl = db.open_table("catalog_products")

print("Esecuzione merge_insert in LanceDB...")
t1 = time.time()
tbl.merge_insert("code").when_matched_update_all().execute(records)
print(f"Merge insert completato in {time.time() - t1:.2f}s!")

print("Ricostruzione indice full-text BM25 Tantivy...")
t2 = time.time()
tbl.create_fts_index("search_text", replace=True)
print(f"Indice FTS Tantivy aggiornato in {time.time() - t2:.2f}s!")
print(f"Totale righe nella tabella: {tbl.count_rows()}")
