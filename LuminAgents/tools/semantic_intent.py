# tools/semantic_intent.py
# ═══════════════════════════════════════════════════════════════
# Lightweight Semantic Intent Detector — no extra packages needed.
# Uses the same SentenceTransformer model already loaded in researcher.py.
# Replaces static GREETING with intent-aware first response.
#
# Intents for first message:
#   "greeting"       — مجرد تحية، ما في معلومات بعد
#   "goal_stated"    — ذكر هدفه صراحةً (تعلم X، أبي أتقن Y)
#   "full_profile"   — ذكر اسم + هدف + مستوى (جاهز للـ onboarding)
#   "question"       — سأل عن البوت أو كيف يعمل
#   "unknown"        — fallback
# ═══════════════════════════════════════════════════════════════
from __future__ import annotations

import numpy as np
from typing import Optional

# ── Model loaded lazily — shares cache with researcher.py ─────
_model = None

def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _model = None
    return _model


# ── Intent examples (AR + EN mixed for better coverage) ───────
INTENT_EXAMPLES: dict[str, list[str]] = {
    "greeting": [
        "مرحبا", "هلا", "السلام عليكم", "أهلاً", "كيف حالك",
        "hi", "hello", "hey", "good morning", "السلام",
        "هلا والله", "وش الأخبار",
    ],
    "goal_stated": [
        "ابي اتعلم Python", "أريد تعلم البرمجة", "هدفي تعلم اللغة الإنجليزية",
        "أبي أتقن Excel", "ودي أتعلم الرسم", "أريد تطوير مهارة الكتابة",
        "I want to learn Python", "I want to improve my English",
        "my goal is to learn data science", "I want to get fit",
        "أبي احترف التصوير", "ودي اتعلم التسويق",
    ],
    "full_profile": [
        "أنا أحمد، أريد تعلم Python، مستواي مبتدئ، ساعة يومياً",
        "اسمي محمد أبي اتعلم إنجليزي مستوى متوسط ساعتين في اليوم",
        "I'm Ahmed, I want to learn Python, I'm a beginner, 1 hour/day, 5 days/week",
        "my name is Sara, goal is fitness, intermediate, 45 min daily",
        "أنا سارة مبتدئة في اليوغا ساعة يومياً خمسة أيام",
    ],
    "question": [
        "كيف تشتغل؟", "وش تقدر تسوي؟", "ايش هو LuminAgents",
        "how does this work?", "what can you do?", "explain how you work",
        "ما الفرق بينك وبين ChatGPT", "هل أنت ذكاء اصطناعي",
        "what is this bot for?", "كيف أستخدمك",
    ],
}

# ── Pre-computed embeddings cache ─────────────────────────────
_intent_embeddings: Optional[dict[str, np.ndarray]] = None


def _build_intent_embeddings() -> dict[str, np.ndarray]:
    """Embed all examples once at startup. Returns {} if model unavailable or stubbed."""
    model = _get_model()
    if model is None:
        return {}
    try:
        result = {}
        for intent, examples in INTENT_EXAMPLES.items():
            vecs = model.encode(examples, convert_to_numpy=True, normalize_embeddings=True)
            result[intent] = vecs.mean(axis=0)           # centroid
            result[intent] /= np.linalg.norm(result[intent])  # re-normalize
        return result
    except Exception:
        # model is a stub (e.g. test env) or encode failed — fallback to keyword mode
        return {}


def _ensure_loaded() -> bool:
    global _intent_embeddings
    if _intent_embeddings is None:
        _intent_embeddings = _build_intent_embeddings()
    return bool(_intent_embeddings)


def detect_intent(message: str, threshold: float = 0.35) -> str:
    """
    Returns one of: greeting | goal_stated | full_profile | question | unknown
    Falls back to 'unknown' if model unavailable or similarity below threshold.
    """
    if not _ensure_loaded():
        return "unknown"

    model = _get_model()
    vec = model.encode([message], convert_to_numpy=True, normalize_embeddings=True)[0]

    best_intent = "unknown"
    best_score  = threshold

    for intent, centroid in _intent_embeddings.items():
        score = float(np.dot(vec, centroid))
        if score > best_score:
            best_score  = score
            best_intent = intent

    return best_intent


# ── Intent → smart greeting builder ──────────────────────────
def build_smart_greeting(message: str, lang: str) -> tuple[str, str]:
    """
    Returns (intent, reply_text).
    Called for new users instead of static GREETING.
    """
    intent = detect_intent(message)

    if intent == "full_profile":
        # User gave everything — tell orchestrator to skip greeting, go straight to FSM
        return intent, ""   # empty = signal to skip greeting, handle as onboarding

    if intent == "goal_stated":
        if lang == "ar":
            reply = (
                "أهلاً! يبدو أن لديك هدفاً واضحاً 🎯\n"
                "أخبرني باسمك ومستواك الحالي وكم ساعة يومياً تستطيع التدريب، وأبني لك خطة فوراً."
            )
        else:
            reply = (
                "Hey! Sounds like you have a clear goal 🎯\n"
                "Tell me your name, current level, and how many hours/day you can practice — I'll build your plan right away."
            )
        return intent, reply

    if intent == "question":
        if lang == "ar":
            reply = (
                "أنا LuminAgents — مدربك الشخصي للمهارات 🧠\n"
                "أبني لك خطة تعلم مخصصة وأتابعك يومياً حتى تصل لهدفك.\n"
                "أخبرني: ما المهارة التي تريد تطويرها؟"
            )
        else:
            reply = (
                "I'm LuminAgents — your personal skills coach 🧠\n"
                "I build you a custom learning plan and check in daily until you reach your goal.\n"
                "What skill do you want to develop?"
            )
        return intent, reply

    # greeting or unknown → standard but slightly warmer
    if lang == "ar":
        reply = (
            "أهلاً وسهلاً! أنا LuminAgents، مدربك الشخصي للمهارات.\n"
            "أخبرني باسمك والمهارة التي تريد تطويرها، ومستواك، وكم ساعة يومياً — وسأبني لك خطة مخصصة فوراً.\n"
            "مثال: أنا أحمد، أريد تعلم Python، مبتدئ، ساعة يومياً، 5 أيام."
        )
    else:
        reply = (
            "Welcome! I'm LuminAgents, your personal skills coach.\n"
            "Tell me your name, the skill you want to develop, your level, and daily hours — I'll build your custom plan instantly.\n"
            "Example: I'm Ahmed, I want to learn Python, beginner, 1 hour/day, 5 days/week."
        )
    return intent, reply
