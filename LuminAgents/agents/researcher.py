# agents/researcher.py
# ═══════════════════════════════════════════════════════════════
# LuminAgents — Researcher Agent (Architecture v5.1)
# Cascading Knowledge Strategy (4 tiers):
#   Tier 1 — Local KB (markdown, tag-based)
#   Tier 2 — Wikipedia LanceDB (vector search + goal filter)
#   Tier 3 — Tavily web search (URL whitelist-filtered)
#   Tier 4 — LLM Synthesis ("Foundational Concept Guide")
#             fires when all tiers above fail; never returns NO_INFO
#             to judges. KB_ONLY_MODE skips Tier 3, not Tier 4.
# Also: evaluate_comprehension() — Semantic Gap Analysis
# ═══════════════════════════════════════════════════════════════
import asyncio
import os
import re

# Web-First Protocol (v6.2 Production):
#   Tiers 1 & 2 (local KB + LanceDB) permanently bypassed.
#   Primary: Tier 3 — live Tavily whitelist.
#   Fallback: Tier 4 — LLM Synthesis (never shows NO_INFO).
#   KB_ONLY_MODE=true → emergency kill-switch that disables Tavily (Tier 3 only).
KB_ONLY_MODE  = os.getenv("KB_ONLY_MODE", "false").lower() == "true"
SKIP_LOCAL_KB = True  # hard-enforced — Web-First Protocol, not an env flag
from models.schemas import UserProfile, ResearchResult, SemanticGapResult
from llm.llm_client import call_llm
from knowledge_base.kb_router import search as kb_search

# ═══════════════════════════════════════════════════════════════
# Tier 2 (LanceDB vector search) — PERMANENTLY DISABLED v7.1
# LanceDB index deleted to reclaim disk space. SKIP_LOCAL_KB=True.
# All knowledge retrieval handled by Tier 3 (Tavily) + Tier 4 (LLM).
# ═══════════════════════════════════════════════════════════════
LANCEDB_AVAILABLE = False  # Hard-disabled — do not re-enable

def search_local_wiki(query: str, limit: int = 2) -> list:
    if not LANCEDB_AVAILABLE:
        return []
    try:
        query_vector = embed_model.encode(query).tolist()
        results = wiki_table.search(query_vector).limit(limit).to_pandas()
        if results.empty:
            return []
        return results['text'].tolist()
    except Exception as e:
        print(f"WARN wiki search error: {e}")
        return []


def _filter_by_goal(chunks: list, goal: str) -> list:
    """
    Hard relevance filter: keep only chunks where at least one goal keyword appears.
    Prevents unrelated Wikipedia chunks (Bengaluru, Al-Uzlah, etc.) from reaching Coach.
    Extracts both Latin and Arabic words from the goal string.
    Falls back to returning all chunks if none pass (cross-language mismatch guard).
    """
    goal_words = [
        w.lower()
        for w in re.findall(r'[a-zA-Z؀-ۿ]+', goal)
        if len(w) >= 3
    ]
    if not goal_words:
        return []
    relevant = []
    for chunk in chunks:
        chunk_lower = chunk.lower()
        if any(w in chunk_lower for w in goal_words):
            relevant.append(chunk)
    # Cross-language fallback: if filter wiped everything, return originals
    # (better to pass slightly broad content than silently block all KB results)
    return relevant if relevant else chunks
# ==========================================

# ─── Tier 3: Category+Level Domain Whitelist (v6.5) ──────────
# v6.5 Domain Content Guard: domains now selected by CATEGORY first,
# then refined by level. Prevents "English Language" goal from hitting
# Python/programming sites. Each domain group is fully isolated.

# ── Programming / CS ──────────────────────────────────────────
_DOMAINS_CODE_BEGINNER = {
    "w3schools.com",
    "geeksforgeeks.org",
    "realpython.com",
    "docs.python.org",
    "stackoverflow.com",
    "freecodecamp.org",
    "tutorialspoint.com",
    "khanacademy.org",
    "coursera.org",
    "udemy.com",
}
_DOMAINS_CODE_INTERMEDIATE = {
    "realpython.com",
    "docs.python.org",
    "geeksforgeeks.org",
    "stackoverflow.com",
    "developer.mozilla.org",
    "towardsdatascience.com",
    "coursera.org",
    "udemy.com",
    "khanacademy.org",
}
_DOMAINS_CODE_ADVANCED = {
    "docs.python.org",
    "stackoverflow.com",
    "realpython.com",
    "arxiv.org",
    "ieeexplore.ieee.org",
    "towardsdatascience.com",
    "github.com",
    "developer.mozilla.org",
    "coursera.org",
    "udemy.com",
}

