"""Skill mapping endpoint: /skills/map."""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from app.config import DEFAULT_OASF_SCHEMA_DIR

logger = logging.getLogger(__name__)

skills_bp = Blueprint("skills", __name__)

_skill_mapper = None
_skill_mapper_init_error = None


class SkillMapper:
    """Lightweight skill taxonomy mapper extracted from OASF schema files."""

    def __init__(self, schema_dir: Path):
        self.schema_dir = schema_dir
        self.categories: Dict[str, Dict[str, Any]] = {}
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.leaf_skills: Dict[str, Dict[str, Any]] = {}
        self.children: Dict[str, List[str]] = {}
        self._load()
        self._compute_leaves()

    def _load(self):
        cat_file = self.schema_dir / "skill_categories.json"
        if cat_file.exists():
            try:
                data = json.loads(cat_file.read_text(encoding="utf-8"))
                for k, v in data.get("attributes", {}).items():
                    self.categories[k] = v
            except Exception as e:
                logger.warning("categories load: %s", e)
        skills_root = self.schema_dir / "skills"
        if not skills_root.exists():
            return
        for category_dir in skills_root.iterdir():
            if not category_dir.is_dir():
                continue
            for json_file in category_dir.rglob("*.json"):
                try:
                    obj = json.loads(json_file.read_text(encoding="utf-8"))
                    name = obj.get("name")
                    if not name:
                        continue
                    self.skills[name] = obj
                    parent = obj.get("extends")
                    if isinstance(parent, str):
                        self.children.setdefault(parent, []).append(name)
                except Exception as e:
                    logger.warning("skill load %s: %s", json_file, e)

    def _compute_leaves(self):
        parent_set = set(self.children.keys())
        for name, obj in self.skills.items():
            if name not in parent_set or not self.children.get(name):
                self.leaf_skills[name] = obj

    def map_capability(self, capability: str):
        cap_norm = capability.lower().strip().replace(" ", "_").replace("-", "_")
        if cap_norm in self.leaf_skills:
            return self._payload(self.leaf_skills[cap_norm])
        for leaf in self.leaf_skills.values():
            caption = (leaf.get("caption") or "").lower()
            if cap_norm in caption:
                return self._payload(leaf)
        rules = [
            ("chat", "natural_language_generation"),
            ("conversation", "natural_language_generation"),
            ("classif", "text_classification"),
            ("retriev", "information_retrieval_synthesis"),
            ("search", "information_retrieval_synthesis"),
            ("vision", "image_classification"),
            ("image", "image_classification"),
            ("tool", "tool_use_planning"),
        ]
        for needle, target in rules:
            if needle in cap_norm and target in self.skills:
                cand = self.skills[target]
                if target not in self.leaf_skills and self.children.get(target):
                    child = self.children[target][0]
                    cand = self.skills.get(child, cand)
                return self._payload(cand)
        return None

    def _payload(self, leaf: Dict[str, Any]):
        chain: list = []
        cur = leaf
        seen: set = set()
        while cur and isinstance(cur.get("extends"), str) and cur.get("extends") != "base_skill":
            parent_name = cur.get("extends")
            if parent_name in seen:
                break
            seen.add(parent_name)
            parent_obj = self.skills.get(parent_name)
            if not parent_obj:
                break
            chain.append(parent_obj)
            cur = parent_obj
        top_parent = chain[-1] if chain else leaf if leaf.get("extends") == "base_skill" else None
        category_key = (top_parent or leaf).get("extends") if (top_parent or leaf) else None
        if category_key == "base_skill":
            category_key = leaf.get("name")
        cat_meta = self.categories.get(category_key, {}) if category_key else {}
        return {
            "skill_id": leaf.get("name"),
            "category_name": cat_meta.get("caption", category_key),
            "category_uid": cat_meta.get("uid", 0),
            "class_name": leaf.get("caption"),
            "class_uid": leaf.get("uid", 0),
        }


def _init_skill_mapper():
    global _skill_mapper, _skill_mapper_init_error
    if _skill_mapper is not None or _skill_mapper_init_error is not None:
        return
    schema_dir = Path(DEFAULT_OASF_SCHEMA_DIR).resolve()
    if not schema_dir.exists():
        _skill_mapper_init_error = f"Schema directory not found: {schema_dir}"
        return
    try:
        _skill_mapper = SkillMapper(schema_dir)
    except Exception as e:
        _skill_mapper_init_error = f"Initialization error: {e}"


@skills_bp.route("/skills/map")
def map_capability():
    """Map a capability string to a skill taxonomy entry.
    ---
    tags:
      - Skills
    parameters:
      - name: capability
        in: query
        type: string
        required: true
        description: Free-form capability string (e.g. "chat", "image classification")
    responses:
      200:
        description: Mapped skill taxonomy entry
        schema:
          type: object
          properties:
            capability:
              type: string
            mapped:
              type: object
              properties:
                skill_id:
                  type: string
                category_name:
                  type: string
                category_uid:
                  type: integer
                class_name:
                  type: string
                class_uid:
                  type: integer
      400:
        description: Missing capability query param
      404:
        description: No matching skill found
      500:
        description: Skill mapper initialization error
    """
    cap = request.args.get("capability", "").strip()
    if not cap:
        return jsonify({"error": "Missing capability query param"}), 400
    _init_skill_mapper()
    if _skill_mapper_init_error:
        return jsonify({"error": "mapper_init_failed", "detail": _skill_mapper_init_error}), 500
    if not _skill_mapper:
        return jsonify({"error": "mapper_unavailable"}), 500
    mapped = _skill_mapper.map_capability(cap)
    if not mapped:
        return jsonify({"capability": cap, "mapped": None}), 404
    return jsonify({"capability": cap, "mapped": mapped})

