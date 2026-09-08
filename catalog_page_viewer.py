"""
catalog_page_viewer.py
Modulo per la consultazione e il rendering visuale on-demand a singola pagina
del catalogo Puglia Termica 2026 (risolve il vincolo del file PDF da 960MB).
Nessun consumo continuo di RAM: apre ed estrae solo la pagina richiesta.
"""

import os
import sys
import json
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(BASE_DIR, "Knowledge", "CAT2600_CATALOGO_2026-V4pdf.pdf")
if not os.path.exists(PDF_PATH):
    parent_pdf = os.path.join(BASE_DIR, "..", "Knowledge", "CAT2600_CATALOGO_2026-V4pdf.pdf")
    if os.path.exists(parent_pdf):
        PDF_PATH = parent_pdf

MASTER_JSON_PATH = os.path.join(BASE_DIR, "Knowledge", "unified_catalog_master.json")
CACHE_DIR = os.path.join(BASE_DIR, "Knowledge", "page_renders")

class CatalogPageViewer:
    def __init__(self, master_path=MASTER_JSON_PATH, pdf_path=PDF_PATH, ocr_jsonl_path=None):
        self.master_path = master_path
        self.pdf_path = pdf_path
        self.ocr_jsonl_path = ocr_jsonl_path
        self._page_to_products = None
        self._fitz_available = None

    def _ensure_products_loaded(self):
        if self._page_to_products is not None:
            return
        self._page_to_products = {}
        if os.path.exists(self.master_path):
            with open(self.master_path, "r", encoding="utf-8") as f:
                records = json.load(f)
            for r in records:
                for p in r.get("catalog_pages", []):
                    if p not in self._page_to_products:
                        self._page_to_products[p] = []
                    self._page_to_products[p].append({
                        "code": r["code"],
                        "mfg_code": r["mfg_code"],
                        "name": r["name"],
                        "brand": r["brand"],
                        "category": r["category_path"],
                        "gross_price": r["gross_price"],
                        "net_price": r["net_price"],
                        "image_url": r["image_url"]
                    })

    def get_products_on_page(self, page_num: int):
        """Restituisce l'elenco di tutti i prodotti presenti sulla pagina indicata."""
        self._ensure_products_loaded()
        return self._page_to_products.get(page_num, [])

    def render_page_image(self, page_num: int, dpi: int = 150) -> str:
        """
        Renderizza la singola pagina dal PDF da 960MB in formato PNG ad alta definizione.
        Salva l'immagine nella cartella cache Knowledge/page_renders/page_{num}.png.
        """
        os.makedirs(CACHE_DIR, exist_ok=True)
        out_image = os.path.join(CACHE_DIR, f"page_{page_num:04d}.png")
        if os.path.exists(out_image):
            return out_image

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(self.pdf_path)
            # In fitz le pagine sono 0-indexed. Nel catalogo cartaceo page_num corrisponde solitamente alla pagina fisica.
            idx = max(0, page_num - 1)
            if idx >= len(doc):
                raise ValueError(f"Pagina {page_num} oltre il limite del documento ({len(doc)})")
            page = doc[idx]
            pix = page.get_pixmap(dpi=dpi)
            pix.save(out_image)
            doc.close()
            return out_image
        except ImportError:
            return f"PyMuPDF non installato. Esegui 'pip install pymupdf' per abilitare il rendering grafico."
        except Exception as e:
            return f"Errore durante il rendering di pagina {page_num}: {e}"

    def get_page_summary(self, page_num: int) -> dict:
        """Restituisce la scheda completa di una pagina di catalogo."""
        products = self.get_products_on_page(page_num)
        return {
            "page": page_num,
            "total_products": len(products),
            "products": products,
            "image_cached": os.path.exists(os.path.join(CACHE_DIR, f"page_{page_num:04d}.png"))
        }

if __name__ == "__main__":
    viewer = CatalogPageViewer()
    test_page = 29
    info = viewer.get_page_summary(test_page)
    print(f"Pagina {test_page}: trovati {info['total_products']} prodotti.")
    for p in info['products'][:3]:
        print(f"  - [{p['code']}] {p['brand']} | {p['name']} (Listino: {p['gross_price']} €)")