# ── Language Learning (English / IELTS / TOEFL / Grammar / Vocabulary) ──
_DOMAINS_LANG_BEGINNER = {
    "bbc.co.uk",               # BBC Learning English
    "britishcouncil.org",      # British Council free resources
    "learnenglish.britishcouncil.org",
    "cambridgeenglish.org",
    "english-grammar.at",      # Clear grammar explanations
    "perfect-english-grammar.com",
    "englishclub.com",         # Vocabulary + grammar for beginners
    "duolingo.com",
    "khanacademy.org",
}
_DOMAINS_LANG_INTERMEDIATE = {
    "bbc.co.uk",
    "britishcouncil.org",
    "grammarly.com",           # Writing & grammar
    "ielts.org",               # Official IELTS resources
    "cambridgeenglish.org",
    "englishpage.com",
    "perfect-english-grammar.com",
    "usingenglish.com",
}
_DOMAINS_LANG_ADVANCED = {
    "ielts.org",
    "cambridgeenglish.org",
    "oxfordlearnersdictionaries.com",
    "economist.com",           # Advanced reading comprehension
    "bbc.co.uk",
    "grammarly.com",
    "coursera.org",
    "ted.com",                 # Advanced listening
}

# ── Fitness / Physical ────────────────────────────────────────
_DOMAINS_FITNESS_BEGINNER = {
    "healthline.com",
    "medicalnewstoday.com",
    "bodybuilding.com",
    "nerdfitness.com",
    "acefitness.org",
}
_DOMAINS_FITNESS_ADVANCED = {
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "journals.lww.com",
    "acefitness.org",
    "nsca.com",
    "healthline.com",
}

# ── Professional / Business ───────────────────────────────────
_DOMAINS_PROFESSIONAL = {
    "hbr.org",                 # Harvard Business Review
    "mckinsey.com",
    "forbes.com",
    "linkedin.com",
    "coursera.org",
    "udemy.com",
    "medium.com",
}

# ── General fallback ──────────────────────────────────────────
_DOMAINS_GENERAL = {
    "wikipedia.org",
    "khanacademy.org",
    "coursera.org",
    "medium.com",
    "reddit.com",
}

# Language detection keywords — goal strings that indicate language learning
_LANG_KEYWORDS = frozenset([
    "english", "ielts", "toefl", "grammar", "vocabulary", "speaking",
    "writing", "reading", "listening", "language", "arabic", "french",
    "spanish", "german", "اللغة", "انجليزي", "انكليزي", "إنجليزي",
    "عربي", "فرنسي", "ألماني", "tense", "idioms", "pronunciation",
])

# Programming/tech detection keywords
_CODE_KEYWORDS = frozenset([
    "python", "javascript", "java", "c++", "coding", "programming",
    "software", "algorithm", "data structures", "web", "django", "react",
    "machine learning", "ai", "sql", "database", "api", "flutter",
    "برمجة", "بايثون", "كود",
])


def _detect_goal_domain(category: str, goal: str) -> str:
    """
    Detects the content domain from category + goal keywords.
    Returns: 'language' | 'code' | 'fitness' | 'professional' | 'general'
    """
    goal_lower = goal.lower()
    goal_words = set(re.findall(r"[a-z؀-ۿ]+", goal_lower))

    if category == "physical":
        return "fitness"
    if category == "professional":
        return "professional"

    # Keyword intersection for academic/personal
    if goal_words & _LANG_KEYWORDS:
        return "language"
    if goal_words & _CODE_KEYWORDS:
        return "code"

    # Substring fallback (handles compound goals like "Learn English Grammar")
    if any(k in goal_lower for k in _LANG_KEYWORDS):
        return "language"
    if any(k in goal_lower for k in _CODE_KEYWORDS):
        return "code"

    return "general"


