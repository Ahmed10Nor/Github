# tools/message_router.py
import re
from models.schemas import UserProfile

_AR_OOS_WORDS = {
    "سياسة", "رياضة", "كرة", "قدم", "لاعب", "فريق", "مباراة", "أخبار",
    "طبخ", "وصفة", "فيلم", "مسلسل", "صور", "ألعاب", "مندي", "كبسة",
    "أكل", "طعام", "ذهب", "فلوس", "بنك", "طقس", "كأس", "بطولة",
    "دوري", "منتخب", "هداف",
}

_AR_PLAN_WORDS = {
    "عدّل", "غيّر", "تعديل", "تغيير", "خفف", "زود", "أبطأ", "أسرع",
    "مشغول", "ضغط", "ما عندي وقت", "تغير جدولي", "سهّل", "تخفيف",
    "تعبت", "محبط", "صعب جداً",
}

_AR_GOAL_RESET_WORDS = {
    "اغير المهارة", "اغير هدفي", "اغير الهدف", "غير المهارة", "غير الهدف",
    "ابدا من جديد", "ابدأ من جديد", "ابدا من الصفر", "ابدأ من الصفر",
    "اعيد من البداية", "أعيد من البداية", "مهارة جديدة", "هدف جديد",
    "اغير المجال", "تغيير المهارة", "تغيير الهدف",
}
_EN_GOAL_RESET_RE = re.compile(
    r"\b(change my (goal|skill|topic|subject)|start over|start fresh|start from scratch"
    r"|new goal|new skill|different skill|reset my (plan|goal|skill)|switch (goal|skill))\b",
    re.IGNORECASE,
)

_AR_CONTENT_WORDS = {
    "كيف", "شرح", "اشرح", "وضح", "مثال", "ايش يعني", "ما هو",
    "ما معنى", "ليش", "متى", "أين", "مين", "ما الفرق",
}

_AR_LANG_PREF_WORDS = {
    "بالعربي", "بالعربية", "باللغة العربية", "شرح عربي",
    "اشرح بالعربي", "اشرح عربي", "جاوب بالعربي",
}
_EN_LANG_PREF_RE = re.compile(
    r"\b(explain|answer|respond|reply|tell me).{0,20}\b(in arabic|in english|بالعربي|بالإنجليزي)\b"
    r"|\b(in arabic|in english)\b",
    re.IGNORECASE,
)

_EN_OOS_RE = re.compile(
    r"\b(politics|sports?|news|recipe|movie|weather|games?|food|cooking|money|bank"
    r"|football|soccer|basketball|player|team|match|won|score|world.?cup|champion|league|tournament)\b",
    re.IGNORECASE,
)
_EN_PLAN_RE = re.compile(
    r"\b(change|modify|update|adjust|slower|faster|easier|harder|busy|less time)\b",
    re.IGNORECASE,
)
_EN_CONTENT_RE = re.compile(
    r"\?|\b(what|how|explain|example|difference|compare|vs|why|when|where|who|which)\b",
    re.IGNORECASE,
)
_AR_QUESTION_RE = re.compile(r"؟")

_AR_PLAN_STATUS_WORDS = {
    "خطتي", "خطط", "أسابيع", "أسبوع", "مراحل", "تقدمي",
    "وين وصلت", "كم أسبوع", "كم باقي",
    "خطة الاسبوع", "خطة الأسبوع", "الخطة الكاملة", "خطة كاملة",
    "اعرض الخطة", "اطرح الخطة", "طرح الخطة", "وضح الخطة",
    "ايش خطتي", "ما هي خطتي", "ما خطتي", "شوف الخطة",
}
_EN_PLAN_STATUS_RE = re.compile(
    r"\b(my plans?|the plan|my schedule|my progress|how many weeks|how long"
    r"|milestone|milestones|weeks left|what.?s next|next step|whats next"
    r"|show (me )?(the |my )?full plan|full week plan|show (the )?plan"
    r"|week(ly)? plan|my (full |complete )?plan)\b",
    re.IGNORECASE,
)

_AR_META_WORDS = {
    "مصادر", "مصدر", "معلوماتك", "من أين تعرف", "كيف تعرف",
    "وين المصادر", "ايش مصادرك", "ما مصادرك", "ما هي المصادر",
    "روابط", "رابط", "وين الروابط", "جدولي", "جدول اليوم",
}
_EN_META_RE = re.compile(
    r"\b(sources?|your (knowledge|info|data|material|content|links?)"
    r"|where do you get|what do you use|show me (the )?sources?"
    r"|my (plan|schedule|timetable)|what.?s (my|the) plan"
    r"|links?|resources?|reading list)\b",
    re.IGNORECASE,
)


def _ar_matches(text: str, word_set: set) -> bool:
    for w in word_set:
        if w in text:
            return True
        if w.endswith("ة") and w[:-1] in text:
            return True
    return False


def route_message(message: str, profile) -> str:
    """
    Returns: out_of_scope | goal_reset | content_question | plan_change | daily_check
    Priority: lang_pref > out_of_scope > goal_reset > plan_change > meta > plan_status > content_question > daily_check
    """
    if _ar_matches(message, _AR_LANG_PREF_WORDS) or _EN_LANG_PREF_RE.search(message):
        return "content_question"
    if _ar_matches(message, _AR_OOS_WORDS) or _EN_OOS_RE.search(message):
        return "out_of_scope"
    if _ar_matches(message, _AR_GOAL_RESET_WORDS) or _EN_GOAL_RESET_RE.search(message):
        return "goal_reset"
    if _ar_matches(message, _AR_PLAN_WORDS) or _EN_PLAN_RE.search(message):
        return "plan_change"
    if _ar_matches(message, _AR_META_WORDS) or _EN_META_RE.search(message):
        return "content_question"
    if _ar_matches(message, _AR_PLAN_STATUS_WORDS) or _EN_PLAN_STATUS_RE.search(message):
        return "daily_check"
    if (
        _ar_matches(message, _AR_CONTENT_WORDS)
        or "?" in message
        or _EN_CONTENT_RE.search(message)
    ):
        return "content_question"
    return "daily_check"


def detect_language(text: str) -> str:
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    return "ar" if arabic_chars > len(text) * 0.3 else "en"


def get_out_of_scope_reply(profile) -> str:
    from llm.llm_client import call_llm
    lang = getattr(profile, "language", "en")
    if lang == "ar":
        prompt = (
            "اكتب رسالة رفض قصيرة جملتان بالعربية بهذا المعنى بالضبط:\n"
            "هذا السؤال خارج نطاقي تماماً، أنا متخصص فقط في مساعدتك على "
            + str(profile.goal)
            + ". جرّب Google أو ChatGPT لهذا الموضوع!\n"
            "اكتبها بأسلوبك الخاص لكن لا تضف أي معلومة أخرى."
        )
    else:
        prompt = (
            "Write a short two-sentence refusal message with exactly this meaning:\n"
            "That topic is completely outside my scope — I only help with "
            + str(profile.goal)
            + ". Try Google or ChatGPT for that one!\n"
            "Rephrase naturally but add no other information whatsoever."
        )
    return call_llm(prompt)
