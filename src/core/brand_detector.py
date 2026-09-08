"""
src/core/brand_detector.py
Rilevatore dinamico di marchi commerciali e industriali per il Catalogo Puglia Termica.
Principi architetturali:
1. Basato dinamicamente sull'anagrafica master unificata (416 brand unici indicizzati).
2. Alias conservativi e documentati: include SOLO ridenominazioni ufficiali, fusioni societarie
   o varianti di registrazione anagrafica documentate nel catalogo Puglia Termica.
   NON include equivalenze OEM, accordi commerciali o joint-venture esterne non anagrafiche.
3. Matching con word-boundary rigorosi e ordinamento per lunghezza decrescente.
"""

import os
import re
import json
from typing import List, Dict, Tuple, Optional, Set

# Alias strettamente documentati nell'anagrafica Puglia Termica 2026:
CONSERVATIVE_BRAND_ALIASES = {
    # Rebranding ufficiale: la divisione termotecnica Junkers è commercializzata come BOSCH
    "JUNKERS": "BOSCH",
    # Denominazione anagrafica PT: i prodotti DAB sono registrati sotto "DAB PUMPS"
    "DAB": "DAB PUMPS",
    # Denominazione anagrafica PT: Mitsubishi Electric è registrato come "MITSUBISHI"
    "MITSUBISHI ELECTRIC": "MITSUBISHI",
    # Ragione sociale e marchio unificato in PT: Hermann e Saunier Duval fusi in un unico marchio
    "HERMANN": "HERMANN SAUNIER DUVAL",
    "SAUNIER DUVAL": "HERMANN SAUNIER DUVAL",
    # Denominazione anagrafica PT: Global Radiatori è registrato come "GLOBAL RADIATORI"
    "GLOBAL": "GLOBAL RADIATORI",
    # Denominazione anagrafica PT: Polymax è registrato come "POLYMAXACCIAI"
    "POLYMAX": "POLYMAXACCIAI",
}


class DynamicBrandDetector:
    """
    Rilevatore dinamico di brand basato sull'anagrafica catalogo + alias conservativi.
    """

    def __init__(
        self,
        master_catalog: Optional[List[Dict]] = None,
        master_catalog_path: Optional[str] = None,
        aliases: Optional[Dict[str, str]] = None
    ):
        self._aliases = dict(aliases or CONSERVATIVE_BRAND_ALIASES)
        self._brands: Set[str] = set()
        self._search_patterns: List[Tuple[re.Pattern, str]] = []
        self._initialized = False

        if master_catalog:
            self._init_from_catalog_list(master_catalog)
        elif master_catalog_path and os.path.exists(master_catalog_path):
            self._init_from_catalog_path(master_catalog_path)

    def _init_from_catalog_list(self, catalog_list: List[Dict]):
        brands = set()
        for it in catalog_list:
            b = (it.get("brand") or "").strip().upper()
            if b and b != "." and len(b) >= 2:
                brands.add(b)
        self._build_patterns(brands)

    def _init_from_catalog_path(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._init_from_catalog_list(data)
        except Exception:
            pass

    def _build_patterns(self, brands: Set[str]):
        self._brands = brands
        search_entries = []

        # 1. Includi gli alias conservativi documentati
        for alias, target in self._aliases.items():
            search_entries.append((alias.strip().upper(), target.strip().upper()))

        # 2. Includi tutti i brand reali presenti nell'anagrafica
        for b in brands:
            search_entries.append((b, b))

        # 3. Rimuovi duplicati preservando l'ordine di lunghezza decrescente
        seen = set()
        unique_entries = []
        for term, target in sorted(search_entries, key=lambda x: len(x[0]), reverse=True):
            if term not in seen:
                seen.add(term)
                unique_entries.append((term, target))

        self._search_patterns = []
        for term, target in unique_entries:
            escaped = re.escape(term)
            pat = re.compile(r'(?<![A-Z0-9])' + escaped + r'(?![A-Z0-9])', re.IGNORECASE)
            self._search_patterns.append((pat, target))

        self._initialized = True

    def ensure_initialized(self, fallback_catalog: Optional[List[Dict]] = None):
        if not self._initialized and fallback_catalog:
            self._init_from_catalog_list(fallback_catalog)

    def detect_brand(self, text: str) -> Optional[str]:
        """
        Rileva il primo brand canonico corrispondente nel testo della query.
        Restituisce il nome canonico del brand (es. 'BOSCH', 'PANASONIC', 'MITSUBISHI').
        """
        if not text:
            return None
        t_clean = text.strip()
        for pat, target in self._search_patterns:
            if pat.search(t_clean):
                return target
        return None

    def get_all_brands(self) -> Set[str]:
        return set(self._brands)