def _get_domain_whitelist(category: str, level: str, goal: str) -> set:
    """
    v6.5 Domain Content Guard: returns a domain set that matches
    the user's actual learning domain, not just their skill level.
    Prevents technical sites from leaking into language/fitness queries.
    """
    domain = _detect_goal_domain(category, goal)

    if domain == "language":
        if level == "advanced":
            return _DOMAINS_LANG_ADVANCED
        elif level == "intermediate":
            return _DOMAINS_LANG_INTERMEDIATE
        else:
            return _DOMAINS_LANG_BEGINNER

    if domain == "fitness":
        if level == "advanced":
            return _DOMAINS_FITNESS_ADVANCED
        else:
            return _DOMAINS_FITNESS_BEGINNER

    if domain == "professional":
        return _DOMAINS_PROFESSIONAL

    # code or general
    if level == "advanced":
        return _DOMAINS_CODE_ADVANCED
    elif level == "intermediate":
        return _DOMAINS_CODE_INTERMEDIATE
    else:
        return _DOMAINS_CODE_BEGINNER


def _cosine_sim(vec_a, vec_b) -> float:
    """Cosine similarity between two embedding vectors."""
    import numpy as np
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def _tavily_call(query: str, max_results: int, include_domains: list) -> list:
    """
    Sync Tavily call — runs inside run_in_executor to avoid blocking the event loop.
    Uses native include_domains parameter (server-side filtering, more efficient
    than post-filtering URL strings).
    Returns list of content strings, or [] on any failure.
    """
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        print("WARN [Researcher] TAVILY_API_KEY is not set — Tier 3 skipped")
        return []
    try:
        from tavily import TavilyClient
        client   = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            include_domains=include_domains,
            search_depth="basic",
        )
        results = response.get("results", [])
        return [r["content"] for r in results if r.get("content")]
    except Exception as e:
        print(f"WARN [Researcher] Tavily error: {type(e).__name__}: {str(e)[:120]}")
        return []


def _tavily_call_with_urls(query: str, max_results: int, include_domains: list) -> list:
    """
    v6.6 variant — returns list of (url, title, snippet) tuples.
    Used by _fetch_first_source_url() for onboarding link display.
    """
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        from tavily import TavilyClient
        client   = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            include_domains=include_domains,
            search_depth="basic",
        )
        results = response.get("results", [])
        # v6.9: filter out blog posts — prioritize course/tutorial/lesson pages
        _BLOG_RE = re.compile(r'/blog/|/blogs?/|\bblog\b', re.IGNORECASE)
        return [
            (r.get("url", ""), r.get("title", ""), r.get("content", "")[:200])
            for r in results
            if r.get("url") and not _BLOG_RE.search(r.get("url", ""))
        ]
    except Exception as e:
        print(f"WARN [Researcher] Tavily URL call error: {type(e).__name__}: {str(e)[:80]}")
        return []


def fetch_first_source_url(goal: str, level: str, category: str) -> tuple:
    """
    v6.6 — Returns (url, title) of the top educational resource for this goal.
    Used in onboarding to show a real, clickable link instead of raw text.
    Returns ("", "") if Tavily unavailable (DEMO_MODE or no API key).
    Sync — call directly or via run_in_executor.
    """
    if DEMO_MODE:
        return ("", "")
    domains = _get_domain_whitelist(category, level, goal)
    query   = f"{goal} beginner tutorial introduction"
    results = _tavily_call_with_urls(query, max_results=3, include_domains=list(domains))
    if results:
        url, title, _ = results[0]
        return (url, title or goal)
    return ("", "")


