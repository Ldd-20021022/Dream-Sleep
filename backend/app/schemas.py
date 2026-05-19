"""All Pydantic schemas in one module — using inheritance to eliminate duplication."""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, validator


# ===== Auth =====
class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    nickname: Optional[str] = ""


class UserLogin(BaseModel):
    username: str
    password: str


class UserProfileBasic(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


def _to_str(v):
    return str(v) if v is not None else None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    nickname: str
    avatar: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    _dt_created = validator('created_at', pre=True, allow_reuse=True)(_to_str)
    _dt_updated = validator('updated_at', pre=True, allow_reuse=True)(_to_str)

    class Config:
        from_attributes = True


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HasProfileResponse(BaseModel):
    has_profile: bool


# ===== Sleep Records =====
class SleepRecordCreate(BaseModel):
    diary_date: date
    bedtime: datetime
    wake_time: datetime
    quality: Optional[int] = None
    tags: Optional[List[str]] = []
    notes: Optional[str] = ""


class SleepRecordResponse(BaseModel):
    id: int
    user_id: int
    diary_date: Optional[str] = None
    bedtime: Optional[str] = None
    wake_time: Optional[str] = None
    duration_hours: Optional[float] = None
    quality: Optional[int] = None
    tags: Optional[str] = "[]"
    notes: Optional[str] = ""
    score: int = 0
    ai_feedback: Optional[str] = ""
    created_at: Optional[str] = None

    _v_dd = validator('diary_date', pre=True, allow_reuse=True)(_to_str)
    _v_bt = validator('bedtime', pre=True, allow_reuse=True)(_to_str)
    _v_wt = validator('wake_time', pre=True, allow_reuse=True)(_to_str)
    _v_ca = validator('created_at', pre=True, allow_reuse=True)(_to_str)

    class Config:
        from_attributes = True


class SleepStatsResponse(BaseModel):
    avg_duration: float
    avg_score: float
    consistency: str
    consistency_minutes: float
    streak_days: int
    total_records: int
    tag_counts: dict
    records: List[SleepRecordResponse]

    class Config:
        from_attributes = True


# ===== Health Profile — uses base class to eliminate 41-field duplication =====
class HealthProfileBase(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    occupation: Optional[str] = None
    sleep_issue_duration: Optional[str] = None
    sleep_goal_hours: Optional[float] = 8.0
    bedtime_target: Optional[str] = "22:30"
    wakeup_target: Optional[str] = "07:00"
    typical_bedtime: Optional[str] = None
    typical_waketime: Optional[str] = None
    chronic_conditions: Optional[str] = ""
    medications: Optional[str] = ""
    caffeine_consumption: Optional[str] = None
    caffeine_intake: Optional[str] = ""
    alcohol_intake: Optional[str] = ""
    exercise_routine: Optional[str] = None
    exercise_frequency: Optional[str] = ""
    exercise_type: Optional[str] = ""
    stress_level: Optional[str] = ""
    sleep_issues: Optional[str] = ""
    snoring: Optional[str] = ""
    dream_frequency: Optional[str] = ""
    wake_up_count: Optional[int] = 0
    screen_time_before_bed: Optional[str] = ""
    reading_before_bed: Optional[str] = ""
    bedroom_temperature: Optional[float] = 22.0
    bedroom_light: Optional[str] = ""
    bedroom_noise: Optional[str] = ""
    improvement_priority: Optional[str] = ""
    preferred_sounds: Optional[str] = ""
    preferred_tasks: Optional[str] = ""
    primary_goal: Optional[str] = None
    notes: Optional[str] = ""


class HealthProfileCreate(HealthProfileBase):
    pass


class HealthProfileResponse(HealthProfileBase):
    id: int
    user_id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    _v_ca = validator('created_at', pre=True, allow_reuse=True)(_to_str)
    _v_ua = validator('updated_at', pre=True, allow_reuse=True)(_to_str)

    class Config:
        from_attributes = True


# ===== Chat =====
class SendMessageRequest(BaseModel):
    session_id: Optional[int] = None
    message: str


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: Optional[str] = None
    session_id: Optional[int] = None

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: int
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class ChatSessionDetailResponse(ChatSessionResponse):
    messages: List[ChatMessageResponse] = []


# ===== Tasks =====
class TaskCompleteRequest(BaseModel):
    task_id: str
    date_key: str


class PointsResponse(BaseModel):
    total_points: int


class BadgeUnlockRequest(BaseModel):
    badge_id: str
