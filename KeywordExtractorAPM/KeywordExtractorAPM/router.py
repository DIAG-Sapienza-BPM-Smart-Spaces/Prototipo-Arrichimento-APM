import json
from pathlib import Path
import config
from text_cleaner import clean_text
from validator import validate_material, validate_against_taxonomy, calculate_confidence
from keyword_extractor import Extractor
def maybe_capture(*_a, **_k):  # orphan_pool retired (online has no ALTRO)
    return False


class Router:
    def __init__(self):
        self.taxonomy = self._load_json(config.TAXONOMY_PATH)

        # --- Regime C: veriden uretilen kategori listeleri (elle yazilan yerine) ---
        for _field, _path in getattr(config, "INDUCED_FIELDS", {}).items():
            _ind = self._load_json(_path)
            _sec = _ind.get(_field)
            if _sec and _sec.get("values"):
                self.taxonomy[_field] = _sec
                print(f"[Regime C] {_field}: induced'dan {len(_sec['values'])} kategori")
            else:
                print(f"[Regime C] UYARI: {_field} induced yok -> elle yazilan.")
        self.material_map = self._load_json(config.MATERIAL_MAP_PATH)

        self.learned_mappings = self._load_json(config.LEARNED_MAPPINGS_PATH)
        if "_meta" not in self.learned_mappings:
            self.learned_mappings = {"_meta": {"total_mappings": 0}}

        self.extractor = Extractor()

        # --- online taxonomy: sistema & sintomo grow as data flows (no build step) ---
        from online_taxonomy import OnlineTaxonomy
        from name_normalizer import load_reference
        from validator import embedder as _emb
        _ref_sin = {}
        _psin = Path(config.BASE_DIR) / "reference_vocabulary_sintomo.json"
        if _psin.exists():
            for _g, _terms in json.loads(_psin.read_text(encoding="utf-8")).items():
                if not str(_g).startswith("_"):
                    _ref_sin.update(_terms)
        _tf = Path(config.BASE_DIR) / "taxonomy_free"
        self.online_sistema = OnlineTaxonomy("sistema", _emb, self.extractor.llm,
                                             load_reference(), path=_tf / "sistema_online.json")
        self.online_sintomo = OnlineTaxonomy("sintomo", _emb, self.extractor.llm,
                                             _ref_sin, path=_tf / "sintomo_online.json")
        _az_sec = self.taxonomy.get("azione", {})
        _az_ref = {v: _az_sec.get("descriptions", {}).get(v, v)
                   for v in _az_sec.get("values", []) if v not in ("ALTRO", "N/A")}
        self.online_azione = OnlineTaxonomy("azione", _emb, self.extractor.llm,
                                            _az_ref, path=_tf / "azione_online.json")
        self.online_componente = OnlineTaxonomy("componente", _emb, self.extractor.llm,
                                                 {}, sim=0.88, path=_tf / "componente_online.json")

        # Remove free fields from the taxonomy (to be sent to LLM)
        self.filtered_taxonomy = {
            k: v for k, v in self.taxonomy.items()
            if k not in ("componente", "luogo")
        }

    def _load_json(self, path):
        if Path(path).exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_mappings(self):
        with open(config.LEARNED_MAPPINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.learned_mappings, f, indent=2, ensure_ascii=False)
        self.online_sistema.save()
        self.online_sintomo.save()
        self.online_azione.save()
        self.online_componente.save()

    def _extract_component_from_materials(self, material_list: list) -> str:
        """
        Extract componente from material columns.
        Priority: if there is a match in material_map, translate it,
        otherwise use the material name as is.
        If there are multiple materials, separate with commas.
        """
        if not material_list:
            return ""

        components = []
        for mat in material_list:
            mat_upper = mat.strip().upper()
            if not mat_upper:
                continue

            # Is there a match in material_map?
            if mat_upper in self.material_map:
                comp = self.material_map[mat_upper].get("componente", mat_upper)
                components.append(comp)
            else:
                # If no match, use the material name as is
                components.append(mat_upper)

        # Remove duplicates, preserve order
        seen = set()
        unique = []
        for c in components:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        return ", ".join(unique) if unique else ""

    def _normalize_componente(self, comp: str) -> str:
        """Clean Componente output: empty empty-like values,
        normalize ORING->O_RING, remove duplicates, fix format."""
        if not comp:
            return ""
        # Empty-like LLM outputs
        junk = {"NON_SPECIFICATO", "N/A", "NA", "NESSUN PEZZO COINVOLTO",
                "NESSUN PEZZO", "NESSUNO", "ALTRO", "GENERALE", "OLIO MOTORE"}
        parts = [p.strip() for p in str(comp).split(",") if p.strip()]
        cleaned = []
        for p in parts:
            pu = p.upper().strip()
            if pu in junk:
                continue
            # Normalize ORING -> O_RING
            pu = pu.replace("ORING", "O_RING").replace("O-RING", "O_RING")
            if pu not in cleaned:
                cleaned.append(pu)
        return ", ".join(cleaned)

    def process_row(self, testo_breve: str, material_list: list) -> dict:
        cleaned_text = clean_text(testo_breve)

        if not cleaned_text:
            return {k: "N/A" for k in config.KEYWORD_COLUMNS}

        # Cache check
        if cleaned_text in self.learned_mappings and cleaned_text != "_meta":
            result = self.learned_mappings[cleaned_text].copy()
            result["kw_confidence"] = "HIGH"
            return result

        # Material hint
        material_hint_str = " ".join(material_list) if material_list else ""
        material_hint = validate_material(material_hint_str, self.material_map)
        material_component = self._extract_component_from_materials(material_list)

        try:
            # --- NEW TWO-STAGE EXTRACTION ---
            
            # Stage 1: Free Extraction (understanding without restricting the LLM)
            # componente is fully LLM-driven; the material column is an INPUT the LLM
            # must translate/use, not a hard-coded authority.
            free_analysis_result = self.extractor.extract_stage_1(
                cleaned_text, {"materiali": material_list})
            
            # Stage 2: Taxonomy Mapping
            raw_result = self.extractor.extract_stage_2(free_analysis_result, self.filtered_taxonomy)

            # componente comes from the LLM (no material_map override).
            
            # Save Luogo info from the first stage (since it has no place in the taxonomy, Stage 2 might sometimes delete it)
            if "luogo" in free_analysis_result and raw_result.get("kw_luogo", "N/A") == "N/A":
                raw_result["kw_luogo"] = str(free_analysis_result["luogo"]).upper()

            # Validation (Inspector)
            validated = validate_against_taxonomy(raw_result, self.taxonomy)

            # AZIONE: free multi-value column (like componente). Kept exactly as the
            # LLM produced it in kw_azione (all actions, comma-separated). No split,
            # no deterministic override, no fixed-list validation.

            # COMPONENTE normalization (ORING->O_RING, empty-like cleaning, remove duplicates)
            validated["kw_componente"] = self._normalize_componente(
                validated.get("kw_componente", "")
            )

            # Calculate confidence
            # --- online taxonomy: grow sistema & sintomo from Stage-1 free words ---
            _sis = str(free_analysis_result.get("sistema_libero", "")).strip()
            _sin = str(free_analysis_result.get("sintomo_libero", "")).strip()
            if _sis:
                validated["kw_sistema"] = self.online_sistema.assign(_sis)
            if _sin:
                validated["kw_sintomo"] = self.online_sintomo.assign(_sin)
            # azione & componente also grow online (multi-value, no ALTRO)
            _az = str(validated.get("kw_azione", "")).strip()
            if _az and _az.upper() not in ("N/A", "ALTRO", "ERROR", "NAN"):
                _ak = [self.online_azione.assign(x.strip())
                       for x in _az.split(",") if x.strip()]
                validated["kw_azione"] = ", ".join(dict.fromkeys(_ak))
            _co = str(validated.get("kw_componente", "")).strip()
            if _co and _co.upper() not in ("N/A", "ALTRO", "ERROR", "NAN"):
                _pf = lambda ph, v: (ph, "", "data")
                _ck = [self.online_componente.assign(x.strip(), name_fn=_pf)
                       for x in _co.split(",") if x.strip()]
                validated["kw_componente"] = ", ".join(dict.fromkeys(_ck))

            real_confidence = calculate_confidence(validated, self.taxonomy, material_hint)
            validated["kw_confidence"] = real_confidence
            validated.pop("_corrections", None)

            # Write only HIGH results to cache
            if real_confidence == "HIGH":
                cache_entry = {k: v for k, v in validated.items() if k.startswith("kw_")}
                self.learned_mappings[cleaned_text] = cache_entry
                self.learned_mappings["_meta"]["total_mappings"] = (
                    self.learned_mappings["_meta"].get("total_mappings", 0) + 1
                )

            # NEW-TERM DISCOVERY (fast path): if the row could not be placed into
            # the taxonomy (sistema == ALTRO/empty), drop it into the orphan pool
            # for the periodic discovery job (discover.py) instead of losing it.
            try:
                maybe_capture(validated, cleaned_text, free_analysis_result)
            except Exception as _e:
                pass  # discovery capture must never break the main pipeline

            return validated

        except Exception as e:
            print(f"  Processing Error ({cleaned_text[:40]}...): {e}")
            error_result = {k: "ERROR" for k in config.KEYWORD_COLUMNS}
            error_result["kw_confidence"] = "LOW"
            return error_result