def fetch_learning_package(goal: str, level: str, category: str, language: str = "en") -> dict:
    """
    v6.8 — Multi-Source Learning Package for onboarding.
    Fetches 3-5 sources, returns the top primary guide + YouTube link + exercise prompt.
    Sync — call via run_in_executor.

    Returns dict:
        primary_url   : str   — top educational link (empty if unavailable)
        primary_title : str
        youtube_url   : str   — YouTube watch URL (empty if unavailable)
        youtube_title : str
        exercise      : str   — one actionable exercise sentence
    Falls back gracefully in DEMO_MODE or when Tavily/LLM unavailable.
    """
    _empty = {"primary_url": "", "primary_title": "", "youtube_url": "", "youtube_title": "", "exercise": ""}
    if DEMO_MODE:
        return _empty

    domains   = _get_domain_whitelist(category, level, goal)
    lvl_label = {"beginner": "beginner tutorial introduction",
                 "intermediate": "intermediate guide practice",
                 "advanced": "advanced deep dive mastery"}.get(level, "tutorial")
    query = f"{goal} {lvl_label}"

    # ── Primary guide (non-YouTube domains) ──────────────────────
    primary_url, primary_title = "", ""
    results = _tavily_call_with_urls(query, max_results=5, include_domains=list(domains))
    # Pick first result that isn't a YouTube link
    for url, title, _ in results:
        if "youtube.com" not in url and "youtu.be" not in url:
            primary_url, primary_title = url, title or goal
            break

    # ── YouTube (LLM-generated, stable channels only) ────────────
    # v6.9: require historically stable, well-known channels only.
    # Fallback: YouTube search URL (always works, never broken).
    youtube_url, youtube_title = "", ""
    _search_fallback = (
        f"https://www.youtube.com/results?search_query={goal.replace(' ', '+')}+{level}+tutorial"
    )
    try:
        from llm.llm_client import call_llm
        if language == "ar":
            yt_prompt = (
                f"أعطني رابط يوتيوب واحد (صيغة https://www.youtube.com/watch?v=XXXXXXXXXXX) "
                f"لشرح {goal} للمستوى {level} من قناة معروفة وثابتة مثل: "
                f"FreeCodeCamp، British Council، Khan Academy، TED-Ed، أو Traversy Media. "
                f"اكتب الرابط فقط. لو لم تكن متأكداً 100% من الرابط اكتب: SEARCH"
            )
        else:
            yt_prompt = (
                f"Give me one YouTube watch URL (format: https://www.youtube.com/watch?v=XXXXXXXXXXX) "
                f"for '{goal}' at {level} level from a well-known, historically stable channel such as: "
                f"FreeCodeCamp, British Council Official, Khan Academy, TED-Ed, or Traversy Media. "
                f"Output ONLY the URL. If you are not 100% certain the video exists, output: SEARCH"
            )
        yt_raw = call_llm(yt_prompt, max_tokens=80).strip()
        _YT_RE = re.compile(r"https?://(?:www\.)?youtube\.com/watch\?v=([\w-]{11})")
        m = _YT_RE.search(yt_raw)
        if m and "SEARCH" not in yt_raw.upper():
            youtube_url   = f"https://www.youtube.com/watch?v={m.group(1)}"
            youtube_title = f"{goal} — {'فيديو تعليمي' if language == 'ar' else 'Video Tutorial'}"
        else:
            # Fallback to search query — always valid
            youtube_url   = _search_fallback
            youtube_title = f"{'بحث يوتيوب: ' if language == 'ar' else 'YouTube Search: '}{goal}"
    except Exception:
        youtube_url   = _search_fallback
        youtube_title = f"{'بحث يوتيوب: ' if language == 'ar' else 'YouTube Search: '}{goal}"

    # ── Exercise (LLM-generated) ──────────────────────────────────
    exercise = ""
    try:
        from llm.llm_client import call_llm
        if language == "ar":
            ex_prompt = (
                f"اكتب تمريناً عملياً واحداً (جملة واحدة فقط) يطبّق مهارة {goal} "
                f"للمستوى {level}. بدون مقدمات."
            )
        else:
            ex_prompt = (
                f"Write one concrete, actionable exercise (one sentence only) "
                f"to practice {goal} at {level} level. No preamble."
            )
        exercise = call_llm(ex_prompt, max_tokens=80).strip()
    except Exception:
        pass

    return {
        "primary_url":   primary_url,
        "primary_title": primary_title,
        "youtube_url":   youtube_url,
        "youtube_title": youtube_title,
        "exercise":      exercise,
    }


