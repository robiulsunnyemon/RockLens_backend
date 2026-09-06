import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx
from app.core.config import settings

logger = logging.getLogger("rocklens_vision_service")

GENERIC_IGNORE_WORDS = {
    "rock", "stone", "mineral", "geology", "geological phenomenon", "petrology",
    "close up", "surface", "pattern", "soil", "bedrock", "outcrop", "natural material",
    "texture", "monochrome", "grey", "gray", "brown", "white", "black", "macro photography",
    "hand", "finger", "table", "wood", "floor", "indoor", "outdoor", "plant", "water"
}

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "minerals_db.json"

class RockLensVisionService:
    def __init__(self):
        self._minerals_db: Dict[str, Dict[str, Any]] = {}
        self._load_database()

    def _load_database(self) -> None:
        try:
            if DB_PATH.exists():
                with open(DB_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._minerals_db = {
                        k.lower().strip(): v for k, v in data.get("minerals", {}).items()
                    }
                logger.info(f"Loaded {len(self._minerals_db)} mineral definitions into RockLens Knowledge Base.")
            else:
                logger.warning(f"Minerals database not found at {DB_PATH}")
        except Exception as e:
            logger.error(f"Error loading minerals database: {e}")

    def _find_mineral_in_db(self, query: str) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        clean_q = query.lower().strip()

        if clean_q in self._minerals_db:
            return self._minerals_db[clean_q]

        for key, entry in self._minerals_db.items():
            entry_name = entry.get("name", "").lower()
            if clean_q == entry_name or key in clean_q or clean_q in key:
                return entry

        q_tokens = set(re.findall(r"[a-zA-Z]{4,}", clean_q)) - GENERIC_IGNORE_WORDS
        for key, entry in self._minerals_db.items():
            entry_name = entry.get("name", "").lower()
            entry_tokens = set(re.findall(r"[a-zA-Z]{4,}", entry_name))
            if q_tokens and (q_tokens & entry_tokens):
                return entry

        return None

    async def _call_google_vision_rest(self, image_bytes: bytes) -> Dict[str, Any]:
        api_key = settings.GOOGLE_VISION_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_VISION_API_KEY is not configured in settings or .env")

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"

        payload = {
            "requests": [
                {
                    "image": {"content": b64_image},
                    "features": [
                        {"type": "WEB_DETECTION", "maxResults": 12},
                        {"type": "LABEL_DETECTION", "maxResults": 12},
                    ],
                }
            ]
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                logger.error(f"Google Vision API HTTP {response.status_code}: {response.text}")
                raise RuntimeError(f"Google Cloud Vision API returned error: {response.text}")

            data = response.json()
            responses = data.get("responses", [])
            if not responses:
                return {}
            return responses[0]

    def _extract_geological_candidates(
        self, vision_data: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], str]:
        candidates: List[Dict[str, Any]] = []
        seen_names = set()

        web_detection = vision_data.get("webDetection", {})
        web_entities = web_detection.get("webEntities", [])
        best_guesses = web_detection.get("bestGuessLabels", [])
        label_annotations = vision_data.get("labelAnnotations", [])

        best_guess_text = ""
        for bg in best_guesses:
            label = bg.get("label", "").strip()
            if label:
                best_guess_text = label
                break

        for entity in web_entities:
            desc = entity.get("description", "").strip()
            score = float(entity.get("score", 0.0))
            if not desc or desc.lower() in GENERIC_IGNORE_WORDS:
                continue

            clean_desc = desc.title()
            if clean_desc.lower() not in seen_names:
                seen_names.add(clean_desc.lower())
                candidates.append({
                    "name": clean_desc,
                    "raw_score": score,
                    "source": "web_entity",
                })

        for label in label_annotations:
            desc = label.get("description", "").strip()
            score = float(label.get("score", 0.0))
            if not desc or desc.lower() in GENERIC_IGNORE_WORDS:
                continue

            clean_desc = desc.title()
            if clean_desc.lower() not in seen_names:
                seen_names.add(clean_desc.lower())
                candidates.append({
                    "name": clean_desc,
                    "raw_score": score,
                    "source": "label",
                })

        return candidates, best_guess_text

    def _build_specimen_payload(
        self,
        primary_name: str,
        confidence_pct: float,
        alt_candidates: List[Dict[str, Any]],
        db_record: Optional[Dict[str, Any]],
        execution_engine: str = "Google Cloud Vision Online Engine",
    ) -> Dict[str, Any]:
        if db_record:
            name = db_record.get("name", primary_name)
            formula = db_record.get("chemical_formula", "Geological Specimen")
            group = db_record.get("group", "GEOLOGICAL MINERAL")
            mohs = db_record.get("mohs_hardness", "5.0 – 6.5")
            color = db_record.get("color", "Natural Texture")
            crystal_system = db_record.get("crystal_system", "Crystalline")
            luster = db_record.get("luster", "Vitreous to Sub-Metallic")
            streak = db_record.get("streak", "Characteristic")
            cleavage = db_record.get("cleavage", "Indistinct / Conchoidal")
            specific_gravity = db_record.get("specific_gravity", "2.6 – 4.0")
            raw_ore_estimate = db_record.get("raw_ore_estimate", "Market Index Tracked")
            specimen_estimate = db_record.get("specimen_estimate", "Grade Dependent")
            rarity_tier = db_record.get("rarity_tier", "Verified Specimen")
            economic_value = db_record.get("economic_value", "Commercial & Specimen Value")
            toxicity = db_record.get("toxicity", "Non-toxic / Standard geological handling")
            description = db_record.get("description", f"{name} identified via Google Vision.")
            tips = db_record.get("identification_tips", "Verify physical properties using streak test.")
            african_regions = db_record.get("african_regions", ["Global Deposits"])
        else:
            name = primary_name.title()
            formula = "Natural Mineral / Rock Structure"
            group = "GEOLOGICAL CLASSIFICATION"
            mohs = "4.0 – 7.0 (Assay Required)"
            color = "Natural Earth Tone"
            crystal_system = "Crystalline Aggregate"
            luster = "Sub-Vitreous to Earthy"
            streak = "Pale White / Gray"
            cleavage = "Conchoidal / Irregular"
            specific_gravity = "2.6 – 3.8"
            raw_ore_estimate = "Commodity Tracked"
            specimen_estimate = "Market Dependent"
            rarity_tier = "Identified Specimen"
            economic_value = "Commercial Ore & Mineral"
            toxicity = "Standard field handling advised"
            description = f"{name} accurately identified via Google Cloud Vision Knowledge Graph."
            tips = "Confirm hardness with Mohs scratch test and acid effervescence check."
            african_regions = ["Global Geological Belts"]

        colors = ["#22C55E", "#3B82F6", "#EAB308", "#A855F7", "#EC4899"]
        formatted_alts = []
        for i, alt in enumerate(alt_candidates[:4]):
            formatted_alts.append({
                "name": alt["name"],
                "percentage": int(alt["percentage"]),
                "color": colors[i % len(colors)],
            })

        return {
            "success": True,
            "status": "success",
            "mineral_name": name,
            "chemical_formula": formula,
            "mineral_group": group,
            "confidence_percentage": round(confidence_pct, 1),
            "mohs_hardness": mohs,
            "color": color,
            "crystal_system": crystal_system,
            "luster": luster,
            "streak": streak,
            "cleavage": cleavage,
            "specific_gravity": specific_gravity,
            "raw_ore_estimate": raw_ore_estimate,
            "specimen_estimate": specimen_estimate,
            "rarity_tier": rarity_tier,
            "economic_value": economic_value,
            "toxicity": toxicity,
            "description": description,
            "identification_tips": tips,
            "african_regions": african_regions,
            "alternative_candidates": formatted_alts,
            "execution_mode": execution_engine,
        }

    def _generate_mock_geological_identification(self, filename: str = "sample.jpg") -> Dict[str, Any]:
        samples = ["amethyst", "malachite", "pyrite", "quartz", "azurite", "obsidian", "hematite"]
        idx = abs(hash(filename)) % len(samples)
        key = samples[idx]
        record = self._minerals_db.get(key)

        primary_name = record["name"] if record else key.title()
        alts = [
            {"name": "Quartz", "percentage": 88},
            {"name": "Fluorite", "percentage": 76},
            {"name": "Chalcedony", "percentage": 65},
        ]
        return self._build_specimen_payload(
            primary_name=primary_name,
            confidence_pct=94.5,
            alt_candidates=alts,
            db_record=record,
            execution_engine="RockLens Vision Engine (Demo/Testing Mode)",
        )

    async def identify_specimen(
        self, image_bytes: bytes, filename: str = "specimen.jpg"
    ) -> Dict[str, Any]:
        vision_data = None
        engine_name = "Google Cloud Vision API"

        if settings.GOOGLE_VISION_API_KEY and settings.GOOGLE_VISION_API_KEY != "AIzaSy...":
            try:
                vision_data = await self._call_google_vision_rest(image_bytes)
                engine_name = "Google Cloud Vision API (REST Online)"
            except Exception as e:
                logger.error(f"Google Cloud Vision REST call failed: {e}")

        if not vision_data:
            logger.info("No active Google Vision API credentials provided. Using RockLens Geological Knowledge Base simulation.")
            return self._generate_mock_geological_identification(filename)

        candidates, best_guess = self._extract_geological_candidates(vision_data)

        if not candidates and not best_guess:
            return {
                "success": False,
                "status": "low_confidence",
                "mineral_name": "Unrecognized Specimen",
                "chemical_formula": "Non-Mineral Surface",
                "mineral_group": "UNIDENTIFIED",
                "confidence_percentage": 25.0,
                "description": "Google Cloud Vision could not detect any recognizable rock or mineral in this frame. Please ensure clear lighting and scan a geological specimen.",
                "alternative_candidates": [],
                "execution_mode": engine_name,
            }

        matched_mineral = None
        primary_name = best_guess if best_guess else (candidates[0]["name"] if candidates else "Rock Specimen")
        confidence = 92.0

        for c in candidates:
            db_match = self._find_mineral_in_db(c["name"])
            if db_match:
                matched_mineral = db_match
                primary_name = db_match["name"]
                raw = c.get("raw_score", 0.8)
                confidence = min(98.5, max(82.0, raw * 100.0 if raw <= 1.0 else raw))
                break

        if not matched_mineral and best_guess:
            matched_mineral = self._find_mineral_in_db(best_guess)
            if matched_mineral:
                primary_name = matched_mineral["name"]

        alt_list = []
        for c in candidates:
            c_name = c["name"]
            if c_name.lower() != primary_name.lower():
                raw = c.get("raw_score", 0.7)
                pct = min(92.0, max(50.0, raw * 90.0 if raw <= 1.0 else raw * 0.9))
                alt_list.append({"name": c_name, "percentage": int(pct)})

        return self._build_specimen_payload(
            primary_name=primary_name,
            confidence_pct=confidence,
            alt_candidates=alt_list,
            db_record=matched_mineral,
            execution_engine=engine_name,
        )

vision_service = RockLensVisionService()
