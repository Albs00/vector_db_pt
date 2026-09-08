"""
web_product_searcher.py
Modulo per la ricerca web e l'estrazione di schede tecniche di prodotti termoidraulici.
Utilizza una cache permanente SQLite per evitare chiamate ripetute e garantire resilienza.
"""

import sys
import os
import re
import json
import sqlite3
import time
import urllib.parse
from typing import Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DB_PATH = os.path.join(BASE_DIR, "web_validation_cache.db")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
}

class WebProductSearcher:
    def __init__(self, db_path: str = CACHE_DB_PATH):
        self.db_path = db_path
        self._init_db()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _init_db(self):
        """Inizializza la tabella di cache SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS web_cache (
                    cache_key TEXT PRIMARY KEY,
                    brand TEXT,
                    mpn TEXT,
                    query TEXT,
                    title TEXT,
                    snippet TEXT,
                    url TEXT,
                    specs_json TEXT,
                    found INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _make_key(self, brand: str, mpn: str) -> str:
        b = (brand or "").strip().upper()
        m = (mpn or "").strip().upper()
        return f"{b}:::{m}"

    def parse_technical_specs(self, text: str) -> Dict[str, Any]:
        """Estrae parametri tecnici chiave (kW, BTU, Gas, Combustibile, Tipologia, ecc.) da un testo web."""
        specs = {
            "kw": None,
            "btu": None,
            "gas": None,
            "fuel": None,
            "boiler_type": None,
            "ac_type": None,
            "ac_ports": None,
            "is_pump": False,
            "raw_matches": []
        }
        t_upper = text.upper()

        # 1. Potenza in kW
        m_kw = re.search(r'\b(\d+(?:[\.,]\d+)?)\s*KW\b', t_upper)
        if m_kw:
            try:
                specs["kw"] = float(m_kw.group(1).replace(',', '.'))
                specs["raw_matches"].append(f"Potenza: {specs['kw']} kW")
            except ValueError:
                pass

        # 2. Taglia BTU / Split
        m_btu = re.search(r'\b(7000|9000|12000|18000|24000)\b', t_upper)
        if m_btu:
            specs["btu"] = int(m_btu.group(1))
            specs["raw_matches"].append(f"Taglia: {specs['btu']} BTU")

        # 3. Gas refrigerante
        if "R-32" in t_upper or "R32" in t_upper:
            specs["gas"] = "R-32"
            specs["raw_matches"].append("Gas: R-32")
        elif "R-410A" in t_upper or "R410A" in t_upper:
            specs["gas"] = "R-410A"
            specs["raw_matches"].append("Gas: R-410A")

        # 4. Combustibile caldaia
        if "METANO" in t_upper or " METHANE" in t_upper:
            specs["fuel"] = "METANO"
            specs["raw_matches"].append("Combustibile: Metano")
        elif "GPL" in t_upper or "LPG" in t_upper:
            specs["fuel"] = "GPL"
            specs["raw_matches"].append("Combustibile: GPL")

        # 5. Tipologia Caldaia
        if "CONDENS" in t_upper:
            specs["boiler_type"] = "CONDENSAZIONE"
            specs["raw_matches"].append("Caldaia a Condensazione")
        elif "CAMERA APERTA" in t_upper or " CF " in t_upper or " 24 CF" in t_upper or " 28 CF" in t_upper:
            specs["boiler_type"] = "CAMERA_APERTA"
            specs["raw_matches"].append("Camera Aperta (Tiraggio Naturale CF)")
        elif "CAMERA STAGNA" in t_upper or " FF " in t_upper:
            specs["boiler_type"] = "CAMERA_STAGNA"
            specs["raw_matches"].append("Camera Stagna (FF)")

        # 6. Tipologia Climatizzatore & Porte Multi
        if any(w in t_upper for w in ["PENTA", "5 ATTACCHI", "5 UNITA", "5 SPLIT"]):
            specs["ac_type"] = "PENTA_SPLIT"
            specs["ac_ports"] = 5
            specs["raw_matches"].append("Multisplit 5 Unità (Penta)")
        elif any(w in t_upper for w in ["QUADRI", "4 ATTACCHI", "4 UNITA", "4 SPLIT"]):
            specs["ac_type"] = "QUADRI_SPLIT"
            specs["ac_ports"] = 4
            specs["raw_matches"].append("Multisplit 4 Unità (Quadri)")
        elif any(w in t_upper for w in ["TRIAL", "3 ATTACCHI", "3 UNITA", "TRE UNITA", "3 SPLIT"]):
            specs["ac_type"] = "TRIAL_SPLIT"
            specs["ac_ports"] = 3
            specs["raw_matches"].append("Multisplit 3 Unità (Trial)")
        elif any(w in t_upper for w in ["DUAL", "2 ATTACCHI", "2 UNITA", "DUE UNITA", "2 SPLIT"]):
            specs["ac_type"] = "DUAL_SPLIT"
            specs["ac_ports"] = 2
            specs["raw_matches"].append("Multisplit 2 Unità (Dual)")
        elif "MONOSPLIT" in t_upper or "MONO SPLIT" in t_upper:
            specs["ac_type"] = "MONOSPLIT"
            specs["ac_ports"] = 1
            specs["raw_matches"].append("Monosplit")

        # 7. Circolatori / Pompe
        if any(w in t_upper for w in ["CIRCOLATORE", "POMPA DI CIRCOLAZIONE", "AUTOCLAVE", "PRESSURIZZAZIONE", "ESYBOX"]):
            specs["is_pump"] = True
            specs["raw_matches"].append("Pompa / Circolatore Idraulico")

        return specs

    def get_from_cache(self, brand: str, mpn: str) -> Optional[Dict[str, Any]]:
        """Restituisce il risultato da cache se presente, senza effettuare chiamate web."""
        clean_brand = (brand or "").strip()
        clean_mpn = (mpn or "").strip()
        if not clean_mpn or clean_mpn.upper() in ("", "(VUOTO)", "VUOTO", "-", "NAN"):
            return None
        cache_key = self._make_key(clean_brand, clean_mpn)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, snippet, url, specs_json, found FROM web_cache WHERE cache_key = ? OR cache_key LIKE ?", (cache_key, f"{cache_key}::%"))
            row = cursor.fetchone()
            if row:
                title, snippet, url, specs_json, found = row
                try:
                    specs = json.loads(specs_json) if specs_json else {}
                except Exception:
                    specs = {}
                return {
                    "found": bool(found),
                    "from_cache": True,
                    "title": title or "",
                    "snippet": snippet or "",
                    "url": url or "",
                    "specs": specs
                }
        return None

    def search_product(self, brand: str, mpn: str, context_hint: Optional[str] = None, custom_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Cerca un prodotto su web tramite brand + MPN.
        Verifica prima la cache SQLite locale. In caso di cache miss, interroga il web.
        """
        clean_brand = (brand or "").strip()
        clean_mpn = (mpn or "").strip()

        if not clean_mpn or clean_mpn.upper() in ("", "(VUOTO)", "VUOTO", "-", "NAN", "NULL"):
            return {
                "found": False,
                "error": "MPN vuoto o non valido",
                "title": "",
                "snippet": "",
                "url": "",
                "specs": {}
            }

        cache_key = self._make_key(clean_brand, f"{clean_mpn}::{context_hint or ''}" if context_hint else clean_mpn)

        # 1. Controllo Cache SQLite
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, snippet, url, specs_json, found FROM web_cache WHERE cache_key = ?", (cache_key,))
            row = cursor.fetchone()
            if row:
                title, snippet, url, specs_json, found = row
                try:
                    specs = json.loads(specs_json) if specs_json else {}
                except Exception:
                    specs = {}
                return {
                    "found": bool(found),
                    "from_cache": True,
                    "title": title or "",
                    "snippet": snippet or "",
                    "url": url or "",
                    "specs": specs
                }

        # 2. Cache Miss: Interrogazione Web con Disambiguazione Termoidraulica
        domain_term = ""
        b_lower = clean_brand.lower()
        if b_lower == "4xe":
            domain_term = "climatizzatore condizionatore"
        elif context_hint:
            c_low = context_hint.lower()
            if "condiz" in c_low or "clima" in c_low:
                domain_term = "climatizzatore"
            elif "cald" in c_low or "riscald" in c_low:
                domain_term = "caldaia"
            elif "scald" in c_low:
                domain_term = "scaldabagno"
            elif "pompa" in c_low or "circolat" in c_low or "autoclave" in c_low:
                domain_term = "pompa idraulica"

        if custom_query:
            query = custom_query
        else:
            query = f"{clean_brand} {clean_mpn} {domain_term} scheda tecnica".strip()
            query = re.sub(r'\s+', ' ', query)

        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

        title = ""
        snippet = ""
        found_url = ""
        found = False
        specs = {}

        try:
            resp = self.session.get(url, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                results = soup.select('.result')
                if results:
                    found = True
                    first_res = results[0]
                    t_elem = first_res.select_one('.result__title')
                    if t_elem:
                        title = t_elem.text.strip()
                    s_elem = first_res.select_one('.result__snippet')
                    if s_elem:
                        snippet = s_elem.text.strip()
                    u_elem = first_res.select_one('.result__url')
                    if u_elem:
                        found_url = u_elem.text.strip()

                    # Raccogli anche snippet dei primi 3 risultati per arricchire l'estrazione
                    combined_text = f"{title} {snippet} "
                    for r in results[1:3]:
                        snip = r.select_one('.result__snippet')
                        if snip:
                            combined_text += snip.text.strip() + " "

                    specs = self.parse_technical_specs(combined_text)
            else:
                found = False
        except Exception as e:
            found = False
            snippet = f"Errore connessione web: {str(e)}"

        # 3. Salvataggio in Cache
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO web_cache (cache_key, brand, mpn, query, title, snippet, url, specs_json, found)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cache_key, clean_brand, clean_mpn, query, title, snippet, found_url, json.dumps(specs, ensure_ascii=False), 1 if found else 0))
            conn.commit()

        return {
            "found": found,
            "from_cache": False,
            "title": title,
            "snippet": snippet,
            "url": found_url,
            "specs": specs
        }


if __name__ == "__main__":
    searcher = WebProductSearcher()
    print("Testing Ariston 3301313...")
    res1 = searcher.search_product("Ariston", "3301313")
    print(json.dumps(res1, indent=2, ensure_ascii=False))

    print("\nTesting Daikin 3MXM68A...")
    res2 = searcher.search_product("Daikin", "3MXM68A")
    print(json.dumps(res2, indent=2, ensure_ascii=False))
