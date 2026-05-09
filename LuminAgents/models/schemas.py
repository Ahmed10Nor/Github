# models/schemas.py
# LuminAgents -- Unified Pydantic Schemas (Architecture v5.4)
from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal
try:
    from pydantic import BaseModel, Field, field_validator
    _PYDANTIC_FULL = True
except ImportError:
    from pydantic import BaseModel  # type: ignore[assignment]
    _PYDANTIC_FULL = False
    def Field(default=None, **_):  # type: ignore[misc]
        return default
    def field_validator(*_, **__):  # type: ignore[misc]
        return lambda f: f


OnboardingStep = Literal["awaiting_goal", "awaiting_level", "complete"]

RouteDecision = Literal["out_of_scope", "content_question", "plan_change", "daily_check"]

LearningTemplate = Literal[
    "80_20_project_based",
    "linear_mastery",
    "habit_stacking",
    "progressive_overload",
]

Category = Literal["academic", "physical", "professional", "personal"]
Level    = Literal["beginner", "intermediate", "advanced"]


class OnboardingInput(BaseModel):
    user_id:       str
    name:          Optional[str]   = None
    goal:          Optional[str]   = None
    category:      Optional[Category] = None
    level:         Optional[Level] = None
    hours_per_day: Optional[float] = None
    days_per_week: Optional[int]   = None
    language:      str             = "ar"
    age:    Optional[int]   = None
    weight: Optional[float] = None
    height: Optional[float] = None

    @property
    def is_complete(self) -> bool:
        return bool(self.goal and self.level)

    @property
    def missing_required(self) -> list:
        missing = []
        if not self.goal:  missing.append("goal")
        if not self.level: missing.append("level")
        return missing


class UserProfile(BaseModel):
    user_id:             str
    name:                str
    goal:                str
    category:            Category
    level:               Level
    hours_per_day:       float = 1.0
    days_per_week:       int   = 5
    estimated_weeks:     int
    start_date:          str
    language:            str = "ar"
    onboarding_complete: int  = 0
    onboarding_step:     OnboardingStep = "awaiting_goal"
    partial_profile:     Optional[str] = None
    age:    Optional[int]   = None
    weight: Optional[float] = None
    height: Optional[float] = None
    # v5.4 -- Hazem Protocol (v6.7: defaults updated to Lumin, Optional for NULL safety)
    agent_name: Optional[str] = "Lumin"
    agent_vibe: Optional[str] = "Professional"


class LessonNode(BaseModel):
    id:         str
    title:      str
    weight:     float  = Field(..., gt=0, le=1)
    depends_on: list   = []
    hours_std:  float  = Field(..., gt=0)

    @field_validator("weight")
    @classmethod
    def weight_range(cls, v: float) -> float:
        if not 0 < v <= 1:
            raise ValueError("weight must be in (0, 1]")
        return round(v, 4)


class CurriculumMap(BaseModel):
    skill:           str
    category:        Category
    template:        LearningTemplate
    total_hours_std: float
    lessons:         list

    @field_validator("lessons")
    @classmethod
    def weights_sum_to_one(cls, lessons) -> list:
        total = round(sum(l.weight for l in lessons), 4)
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Lesson weights must sum to ~1.0, got {total}")
        return lessons


class ContextFrame(BaseModel):
    user_id:        str
    skill:          str
    user_level:     Level
    chunks:         list
    curriculum_map: CurriculumMap
    user_state:     dict
    fallback_used:  bool  = False
    retrieved_at:   datetime = Field(default_factory=datetime.utcnow)


class DailyTask(BaseModel):
    day:         int
    week:        int
    lesson_id:   str
    description: str
    hours:       float
    completed:   bool = False


class Milestone(BaseModel):
    title:      str
    week_start: int
    week_end:   int
    lesson_ids: list = []
    completed:  bool = False


class MacroPlan(BaseModel):
    milestones:  list
    total_weeks: int
    template:    LearningTemplate
    snapshot:    str = ""


class MicroPlan(BaseModel):
    daily_tasks: list
    total_days:  int
    h_total:     float
    user_id:     str


class ValidationResult(BaseModel):
    passed:      bool
    h_total:     float
    h_available: float
    delta:       float
    error_trace: Optional[str] = None


class CoachReport(BaseModel):
    task_completed:   bool
    failure_streak:   int
    updated_estimate: int
    notes:            str
    day_index:        int = 0


class SemanticGapResult(BaseModel):
    gap_detected:   bool
    challenge_hint: str = ""


class FixerTrigger(BaseModel):
    reason:           Literal["streak", "gap", "manual_request", "behavior"]
    streak_count:     int = 0
    gap_days:         int = 0
    behavioral_score: int = 0   # 1=warning, 2=intervention (long gap OR repeated query)


class FixerReport(BaseModel):
    message:      str
    rescheduled:  bool = False
    rebuilt:      bool = False
    streak_reset: bool = False


class ResearchResult(BaseModel):
    chunks:        list
    sources:       list
    tags_used:     list
    fallback_used: bool = False


class MessageInput(BaseModel):
    user_id: str
    message: str


class ProgressResponse(BaseModel):
    user_id:             str
    current_day:         int
    current_week:        int
    failure_streak:      int
    estimated_weeks:     int
    onboarding_complete: int


# v5.4 -- Hot Swap
class ArchivedSkill(BaseModel):
    id:                int
    user_id:           str
    goal:              str
    category:          Category
    level:             Level
    milestone_reached: int   = 0
    total_milestones:  int   = 0
    success_rate:      float = 0.0
    strengths:         str   = ""
    weaknesses:        str   = ""
    snapshot_text:     str   = ""
    archived_at:       str   = ""


# v5.1 -- Consensus Engine
class ConsensusResult(BaseModel):
    coach_view: str
    fixer_view: str
    decision:   str
    action:     Literal["proceed", "proceed_adjusted", "simplify", "rebuild"] = "proceed"