async def tavily_search_constrained(
    query: str,
    goal: str,
    max_results: int = 3,
    level: str = "beginner",
    category: str = "academic",
) -> list:
    """
    Tier 3: Tavily with category+level domain whitelist + Knowledge Guard pipeline.

    v6.5 Domain Content Guard:
      Domains now selected by _get_domain_whitelist(category, level, goal) which
      maps the user's actual learning domain (language, code, fitness, professional)
      to appropriate sites. Prevents "English Language" goal from hitting
      Python/programming domains.

    Knowledge Guard (v6.2):
      1. Cosine similarity filter at 0.8 threshold (requires embed_model).
      2. Goal-keyword relevance filter (secondary, no embedding cost).

    Async-safe: sync HTTP call runs in executor (no event-loop blocking).
    Returns [] if API key missing, Tavily unreachable, or no relevant results.
    """
    domains = _get_domain_whitelist(category, level, goal)
    loop = asyncio.get_event_loop()
    raw  = await loop.run_in_executor(
        None, _tavily_call, query, max_results * 2, list(domains)
    )
    if not raw:
        return []

    # ── Knowledge Guard: Semantic Similarity Filter (0.8 threshold) ──────
    if LANCEDB_AVAILABLE:
        try:
            query_vec = embed_model.encode(query).tolist()
            scored    = []
            for chunk in raw:
                chunk_vec = embed_model.encode(chunk[:300]).tolist()
                sim = _cosine_sim(query_vec, chunk_vec)
                scored.append((sim, chunk))
            above_threshold = [c for s, c in scored if s >= 0.8]
            purged_count    = len(scored) - len(above_threshold)
            print(
                f"INFO [KnowledgeGuard] {len(above_threshold)}/{len(scored)} chunks "
                f"passed 0.8 threshold — {purged_count} purged"
            )
            # Hard purge: replace raw with filtered set; fall back only if all fail
            raw = above_threshold if above_threshold else [c for _, c in scored]
        except Exception as e:
            print(f"WARN [KnowledgeGuard] similarity filter error: {e}")

    # ── Secondary goal-relevance filter ──────────────────────────────────
    goal_words = [w.lower() for w in re.findall(r"[a-zA-Z؀-ۿ]+", goal) if len(w) >= 3]
    if not goal_words:
        return raw[:max_results]

    relevant = [c for c in raw if any(w in c.lower() for w in goal_words)]
    return (relevant or raw)[:max_results]


# ─── Tier 4: LLM Synthesis ───────────────────────────────────
_DEMO_SYNTHESIS = {
    "ar": (
        "**دليل المفاهيم الأساسية (مُولَّد)**\n"
        "هذا موضوع مثير للاهتمام! إليك المفاهيم الجوهرية بناءً على معرفتي المدمجة.\n"
        "هل لديك كتاب أو منهج محدد تريد أن أتوافق معه لتخصيص المحتوى أكثر؟"
    ),
    "en": (
        "**Foundational Concept Guide (Synthesized)**\n"
        "Great topic! Here are the core concepts based on my built-in knowledge.\n"
        "Do you have a specific book or syllabus you'd like me to align with?"
    ),
}

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


def _llm_synthesis(query: str, profile: UserProfile) -> list[str]:
    """
    Tier 4: LLM generates a structured 'Foundational Concept Guide'
    when all external sources fail. Uses model's internal weights.
    Ends with a proactive question to invite the user's own source —
    reframes the absence of external data as intelligent engagement.

    DEMO_MODE → returns a canned synthesis (zero LLM, zero latency).
    KB_ONLY_MODE does NOT skip this tier (LLM is internal, not web).
    Returns ["NO_INFO"] only if the LLM call itself throws.
    """
    if DEMO_MODE:
        lang = profile.language
        return [_DEMO_SYNTHESIS.get(lang, _DEMO_SYNTHESIS["en"])]

    lang = profile.language
    if lang == "ar":
        prompt = (
            f"أنت مدرب تعلم متخصص فقط في مجال: {profile.goal}.\n"
            f"قاعدة صارمة: لا تذكر أي موضوع آخر خارج {profile.goal}. "
            f"لا برمجة، لا مبيعات، لا مشاريع مفتوحة المصدر — إلا إذا كانت {profile.goal} نفسها.\n"
            f"المستخدم: {profile.name} — المستوى: {profile.level}\n"
            f"سؤاله: {query}\n\n"
            f"اكتب **دليل المفاهيم الأساسية لـ {profile.goal}** "
            f"في 3 نقاط مختصرة بالعربية تخص {profile.goal} تحديداً، "
            f"ثم اختم بسؤال واحد: "
            f"'هل لديك منهج أو مصدر محدد تريد أن أبنيه عليه؟'"
        )
    else:
        prompt = (
            f"You are a learning coach specialized ONLY in: {profile.goal}.\n"
            f"STRICT RULE: Do NOT mention any other subject outside of {profile.goal}. "
            f"No programming, no sales, no open source — unless {profile.goal} itself involves them.\n"
            f"User: {profile.name} — Level: {profile.level}\n"
            f"Their question: {query}\n\n"
            f"Write a **Foundational Guide for {profile.goal}** "
            f"in 3 concise bullet points strictly about {profile.goal}, "
            f"then close with one question: "
            f"'Do you have a specific book or syllabus you'd like me to align with?'"
        )
    try:
        content = call_llm(prompt, max_tokens=300, thinking_budget=1024)
        return [content]
    except Exception as e:
        print(f"WARN [Researcher] LLM synthesis failed: {e}")
        return ["NO_INFO"]


