# agents/onboarding.py
import math
from datetime import date
from models.schemas import UserProfile, OnboardingInput
from db.database import get_connection
from llm.llm_client import call_llm

H_BASE_TABLE = {
    ("academic", "programming", "beginner"): 60,
    ("academic", "programming", "intermediate"): 40,
    ("academic", "programming", "advanced"): 25,
    ("academic", "language", "beginner"): 150,
    ("academic", "language", "intermediate"): 100,
    ("academic", "math", "beginner"): 80,
    ("physical", "fitness", "beginner"): 48,
    ("physical", "fitness", "intermediate"): 32,
    ("professional", "marketing", "beginner"): 80,
    ("professional", "business", "beginner"): 90,
    ("personal", "habits", "beginner"): 30,
    ("personal", "habits", "intermediate"): 20,
}

DEFAULT_H_BASE = 60

def estimate_weeks(h_base: int, h: float, d: int, C: float = 1.2) -> int:
    return math.ceil((h_base / (h * d)) * C)

def get_h_base(category: str, goal: str, level: str) -> int:
    goal_lower = goal.lower()
    for keyword in ["python", "programming", "code", "برمجة"]:
        if keyword in goal_lower:
            return H_BASE_TABLE.get((category, "programming", level), DEFAULT_H_BASE)
    for keyword in ["english", "ielts", "language", "لغة", "ايلتس"]:
        if keyword in goal_lower:
            return H_BASE_TABLE.get((category, "language", level), DEFAULT_H_BASE)
    for keyword in ["math", "رياضيات"]:
        if keyword in goal_lower:
            return H_BASE_TABLE.get((category, "math", level), DEFAULT_H_BASE)
    for keyword in ["fitness", "gym", "لياقة", "رياضة"]:
        if keyword in goal_lower:
            return H_BASE_TABLE.get((category, "fitness", level), DEFAULT_H_BASE)
    for keyword in ["marketing", "تسويق"]:
        if keyword in goal_lower:
            return H_BASE_TABLE.get((category, "marketing", level), DEFAULT_H_BASE)
    for keyword in ["habit", "عادة", "عادات"]:
        if keyword in goal_lower:
            return H_BASE_TABLE.get((category, "habits", level), DEFAULT_H_BASE)
    return DEFAULT_H_BASE

class OnboardingAgent:
    def run(self, data: OnboardingInput) -> UserProfile:
        h_base = get_h_base(data.category, data.goal, data.level)
        weeks  = estimate_weeks(h_base, data.hours_per_day, data.days_per_week)

        profile = UserProfile(
            user_id=data.user_id,
            name=data.name,
            goal=data.goal,
            category=data.category,
            level=data.level,
            hours_per_day=data.hours_per_day,
            days_per_week=data.days_per_week,
            estimated_weeks=weeks,
            start_date=str(date.today()),
            language=data.language
        )

        self._save(profile)
        return profile

    def _save(self, profile: UserProfile):
        conn = get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO users
            (user_id, name, goal, category, level, hours_per_day, days_per_week, estimated_weeks, start_date, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            profile.user_id, profile.name, profile.goal,
            profile.category, profile.level, profile.hours_per_day,
            profile.days_per_week, profile.estimated_weeks, profile.start_date, profile.language
        ))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    agent = OnboardingAgent()
    test_input = OnboardingInput(
        user_id="test_001",
        name="أحمد",
        goal="تعلم Python",
        category="academic",
        level="beginner",
        hours_per_day=1.0,
        days_per_week=5
    )
    profile = agent.run(test_input)
    print(f"✅ Onboarding done: {profile.name} | {profile.estimated_weeks} weeks | goal: {profile.goal}")
