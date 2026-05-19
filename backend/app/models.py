"""All ORM models in one module — 7 tables."""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nickname = Column(String(50), default="")
    avatar = Column(String(255), default="")
    is_admin = Column(Integer, default=0)  # 0=user, 1=admin
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SleepRecord(Base):
    __tablename__ = "sleep_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    diary_date = Column(Date, nullable=False)
    bedtime = Column(DateTime, nullable=False)
    wake_time = Column(DateTime, nullable=False)
    duration_hours = Column(Float, nullable=True)
    quality = Column(Integer, nullable=True)
    tags = Column(String(200), default="[]")
    notes = Column(Text, default="")
    score = Column(Integer, default=0)
    ai_feedback = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class HealthProfile(Base):
    __tablename__ = "health_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)
    height = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    occupation = Column(String(50), nullable=True)
    sleep_issue_duration = Column(String(50), nullable=True)
    sleep_goal_hours = Column(Float, default=8.0)
    bedtime_target = Column(String(5), default="22:30")
    wakeup_target = Column(String(5), default="07:00")
    typical_bedtime = Column(String(5), nullable=True)
    typical_waketime = Column(String(5), nullable=True)
    chronic_conditions = Column(Text, default="")
    medications = Column(Text, default="")
    caffeine_consumption = Column(String(50), nullable=True)
    caffeine_intake = Column(String(50), default="")
    alcohol_intake = Column(String(50), default="")
    exercise_routine = Column(String(50), nullable=True)
    exercise_frequency = Column(String(50), default="")
    exercise_type = Column(Text, default="")
    stress_level = Column(String(20), default="")
    sleep_issues = Column(Text, default="")
    snoring = Column(String(20), default="")
    dream_frequency = Column(String(20), default="")
    wake_up_count = Column(Integer, default=0)
    screen_time_before_bed = Column(String(20), default="")
    reading_before_bed = Column(String(20), default="")
    bedroom_temperature = Column(Float, default=22.0)
    bedroom_light = Column(String(20), default="")
    bedroom_noise = Column(String(20), default="")
    improvement_priority = Column(Text, default="")
    preferred_sounds = Column(Text, default="")
    preferred_tasks = Column(Text, default="")
    primary_goal = Column(Text, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    session = relationship("ChatSession", back_populates="messages")


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(10), nullable=False)
    date_key = Column(String(20), nullable=False)
    points = Column(Integer, default=5)
    completed_at = Column(DateTime, server_default=func.now())


class UserPoints(Base):
    __tablename__ = "user_points"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    total_points = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BadgeUnlock(Base):
    __tablename__ = "badge_unlocks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    badge_id = Column(String(10), nullable=False)
    unlocked_at = Column(DateTime, server_default=func.now())


class PlanEnrollment(Base):
    """Tracks which improvement plan a user has activated."""
    __tablename__ = "plan_enrollments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(String(30), nullable=False)
    status = Column(String(20), default="active")  # active, completed, cancelled
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    current_day = Column(Integer, default=1)


class PlanCheckIn(Base):
    """Daily check-in for plan tasks."""
    __tablename__ = "plan_checkins"
    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(Integer, ForeignKey("plan_enrollments.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date_key = Column(String(20), nullable=False)
    task_index = Column(Integer, nullable=False)
    checked = Column(DateTime, server_default=func.now())


class PasswordReset(Base):
    """Password reset tokens."""
    __tablename__ = "password_resets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Integer, default=0)


class NotificationSetting(Base):
    """User notification preferences."""
    __tablename__ = "notification_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    sleep_reminder = Column(Integer, default=1)     # remind to record sleep
    task_reminder = Column(Integer, default=1)       # daily task reminder
    plan_reminder = Column(Integer, default=1)       # plan progress reminder
    reminder_time = Column(String(5), default="21:00")  # reminder time
    push_enabled = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    """Security audit trail."""
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(50), nullable=False)     # login, login_failed, password_change, register, etc.
    ip_address = Column(String(50), default="")
    detail = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class LoginAttempt(Base):
    """Track login attempts for rate limiting."""
    __tablename__ = "login_attempts"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False)
    ip_address = Column(String(50), default="")
    success = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class HealthData(Base):
    """External health data (steps, heart rate, etc.)."""
    __tablename__ = "health_data"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date_key = Column(String(20), nullable=False)
    steps = Column(Integer, default=0)
    heart_rate_avg = Column(Integer, nullable=True)
    source = Column(String(30), default="manual")
    created_at = Column(DateTime, server_default=func.now())