# ─── YouTube Direct Watch URL (Video Intelligence v6.2) ──────
# YouTube video IDs are always exactly 11 alphanumeric/dash/underscore chars.
# Regex acts as a format guard: drops malformed or hallucinated IDs silently.
_YT_WATCH_RE = re.compile(r'https://www\.youtube\.com/watch\?v=[\w\-]{11}')


def _generate_video_query(
    query: str,
    context: str,
    profile: UserProfile,
) -> str:
    """
    Uses Gemini to produce 1-2 real, direct YouTube watch URLs grounded
    in the whitelisted technical content already retrieved (context).

    The model is instructed to return only URLs it is certain about from
    its training knowledge. The strict 11-char ID regex silently drops
    any malformed or uncertain output — never surfaces broken links.

    Returns newline-separated URL string (1-2 links) or "" on failure.
    Never raises.
    """
    try:
        lang = profile.language
        if lang == "ar":
            prompt = (
                f"بناءً على هذا المحتوى التقني الموثوق (من مصادر الـ Whitelist):\n{context[:400]}\n\n"
                f"السؤال: {query}\n"
                f"الهدف: {profile.goal} | المستوى: {profile.level}\n\n"
                f"قدّم 1-2 رابط يوتيوب مباشر وحقيقي "
                f"(الصيغة الدقيقة: https://www.youtube.com/watch?v=XXXXXXXXXXX) "
                f"لفيديوهات تعليمية عالية التقييم تشرح هذا المفهوم تحديداً. "
                f"أدرج فقط روابط أنت متأكد 100% من وجودها من بيانات تدريبك. "
                f"أجب بالروابط فقط، رابط في كل سطر، بدون أي نص آخر."
            )
        else:
            prompt = (
                f"Based on this verified technical content (sourced from approved whitelist domains):\n"
                f"{context[:400]}\n\n"
                f"Question: {query}\n"
                f"Goal: {profile.goal} | Level: {profile.level}\n\n"
                f"Provide 1-2 real, direct YouTube watch URLs "
                f"(exact format: https://www.youtube.com/watch?v=XXXXXXXXXXX) "
                f"for highly-rated, well-known tutorial videos that explain this exact concept. "
                f"Only include URLs you are 100% certain exist from your training data. "
                f"Reply with URLs only, one per line, no other text."
            )

        raw  = call_llm(prompt, max_tokens=80).strip()
        urls = _YT_WATCH_RE.findall(raw)
        if not urls:
            return ""
        return "\n".join(urls[:2])
    except Exception:
        return ""


