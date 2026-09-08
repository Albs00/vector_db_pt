"""
server_ui.py
Server HTTP leggero e multi-threaded per l'interfaccia di ricerca
e consultazione visuale del Catalogo Puglia Termica 2026.
Nessuna dipendenza esterna: usa ThreadingHTTPServer della standard library.
"""

import sys
import os
import json
import urllib.parse
import mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import time

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

# Aggiungi cartella di lavoro al path
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORKSPACE_DIR)

from catalog_search_engine import CatalogSearchEngine
from catalog_page_viewer import CatalogPageViewer

UI_DIR = os.path.join(WORKSPACE_DIR, "ui")
PORT = 8085

search_engine = None
page_viewer = None

def init_engines():
    global search_engine, page_viewer
    if search_engine is None:
        print("Inizializzazione motore di ricerca e visualizzatore PDF...")
        search_engine = CatalogSearchEngine()
        page_viewer = CatalogPageViewer()
        search_engine._ensure_initialized()
        print("Motore pronto.")


class CatalogRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Log sintetico delle richieste
        sys.stderr.write(f"[{self.log_date_time_string()}] {args[0]} {args[1]} {args[2]}\n")

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # CORS headers per flessibilità
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }

        # 1. API: /api/search
        if path == "/api/search":
            q = query_params.get("q", [""])[0].strip()
            brand = query_params.get("brand", [None])[0]
            category = query_params.get("category", [None])[0]
            catalog_only = query_params.get("catalog_only", ["false"])[0].lower() in ("true", "1")
            limit = int(query_params.get("limit", [10])[0])

            if not q:
                self._send_json({"error": "Query vuota", "results": [], "total_results": 0}, headers)
                return

            try:
                res = search_engine.search(
                    query=q,
                    brand=brand if brand and brand != "ALL" else None,
                    category=category if category and category != "ALL" else None,
                    catalog_only=catalog_only,
                    limit=limit
                )
                self._send_json(res, headers)
            except Exception as e:
                self._send_json({"error": str(e), "results": [], "total_results": 0}, headers, status=500)
            return

        # 2. API: /api/page-image/<page_num>
        if path.startswith("/api/page-image/"):
            try:
                page_str = path.replace("/api/page-image/", "").strip()
                page_num = int(page_str)
                dpi = int(query_params.get("dpi", [150])[0])
                img_path = page_viewer.render_page_image(page_num, dpi=dpi)

                if os.path.exists(img_path):
                    with open(img_path, "rb") as f:
                        img_bytes = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(img_bytes)))
                    self.send_header("Cache-Control", "public, max-age=86400")
                    for k, v in headers.items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(img_bytes)
                else:
                    self._send_json({"error": f"Impossibile generare l'immagine per la pagina {page_num}"}, headers, status=404)
            except Exception as e:
                self._send_json({"error": str(e)}, headers, status=500)
            return

        # 3. API: /api/page-summary/<page_num>
        if path.startswith("/api/page-summary/"):
            try:
                page_str = path.replace("/api/page-summary/", "").strip()
                page_num = int(page_str)
                summary = page_viewer.get_page_summary(page_num)
                self._send_json(summary, headers)
            except Exception as e:
                self._send_json({"error": str(e)}, headers, status=500)
            return

        # 4. API: /api/stats
        if path == "/api/stats":
            stats = {
                "total_catalog_products": 32232,
                "total_api_products": 57608,
                "exact_lookup_keys": 125559,
                "vector_dim": 384,
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "pdf_source": "CAT2600_CATALOGO_2026-V4pdf.pdf (960MB)"
            }
            self._send_json(stats, headers)
            return

        # 5. Servizio File Statici (UI)
        if path == "/" or path == "/index.html":
            file_to_serve = os.path.join(UI_DIR, "index.html")
        else:
            rel_path = path.lstrip("/")
            file_to_serve = os.path.join(UI_DIR, rel_path)

        if os.path.exists(file_to_serve) and os.path.isfile(file_to_serve):
            mime_type, _ = mimetypes.guess_type(file_to_serve)
            mime_type = mime_type or "application/octet-stream"
            with open(file_to_serve, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if "text" in mime_type or "javascript" in mime_type else mime_type)
            self.send_header("Content-Length", str(len(content)))
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_json({"error": "File non trovato", "path": path}, headers, status=404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_json(self, data, extra_headers, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra_headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

import socket
import webbrowser
import threading
import urllib.request

def check_server_running(port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/stats", headers={"User-Agent": "HealthCheck"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return "total_catalog_products" in data
    except Exception:
        return False

def start_server(port=PORT):
    # 1. Se il server e gia in esecuzione, apri il browser ed esci pacificamente
    if check_server_running(port):
        print(f"\n=======================================================")
        print(f" [INFO] Un'istanza del server Puglia Termica e gia attiva su:")
        print(f"        URL: http://127.0.0.1:{port}")
        print(f"=======================================================\n")
        print("Apertura interfaccia nel browser predefinito...")
        webbrowser.open(f"http://127.0.0.1:{port}")
        return

    # 2. Trova una porta libera se 8085 e occupata da un altro processo
    current_port = port
    server = None
    for attempt_port in range(port, port + 10):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", attempt_port), CatalogRequestHandler)
            current_port = attempt_port
            break
        except OSError:
            continue

    if server is None:
        print(f"[ERRORE] Impossibile avviare il server: tutte le porte tra {port} e {port+10} sono occupate.")
        return

    init_engines()

    print(f"\n=======================================================")
    print(f" [PUGLIA TERMICA 2026] CATALOG SEARCH & VIEWER UI     ")
    print(f" URL: http://127.0.0.1:{current_port}")
    print(f"=======================================================\n")

    # 3. Apertura browser solo ORA che il server e effettivamente in ascolto
    def _open_browser():
        time.sleep(0.5)
        webbrowser.open(f"http://127.0.0.1:{current_port}")

    threading.Thread(target=_open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto del server...")
        server.server_close()

if __name__ == "__main__":
    start_server()

