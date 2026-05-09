# llm/llm_client.py
import os
import hashlib
import time
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY")
GEMINI_KEY     = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-flash-latest"
PRIMARY_MODEL  = "google/gemini-flash-latest"
FALLBACK_MODEL = "claude-sonnet-4-20250514"
DEMO_MODE      = os.getenv("DEMO_MODE", "false").lower() == "true"

_genai_client = None


def _get_genai_client():
    global _genai_client
    if _genai_client is None:
        from google import genai
        _genai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None
    return _genai_client


def get_crewai_llm():
    from crewai import LLM
    return LLM(model="gemini/gemini-1.5-flash", api_key=GEMINI_KEY)


# ── Security audit helper ─────────────────────────────────────────────────
def _audit(prompt: str, response: str, model: str, duration_ms: int,
           status: str = "ok", route: str = "") -> None:
    """Fire-and-forget — SHA-256 hash of first 200 chars; never raises."""
    try:
        from db.database import log_audit
        input_hash = hashlib.sha256(prompt[:200].encode("utf-8")).hexdigest()[:16]
        tokens_in  = max(1, len(prompt) // 4)
        tokens_out = max(1, len(response) // 4)
        log_audit(
            input_hash=input_hash,
            route=route,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            status=status,
        )
    except Exception:
        pass


def _demo_response(prompt: str) -> str:
    prompt_lower = prompt.lower()
    if "yes or no" in prompt_lower:
        return "YES"
    if "out of scope" in prompt_lower or "outside" in prompt_lower:
        return "That topic is outside my scope. I only help with your learning goal — try Google for that!"
    if "fixer" in prompt_lower or "failed" in prompt_lower or "streak" in prompt_lower:
        return "You've hit a wall — that's completely normal! Let's simplify your plan and take it one small step at a time. You've got this!"
    if "rebuild" in prompt_lower or "easier" in prompt_lower:
        return "I've rebuilt your plan with shorter daily sessions. Small consistent steps will get you there faster than big irregular ones."
    if "revise" in prompt_lower or "busy" in prompt_lower or "adjust" in prompt_lower:
        return "Plan adjusted! I've reduced your daily commitment to fit your schedule while keeping your goal on track."
    if "milestone" in prompt_lower or "plan" in prompt_lower or "week" in prompt_lower:
        return '{"milestones":[{"title":"Foundations","week_start":1,"week_end":3},{"title":"Core Concepts","week_start":4,"week_end":7},{"title":"Practice Projects","week_start":8,"week_end":12}],"snapshot":"A structured 12-week plan from foundations to real projects."}'
    if "not registered" in prompt_lower or "not found" in prompt_lower:
        return "You're not registered yet. Please start with /start to set up your profile!"
    return "Today's task: spend 30 focused minutes on your current topic. Log your progress when done!"


def call_llm(prompt: str, system: str = "", max_tokens: int = 500,
             thinking_budget: int = 0, _audit_route: str = "") -> str:
    """Sync — google-genai SDK.
    thinking_budget=0    -> Coach, Onboarding, Router (instant)
    thinking_budget=1024 -> Planner, Researcher (deep reasoning)
    _audit_route         -> optional route tag written to security_audit
    """
    _t0 = time.monotonic()
    if DEMO_MODE:
        result = _demo_response(prompt)
        _audit(prompt, result, "demo", 0, "demo", _audit_route)
        return result
    client = _get_genai_client()
    if not client:
        raise RuntimeError("GEMINI_API_KEY not set")
    from google.genai import types as genai_types
    config = genai_types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        thinking_config=genai_types.ThinkingConfig(thinking_budget=thinking_budget),
        system_instruction=system or None,
    )
    _status = "ok"
    text = ""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        candidate = response.candidates[0]
        finish = candidate.finish_reason
        text = "".join(
            part.text for part in candidate.content.parts if hasattr(part, "text")
        )
        if finish.name != "STOP":
            pass  # suppressed: finish_reason logged to security_audit only
            _status = f"finish_{finish.name.lower()}"
    except Exception:
        _status = "error"
        raise
    finally:
        _ms = int((time.monotonic() - _t0) * 1000)
        _audit(prompt, text, GEMINI_MODEL, _ms, _status, _audit_route)
    return text


async def async_call_llm(
    prompt: str,
    system: str = "",
    max_tokens: int = 500,
    json_mode: bool = False,
    thinking_budget: int = 0,
    _audit_route: str = "",
) -> str:
    """Async — google-genai async SDK.
    thinking_budget=0    -> Coach, Onboarding, Router (instant)
    thinking_budget=1024 -> Planner, Researcher (deep reasoning)
    _audit_route         -> optional route tag written to security_audit
    """
    _t0 = time.monotonic()
    if DEMO_MODE:
        result = _demo_response(prompt)
        _audit(prompt, result, "demo", 0, "demo", _audit_route)
        return result
    client = _get_genai_client()
    if not client:
        raise RuntimeError("GEMINI_API_KEY not set")
    from google.genai import types as genai_types
    config = genai_types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        thinking_config=genai_types.ThinkingConfig(thinking_budget=thinking_budget),
        system_instruction=system or None,
    )
    _status = "ok"
    text = ""
    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        text = response.text or ""
        return text
    except Exception as e:
        _status = "error"
        print(f"[async_call_llm ERROR] {type(e).__name__}: {e}")
        raise
    finally:
        _ms = int((time.monotonic() - _t0) * 1000)
        _audit(prompt, text, GEMINI_MODEL, _ms, _status, _audit_route)


if __name__ == "__main__":
    resp = call_llm("قل مرحبا باختصار")
    print("LLM test:", resp)