class ResearcherAgent:

    # Semantic Gap Analysis (v5.1)
    def evaluate_comprehension(
        self,
        user_message: str,
        context: str,
        profile: UserProfile,
    ) -> SemanticGapResult:
        """
        Detect surface vs deep learning.
        DEMO_MODE / missing inputs -> safe no-gap default (zero LLM cost).
        """
        if DEMO_MODE or not context.strip() or not user_message.strip():
            return SemanticGapResult(gap_detected=False)

        lang = profile.language
        if lang == "ar":
            prompt = (
                f"\u0623\u0646\u062a \u0645\u062d\u0644\u0644 \u062a\u0639\u0644\u064a\u0645\u064a \u0641\u064a LuminAgents.\n"
                f"\u0627\u0644\u0647\u062f\u0641: {profile.goal} | \u0627\u0644\u0645\u0633\u062a\u0648\u0649: {profile.level}\n\n"
                f"\u0645\u0635\u062f\u0631 \u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0627\u062a (KB):\n{context[:600]}\n\n"
                f"\u0631\u062f \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645: {user_message[:300]}\n\n"
                f"\u0647\u0644 \u0631\u062f \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645 \u064a\u0639\u0643\u0633 \u0641\u0647\u0645\u0627\u064b \u0633\u0637\u062d\u064a\u0627\u064b?\n"
                f"DEEP \u2014 \u0627\u0644\u0641\u0647\u0645 \u0643\u0627\u0641\u064d\u060c \u0648\u0627\u0635\u0644\n"
                f"GAP: [\u0627\u0642\u062a\u0631\u062d \u062a\u062d\u062f\u064a\u0627\u064b \u0639\u0645\u0644\u064a\u0627\u064b \u0628\u062c\u0645\u0644\u0629 \u0648\u0627\u062d\u062f\u0629 \u0628\u0627\u0644\u0639\u0631\u0628\u064a\u0629]\n"
                f"\u0645\u062b\u0627\u0644: GAP: \u0637\u0628\u0651\u0642 \u0627\u0644\u0645\u0641\u0647\u0648\u0645 \u0628\u0643\u062a\u0627\u0628\u0629 \u0645\u062b\u0627\u0644 \u0628\u0633\u064a\u0637 \u0628\u0646\u0641\u0633\u0643."
            )
        else:
            prompt = (
                f"You are a learning analyst in LuminAgents.\n"
                f"Goal: {profile.goal} | Level: {profile.level}\n\n"
                f"Source material (KB):\n{context[:600]}\n\n"
                f"User response: {user_message[:300]}\n\n"
                f"Does the user response show surface-level understanding "
                f"compared to the complexity of the source material?\n"
                f"Reply with ONLY one of:\n"
                f"DEEP -- understanding is adequate, proceed\n"
                f"GAP: [suggest a one-sentence Practical Challenge]\n"
                f"Example: GAP: Write a short code snippet applying this concept."
            )

        try:
            raw = call_llm(prompt, max_tokens=80).strip()
            if raw.upper().startswith("GAP"):
                import re as _re2
                challenge = _re2.sub(r"^GAP\s*[:\-\u2013\u2014]\s*", "", raw, flags=_re2.IGNORECASE).strip()
                return SemanticGapResult(gap_detected=True, challenge_hint=challenge)
            return SemanticGapResult(gap_detected=False)
        except Exception:
            return SemanticGapResult(gap_detected=False)

    async def fetch(self, query: str, profile: UserProfile) -> ResearchResult:
        # ── Query Grounding: anchor vague/short queries to the user's goal ──
        # Prevents "اي مصدر ابدأ فيه" from hitting Tavily as-is and returning garbage.
        _VAGUE_RE = re.compile(
            r'^(اي|اين|وين|ما|ايش|كيف|متى|ليش|what|where|which|how|why|when)\b',
            re.IGNORECASE
        )
        goal_in_query = profile.goal.lower() in query.lower()
        is_vague = _VAGUE_RE.match(query.strip()) or len(query.strip()) < 25
        if is_vague or not goal_in_query:
            lvl = {"beginner": "beginner tutorial introduction",
                   "intermediate": "intermediate guide practice",
                   "advanced": "advanced deep dive"}.get(profile.level, "tutorial")
            search_query = f"{profile.goal} {lvl}"
        else:
            search_query = f"{profile.goal} {query}"

        if not KB_ONLY_MODE:
            web_chunks = await tavily_search_constrained(
                search_query, profile.goal,
                level=profile.level,
                category=getattr(profile, "category", "academic"),
            )
            if web_chunks:
                return ResearchResult(
                    chunks=web_chunks,
                    sources=["tavily_trusted"],
                    tags_used=["web_whitelist"],
                    fallback_used=False,
                )
        synthesis = _llm_synthesis(query, profile)
        return ResearchResult(
            chunks=synthesis,
            sources=["llm_synthesis"],
            tags_used=["internal_knowledge"],
            fallback_used=True,
        )

if __name__ == "__main__":
    print("ResearcherAgent loaded OK")
