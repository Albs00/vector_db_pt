"""Authoritative, fail-closed resolver for PT26_CLIMA_PROD_1.

The resolver is intentionally isolated from retrieval.  It loads the production
masters once, resolves only exact or uniquely demonstrated configurations, and
never lets ranking invent a UI/UE relationship.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.core.color_variants import normalize_color_variant
from src.core.model_identity import normalize_structural_model


class ClimaMasterError(RuntimeError):
    """Raised when a production master fails its release contract."""


class ClimaMasterResolver:
    DATASET_VERSION = "PT26_CLIMA_PROD_1"
    SCHEMA_VERSION = "3.0.0"
    POLICY = "FAIL_CLOSED"
    EXPECTED_SHA256 = {
        "clima_monosplit_master.json": "05f56077cc1254025bc995ca2cfcdcf374ce8529846cba023f3898e1b0bbd81b",
        "clima_multisplit_master.json": "0cf07f4e71768af267c81b1dd64171604a72432ea796f159245991af9a0c1e9b",
        "manual_overrides_clima.json": "ce4eb075c46717276835e18219ba36c5a59879befe11bca32b97709403a9ba68",
    }

    def __init__(self, knowledge_dir: str | Path):
        self.knowledge_dir = Path(knowledge_dir)
        self.hashes: Dict[str, str] = {}
        self.mono = self._load_release("clima_monosplit_master.json")
        self.multi = self._load_release("clima_multisplit_master.json")
        self.manual = self._load_release("manual_overrides_clima.json", release_contract=False)
        accessory_path = self.knowledge_dir / "clima_accessori_master.json"
        self.accessories = self._load_json(accessory_path) if accessory_path.exists() else None
        if accessory_path.exists():
            self.hashes[accessory_path.name] = self._sha256(accessory_path)

        self.products_by_scope_pt: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
            "MONOSPLIT": defaultdict(list),
            "MULTISPLIT": defaultdict(list),
        }
        for scope, document in (("MONOSPLIT", self.mono), ("MULTISPLIT", self.multi)):
            for product in document["products"]:
                self.products_by_scope_pt[scope][str(product["pt"])].append(product)

        self.model_index: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
            "MONOSPLIT": defaultdict(list),
            "MULTISPLIT": defaultdict(list),
        }
        for scope, document in (("MONOSPLIT", self.mono), ("MULTISPLIT", self.multi)):
            for product in document["products"]:
                if product.get("exact_manufacturer_model_eligible") is False:
                    continue
                if product.get("model_kind") == "CATALOG_LABEL":
                    continue
                spellings = [product.get("model"), product.get("manufacturer_model")]
                spellings.extend(product.get("model_aliases") or [])
                for spelling in spellings:
                    key = normalize_structural_model(spelling)
                    if len(key) >= 4 and product not in self.model_index[scope][key]:
                        self.model_index[scope][key].append(product)

        self.mono_pairs = [row for row in self.mono["pairs"] if row.get("status") == "CONFIRMED"]
        self.mono_pairs_by_ui: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.mono_pairs_by_ue: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for pair in self.mono_pairs:
            self.mono_pairs_by_ui[str(pair["ui_pt"])].append(pair)
            self.mono_pairs_by_ue[str(pair["ue_pt"])].append(pair)

        self.multi_configurations = [
            row for row in self.multi["combination_master"] if row.get("status") == "CONFIRMED"
        ]
        self.multi_configs_by_ue: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for configuration in self.multi_configurations:
            self.multi_configs_by_ue[str(configuration["ue_pt"])].append(configuration)
        self.systems = self.multi["systems"]
        self.ui_context_by_system_pt: Dict[Tuple[int, str], Dict[str, Any]] = {}
        for system_id, system in enumerate(self.systems):
            for edge in system.get("allowed_ui") or []:
                context_id = edge.get("ui_context_id")
                if isinstance(context_id, int) and 0 <= context_id < len(self.multi["ui_catalog"]):
                    self.ui_context_by_system_pt[(system_id, str(edge["pt"]))] = self.multi["ui_catalog"][context_id]

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _load_release(self, filename: str, release_contract: bool = True) -> Dict[str, Any]:
        path = self.knowledge_dir / filename
        if not path.exists():
            raise ClimaMasterError(f"Missing production master: {path}")
        actual = self._sha256(path)
        expected = self.EXPECTED_SHA256[filename]
        if actual != expected:
            raise ClimaMasterError(f"SHA256 mismatch for {filename}: {actual} != {expected}")
        document = self._load_json(path)
        self.hashes[filename] = actual
        if release_contract:
            if document.get("schema_version") != self.SCHEMA_VERSION:
                raise ClimaMasterError(f"Unsupported schema for {filename}")
            if document.get("dataset_version") != self.DATASET_VERSION:
                raise ClimaMasterError(f"Unexpected dataset release for {filename}")
            if document.get("production_policy") != self.POLICY:
                raise ClimaMasterError(f"Non fail-closed master: {filename}")
            if document.get("release_status") != "PRODUCTION_MASTER":
                raise ClimaMasterError(f"Master is not production-approved: {filename}")
        elif (
            document.get("schema_version") != "1.0.0"
            or document.get("source_id") != "MANUAL_OVERRIDES_CLIMA_V1"
            or document.get("policy") != "EXISTING_V3_MANUAL_ASSERTIONS_ONLY_NO_NEW_AUTHORIZATION"
        ):
            raise ClimaMasterError(f"Invalid manual override contract: {filename}")
        return document

    @staticmethod
    def _brand_matches(requested: Optional[str], actual: Optional[str]) -> bool:
        if not requested:
            return True
        left = normalize_structural_model(requested)
        right = normalize_structural_model(actual)
        return bool(left and right and (left in right or right in left))

    @staticmethod
    def _family_score(query: str, family: Optional[str]) -> int:
        query_words = set(re.findall(r"[A-Z0-9]+", str(query).upper()))
        family_words = [word for word in re.findall(r"[A-Z0-9]+", str(family or "").upper()) if len(word) >= 3]
        return sum(1 for word in family_words if word in query_words)

    @staticmethod
    def _requested_type(context: Dict[str, Any]) -> Optional[str]:
        value = context.get("explicit_tipologia") or context.get("probable_tipologia")
        aliases = {
            "PARETE": "WALL",
            "CANALIZZATO": "DUCTED",
            "CASSETTA": "CASSETTE",
            "PAVIMENTO": "FLOOR",
            "SOFFITTO": "CEILING",
        }
        return aliases.get(value, value)

    def _exact_products(
        self,
        query: str,
        scope: str,
        exact_candidates: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        selected: Dict[Tuple[str, str], Dict[str, Any]] = {}
        explicit_pts = set(re.findall(r"(?<!\d)\d{8}(?!\d)", query))
        explicit_pts.update(str(item.get("code") or "") for item in exact_candidates)
        for pt in explicit_pts:
            for product in self.products_by_scope_pt[scope].get(pt, []):
                selected[(product["pt"], product["role"])] = product

        normalized_query = normalize_structural_model(query)
        for model, products in self.model_index[scope].items():
            if model not in normalized_query:
                continue
            for product in products:
                selected[(product["pt"], product["role"])] = product

        requested_color = normalize_color_variant(query).get("color_base")
        result = []
        for product in selected.values():
            color = product.get("color_base")
            if requested_color and color and color != requested_color:
                continue
            result.append(product)
        return result

    def _product(self, scope: str, pt: str, role: Optional[str] = None) -> Optional[Dict[str, Any]]:
        rows = self.products_by_scope_pt[scope].get(str(pt), [])
        if role:
            rows = [row for row in rows if row.get("role") == role]
        return rows[0] if rows else None

    def _component(
        self,
        product: Dict[str, Any],
        family: Optional[str],
        capacity: Optional[int],
        source: Dict[str, Any],
    ) -> Dict[str, Any]:
        role = product.get("role")
        return {
            "code": str(product["pt"]),
            "mfg_code": product.get("model"),
            "name": product.get("model"),
            "brand": product.get("brand"),
            "role": role,
            "is_ui": role == "UI",
            "is_ue": role == "UE",
            "tipo_unita": role,
            "taglia_btu": capacity if role == "UI" else None,
            "catalog_family": family,
            "family_key": family,
            "color_base": product.get("color_base"),
            "variant_full": product.get("variant_full"),
            "product_type": product.get("type"),
            "slot_id": "slot_ue" if role == "UE" else f"slot_ui_{capacity or 'exact'}",
            "match_type": "MASTER_EXACT",
            "identity_evidence": "MASTER_EXACT_IDENTITY",
            "relation_evidence": source,
            "evidence_tier": 1,
            "score": 1000.0,
        }

    def _accessory_resolution(self, query: str, main_components: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.accessories:
            return {"status": "NOT_AVAILABLE", "bom": [], "evidence": [], "ambiguous": []}
        query_upper = query.upper()
        pt_counts = Counter(str(item["code"]) for item in main_components if item.get("code"))
        bom: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []
        ambiguous: List[Dict[str, Any]] = []
        seen_requirements = set()

        for product_pt, instances in pt_counts.items():
            offsets = (self.accessories.get("index_by_product_pt") or {}).get(product_pt) or {}
            for requirement_offset in offsets.get("requirements") or []:
                requirement = self.accessories["requirements"][requirement_offset]
                if requirement.get("status") != "CONFIRMED":
                    continue
                dedupe_key = (product_pt, requirement.get("category"), requirement.get("family_id"))
                if dedupe_key in seen_requirements:
                    continue
                seen_requirements.add(dedupe_key)
                alternatives = [str(pt) for pt in requirement.get("alternatives") or []]
                explicitly_named = [pt for pt in alternatives if pt in query]
                chosen = None
                if len(explicitly_named) == 1:
                    chosen = explicitly_named[0]
                elif requirement.get("AUTO_RESOLVABLE") and len(alternatives) == 1:
                    chosen = alternatives[0]
                elif requirement.get("requirement_type") == "ONE_OF":
                    ambiguous.append({
                        "product_pt": product_pt,
                        "category": requirement.get("category"),
                        "alternatives": alternatives,
                        "requirement_id": requirement.get("id"),
                    })
                if chosen:
                    quantity = requirement.get("quantity")
                    if requirement.get("quantity_basis") == "PER_PRODUCT_INSTANCE":
                        quantity = int(quantity or 1) * instances
                    elif requirement.get("quantity_basis") == "PER_SYSTEM":
                        quantity = int(quantity or 1)
                    elif requirement.get("quantity_basis") == "EXPLICIT_QUANTITY":
                        quantity = int(quantity or 1)
                    else:
                        continue
                    bom.extend({
                        "code": chosen,
                        "role": "ACCESSORY",
                        "category": requirement.get("category"),
                        "required_for_pt": product_pt,
                        "source": requirement.get("source"),
                    } for _ in range(quantity))
                    evidence.append(requirement)

            for relation_offset in offsets.get("relations") or []:
                relation = self.accessories["relations"][relation_offset]
                if relation.get("relation_status") != "CONFIRMED" or relation.get("selection_policy") != "EXPLICIT_ONLY":
                    continue
                accessory_pt = str(relation.get("accessory_pt") or "")
                accessory_model = ""
                for index in (self.accessories.get("index_by_accessory_pt") or {}).get(accessory_pt, {}).get("accessories") or []:
                    accessory_model = str(self.accessories["accessories"][index].get("model") or "")
                    break
                if accessory_pt not in query and (not accessory_model or accessory_model.upper() not in query_upper):
                    continue
                quantity = relation.get("quantity")
                if relation.get("quantity_basis") == "PER_PRODUCT_INSTANCE":
                    quantity = int(quantity or 1) * instances
                elif relation.get("quantity_basis") in {"PER_SYSTEM", "EXPLICIT_QUANTITY"}:
                    quantity = int(quantity or 1)
                else:
                    continue
                bom.extend({
                    "code": accessory_pt,
                    "mfg_code": accessory_model or None,
                    "role": "ACCESSORY",
                    "category": relation.get("category"),
                    "required_for_pt": product_pt,
                    "source": relation.get("source"),
                } for _ in range(quantity))
                evidence.append(relation)

        status = "ACCESSORY_AMBIGUOUS" if ambiguous else "CONFIRMED" if bom else "NONE_SELECTED"
        return {"status": status, "bom": bom, "evidence": evidence, "ambiguous": ambiguous}

    def resolve_accessories(self, query: str, main_components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve accessories only after the exact main-unit BOM is known."""
        return self._accessory_resolution(query, main_components)

    def _result(
        self,
        query: str,
        scope: str,
        components: List[Dict[str, Any]],
        evidence: Dict[str, Any],
        include_accessories: bool,
        configuration_status: str,
    ) -> Dict[str, Any]:
        accessory = self._accessory_resolution(query, components) if include_accessories else {
            "status": "DISABLED", "bom": [], "evidence": [], "ambiguous": []
        }
        bom = components + accessory["bom"]
        candidate_pools: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in components:
            candidate_pools[item["slot_id"]].append(item)
        confirmed = configuration_status in {"VERIFIED_MASTER_PAIR", "VERIFIED_FULL_COMBINATION", "NOT_APPLICABLE_EXACT_IDENTITY"}
        source = evidence.get("source") or {}
        reason = evidence.get("reason") or "MASTER_EXACT_IDENTITY"
        return {
            "query": query,
            "detected_brand": components[0].get("brand") if components else None,
            "detected_category": "CLIMA",
            "match_type": "clima_master_authoritative",
            "total_results": len(components),
            "results": components,
            "candidate_pools": dict(candidate_pools),
            "relations": [],
            "query_analysis": {
                "query_context": {"product_scope": scope},
                "product_scope": scope,
                "product_identity_status": "EXACT",
                "configuration_status": configuration_status,
                "pairing_status": "PAIRING_CONFIRMED" if confirmed else "CONFIGURAZIONE_NON_CONFERMATA",
                "mpn_final_allowed": confirmed,
                "master_evidence": evidence,
            },
            "product_scope": scope,
            "compatibility_status": "VERIFIED" if confirmed else "NOT_VERIFIED",
            "compatibility_evidence": {"source": source, "reason": reason, "dataset": self.DATASET_VERSION},
            "bom": bom,
            "main_unit_bom": components,
            "accessory_bom": accessory["bom"],
            "accessory_status": accessory["status"],
            "accessory_ambiguous": accessory["ambiguous"],
            "component_relations": accessory["evidence"],
            "component_relation_source": "clima_accessori_master.json" if self.accessories else None,
            "pairing_reason": reason,
            "pairing_status": "PAIRING_CONFIRMED" if confirmed else "CONFIGURAZIONE_NON_CONFERMATA",
            "mpn_final_allowed": confirmed,
            "product_identity_status": "EXACT",
            "configuration_status": configuration_status,
            "master_evidence": evidence,
            "dataset_release": self.DATASET_VERSION,
            "schema_version": self.SCHEMA_VERSION,
            "production_policy": self.POLICY,
        }

    def resolve(
        self,
        query: str,
        query_context: Dict[str, Any],
        exact_candidates: Iterable[Dict[str, Any]],
        include_accessories: bool = True,
    ) -> Optional[Dict[str, Any]]:
        raw_scope = str(query_context.get("product_scope") or "GENERAL")
        requested_btus = [int(value) for value in query_context.get("requested_btus") or []]
        if not requested_btus:
            capacity_map = {
                "7": 7000, "9": 9000, "12": 12000, "15": 15000,
                "18": 18000, "21": 21000, "24": 24000, "28": 28000,
                "30": 30000, "36": 36000, "42": 42000, "48": 48000,
            }
            for token in re.findall(
                r"(?<![A-Z0-9])(7000|9000|12000|15000|18000|21000|24000|28000|30000|36000|42000|48000|7|9|12|15|18|21|24|28|30|36|42|48)(?![A-Z0-9])",
                query,
                flags=re.IGNORECASE,
            ):
                requested_btus.append(int(token) if len(token) >= 4 else capacity_map[token])
        if raw_scope == "GENERAL" and requested_btus:
            raw_scope = "MULTISPLIT" if len(requested_btus) > 1 else "MONOSPLIT"
        explicit_or_exact_pts = set(re.findall(r"(?<!\d)\d{8}(?!\d)", query))
        explicit_or_exact_pts.update(str(item.get("code") or "") for item in exact_candidates)
        only_multi = any(
            self.products_by_scope_pt["MULTISPLIT"].get(pt)
            and not self.products_by_scope_pt["MONOSPLIT"].get(pt)
            for pt in explicit_or_exact_pts
        )
        scope = "MULTISPLIT" if raw_scope == "MULTISPLIT" or only_multi else "MONOSPLIT"
        exact = self._exact_products(query, scope, exact_candidates)
        requested_color = normalize_color_variant(query).get("color_base")
        requested_type = self._requested_type(query_context)
        brand = query_context.get("detected_brand") or query_context.get("requested_brand")

        if raw_scope in {"UI_ONLY", "UE_ONLY", "GENERAL"} and exact:
            expected_role = "UI" if raw_scope == "UI_ONLY" else "UE" if raw_scope == "UE_ONLY" else None
            filtered = [item for item in exact if expected_role is None or item.get("role") == expected_role]
            identities = {(item["pt"], item["role"]): item for item in filtered}
            if len(identities) == 1:
                product = next(iter(identities.values()))
                resolved_scope = f"{product['role']}_ONLY"
                component = self._component(product, None, requested_btus[0] if requested_btus else None, {"id": self.DATASET_VERSION})
                return self._result(query, resolved_scope, [component], {
                    "reason": "MASTER_EXACT_IDENTITY", "pt": product["pt"], "source": {"id": self.DATASET_VERSION}
                }, include_accessories, "NOT_APPLICABLE_EXACT_IDENTITY")

        exact_ui = {item["pt"] for item in exact if item.get("role") == "UI"}
        exact_ue = {item["pt"] for item in exact if item.get("role") == "UE"}

        if scope == "MONOSPLIT":
            candidates = self.mono_pairs
            if exact_ui:
                candidates = [row for row in candidates if row["ui_pt"] in exact_ui]
            if exact_ue:
                candidates = [row for row in candidates if row["ue_pt"] in exact_ue]
            candidates = [row for row in candidates if self._brand_matches(brand, row.get("brand"))]
            if requested_btus:
                candidates = [row for row in candidates if row.get("ui_capacity", {}).get("btu_match") == requested_btus[0]]
            if requested_color:
                candidates = [row for row in candidates if not (self._product("MONOSPLIT", row["ui_pt"], "UI") or {}).get("color_base") or (self._product("MONOSPLIT", row["ui_pt"], "UI") or {}).get("color_base") == requested_color]
            if requested_type:
                candidates = [row for row in candidates if (self._product("MONOSPLIT", row["ui_pt"], "UI") or {}).get("type") == requested_type]
            if not candidates:
                return None
            scored = sorted(candidates, key=lambda row: self._family_score(query, row.get("family")), reverse=True)
            best_score = self._family_score(query, scored[0].get("family"))
            best = [row for row in scored if self._family_score(query, row.get("family")) == best_score]
            sufficient = bool(exact_ui or exact_ue) or bool(brand and requested_btus and best_score > 0)
            if len(best) != 1 or not sufficient:
                return None
            pair = best[0]
            ui_product = self._product("MONOSPLIT", pair["ui_pt"], "UI")
            ue_product = self._product("MONOSPLIT", pair["ue_pt"], "UE")
            if not ui_product or not ue_product:
                return None
            source = pair.get("source") or {}
            components = [
                self._component(ui_product, pair.get("family"), pair.get("ui_capacity", {}).get("btu_match"), source),
                self._component(ue_product, pair.get("family"), None, source),
            ]
            return self._result(query, "MONOSPLIT", components, {
                "reason": "MASTER_EXACT_PAIR", "configuration_key": f"MONOSPLIT|{pair['ui_pt']}|{pair['ue_pt']}",
                "source": source, "provenance": pair.get("provenance"),
            }, include_accessories, "VERIFIED_MASTER_PAIR")

        candidates = self.multi_configurations
        if exact_ue:
            candidates = [row for row in candidates if row["ue_pt"] in exact_ue]
        if exact_ui:
            requested_multiset = Counter(exact_ui)
            # Direct repeated PTs in the query carry their actual multiplicity.
            query_pts = re.findall(r"(?<!\d)\d{8}(?!\d)", query)
            requested_multiset = Counter(pt for pt in query_pts if pt in exact_ui) or requested_multiset
            candidates = [row for row in candidates if all(Counter(row["ui_pts"])[pt] >= count for pt, count in requested_multiset.items())]
        if requested_btus:
            signature = sorted(requested_btus)
            candidates = [row for row in candidates if sorted(value for value in row.get("capacity_signature") or [] if value is not None) == signature]
        filtered = []
        for row in candidates:
            system = self.systems[row["system_id"]]
            if not self._brand_matches(brand, system.get("brand")):
                continue
            products = [self._product("MULTISPLIT", pt, "UI") for pt in row["ui_pts"]]
            if any(product is None for product in products):
                continue
            if requested_color and any(product.get("color_base") and product.get("color_base") != requested_color for product in products):
                continue
            if requested_type and any(product.get("type") != requested_type for product in products):
                continue
            filtered.append(row)
        if not filtered:
            return None
        scored = sorted(filtered, key=lambda row: self._family_score(query, self.systems[row["system_id"]].get("family")), reverse=True)
        best_score = self._family_score(query, self.systems[scored[0]["system_id"]].get("family"))
        best = [row for row in scored if self._family_score(query, self.systems[row["system_id"]].get("family")) == best_score]
        sufficient = bool(exact_ue or exact_ui) or bool(brand and requested_btus and best_score > 0)
        if len(best) != 1 or not sufficient:
            return None
        configuration = best[0]
        system = self.systems[configuration["system_id"]]
        source = configuration.get("source") or {}
        components = []
        occurrence = Counter()
        for pt in configuration["ui_pts"]:
            occurrence[pt] += 1
            product = self._product("MULTISPLIT", pt, "UI")
            context = self.ui_context_by_system_pt.get((configuration["system_id"], pt), {})
            components.append(self._component(product, context.get("family") or system.get("family"), context.get("btu_match"), source))
        ue_product = self._product("MULTISPLIT", configuration["ue_pt"], "UE")
        if not ue_product:
            return None
        components.append(self._component(ue_product, system.get("family"), None, source))
        return self._result(query, "MULTISPLIT", components, {
            "reason": "MASTER_EXACT_CONFIGURATION", "configuration_key": configuration["configuration_key"],
            "source": source, "provenance": configuration.get("provenance"),
        }, include_accessories, "VERIFIED_FULL_COMBINATION")

    def validate_legacy_bom(self, product_scope: Optional[str], bom: List[Dict[str, Any]]) -> Dict[str, Any]:
        ui_pts = [str(item.get("code")) for item in bom if (item.get("role") == "UI" or item.get("is_ui")) and item.get("code")]
        ue_pts = [str(item.get("code")) for item in bom if (item.get("role") == "UE" or item.get("is_ue")) and item.get("code")]
        if product_scope == "MONOSPLIT" and len(ui_pts) == 1 and len(ue_pts) == 1:
            key = f"MONOSPLIT|{ui_pts[0]}|{ue_pts[0]}"
            if key in self.mono.get("index_by_configuration_key", {}):
                return {"confirmed": True, "configuration_status": "VERIFIED_MASTER_PAIR", "configuration_key": key}
        if product_scope == "MULTISPLIT" and len(ue_pts) == 1:
            key = f"MULTISPLIT|{ue_pts[0]}|{','.join(sorted(ui_pts))}"
            if key in self.multi.get("index_by_configuration_key", {}):
                return {"confirmed": True, "configuration_status": "VERIFIED_FULL_COMBINATION", "configuration_key": key}
        all_known = all(
            self.products_by_scope_pt.get(product_scope or "", {}).get(pt)
            for pt in ui_pts + ue_pts
        )
        return {
            "confirmed": False,
            "configuration_status": "CONFIGURAZIONE_NON_CONFERMATA",
            "configuration_key": None,
            "all_main_pt_in_master": all_known,
        }
