# agents/bootstrap.py
# ═══════════════════════════════════════════════════════════════
# LuminAgents — Bootstrap Agent (offline, one-time per skill)
# Reads KB markdown files → LLM extracts curriculum → saves JSON.
# Usage: python agents/bootstrap.py --skill python_basics --category academic
# ═══════════════════════════════════════════════════════════════
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from llm.llm_client import call_llm
from models.schemas import CurriculumMap

# crewai monkey-patches sys.stdout to cp1252 on Windows — fix it after imports
import io as _io
if hasattr(sys.stdout, "buffer"):
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

KB_ROOT = ROOT / "knowledge_base"

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# ──────────────────────────────────────────────────────────────
# TEMPLATE SELECTION
# ──────────────────────────────────────────────────────────────
CATEGORY_TEMPLATE = {
    "academic":     "linear_mastery",
    "professional": "80_20_project_based",
    "personal":     "habit_stacking",
    "physical":     "progressive_overload",
}

# ──────────────────────────────────────────────────────────────
# FILE DISCOVERY
# ──────────────────────────────────────────────────────────────
def find_skill_files(category: str, skill: str) -> list[Path]:
    category_dir = KB_ROOT / category
    if not category_dir.exists():
        raise FileNotFoundError(f"Category directory not found: {category_dir}")

    # Prefer files that match the skill name
    matches = sorted(category_dir.rglob(f"*{skill}*.md"))
    if not matches:
        # Fallback: all MD files in the category subtree
        matches = sorted(category_dir.rglob("*.md"))
    return matches


def read_files(paths: list[Path]) -> str:
    parts = []
    for p in paths:
        parts.append(f"=== FILE: {p.name} ===\n{p.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


# ──────────────────────────────────────────────────────────────
# LLM PROMPT
# ──────────────────────────────────────────────────────────────
EXTRACTION_PROMPT = """\
You are a curriculum designer. Analyze the following knowledge base content \
for the skill "{skill}" (category: {category}).

Extract a structured curriculum map with:
1. lessons — each lesson has:
   - id: snake_case identifier (e.g. "variables_and_types")
   - title: human-readable name (Arabic or English matching the content)
   - weight: fraction of total time — ALL weights MUST sum to EXACTLY 1.0
   - depends_on: list of lesson IDs required first (empty list if none)
   - hours_std: standard hours needed at intermediate level
2. template: "{template}"
3. total_hours_std: sum of all lesson hours_std values

Rules:
- Derive lessons from the actual content, not from imagination.
- Weights must be positive and sum to 1.0 (round to 4 decimal places).
- hours_std per lesson: typically 2–20 h for academic skills.

Return ONLY valid JSON — no markdown fences, no explanation:
{{
  "skill": "{skill}",
  "category": "{category}",
  "template": "{template}",
  "total_hours_std": <float>,
  "lessons": [
    {{
      "id": "<str>",
      "title": "<str>",
      "weight": <float>,
      "depends_on": [],
      "hours_std": <float>
    }}
  ]
}}

Knowledge Base Content:
{content}"""


# ──────────────────────────────────────────────────────────────
# DEMO CURRICULUM (used when DEMO_MODE=true)
# ──────────────────────────────────────────────────────────────
def _demo_curriculum(skill: str, category: str) -> dict:
    template = CATEGORY_TEMPLATE.get(category, "linear_mastery")
    return {
        "skill": skill,
        "category": category,
        "template": template,
        "total_hours_std": 20.0,
        "lessons": [
            {"id": "intro",       "title": "Introduction",     "weight": 0.2, "depends_on": [],        "hours_std": 4.0},
            {"id": "core",        "title": "Core Concepts",    "weight": 0.4, "depends_on": ["intro"], "hours_std": 8.0},
            {"id": "practice",    "title": "Practice",         "weight": 0.3, "depends_on": ["core"],  "hours_std": 6.0},
            {"id": "capstone",    "title": "Capstone Project", "weight": 0.1, "depends_on": ["practice"], "hours_std": 2.0},
        ],
    }


# ──────────────────────────────────────────────────────────────
# JSON EXTRACTION (strips markdown fences if present)
# ──────────────────────────────────────────────────────────────
def extract_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        # drop first line (```json) and last line (```)
        inner = lines[1:] if lines[-1].strip() != "```" else lines[1:-1]
        raw = "\n".join(inner)
    return json.loads(raw)


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap: build curriculum_map.json for a skill"
    )
    parser.add_argument("--skill",    required=True,
                        help="Skill identifier, e.g. python_basics")
    parser.add_argument("--category", required=True,
                        choices=["academic", "physical", "professional", "personal"])
    args = parser.parse_args()

    skill    = args.skill
    category = args.category
    template = CATEGORY_TEMPLATE[category]

    print(f"[bootstrap] skill={skill}  category={category}  template={template}")

    # ── 1. DEMO MODE shortcut ──────────────────────────────────
    if DEMO_MODE:
        print("[bootstrap] DEMO_MODE=true — using synthetic curriculum")
        data = _demo_curriculum(skill, category)
    else:
        # ── 2. Read KB files ───────────────────────────────────
        try:
            files = find_skill_files(category, skill)
        except FileNotFoundError as e:
            print(f"[bootstrap] ERROR: {e}")
            sys.exit(1)

        if not files:
            print(f"[bootstrap] ERROR: No markdown files found for skill '{skill}' "
                  f"in category '{category}'")
            sys.exit(1)

        print(f"[bootstrap] Found {len(files)} file(s): {[f.name for f in files]}")
        content = read_files(files)

        # ── 3. Call LLM ────────────────────────────────────────
        prompt = EXTRACTION_PROMPT.format(
            skill=skill, category=category, template=template, content=content
        )
        print("[bootstrap] Calling LLM...")
        raw = call_llm(prompt, max_tokens=2000)

        # ── 4. Parse JSON ──────────────────────────────────────
        try:
            data = extract_json(raw)
        except json.JSONDecodeError as e:
            print(f"[bootstrap] ERROR: LLM returned invalid JSON — {e}")
            print("Raw (first 600 chars):", raw[:600])
            sys.exit(1)

    # ── 5. Pydantic validation (checks weight sum automatically) ──
    try:
        curriculum = CurriculumMap(**data)
    except Exception as e:
        print(f"[bootstrap] ERROR: Validation failed — {e}")
        sys.exit(1)

    weight_sum = round(sum(l.weight for l in curriculum.lessons), 4)
    print(f"[bootstrap] Lessons={len(curriculum.lessons)}  "
          f"total_hours_std={curriculum.total_hours_std}  weight_sum={weight_sum}")

    # ── 6. Save curriculum_map.json ───────────────────────────
    output_dir  = KB_ROOT / category / skill
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "curriculum_map.json"
    output_path.write_text(curriculum.model_dump_json(indent=2), encoding="utf-8")

    print(f"[bootstrap] Saved -> {output_path}")
    print("[bootstrap] Done.")


if __name__ == "__main__":
    main()