# ===== Community Models =====
class CommunityGroup(Base):
    """Topic-based sleep support groups."""
    __tablename__ = "community_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    icon = Column(String(10), default="💬")
    member_count = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class GroupMember(Base):
    """Membership in a community group."""
    __tablename__ = "group_members"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("community_groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, server_default=func.now())


class SleepChallenge(Base):
    """Time-limited sleep challenges."""
    __tablename__ = "sleep_challenges"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, default="")
    icon = Column(String(10), default="🏆")
    target_type = Column(String(30), default="streak")  # streak, early_bed, duration, score
    target_value = Column(Integer, default=7)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    participant_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class ChallengeParticipant(Base):
    """User participation in a challenge."""
    __tablename__ = "challenge_participants"
    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("sleep_challenges.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    progress = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    joined_at = Column(DateTime, server_default=func.now())


class SleepPost(Base):
    """User-shared sleep diary post."""
    __tablename__ = "sleep_posts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, default="")
    sleep_score = Column(Integer, nullable=True)
    sleep_duration = Column(Float, nullable=True)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    is_anonymous = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class PostComment(Base):
    """Comment on a sleep post."""
    __tablename__ = "post_comments"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("sleep_posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class PostLike(Base):
    """Like on a sleep post."""
    __tablename__ = "post_likes"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("sleep_posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Membership(Base):
    """User membership subscription."""
    __tablename__ = "memberships"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    tier = Column(String(20), default="free")  # free, pro, premium
    started_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    auto_renew = Column(Integer, default=0)


class SleepStory(Base):
    """Guided sleep stories / meditations."""
    __tablename__ = "sleep_stories"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    category = Column(String(50), default="故事")
    duration_minutes = Column(Integer, default=15)
    audio_url = Column(String(500), default="")
    narrator = Column(String(50), default="AI")
    is_premium = Column(Integer, default=0)
    play_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class PaymentOrder(Base):
    """Payment orders for membership subscriptions."""
    __tablename__ = "payment_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tier = Column(String(20), nullable=False)  # pro, premium
    amount = Column(Integer, nullable=False)    # in cents (分)
    status = Column(String(20), default="pending")  # pending, paid, cancelled, refunded
    payment_method = Column(String(20), default="wechat")  # wechat, alipay, manual
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)  # membership expiry


class PaymentRecord(Base):
    """Payment transaction records."""
    __tablename__ = "payment_records"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("payment_orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    transaction_id = Column(String(64), default="")
    amount = Column(Integer, nullable=False)
    method = Column(String(20), default="wechat")
    status = Column(String(20), default="pending")
    raw_response = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class MoodRecord(Base):
    """Daily mood tracking."""
    __tablename__ = "mood_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date_key = Column(String(20), nullable=False)
    mood_level = Column(Integer, nullable=False)     # 1-5
    energy_level = Column(Integer, nullable=False)    # 1-5
    anxiety_level = Column(Integer, nullable=False)   # 1-5
    note = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class SleepAssessment(Base):
    """Standard sleep assessment results."""
    __tablename__ = "sleep_assessments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scale_type = Column(String(10), nullable=False)  # PSQI, ISI, ESS
    score = Column(Integer, nullable=False)
    severity = Column(String(20), nullable=False)     # mild, moderate, severe
    answers = Column(Text, default="{}")              # JSON answers
    ai_analysis = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class UserLevel(Base):
    """User gamification level."""
    __tablename__ = "user_levels"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    level = Column(Integer, default=1)
    total_xp = Column(Integer, default=0)
    current_xp = Column(Integer, default=0)
    streak_days = Column(Integer, default=0)
    max_streak = Column(Integer, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(100), nullable=False)
    code = Column(String(6), nullable=False)
    verified = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class UserSettings(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    theme = Column(String(10), default="dark")
    language = Column(String(10), default="zh")
    font_size = Column(String(10), default="medium")
    show_xp_animations = Column(Integer, default=1)


class SleepProduct(Base):
    """Sleep wellness products for store."""
    __tablename__ = "sleep_products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    desc = Column(Text, default="")
    price = Column(Integer, nullable=False)
    image_url = Column(String(500), default="")
    category = Column(String(30), default="其他")
    stock = Column(Integer, default=0)
    sales = Column(Integer, default=0)
    rating = Column(Float, default=4.5)
    is_active = Column(Integer, default=1)


class SleepCourse(Base):
    """Sleep education courses."""
    __tablename__ = "sleep_courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    desc = Column(Text, default="")
    instructor = Column(String(50), default="睡眠专家")
    duration_hours = Column(Float, default=1)
    chapters = Column(Integer, default=1)
    price = Column(Integer, default=0)
    enrolled = Column(Integer, default=0)
    rating = Column(Float, default=4.8)
    is_premium = Column(Integer, default=0)


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("sleep_courses.id", ondelete="CASCADE"), nullable=False)
    progress = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    enrolled_at = Column(DateTime, server_default=func.now())


class ReferralCode(Base):
    """User referral/invite codes."""
    __tablename__ = "referral_codes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    code = Column(String(10), unique=True, nullable=False)
    invite_count = Column(Integer, default=0)
    reward_earned = Column(Integer, default=0)  # in cents
    created_at = Column(DateTime, server_default=func.now())


class ReferralRecord(Base):
    """Track referrals."""
    __tablename__ = "referral_records"
    id = Column(Integer, primary_key=True, index=True)
    inviter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invited_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rewarded = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class SleepDoctor(Base):
    """Sleep specialist profiles."""
    __tablename__ = "sleep_doctors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    title = Column(String(100), default="")
    specialty = Column(String(100), default="")
    experience_years = Column(Integer, default=5)
    rating = Column(Float, default=4.8)
    consult_fee = Column(Integer, default=19900)
    avatar_url = Column(String(500), default="")
    available = Column(Integer, default=1)


class DoctorAppointment(Base):
    """Appointment booking."""
    __tablename__ = "doctor_appointments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("sleep_doctors.id"), nullable=False)
    date_key = Column(String(20), nullable=False)
    time_slot = Column(String(10), nullable=False)
    status = Column(String(20), default="pending")
    note = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class CourseChapter(Base):
    """Course chapter content."""
    __tablename__ = "course_chapters"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("sleep_courses.id", ondelete="CASCADE"), nullable=False)
    order_num = Column(Integer, default=1)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    video_url = Column(String(500), default="")
    duration_minutes = Column(Integer, default=15)


class StoreCart(Base):
    """Shopping cart item."""
    __tablename__ = "store_cart"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("sleep_products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, default=1)


class StoreOrder(Base):
    """Store order."""
    __tablename__ = "store_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total_amount = Column(Integer, nullable=False)
    status = Column(String(20), default="pending")
    address = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class SleepEnvironment(Base):
    """Sleep environment sensor data."""
    __tablename__ = "sleep_environments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date_key = Column(String(20), nullable=False)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    light_level = Column(Float, nullable=True)
    noise_level = Column(Float, nullable=True)
    source = Column(String(30), default="manual")
    created_at = Column(DateTime, server_default=func.now())


class DataExport(Base):
    """User data export requests (GDPR)."""
    __tablename__ = "data_exports"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending")
    file_url = Column(String(500), default="")
    requested_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


class SearchHistory(Base):
    """User search history for recommendations."""
    __tablename__ = "search_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    query = Column(String(200), nullable=False)
    result_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class Achievement(Base):
    """Special user achievements beyond badges."""
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    achievement_key = Column(String(30), nullable=False)
    title = Column(String(100), nullable=False)
    desc = Column(String(200), default="")
    icon = Column(String(10), default="🏆")
    unlocked_at = Column(DateTime, server_default=func.now())


class WeeklyDigest(Base):
    """Auto-generated weekly digest history."""
    __tablename__ = "weekly_digests"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    week_start = Column(String(10), nullable=False)
    content = Column(Text, default="")
    sent = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class Integration(Base):
    """External platform integrations."""
    __tablename__ = "integrations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(30), nullable=False)  # apple_health, google_fit, fitbit, oura
    access_token = Column(String(500), default="")
    refresh_token = Column(String(500), default="")
    last_sync = Column(DateTime, nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())


class Coupon(Base):
    __tablename__ = "coupons"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False)
    discount_percent = Column(Integer, default=10)
    max_uses = Column(Integer, default=100)
    used_count = Column(Integer, default=0)
    min_amount = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Integer, default=1)


class UserCoupon(Base):
    __tablename__ = "user_coupons"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False)
    used = Column(Integer, default=0)
    claimed_at = Column(DateTime, server_default=func.now())


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rec_type = Column(String(20), nullable=False)
    content = Column(Text, default="")
    reason = Column(Text, default="")
    applied = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class SleepCompetition(Base):
    """Multiplayer sleep challenge competitions."""
    __tablename__ = "sleep_competitions"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    desc = Column(Text, default="")
    icon = Column(String(10), default="🏆")
    metric = Column(String(20), default="avg_score")  # avg_score, streak, early_bed
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    min_participants = Column(Integer, default=5)
    participant_count = Column(Integer, default=0)
    prize = Column(String(100), default="")


