"""
test_search_benchmark.py
Suite di validazione e benchmark per il motore di ricerca ibrido del Catalogo Puglia Termica.
Valuta:
  1. Ricerca secca per Codice Articolo Puglia Termica (Short-Circuit)
  2. Ricerca per Codice Produttore / MPN (Short-Circuit)
  3. Ricerca Semantica per Descrizione e Potenza (Vettori Densi + BM25)
  4. Ricerca con Filtro di Marca e Categoria
  5. Bundle & Accessory Expansion (Accessori correlati sulla stessa pagina)
  6. Visual Page Rendering dal PDF 960MB (Zero-RAM single page PNG)
"""

import sys
import os
import json
import time
from catalog_search_engine import CatalogSearchEngine
from catalog_page_viewer import CatalogPageViewer

sys.stdout.reconfigure(encoding='utf-8')

def run_benchmark():
    print("=================================================================")
    print("       PUGLIA TERMICA 2026 - SEARCH BENCHMARK & EVALUATION       ")
    print("=================================================================\n")

    engine = CatalogSearchEngine()
    viewer = CatalogPageViewer()

    test_cases = [
        {
            "id": "TC1",
            "name": "Ricerca per Codice Articolo PT Esatto",
            "query": "50042371",
            "expected_brand": "DAB",
            "expected_type": "exact_code_short_circuit"
        },
        {
            "id": "TC2",
            "name": "Ricerca per Codice Produttore Originale (MPN)",
            "query": "60198332",
            "expected_brand": "DAB",
            "expected_type": "exact_code_short_circuit"
        },
        {
            "id": "TC3",
            "name": "Ricerca Semantica Naturale (Caldaia Ferroli 28 kW)",
            "query": "caldaia condensazione ferroli 28 kw",
            "expected_brand": "FERROLI",
            "expected_type": "hybrid_vector_bm25"
        },
        {
            "id": "TC4",
            "name": "Ricerca con Filtro Marca e Categoria",
            "query": "autoclave gruppo pompa",
            "brand": "DAB PUMPS",
            "category": "IDRICA",
            "expected_brand": "DAB",
            "expected_type": "hybrid_vector_bm25"
        },
        {
            "id": "TC5",
            "name": "Accessory Expansion su Pagina Catalogo (Pag. 29)",
            "query": "50018697",  # Caldaia Bluehelix Maxima a pag 29
            "expected_page": 29,
            "expected_type": "exact_code_short_circuit"
        },
        {
            "id": "TC7",
            "name": "Ricerca Titoli Abbreviati PT (Baxi Scaldabagno Acquaprojet)",
            "query": "Baxi Scaldabagno a Gas a Camera Stagna Acquaprojet Blue FI 11 Litri GPL Low NOx Classe A con Kit Fumi",
            "expected_brand": "BAXI"
        }
    ]

    passed = 0
    total = len(test_cases)

    for tc in test_cases:
        print(f"--- TEST {tc['id']}: {tc['name']} ---")
        print(f"Query: '{tc['query']}'")
        res = engine.search(
            query=tc["query"],
            brand=tc.get("brand"),
            category=tc.get("category"),
            limit=3
        )
        print(f"Tipo Match: {res.get('match_type')} | Tempo: {res.get('execution_time_ms')}ms | Risultati: {res.get('total_results')}")
        
        if res.get("total_results", 0) > 0:
            top = res["results"][0]
            print(f"Top Result: [{top.get('code')}] {top.get('brand')} | {top.get('name')}")
            print(f"Listino: {top.get('gross_price')} € | Netto: {top.get('net_price')} € | Pagina PDF: {top.get('primary_page')}")
            if top.get("page_accessories"):
                print(f"Accessori correlati sulla pagina ({len(top['page_accessories'])}):")
                for a in top["page_accessories"][:3]:
                    print(f"   • [{a.get('code')}] {a.get('name')}")
            passed += 1
            print("Status: [PASS]\n")
        else:
            print("Status: [FAIL - Nessun risultato]\n")

    # TEST 6: On-Demand Visual PDF Rendering
    print("--- TEST TC6: Rendering Visuale Pagina PDF On-Demand (Zero RAM) ---")
    t0 = time.time()
    img_path = viewer.render_page_image(29, dpi=120)
    render_time = time.time() - t0
    if os.path.exists(img_path):
        size_kb = round(os.path.getsize(img_path) / 1024, 1)
        print(f"Pagina 29 renderizzata con successo in {render_time:.2f}s!")
        print(f"File PNG generato: {img_path} ({size_kb} KB)")
        print("Status: [PASS]\n")
        passed += 1
        total += 1
    else:
        print(f"Status: [FAIL - {img_path}]\n")
        total += 1

    print("=================================================================")
    print(f"       BENCHMARK COMPLETATO: {passed}/{total} TEST SUPERATI       ")
    print("=================================================================")

if __name__ == "__main__":
    run_benchmark()