class CompetitionEntry(Base):
    """User participation in a competition."""
    __tablename__ = "competition_entries"
    id = Column(Integer, primary_key=True, index=True)
    competition_id = Column(Integer, ForeignKey("sleep_competitions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, default=0)
    rank = Column(Integer, nullable=True)
    joined_at = Column(DateTime, server_default=func.now())


class RelaxationSpace(Base):
    """Immersive 3D relaxation space presets."""
    __tablename__ = "relaxation_spaces"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    scene_type = Column(String(30), default="nature")  # nature, space, ocean, forest
    bgm = Column(String(200), default="")
    ambient = Column(String(30), default="")
    is_premium = Column(Integer, default=0)


class LiveCourse(Base):
    """Live streaming sleep courses."""
    __tablename__ = "live_courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    instructor = Column(String(50), default="")
    scheduled_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=60)
    participant_limit = Column(Integer, default=100)
    enrolled = Column(Integer, default=0)
    stream_url = Column(String(500), default="")
    is_premium = Column(Integer, default=0)


class LiveEnrollment(Base):
    __tablename__ = "live_enrollments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    live_id = Column(Integer, ForeignKey("live_courses.id", ondelete="CASCADE"), nullable=False)
    enrolled_at = Column(DateTime, server_default=func.now())


class LifecycleEmail(Base):
    """Automated lifecycle email triggers."""
    __tablename__ = "lifecycle_emails"
    id = Column(Integer, primary_key=True, index=True)
    trigger = Column(String(30), nullable=False)  # welcome, inactive_3d, inactive_7d, streak_7, premium_expiring
    subject = Column(String(200), default="")
    template = Column(Text, default="")
    delay_hours = Column(Integer, default=0)
    is_active = Column(Integer, default=1)


class ABTest(Base):
    """A/B testing experiments."""
    __tablename__ = "ab_tests"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    variant_a = Column(Text, default="{}")
    variant_b = Column(Text, default="{}")
    a_users = Column(Integer, default=0)
    b_users = Column(Integer, default=0)
    a_conversions = Column(Integer, default=0)
    b_conversions = Column(Integer, default=0)
    is_active = Column(Integer, default=1)


class AnalyticsEvent(Base):
    """User behavior events for funnel analysis."""
    __tablename__ = "analytics_events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    event = Column(String(50), nullable=False)
    properties = Column(Text, default="{}")
    created_at = Column(DateTime, server_default=func.now())


class SleepNFT(Base):
    """Blockchain sleep achievement NFTs."""
    __tablename__ = "sleep_nfts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_id = Column(String(64), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    image_url = Column(String(500), default="")
    rarity = Column(String(20), default="common")
    nft_metadata = Column(Text, default="{}")
    minted_at = Column(DateTime, server_default=func.now())


class SleepToken(Base):
    """In-app token/points economy."""
    __tablename__ = "sleep_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    balance = Column(Integer, default=0)
    earned_total = Column(Integer, default=0)
    spent_total = Column(Integer, default=0)


class TokenTransaction(Base):
    """Token transaction history."""
    __tablename__ = "token_transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False)
    tx_type = Column(String(20), nullable=False)  # earn, spend, stake, reward
    description = Column(String(200), default="")
    created_at = Column(DateTime, server_default=func.now())


class OpenDataset(Base):
    """Community-contributed anonymized sleep data."""
    __tablename__ = "open_datasets"
    id = Column(Integer, primary_key=True, index=True)
    contributor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    dataset_hash = Column(String(64), default="")
    data_summary = Column(Text, default="{}")
    record_count = Column(Integer, default=0)
    tags = Column(String(200), default="")
    downloads = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class LocalLLM(Base):
    """Local LLM deployment config."""
    __tablename__ = "local_llms"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    model = Column(String(50), default="llama3")
    endpoint = Column(String(200), default="http://localhost:11434")
    is_active = Column(Integer, default=0)


class IoTDevice(Base):
    """Smart home IoT devices."""
    __tablename__ = "iot_devices"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_type = Column(String(30), nullable=False)  # mattress, light, curtain, watch
    device_id = Column(String(100), default="")
    name = Column(String(100), default="")
    status = Column(Text, default="{}")
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class SmartAlarm(Base):
    """Smart wake-up alarm config."""
    __tablename__ = "smart_alarms"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_time = Column(String(5), nullable=False)  # HH:MM
    wake_window = Column(Integer, default=30)  # minutes before target
    smart_method = Column(String(20), default="light")  # light, sound, vibration
    enabled_days = Column(String(50), default="1,2,3,4,5")
    is_active = Column(Integer, default=1)


class WatchAppData(Base):
    """Smartwatch sleep data sync."""
    __tablename__ = "watch_app_data"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device = Column(String(30), default="apple_watch")
    heart_rate = Column(Text, default="[]")
    hrv = Column(Float, nullable=True)
    spo2 = Column(Float, nullable=True)
    steps = Column(Integer, default=0)
    date_key = Column(String(20), nullable=False)
    synced_at = Column(DateTime, server_default=func.now())
