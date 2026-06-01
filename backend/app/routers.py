# -*- coding: utf-8 -*-
"""All API routers in one module."""
import json, time, random
from datetime import datetime, timedelta
from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.security import sanitize_input, validate_password_strength, blacklist_token, is_token_blacklisted
from app.dependencies import current_user_and_db
from app.database import get_db
from app.models import (
    User, SleepRecord, HealthProfile,
    ChatSession, ChatMessage,
    TaskCompletion, UserPoints, BadgeUnlock,
    PlanEnrollment, PlanCheckIn,
    SleepPost, PostComment, PostLike,
    UserFollow, Notification, PostBookmark, PostReport,
)
from app.schemas import (
    UserRegister, UserLogin, UserResponse, UserProfileBasic, ChangePassword,
    TokenPair, TokenRefresh, TokenRefreshResponse, HasProfileResponse,
    SleepRecordCreate, SleepRecordResponse, SleepStatsResponse,
    HealthProfileCreate, HealthProfileResponse,
    SendMessageRequest,
    TaskCompleteRequest, PointsResponse, BadgeUnlockRequest,
)
from app.services import (
    hash_pw, verify_pw,
    create_access_token, create_refresh_token, decode_token,
    get_sleep_feedback,
    calc_score, calc_duration, calc_consistency_minutes, consistency_label,
    calc_streak, get_tag_stats,
    calc_sleep_efficiency, calc_sleep_debt,
    generate_weekly_report, export_records_csv,
    ai_generate_tasks, ai_design_soundscape, generate_today_tasks_rule_based, ALL_BADGES,
    chat_with_rag, ai_sentiment_analysis, ai_deep_sleep_report, ai_predict_sleep_quality, rag_retrieve_knowledge,
    _ai_chat,
    KNOWLEDGE_ARTICLES, KNOWLEDGE_CATEGORIES,
    IMPROVEMENT_PLANS, ONBOARDING_STEPS,
    generate_daily_insight, get_week_streak_days,
)

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Initialize WeChat config on startup
from app.config import settings as _cfg
from app.security import set_wechat_config
set_wechat_config(_cfg.WECHAT_APPID, _cfg.WECHAT_SECRET)
sleep_router = APIRouter(prefix="/api/v1/sleep-records", tags=["sleep-records"])
profile_router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])
chat_router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
task_router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
wellness_router = APIRouter(prefix="/api/v1/wellness", tags=["wellness"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
community_router = APIRouter(prefix="/api/v1/community", tags=["community"])
voice_router = APIRouter(prefix="/api/v1/voice", tags=["voice"])
premium_router = APIRouter(prefix="/api/v1/premium", tags=["premium"])
payment_router = APIRouter(prefix="/api/v1/payment", tags=["payment"])
platform_router = APIRouter(prefix="/api/v1/platform", tags=["platform"])
game_router = APIRouter(prefix="/api/v1/game", tags=["game"])
mood_router = APIRouter(prefix="/api/v1/mood", tags=["mood"])
settings_router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
store_router = APIRouter(prefix="/api/v1/store", tags=["store"])
course_router = APIRouter(prefix="/api/v1/courses", tags=["courses"])
program_router = APIRouter(prefix="/api/v1/program", tags=["program"])
referral_router = APIRouter(prefix="/api/v1/referral", tags=["referral"])
doctor_router = APIRouter(prefix="/api/v1/doctors", tags=["doctors"])
environment_router = APIRouter(prefix="/api/v1/environment", tags=["environment"])
data_router = APIRouter(prefix="/api/v1/data", tags=["data"])
integration_router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
competition_router = APIRouter(prefix="/api/v1/competitions", tags=["competitions"])
relax_router = APIRouter(prefix="/api/v1/relax", tags=["relax"])
live_router = APIRouter(prefix="/api/v1/live", tags=["live"])
growth_router = APIRouter(prefix="/api/v1/growth", tags=["growth"])
web3_router = APIRouter(prefix="/api/v1/web3", tags=["web3"])
dataset_router = APIRouter(prefix="/api/v1/dataset", tags=["dataset"])
llm_router = APIRouter(prefix="/api/v1/llm", tags=["llm"])
iot_router = APIRouter(prefix="/api/v1/iot", tags=["iot"])
watch_router = APIRouter(prefix="/api/v1/watch", tags=["watch"])


# ==================== AUTH ====================
@auth_router.post("/wx-login")
def wx_login(data: dict, db: Session = Depends(get_db)):
    """WeChat one-click login: exchange code for JWT."""
    code = data.get("code", "")
    nickname = data.get("nickname", "")
    avatar = data.get("avatar", "")

    if not code:
        raise HTTPException(status_code=400, detail="缺少登录凭证")

    appid = _cfg.WECHAT_APPID
    secret = _cfg.WECHAT_SECRET
    if not secret:
        raise HTTPException(status_code=400, detail="微信登录未配置，请联系管理员")
    else:
        try:
            import urllib.request, json as _json
            wx_url = f"https://api.weixin.qq.com/sns/jscode2session?appid={appid}&secret={secret}&js_code={code}&grant_type=authorization_code"
            resp = urllib.request.urlopen(wx_url, timeout=10)
            wx_data = _json.loads(resp.read())
            openid = wx_data.get("openid", "")
            if not openid:
                raise HTTPException(status_code=400, detail=f"微信登录失败: {wx_data.get('errmsg','?')}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"微信服务异常: {str(e)}")

    user = db.query(User).filter(User.openid == openid).first()
    is_new = False
    if not user:
        is_new = True
        username = f"wx_{openid[-12:]}"
        while db.query(User).filter(User.username == username).first():
            username = f"wx_{openid[-10:]}{random.randint(10,99)}"
        user = User(
            username=username,
            email=f"{openid[-16:]}@wx.local",
            hashed_password=hash_pw(openid),
            nickname=nickname or f"微信用户{openid[-6:]}",
            avatar=avatar,
            openid=openid,
        )
        db.add(user); db.commit(); db.refresh(user)
    elif nickname:
        user.nickname = nickname or user.nickname
        if avatar: user.avatar = avatar
        db.commit()

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return {
        "access_token": access_token, "refresh_token": refresh_token,
        "token_type": "bearer", "is_new_user": is_new,
        "user": {"id": user.id, "nickname": user.nickname or user.username, "avatar": user.avatar},
    }


@auth_router.post("/register", response_model=UserResponse)
def register(data: UserRegister, db: Session = Depends(get_db)):
    # Validate password strength
    pw_check = validate_password_strength(data.password)
    if not pw_check["valid"]:
        raise HTTPException(status_code=400, detail="; ".join(pw_check["errors"]))

    # Sanitize inputs
    username = sanitize_input(data.username)
    email = sanitize_input(data.email)
    nickname = sanitize_input(data.nickname or username)

    if db.query(User).filter((User.username == username) | (User.email == email)).first():
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少2个字符")

    user = User(username=username, email=email, phone=data.phone or "",
                hashed_password=hash_pw(data.password), nickname=nickname)
    db.add(user); db.commit(); db.refresh(user)
    return UserResponse.model_validate(user)


@auth_router.post("/login", response_model=TokenPair)
def login(data: UserLogin, db: Session = Depends(get_db), request: Request = None):
    # Get client IP from request
    client_ip = ""
    if request and request.client:
        client_ip = request.client.host or ""

    # Rate limit check — by both username and IP
    if _rate_limit_login(db, data.username, client_ip):
        raise HTTPException(status_code=429, detail="登录尝试过多，请15分钟后再试")

    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_pw(data.password, user.hashed_password):
        db.add(LoginAttempt(username=data.username, ip_address=client_ip, success=0))
        db.commit()
        _log_audit(db, user.id if user else None, "login_failed", f"Username: {data.username}", client_ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    db.add(LoginAttempt(username=data.username, ip_address=client_ip, success=1))
    db.commit()
    _log_audit(db, user.id, "login", f"User logged in", client_ip)
    return TokenPair(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


@auth_router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_token(data: TokenRefresh, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="刷新令牌无效")
    user_id = payload.get("sub")
    if not user_id or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="无效的刷新令牌")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return TokenRefreshResponse(access_token=create_access_token({"sub": str(user.id)}))


@auth_router.get("/me", response_model=UserResponse)
def me(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, _ = user_and_db
    return UserResponse.model_validate(user)


@auth_router.post("/quick-mood")
def quick_mood(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Quick mood check-in from profile page."""
    user, db = user_and_db
    mood = data.get("mood", "")
    if not mood:
        raise HTTPException(status_code=400, detail="请选择心情")
    from app.models import MoodRecord
    from datetime import date as _d
    today = _d.today().strftime("%Y-%m-%d")
    existing = db.query(MoodRecord).filter(MoodRecord.user_id == user.id, MoodRecord.date_key == today).first()
    if existing:
        existing.mood = mood
    else:
        db.add(MoodRecord(user_id=user.id, date_key=today, mood=mood))
    db.commit()
    return {"message": "心情已记录", "mood": mood}


@auth_router.put("/profile-basic")
def update_profile_basic(data: UserProfileBasic, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    if data.nickname is not None:
        user.nickname = sanitize_input(data.nickname)
    if data.avatar is not None:
        user.avatar = sanitize_input(data.avatar)
    db.commit()
    return {"message": "已更新", "nickname": user.nickname, "avatar": user.avatar}


@auth_router.get("/profile-summary")
def get_profile_summary(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get comprehensive profile summary with stats."""
    user, db = user_and_db
    from app.models import SleepRecord as SR, UserLevel as UL, UserSettings as US, HealthProfile as HP
    from datetime import date as _date
    _today = _date.today()

    # Sleep stats
    total_records = db.query(SR).filter(SR.user_id == user.id).count()
    last_record = db.query(SR).filter(SR.user_id == user.id).order_by(SR.bedtime.desc()).first()
    profile = db.query(HP).filter(HP.user_id == user.id).first()
    week_ago = _today - timedelta(days=6)
    week_records = db.query(SR).filter(SR.user_id == user.id, SR.diary_date >= week_ago).all()
    avg_score = round(sum(r.score for r in week_records) / len(week_records)) if week_records else 0
    avg_duration = round(sum(r.duration_hours or 0 for r in week_records) / len(week_records), 1) if week_records else 0
    streak = calc_streak(db, user.id)

    # Level
    ul = db.query(UL).filter(UL.user_id == user.id).first()
    level = ul.level if ul else 1
    total_xp = ul.total_xp if ul else 0
    level_name = LEVEL_NAMES[min(level - 1, len(LEVEL_NAMES) - 1)] if ul else "睡眠新手"

    # Badges
    unlocked_badges = db.query(BadgeUnlock).filter(BadgeUnlock.user_id == user.id).count()
    total_badges = len(ALL_BADGES)

    # Community stats
    post_count = db.query(SleepPost).filter(SleepPost.user_id == user.id).count()
    follower_count = db.query(UserFollow).filter(UserFollow.followee_id == user.id).count()
    following_count = db.query(UserFollow).filter(UserFollow.follower_id == user.id).count()

    # Points
    pts = db.query(UserPoints).filter(UserPoints.user_id == user.id).first()
    total_points = pts.total_points if pts else 0

    # Settings
    settings = db.query(US).filter(US.user_id == user.id).first()

    # Unread counts
    unread_notifs = db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read == 0).count()
    unread_msgs = db.query(Message).filter(Message.receiver_id == user.id, Message.is_read == 0).count()

    # Today's task completion
    today_key = _today.strftime("%Y-%m-%d")
    today_done = db.query(TaskCompletion).filter(TaskCompletion.user_id == user.id, TaskCompletion.date_key == today_key).count()

    return {
        "user": {
            "id": user.id, "username": user.username, "nickname": user.nickname or user.username,
            "avatar": user.avatar, "email": user.email,
            "created_at": str(user.created_at) if user.created_at else None,
            "days_since_join": (_today - user.created_at.date()).days if user.created_at else 0,
        },
        "sleep_goal": {
            "target_hours": profile.sleep_goal_hours if profile else 8.0,
            "target_bedtime": profile.bedtime_target if profile else "22:30",
            "target_wakeup": profile.wakeup_target if profile else "07:00",
            "last_duration": last_record.duration_hours if last_record else 0,
        },
        "sleep_stats": {
            "total_records": total_records,
            "avg_score": avg_score, "avg_duration": avg_duration,
            "streak_days": streak,
        },
        "level": {"level": level, "level_name": level_name, "total_xp": total_xp},
        "badges": {"unlocked": unlocked_badges, "total": total_badges},
        "community": {"posts": post_count, "followers": follower_count, "following": following_count},
        "points": total_points,
        "today_tasks_done": today_done,
        "unread": {"notifications": unread_notifs, "messages": unread_msgs},
        "settings": {
            "theme": settings.theme if settings else "dark",
            "language": settings.language if settings else "zh",
            "font_size": settings.font_size if settings else "medium",
        } if settings else None,
    }


@auth_router.put("/change-password")
def change_password(data: ChangePassword, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    if not verify_pw(data.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")

    pw_check = validate_password_strength(data.new_password)
    if not pw_check["valid"]:
        raise HTTPException(status_code=400, detail="; ".join(pw_check["errors"]))

    user.hashed_password = hash_pw(data.new_password)
    db.commit()
    _log_audit(db, user.id, "password_change", "Password changed")
    return {"message": "密码已修改", "strength": pw_check["strength_label"]}


@auth_router.post("/logout")
def logout(request: Request = None, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Logout — blacklist the current JWT token."""
    user, _ = user_and_db
    auth_header = request.headers.get("Authorization", "") if request else ""
    token = auth_header.replace("Bearer ", "")
    if token:
        blacklist_token(token)
    return {"message": "已退出登录"}


@auth_router.get("/has-profile", response_model=HasProfileResponse)
def has_profile(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    p = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    return HasProfileResponse(has_profile=p is not None)


# ==================== PUBLIC CONFIG ====================
# 小程序/前端拉取的非敏感配置 — 不暴露任何密钥
_public_config_router = APIRouter(prefix="/api/v1/public", tags=["public-config"])


@_public_config_router.get("/config")
def get_public_config():
    """返回客户端可用的公共配置。不含任何密钥。"""
    return {
        "app_name": "梦眠阁",
        "version": "1.0.0",
        "features": {
            "chat": True,
            "tasks": True,
            "community": True,
            "game": True,
            "vip": True,
            "noise": True,
        },
        "limits": {
            "sleep_record_days": 365,
            "chat_sessions_max": 50,
        },
    }


# ==================== SLEEP RECORDS ====================
def _to_record_response(r: SleepRecord) -> SleepRecordResponse:
    resp = SleepRecordResponse.model_validate(r)
    # Compute score breakdown on-the-fly
    _, breakdown = calc_score(r.duration_hours or 0, r.quality or 3, r.tags or "[]")
    resp.score_breakdown = breakdown
    return resp


@sleep_router.post("", response_model=SleepRecordResponse)
def create_sleep_record(data: SleepRecordCreate, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    duration = calc_duration(data.bedtime, data.wake_time)
    tags_str = json.dumps(data.tags or [], ensure_ascii=False)

    record = SleepRecord(user_id=user.id, diary_date=data.diary_date,
                         bedtime=data.bedtime, wake_time=data.wake_time,
                         duration_hours=duration, quality=data.quality,
                         tags=tags_str, notes=data.notes or "")

    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    goal = profile.sleep_goal_hours if profile else 8.0
    record.score, _ = calc_score(duration, data.quality or 3, tags_str, goal)

    diary_desc = f"入睡时间：{data.bedtime}，起床时间：{data.wake_time}，睡眠质量评分：{data.quality or '未填'}，备注：{data.notes or '无'}，标签：{', '.join(data.tags) if data.tags else '无'}"
    record.ai_feedback = get_sleep_feedback(diary_desc)

    db.add(record); db.commit(); db.refresh(record)
    return _to_record_response(record)


@sleep_router.get("")
def list_sleep_records(
    days: int = Query(None), limit: int = Query(None),
    user_and_db: Tuple[User, Session] = Depends(current_user_and_db),
):
    user, db = user_and_db
    q = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).order_by(SleepRecord.bedtime.desc())
    if days:
        q = q.filter(SleepRecord.bedtime >= datetime.now() - timedelta(days=days))
    records = q.all()
    if limit:
        records = records[:limit]
    return {"records": [_to_record_response(r) for r in records], "total": len(records)}


@sleep_router.get("/last")
def get_last(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    r = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).order_by(SleepRecord.bedtime.desc()).first()
    return _to_record_response(r) if r else None


@sleep_router.get("/stats/summary", response_model=SleepStatsResponse)
def get_stats(days: int = Query(default=7), user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).order_by(SleepRecord.bedtime).all()

    if not records:
        return SleepStatsResponse(avg_duration=0, avg_score=0, consistency="--", consistency_minutes=0, streak_days=0, total_records=0, tag_counts={}, records=[])

    avg_dur = round(sum(r.duration_hours or 0 for r in records) / len(records), 1)
    avg_score = round(sum(r.score for r in records) / len(records))
    cons_mins = calc_consistency_minutes(records)

    return SleepStatsResponse(
        avg_duration=avg_dur, avg_score=avg_score,
        consistency=consistency_label(cons_mins), consistency_minutes=round(cons_mins, 1),
        streak_days=calc_streak(db, user.id), total_records=len(records),
        tag_counts=get_tag_stats(records),
        records=[_to_record_response(r) for r in records],
    )


# Enhanced stats with efficiency and sleep debt
@sleep_router.get("/stats/enhanced")
def get_enhanced_stats(days: int = Query(default=7), user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).order_by(SleepRecord.bedtime).all()

    if not records:
        return {"avg_duration": 0, "avg_score": 0, "avg_efficiency": 0, "sleep_debt": {}, "streak": 0, "records": []}

    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    goal = profile.sleep_goal_hours if profile else 8.0

    avg_dur = round(sum(r.duration_hours or 0 for r in records) / len(records), 1)
    avg_score = round(sum(r.score for r in records) / len(records))
    efficiencies = [calc_sleep_efficiency(r.duration_hours or 0, r.bedtime, r.wake_time) for r in records]
    avg_eff = round(sum(efficiencies) / len(efficiencies), 1)
    debt = calc_sleep_debt(records, goal)
    cons_mins = calc_consistency_minutes(records)

    return {
        "avg_duration": avg_dur,
        "avg_score": avg_score,
        "avg_efficiency": avg_eff,
        "consistency": consistency_label(cons_mins),
        "consistency_minutes": round(cons_mins, 1),
        "sleep_debt": debt,
        "streak_days": calc_streak(db, user.id),
        "total_records": len(records),
        "tag_counts": get_tag_stats(records),
        "records": [_to_record_response(r) for r in records],
    }


# Weekly AI-powered sleep report
@sleep_router.get("/report")
def get_sleep_report(days: int = Query(default=7), user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).order_by(SleepRecord.bedtime).all()
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()

    if not records:
        return {"error": "暂无记录", "records_count": 0}

    avg_dur = round(sum(r.duration_hours or 0 for r in records) / len(records), 1)
    avg_score = round(sum(r.score for r in records) / len(records))
    cons_mins = calc_consistency_minutes(records)
    goal = profile.sleep_goal_hours if profile else 8.0

    stats = {
        "avg_duration": avg_dur, "avg_score": avg_score,
        "consistency": consistency_label(cons_mins), "consistency_minutes": round(cons_mins, 1),
        "streak_days": calc_streak(db, user.id),
        "tag_counts": get_tag_stats(records),
        "sleep_debt": calc_sleep_debt(records, goal),
        "avg_efficiency": round(sum(calc_sleep_efficiency(r.duration_hours or 0, r.bedtime, r.wake_time) for r in records) / len(records), 1),
    }

    profile_dict = None
    if profile:
        profile_dict = {"sleep_goal_hours": profile.sleep_goal_hours, "sleep_issues": profile.sleep_issues,
                         "stress_level": profile.stress_level, "improvement_priority": profile.improvement_priority}

    report = generate_weekly_report(user.nickname or user.username, profile_dict, records, stats)
    return report


# CSV export — returns JSON-wrapped CSV for SPA compatibility
@sleep_router.get("/export")
def export_sleep_csv(days: int = Query(default=30), user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    from fastapi.responses import JSONResponse
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).order_by(SleepRecord.bedtime.desc()).all()
    csv_data = export_records_csv(records)
    filename = f"sleep_records_{datetime.now().strftime('%Y%m%d')}.csv"
    return JSONResponse({"csv": csv_data, "count": len(records), "filename": filename})


# ==================== HEALTH PROFILES ====================
def _to_profile_response(p: HealthProfile) -> HealthProfileResponse:
    return HealthProfileResponse.model_validate(p)


@profile_router.get("")
def get_profile(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    p = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    if not p:
        return {"id": 0, "user_id": user.id, "exists": False}
    result = _to_profile_response(p)
    result_dict = result.dict()
    result_dict["exists"] = True
    return result_dict


@profile_router.put("", response_model=HealthProfileResponse)
def upsert_profile(data: HealthProfileCreate, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    p = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    updates = data.dict(exclude_unset=True)
    if p:
        for k, v in updates.items():
            setattr(p, k, v)
    else:
        p = HealthProfile(user_id=user.id, **updates)
        db.add(p)
    db.commit(); db.refresh(p)
    return _to_profile_response(p)


# ==================== CHAT ====================
@chat_router.get("/sessions")
def list_sessions(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    sessions = db.query(ChatSession).filter(ChatSession.user_id == user.id).order_by(ChatSession.updated_at.desc()).all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at.isoformat() if s.created_at else None, "updated_at": s.updated_at.isoformat() if s.updated_at else None} for s in sessions]


@chat_router.get("/sessions/{session_id}")
def get_session(session_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    s = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user.id).first()
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None} for m in s.messages]
    return {"id": s.id, "title": s.title, "created_at": s.created_at.isoformat() if s.created_at else None, "updated_at": s.updated_at.isoformat() if s.updated_at else None, "messages": msgs}


@chat_router.post("/send")
def send_message(data: SendMessageRequest, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db

    if data.session_id:
        session = db.query(ChatSession).filter(ChatSession.id == data.session_id, ChatSession.user_id == user.id).first()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
    else:
        title = data.message[:20] + ("..." if len(data.message) > 20 else "")
        session = ChatSession(user_id=user.id, title=title)
        db.add(session); db.commit(); db.refresh(session)

    user_msg = ChatMessage(session_id=session.id, role="user", content=data.message)
    db.add(user_msg); db.commit()

    history_msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc()).all()
    history = [{"role": m.role, "content": m.content} for m in history_msgs]

    context = ""
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    if profile:
        parts = []
        if profile.age: parts.append(f"年龄：{profile.age}")
        if profile.gender: parts.append(f"性别：{profile.gender}")
        if profile.sleep_goal_hours: parts.append(f"目标睡眠时长：{profile.sleep_goal_hours}h")
        if profile.sleep_issues: parts.append(f"睡眠问题：{profile.sleep_issues}")
        if profile.stress_level: parts.append(f"压力水平：{profile.stress_level}")
        context = "，".join(parts)

    # Enhanced context: recent 7-day sleep data + trends
    recent = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).order_by(SleepRecord.bedtime.desc()).limit(7).all()
    if recent:
        avg_score = round(sum(r.score for r in recent) / len(recent))
        avg_dur = round(sum(r.duration_hours or 0 for r in recent) / len(recent), 1)
        scores = [r.score for r in recent]
        trend = "上升" if len(scores) >= 2 and scores[0] > scores[-1] else ("下降" if len(scores) >= 2 and scores[0] < scores[-1] else "稳定")
        last = recent[0]
        context += f"\n\n近期睡眠数据：近7天平均{avg_dur}h，均分{avg_score}，趋势{trend}。最近一次：{last.diary_date}，{last.duration_hours}h，评分{last.score}分。"
    from app.models import ProgramProgress as _PP
    _pp = db.query(_PP).filter(_PP.user_id == user.id).first()
    if _pp and _pp.current_day > 0:
        context += f" 21天课程进度：第{_pp.current_day}/21天。"

    ai_reply = chat_with_rag(data.message, history, context)
    assistant_msg = ChatMessage(session_id=session.id, role="assistant", content=ai_reply)
    db.add(assistant_msg); db.commit(); db.refresh(assistant_msg)

    session.updated_at = datetime.utcnow()
    db.commit()

    return {"id": assistant_msg.id, "role": "assistant", "content": assistant_msg.content, "created_at": str(assistant_msg.created_at), "session_id": session.id}


@chat_router.delete("/sessions/{session_id}")
def delete_session(session_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    s = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user.id).first()
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.delete(s); db.commit()
    return {"message": "已删除"}


# ==================== TASKS ====================
@task_router.get("/today")
def get_today_tasks(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    pdict = None
    if profile:
        pdict = {"improvement_priority": profile.improvement_priority, "sleep_issues": profile.sleep_issues, "stress_level": profile.stress_level, "preferred_tasks": profile.preferred_tasks}
    # AI-generated tasks with sleep stats context
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=7)
    sleep_records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).all()
    sleep_stats = None
    if sleep_records:
        avg_dur = round(sum(r.duration_hours or 0 for r in sleep_records) / len(sleep_records), 1)
        avg_score = round(sum(r.score for r in sleep_records) / len(sleep_records))
        sleep_stats = {"avg_duration": avg_dur, "avg_score": avg_score, "total_records": len(sleep_records)}

    tasks = ai_generate_tasks(pdict, sleep_stats, user.nickname or user.username)
    streak_week = get_week_streak_days(db, user.id)
    return {"tasks": tasks, "ai_generated": True, "streak_week": streak_week}


@task_router.get("/badges")
def get_badges(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    unlocked = {u[0] for u in db.query(BadgeUnlock.badge_id).filter(BadgeUnlock.user_id == user.id).all()}
    return [{"badge_id": b["id"], "name": b["name"], "icon": b["icon"], "desc": b["desc"], "unlocked": b["id"] in unlocked} for b in ALL_BADGES]


@task_router.get("/points/summary", response_model=PointsResponse)
def get_points(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    pts = db.query(UserPoints).filter(UserPoints.user_id == user.id).first()
    return PointsResponse(total_points=pts.total_points if pts else 0)


@task_router.post("/complete")
def complete_task(data: TaskCompleteRequest, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    existing = db.query(TaskCompletion).filter(TaskCompletion.user_id == user.id, TaskCompletion.task_id == data.task_id, TaskCompletion.date_key == data.date_key).first()
    if existing:
        return {"message": "已完成", "already": True}
    db.add(TaskCompletion(user_id=user.id, task_id=data.task_id, date_key=data.date_key, points=5, completed_at=datetime.utcnow()))
    pts = db.query(UserPoints).filter(UserPoints.user_id == user.id).first()
    if not pts:
        db.add(UserPoints(user_id=user.id, total_points=5))
    else:
        pts.total_points += 5
    db.commit()
    pts = db.query(UserPoints).filter(UserPoints.user_id == user.id).first()
    return {"message": "任务完成", "points": pts.total_points if pts else 5}


@task_router.delete("/complete")
def uncomplete_task(data: TaskCompleteRequest, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    c = db.query(TaskCompletion).filter(TaskCompletion.user_id == user.id, TaskCompletion.task_id == data.task_id, TaskCompletion.date_key == data.date_key).first()
    if not c:
        return {"message": "未完成"}
    db.delete(c)
    pts = db.query(UserPoints).filter(UserPoints.user_id == user.id).first()
    if pts:
        pts.total_points = max(0, pts.total_points - 5)
    db.commit()
    return {"message": "已取消", "points": pts.total_points if pts else 0}


@task_router.post("/badges/unlock")
def unlock_badge(data: BadgeUnlockRequest, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    existing = db.query(BadgeUnlock).filter(BadgeUnlock.user_id == user.id, BadgeUnlock.badge_id == data.badge_id).first()
    if existing:
        return {"message": "已解锁", "already": True}
    db.add(BadgeUnlock(user_id=user.id, badge_id=data.badge_id))
    db.commit()
    return {"message": "徽章解锁成功"}


@task_router.get("/{date_key}")
def get_task_completions(date_key: str, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    completions = db.query(TaskCompletion).filter(TaskCompletion.user_id == user.id, TaskCompletion.date_key == date_key).all()
    return [{"task_id": c.task_id, "points": c.points} for c in completions]


# ==================== WELLNESS: Knowledge + Plans + Onboarding ====================
@wellness_router.get("/knowledge/categories")
def get_knowledge_categories():
    return {"categories": KNOWLEDGE_CATEGORIES}


@wellness_router.get("/knowledge/articles")
def get_knowledge_articles(category: str = None):
    articles = KNOWLEDGE_ARTICLES
    if category:
        articles = [a for a in articles if a["category"] == category]
    return {"articles": articles, "total": len(articles)}


@wellness_router.get("/knowledge/articles/{article_id}")
def get_knowledge_article(article_id: str):
    for a in KNOWLEDGE_ARTICLES:
        if a["id"] == article_id:
            return a
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="文章不存在")


@wellness_router.get("/plans")
def get_improvement_plans(target: str = None):
    plans = IMPROVEMENT_PLANS
    if target:
        plans = [p for p in plans if p["target"] == target]
    return {"plans": plans, "total": len(plans)}


# ===== Plan Enrollment & Tracking (named routes BEFORE parameterized) =====


@wellness_router.get("/plans/active")
def get_active_plan(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    enrollment = db.query(PlanEnrollment).filter(
        PlanEnrollment.user_id == user.id, PlanEnrollment.status == "active"
    ).first()
    if not enrollment:
        return {"active": False}

    plan = None
    for p in IMPROVEMENT_PLANS:
        if p["id"] == enrollment.plan_id:
            plan = p
            break

    total_tasks = sum(len(phase["tasks"]) for phase in plan["phases"]) if plan else 0
    completed_tasks = db.query(PlanCheckIn).filter(
        PlanCheckIn.enrollment_id == enrollment.id
    ).count()

    today = f"{datetime.now().year}-{datetime.now().month}-{datetime.now().day}"
    today_checks = db.query(PlanCheckIn).filter(
        PlanCheckIn.enrollment_id == enrollment.id,
        PlanCheckIn.date_key == today,
    ).all()
    checked_indices = {c.task_index for c in today_checks}

    days_in = (datetime.now().date() - enrollment.started_at.date()).days + 1 if enrollment.started_at else 1
    current_phase_idx = 0
    days_accumulated = 0
    for i, phase in enumerate(plan["phases"]) if plan else []:
        phase_days = 7
        if days_in <= days_accumulated + phase_days:
            current_phase_idx = i
            break
        days_accumulated += phase_days
    else:
        current_phase_idx = len(plan["phases"]) - 1 if plan else 0

    current_phase = plan["phases"][current_phase_idx] if plan else None
    today_tasks = []
    if current_phase:
        day_in_phase = days_in - days_accumulated - 1
        task_idx = day_in_phase % len(current_phase["tasks"])
        today_tasks = [{"index": task_idx, "task": current_phase["tasks"][task_idx], "checked": task_idx in checked_indices}]

    return {
        "active": True,
        "enrollment_id": enrollment.id, "plan": plan,
        "started_at": str(enrollment.started_at) if enrollment.started_at else None,
        "current_day": days_in, "current_phase": current_phase,
        "progress": {"completed": completed_tasks, "total": total_tasks,
                     "percent": round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0},
        "today_tasks": today_tasks,
    }


@wellness_router.get("/plans/checkins/{date_key}")
def get_checkins(date_key: str, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    enrollment = db.query(PlanEnrollment).filter(
        PlanEnrollment.user_id == user.id, PlanEnrollment.status.in_(["active", "completed"])
    ).first()
    if not enrollment:
        return {"checked_indices": []}
    checkins = db.query(PlanCheckIn).filter(
        PlanCheckIn.enrollment_id == enrollment.id, PlanCheckIn.date_key == date_key,
    ).all()
    return {"checked_indices": [c.task_index for c in checkins]}


@wellness_router.get("/plans/history")
def get_plan_history(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    enrollments = db.query(PlanEnrollment).filter(
        PlanEnrollment.user_id == user.id
    ).order_by(PlanEnrollment.started_at.desc()).all()
    result = []
    for e in enrollments:
        plan = None
        for p in IMPROVEMENT_PLANS:
            if p["id"] == e.plan_id: plan = p; break
        completed = db.query(PlanCheckIn).filter(PlanCheckIn.enrollment_id == e.id).count()
        total = sum(len(ph["tasks"]) for ph in plan["phases"]) if plan else 0
        result.append({
            "enrollment_id": e.id, "plan": plan, "status": e.status,
            "started_at": str(e.started_at) if e.started_at else None,
            "completed_at": str(e.completed_at) if e.completed_at else None,
            "progress": {"completed": completed, "total": total},
        })
    return {"history": result}


@wellness_router.post("/plans/checkin")
def checkin_task(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    date_key = data.get("date_key"); task_index = data.get("task_index")
    enrollment = db.query(PlanEnrollment).filter(
        PlanEnrollment.user_id == user.id, PlanEnrollment.status == "active"
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="没有激活的计划")
    existing = db.query(PlanCheckIn).filter(
        PlanCheckIn.enrollment_id == enrollment.id,
        PlanCheckIn.date_key == date_key, PlanCheckIn.task_index == task_index,
    ).first()
    if existing:
        return {"message": "已完成", "already": True}
    checkin = PlanCheckIn(enrollment_id=enrollment.id, user_id=user.id, date_key=date_key, task_index=task_index)
    db.add(checkin)
    pts = db.query(UserPoints).filter(UserPoints.user_id == user.id).first()
    if not pts: db.add(UserPoints(user_id=user.id, total_points=5))
    else: pts.total_points += 5
    plan = None
    for p in IMPROVEMENT_PLANS:
        if p["id"] == enrollment.plan_id: plan = p; break
    total_tasks = sum(len(phase["tasks"]) for phase in plan["phases"]) if plan else 999
    completed = db.query(PlanCheckIn).filter(PlanCheckIn.enrollment_id == enrollment.id).count() + 1
    completed_plan = False
    if completed >= total_tasks:
        enrollment.status = "completed"; enrollment.completed_at = datetime.utcnow(); completed_plan = True
        existing_badge = db.query(BadgeUnlock).filter(BadgeUnlock.user_id == user.id, BadgeUnlock.badge_id == "b9").first()
        if not existing_badge: db.add(BadgeUnlock(user_id=user.id, badge_id="b9"))
    db.commit()
    return {"message": "已完成" if not completed_plan else "计划完成！🎉", "points": pts.total_points if pts else 5, "plan_completed": completed_plan}


@wellness_router.post("/plans/{plan_id}/enroll")
def enroll_plan(plan_id: str, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    plan = None
    for p in IMPROVEMENT_PLANS:
        if p["id"] == plan_id: plan = p; break
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    active = db.query(PlanEnrollment).filter(
        PlanEnrollment.user_id == user.id, PlanEnrollment.status == "active"
    ).all()
    for a in active: a.status = "cancelled"
    enrollment = PlanEnrollment(user_id=user.id, plan_id=plan_id)
    db.add(enrollment); db.commit(); db.refresh(enrollment)
    return {"enrollment_id": enrollment.id, "plan": plan, "started_at": str(enrollment.started_at)}


# MUST be last — parameterized route catches all single-segment paths
@wellness_router.get("/plans/{plan_id}")
def get_improvement_plan(plan_id: str):
    for p in IMPROVEMENT_PLANS:
        if p["id"] == plan_id:
            return p
    raise HTTPException(status_code=404, detail="计划不存在")


@wellness_router.get("/onboarding")
def get_onboarding_steps(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    return {
        "steps": ONBOARDING_STEPS,
        "completed": profile is not None,
        "profile_exists": profile is not None,
    }


@wellness_router.post("/onboarding/complete")
def complete_onboarding(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Save onboarding data and create/update health profile."""
    user, db = user_and_db
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    if not profile:
        profile = HealthProfile(user_id=user.id)
        db.add(profile)

    # Map onboarding fields to HealthProfile
    if data.get("age"): profile.age = int(data["age"])
    if data.get("gender"): profile.gender = data["gender"]
    if data.get("sleep_goal_hours"): profile.sleep_goal_hours = float(data["sleep_goal_hours"])
    if data.get("bedtime_target"): profile.target_bedtime = data["bedtime_target"]
    if data.get("wakeup_target"): profile.target_wake_time = data["wakeup_target"]
    if data.get("sleep_issues"): profile.sleep_issues = data["sleep_issues"]
    if data.get("sleep_issue_duration"): profile.sleep_issue_duration = data["sleep_issue_duration"]
    if data.get("caffeine_intake"): profile.caffeine_intake = data["caffeine_intake"]
    if data.get("exercise_frequency"): profile.exercise_frequency = data["exercise_frequency"]
    if data.get("stress_level"): profile.stress_level = data["stress_level"]
    if data.get("improvement_priority"): profile.improvement_priority = data["improvement_priority"]
    if data.get("primary_goal"): profile.primary_goal = data["primary_goal"]

    db.commit()
    return {"message": "引导完成", "profile_created": True}


@wellness_router.post("/ai-soundscape")
def ai_soundscape(data: dict = None, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """AI designs a personalized white noise soundscape."""
    user, db = user_and_db
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    profile_dict = None
    if profile:
        profile_dict = {
            "sleep_issues": profile.sleep_issues,
            "stress_level": profile.stress_level,
            "preferred_sounds": profile.preferred_sounds,
            "sleep_goal_hours": profile.sleep_goal_hours,
        }

    cutoff = datetime.now() - timedelta(days=7)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).all()
    sleep_stats = None
    if records:
        sleep_stats = {"avg_score": round(sum(r.score for r in records) / len(records))}

    preference = data.get("preference", "") if data else ""
    return ai_design_soundscape(profile_dict, sleep_stats, preference)


# AI Deep Analysis
@sleep_router.get("/ai/deep-report")
def get_ai_deep_report(days: int = 30, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).order_by(SleepRecord.bedtime).all()
    if not records:
        return {"error": "暂无足够数据", "records_count": 0}

    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    profile_dict = None
    if profile:
        profile_dict = {"sleep_goal_hours": profile.sleep_goal_hours, "sleep_issues": profile.sleep_issues,
                         "stress_level": profile.stress_level, "caffeine_intake": profile.caffeine_intake,
                         "exercise_frequency": profile.exercise_frequency}

    avg_dur = round(sum(r.duration_hours or 0 for r in records) / len(records), 1)
    avg_score = round(sum(r.score for r in records) / len(records))
    cons_mins = calc_consistency_minutes(records)
    goal = profile.sleep_goal_hours if profile else 8.0
    efficiencies = [calc_sleep_efficiency(r.duration_hours or 0, r.bedtime, r.wake_time) for r in records]
    avg_eff = round(sum(efficiencies) / len(efficiencies), 1)

    stats = {"avg_duration": avg_dur, "avg_score": avg_score, "avg_efficiency": avg_eff,
             "consistency_minutes": round(cons_mins, 1), "streak_days": calc_streak(db, user.id),
             "sleep_debt": calc_sleep_debt(records, goal)}

    health = db.query(HealthData).filter(HealthData.user_id == user.id, HealthData.date_key >= cutoff.strftime("%Y-%m-%d")).all()
    health_data = [{"date_key": h.date_key, "steps": h.steps, "heart_rate_avg": h.heart_rate_avg} for h in health] if health else None

    return ai_deep_sleep_report(user.nickname or user.username, profile_dict, records, stats, health_data)


# AI Sentiment
@wellness_router.post("/ai/sentiment")
def analyze_sentiment(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    text = data.get("text", "")
    if not text:
        return {"error": "请提供文本"}
    return ai_sentiment_analysis(text)


# AI Sleep Prediction
@sleep_router.get("/ai/predict")
def predict_sleep(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=14)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).order_by(SleepRecord.bedtime).all()
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    profile_dict = {"sleep_goal_hours": profile.sleep_goal_hours} if profile else None
    return ai_predict_sleep_quality(records, profile_dict)


# RAG Knowledge Search
@wellness_router.get("/ai/rag-search")
def rag_search(q: str = ""):
    if not q:
        return {"results": []}
    articles = rag_retrieve_knowledge(q, top_k=5)
    return {"results": [{"id": a["id"], "title": a["title"], "category": a["category"], "summary": a["summary"]} for a in articles]}


@wellness_router.get("/recommend-plan")
def recommend_plan(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Recommend improvement plan based on user's health profile."""
    user, db = user_and_db
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    if not profile:
        return {"recommended": "plan_sleep_hygiene", "reason": "建议从基础睡眠卫生计划开始"}

    issues = (profile.sleep_issues or "").split(",")
    priority = (profile.improvement_priority or "").split(",")

    if "入睡困难" in str(issues) or "入睡速度" in str(priority):
        return {"recommended": "plan_insomnia", "reason": "基于你的入睡困难问题推荐"}
    if "早醒" in str(issues):
        return {"recommended": "plan_early_wake", "reason": "基于你的早醒问题推荐"}
    if "作息不规律" in str(issues) or "作息规律" in str(priority):
        return {"recommended": "plan_irregular", "reason": "基于你的作息规律需求推荐"}
    if "睡眠浅" in str(issues) or "睡眠深度" in str(priority):
        return {"recommended": "plan_shallow_sleep", "reason": "基于你的睡眠深度改善目标推荐"}
    if profile.stress_level in ("高", "极高"):
        return {"recommended": "plan_stress", "reason": "基于你的压力水平推荐"}
    return {"recommended": "plan_sleep_hygiene", "reason": "推荐从基础睡眠卫生开始"}


# ==================== ADMIN ====================
def _require_admin(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user, db


@admin_router.get("/stats")
def admin_stats(admin_data: Tuple[User, Session] = Depends(_require_admin)):
    user, db = admin_data
    from sqlalchemy import func as sa_func
    total_users = db.query(sa_func.count(User.id)).scalar()
    total_records = db.query(sa_func.count(SleepRecord.id)).scalar()
    total_chats = db.query(sa_func.count(ChatMessage.id)).scalar()
    total_tasks = db.query(sa_func.count(TaskCompletion.id)).scalar()
    today = datetime.now().date()
    today_records = db.query(sa_func.count(SleepRecord.id)).filter(SleepRecord.created_at >= today).scalar()
    today_new_users = db.query(sa_func.count(User.id)).filter(User.created_at >= today).scalar()

    # Top sleep scorers
    top_records = db.query(SleepRecord.user_id, sa_func.avg(SleepRecord.score).label("avg_score"), sa_func.count(SleepRecord.id).label("count")).group_by(SleepRecord.user_id).order_by(sa_func.avg(SleepRecord.score).desc()).limit(5).all()

    return {
        "total_users": total_users,
        "total_sleep_records": total_records,
        "total_chat_messages": total_chats,
        "total_task_completions": total_tasks,
        "today_records": today_records,
        "today_new_users": today_new_users,
        "top_users": [{"user_id": t[0], "avg_score": round(t[1], 1), "records": t[2]} for t in top_records],
    }


@admin_router.get("/users")
def admin_users(page: int = 1, page_size: int = 20, admin_data: Tuple[User, Session] = Depends(_require_admin)):
    user, db = admin_data
    total = db.query(User).count()
    users = db.query(User).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    result = []
    for u in users:
        record_count = db.query(SleepRecord).filter(SleepRecord.user_id == u.id).count()
        profile = db.query(HealthProfile).filter(HealthProfile.user_id == u.id).first()
        result.append({
            "id": u.id, "username": u.username, "email": u.email,
            "nickname": u.nickname, "is_admin": u.is_admin,
            "created_at": str(u.created_at) if u.created_at else None,
            "record_count": record_count,
            "has_profile": profile is not None,
        })
    return {"users": result, "total": total, "page": page, "page_size": page_size}


@admin_router.get("/users/{user_id}")
def admin_user_detail(user_id: int, admin_data: Tuple[User, Session] = Depends(_require_admin)):
    _, db = admin_data
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(status_code=404, detail="用户不存在")
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == u.id).first()
    records = db.query(SleepRecord).filter(SleepRecord.user_id == u.id).order_by(SleepRecord.bedtime.desc()).limit(10).all()
    active_plan = db.query(PlanEnrollment).filter(PlanEnrollment.user_id == u.id, PlanEnrollment.status == "active").first()
    return {
        "user": {"id": u.id, "username": u.username, "email": u.email, "nickname": u.nickname, "is_admin": u.is_admin, "created_at": str(u.created_at)},
        "profile": HealthProfileResponse.model_validate(profile) if profile else None,
        "recent_records": [_to_record_response(r) for r in records],
        "active_plan": str(active_plan.plan_id) if active_plan else None,
    }


@admin_router.put("/users/{user_id}/toggle-admin")
def admin_toggle_admin(user_id: int, admin_data: Tuple[User, Session] = Depends(_require_admin)):
    _, db = admin_data
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(status_code=404, detail="用户不存在")
    u.is_admin = 1 if not u.is_admin else 0
    db.commit()
    return {"user_id": u.id, "is_admin": u.is_admin}


# ===== Admin Visualization APIs =====
@admin_router.get("/viz/overview")
def admin_viz_overview(admin_data: Tuple[User, Session] = Depends(_require_admin)):
    """Comprehensive system overview for dashboard."""
    _, db = admin_data
    from sqlalchemy import func as sa_func
    now = datetime.now()

    total_users = db.query(sa_func.count(User.id)).scalar()
    today_users = db.query(sa_func.count(User.id)).filter(User.created_at >= now.date()).scalar()
    total_records = db.query(sa_func.count(SleepRecord.id)).scalar()
    today_records = db.query(sa_func.count(SleepRecord.id)).filter(SleepRecord.created_at >= now.date()).scalar()
    total_chats = db.query(sa_func.count(ChatMessage.id)).scalar()
    total_plans = db.query(sa_func.count(PlanEnrollment.id)).scalar()
    active_plans = db.query(sa_func.count(PlanEnrollment.id)).filter(PlanEnrollment.status == "active").scalar()
    premium_users = db.query(sa_func.count(Membership.id)).filter(Membership.tier.in_(["pro", "premium"])).scalar()
    total_posts = db.query(sa_func.count(SleepPost.id)).scalar()

    # Average sleep score across all users
    avg_score = db.query(sa_func.avg(SleepRecord.score)).scalar() or 0

    return {
        "users": {"total": total_users, "today": today_users, "premium": premium_users},
        "sleep": {"total_records": total_records, "today": today_records, "avg_score": round(avg_score, 1)},
        "engagement": {"total_chats": total_chats, "total_plans": total_plans, "active_plans": active_plans, "total_posts": total_posts},
    }


@admin_router.get("/viz/user-growth")
def admin_user_growth(days: int = 30, admin_data: Tuple[User, Session] = Depends(_require_admin)):
    """User registration trend over time."""
    _, db = admin_data
    from sqlalchemy import func as sa_func
    cutoff = datetime.now() - timedelta(days=days)
    rows = db.query(
        sa_func.date(User.created_at).label("date"),
        sa_func.count(User.id).label("count"),
    ).filter(User.created_at >= cutoff).group_by(sa_func.date(User.created_at)).order_by("date").all()

    # Also get cumulative
    data, cumulative, running = [], [], 0
    from datetime import date
    for d in range(days):
        day = (datetime.now().date() - timedelta(days=days - d - 1))
        count = next((r[1] for r in rows if r[0] == day), 0)
        running += count
        data.append({"date": str(day), "count": count})
        cumulative.append({"date": str(day), "count": running})

    return {"daily": data, "cumulative": cumulative, "days": days}


@admin_router.get("/viz/sleep-distribution")
def admin_sleep_distribution(days: int = 7, admin_data: Tuple[User, Session] = Depends(_require_admin)):
    """Sleep score distribution across all users."""
    _, db = admin_data
    from sqlalchemy import func as sa_func
    cutoff = datetime.now() - timedelta(days=days)
    rows = db.query(SleepRecord.score, sa_func.count(SleepRecord.id)).filter(
        SleepRecord.bedtime >= cutoff
    ).group_by(SleepRecord.score).order_by(SleepRecord.score).all()

    brackets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
    for score, count in rows:
        s = score or 0
        if s < 20: brackets["0-20"] += count
        elif s < 40: brackets["20-40"] += count
        elif s < 60: brackets["40-60"] += count
        elif s < 80: brackets["60-80"] += count
        else: brackets["80-100"] += count

    return {"distribution": [{"range": k, "count": v} for k, v in brackets.items()], "days": days}


@admin_router.get("/viz/activity-heatmap")
def admin_activity_heatmap(days: int = 90, admin_data: Tuple[User, Session] = Depends(_require_admin)):
    """Daily activity heatmap data."""
    _, db = admin_data
    from sqlalchemy import func as sa_func
    cutoff = datetime.now() - timedelta(days=days)

    records = db.query(sa_func.date(SleepRecord.created_at).label("date"), sa_func.count(SleepRecord.id).label("count")).filter(SleepRecord.created_at >= cutoff).group_by("date").all()
    chats = db.query(sa_func.date(ChatMessage.created_at).label("date"), sa_func.count(ChatMessage.id).label("count")).filter(ChatMessage.created_at >= cutoff).group_by("date").all()
    users = db.query(sa_func.date(User.created_at).label("date"), sa_func.count(User.id).label("count")).filter(User.created_at >= cutoff).group_by("date").all()

    rec_map = {str(r[0]): r[1] for r in records}
    chat_map = {str(c[0]): c[1] for c in chats}
    user_map = {str(u[0]): u[1] for u in users}

    heatmap = []
    for d in range(days):
        day = (datetime.now().date() - timedelta(days=days - d - 1))
        ds = str(day)
        heatmap.append({
            "date": ds,
            "records": rec_map.get(ds, 0),
            "chats": chat_map.get(ds, 0),
            "new_users": user_map.get(ds, 0),
            "level": min(4, (rec_map.get(ds, 0) + chat_map.get(ds, 0)) // 10),
        })
    return {"heatmap": heatmap, "days": days}


@admin_router.get("/viz/ai-stats")
def admin_ai_stats(days: int = 7, admin_data: Tuple[User, Session] = Depends(_require_admin)):
    """AI usage statistics."""
    _, db = admin_data
    from sqlalchemy import func as sa_func
    cutoff = datetime.now() - timedelta(days=days)

    total_ai = db.query(sa_func.count(ChatMessage.id)).filter(ChatMessage.created_at >= cutoff, ChatMessage.role == "assistant").scalar()
    daily_ai = db.query(sa_func.date(ChatMessage.created_at).label("date"), sa_func.count(ChatMessage.id).label("count")).filter(ChatMessage.created_at >= cutoff, ChatMessage.role == "assistant").group_by("date").order_by("date").all()

    # Unique users using AI
    ai_users = db.query(sa_func.count(sa_func.distinct(ChatMessage.session_id))).filter(ChatMessage.created_at >= cutoff, ChatMessage.role == "assistant").scalar()

    return {
        "total_ai_messages": total_ai,
        "unique_sessions": ai_users if ai_users else 0,
        "daily": [{"date": str(d[0]), "count": d[1]} for d in daily_ai],
        "days": days,
    }


@admin_router.get("/knowledge")
def admin_knowledge(admin_data: Tuple[User, Session] = Depends(_require_admin)):
    return {"articles": KNOWLEDGE_ARTICLES, "total": len(KNOWLEDGE_ARTICLES), "categories": KNOWLEDGE_CATEGORIES}


@admin_router.post("/knowledge")
def admin_add_article(data: dict, admin_data: Tuple[User, Session] = Depends(_require_admin)):
    new_id = f"k{len(KNOWLEDGE_ARTICLES) + 1}"
    article = {
        "id": new_id,
        "category": data.get("category", "睡眠科学"),
        "title": data.get("title", ""),
        "summary": data.get("summary", ""),
        "content": data.get("content", ""),
        "tags": data.get("tags", []),
    }
    KNOWLEDGE_ARTICLES.append(article)
    return {"article": article, "message": "文章已添加"}


@admin_router.delete("/knowledge/{article_id}")
def admin_delete_article(article_id: str, admin_data: Tuple[User, Session] = Depends(_require_admin)):
    global KNOWLEDGE_ARTICLES
    KNOWLEDGE_ARTICLES = [a for a in KNOWLEDGE_ARTICLES if a["id"] != article_id]
    return {"message": "文章已删除"}


# ==================== SECURITY ====================
from app.models import PasswordReset, LoginAttempt, NotificationSetting, AuditLog, HealthData
import hashlib, secrets


def _log_audit(db, user_id, action, detail="", ip=""):
    try:
        db.add(AuditLog(user_id=user_id, action=action, detail=detail, ip_address=ip))
        db.commit()
    except: pass


def _rate_limit_login(db, username, ip) -> bool:
    """Check if login should be blocked. Returns True if blocked.
    Checks failed attempts by username in the last 15 minutes."""
    cutoff = datetime.now() - timedelta(minutes=15)
    if ip:
        # Check by IP AND username for more precise rate limiting
        attempts_by_ip = db.query(LoginAttempt).filter(
            LoginAttempt.ip_address == ip,
            LoginAttempt.created_at >= cutoff,
            LoginAttempt.success == 0,
        ).count()
        if attempts_by_ip >= 10:
            return True
    attempts = db.query(LoginAttempt).filter(
        LoginAttempt.username == username,
        LoginAttempt.created_at >= cutoff,
        LoginAttempt.success == 0,
    ).count()
    return attempts >= 5  # Block after 5 failures in 15 min


@auth_router.post("/forgot-password")
def forgot_password(data: dict, db: Session = Depends(get_db)):
    """Send password reset email (returns token for dev mode)."""
    email = data.get("email", "")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"message": "如果该邮箱已注册，重置链接已发送"}
    token = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    reset = PasswordReset(user_id=user.id, token=token,
                          expires_at=datetime.utcnow() + timedelta(hours=1))
    db.add(reset); db.commit()
    # In production: send email. Dev mode: return token
    return {"message": "重置链接已发送", "reset_token": token}


@auth_router.post("/reset-password")
def reset_password(data: dict, db: Session = Depends(get_db)):
    """Reset password using token."""
    token = data.get("token", "")
    new_password = data.get("new_password", "")
    reset = db.query(PasswordReset).filter(
        PasswordReset.token == token,
        PasswordReset.used == 0,
        PasswordReset.expires_at > datetime.utcnow(),
    ).first()
    if not reset:
        raise HTTPException(status_code=400, detail="无效或过期的重置令牌")
    user = db.query(User).filter(User.id == reset.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")
    user.hashed_password = hash_pw(new_password)
    reset.used = 1
    db.commit()
    _log_audit(db, user.id, "password_reset", "Password reset via email")
    return {"message": "密码已重置，请使用新密码登录"}


# ==================== NOTIFICATIONS ====================
@auth_router.get("/notification-settings")
def get_notification_settings(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    s = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id).first()
    if not s:
        s = NotificationSetting(user_id=user.id)
        db.add(s); db.commit(); db.refresh(s)
    return {
        "sleep_reminder": s.sleep_reminder, "task_reminder": s.task_reminder,
        "plan_reminder": s.plan_reminder, "reminder_time": s.reminder_time,
        "push_enabled": s.push_enabled,
    }


@auth_router.put("/notification-settings")
def update_notification_settings(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    s = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id).first()
    if not s:
        s = NotificationSetting(user_id=user.id)
        db.add(s)
    for field in ["sleep_reminder", "task_reminder", "plan_reminder", "reminder_time", "push_enabled"]:
        if field in data:
            setattr(s, field, data[field])
    db.commit()
    return {"message": "通知设置已更新"}


@auth_router.get("/reminders/today")
def get_today_reminders(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Return list of reminders user should see today."""
    user, db = user_and_db
    s = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id).first()
    reminders = []
    if not s or s.sleep_reminder:
        last_record = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).order_by(SleepRecord.bedtime.desc()).first()
        today = datetime.now().date()
        if not last_record or (last_record.created_at and last_record.created_at.date() != today):
            reminders.append({"type": "sleep", "title": "记录今晚睡眠", "message": "别忘了记录你的睡眠情况哦", "time": s.reminder_time if s else "21:00"})
    if not s or s.task_reminder:
        today_key = f"{datetime.now().year}-{datetime.now().month}-{datetime.now().day}"
        comps = db.query(TaskCompletion).filter(TaskCompletion.user_id == user.id, TaskCompletion.date_key == today_key).count()
        if comps < 4:
            reminders.append({"type": "task", "title": "每日任务", "message": f"已完成 {comps}/4 个任务，继续加油！", "time": "20:00"})
    if not s or s.plan_reminder:
        active = db.query(PlanEnrollment).filter(PlanEnrollment.user_id == user.id, PlanEnrollment.status == "active").first()
        if active:
            reminders.append({"type": "plan", "title": "计划进度", "message": "你的改善计划等待打卡", "time": "19:00"})
    return {"reminders": reminders}


@auth_router.post("/wx/subscribe")
def wx_subscribe(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Store WeChat openid and subscribe to push notifications."""
    user, db = user_and_db
    openid = data.get("openid", "")
    if openid:
        user.openid = openid
    # Enable push notifications
    s = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id).first()
    if not s:
        s = NotificationSetting(user_id=user.id, push_enabled=1)
        db.add(s)
    else:
        s.push_enabled = 1
    db.commit()
    return {"message": "订阅成功"}


@auth_router.post("/wx/unsubscribe")
def wx_unsubscribe(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Disable push notifications."""
    user, db = user_and_db
    s = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id).first()
    if s:
        s.push_enabled = 0
        db.commit()
    return {"message": "已取消订阅"}


@community_router.get("/reply-notifications")
def get_reply_notifications(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get unread reply notifications for user's posts."""
    user, db = user_and_db
    # Find comments on user's posts where the commenter is not the user
    user_posts = db.query(SleepPost.id).filter(SleepPost.user_id == user.id).subquery()
    replies = db.query(PostComment).filter(
        PostComment.post_id.in_(user_posts),
        PostComment.user_id != user.id
    ).order_by(PostComment.created_at.desc()).limit(20).all()
    return {"notifications": [{
        "id": r.id,
        "post_id": r.post_id,
        "content": r.content[:50],
        "author": (db.query(User).filter(User.id == r.user_id).first().nickname or "用户") if r.user_id else "用户",
        "created_at": str(r.created_at) if r.created_at else None,
    } for r in replies]}


# ==================== FOLLOW SYSTEM ====================
@community_router.post("/follow/{user_id}")
def follow_user(user_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="不能关注自己")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    existing = db.query(UserFollow).filter(
        UserFollow.follower_id == user.id, UserFollow.followee_id == user_id
    ).first()
    if existing:
        return {"message": "已关注", "following": True}
    db.add(UserFollow(follower_id=user.id, followee_id=user_id))
    # Create notification
    db.add(Notification(user_id=user_id, type="follow", title="新粉丝",
                        body=f"{user.nickname or user.username} 关注了你", related_id=user.id))
    db.commit()
    return {"message": "关注成功", "following": True}


@community_router.delete("/follow/{user_id}")
def unfollow_user(user_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    db.query(UserFollow).filter(
        UserFollow.follower_id == user.id, UserFollow.followee_id == user_id
    ).delete()
    db.commit()
    return {"message": "已取消关注", "following": False}


@community_router.get("/follow/status/{user_id}")
def follow_status(user_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    following = db.query(UserFollow).filter(
        UserFollow.follower_id == user.id, UserFollow.followee_id == user_id
    ).first() is not None
    follower_count = db.query(UserFollow).filter(UserFollow.followee_id == user_id).count()
    following_count = db.query(UserFollow).filter(UserFollow.follower_id == user_id).count()
    return {"following": following, "follower_count": follower_count, "following_count": following_count}


@community_router.get("/following-feed")
def following_feed(page: int = 1, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Posts from users the current user follows."""
    user, db = user_and_db
    followee_ids = [f.followee_id for f in db.query(UserFollow).filter(
        UserFollow.follower_id == user.id).all()]
    if not followee_ids:
        return {"posts": [], "total": 0}
    q = db.query(SleepPost).filter(SleepPost.user_id.in_(followee_ids))
    total = q.count()
    posts = q.order_by(SleepPost.created_at.desc()).offset((page - 1) * 20).limit(20).all()
    result = []
    for p in posts:
        author = db.query(User).filter(User.id == p.user_id).first()
        liked = db.query(PostLike).filter(PostLike.post_id == p.id, PostLike.user_id == user.id).first() is not None
        result.append({
            "id": p.id, "content": p.content, "topic_id": p.topic_id,
            "image": p.image or "", "video_url": p.video_url or "",
            "author": "匿名" if p.is_anonymous else (author.nickname if author else "用户"),
            "sleep_score": p.sleep_score, "sleep_duration": p.sleep_duration,
            "like_count": p.like_count, "comment_count": p.comment_count,
            "is_liked": liked, "is_anonymous": p.is_anonymous,
            "created_at": str(p.created_at) if p.created_at else None,
        })
    return {"posts": result, "total": total, "page": page}


# ==================== SEARCH ====================
@community_router.get("/search")
def community_search(q: str = "", user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Search posts, topics, and users."""
    user, db = user_and_db
    if not q or len(q.strip()) < 1:
        return {"posts": [], "users": [], "topics": []}

    keyword = f"%{q.strip()}%"
    # Search posts
    posts = db.query(SleepPost).filter(SleepPost.content.like(keyword)).order_by(
        SleepPost.created_at.desc()).limit(10).all()
    post_results = []
    for p in posts:
        author = db.query(User).filter(User.id == p.user_id).first()
        post_results.append({
            "id": p.id, "content": p.content[:80],
            "author": "匿名" if p.is_anonymous else (author.nickname if author else "用户"),
            "like_count": p.like_count, "comment_count": p.comment_count,
            "created_at": str(p.created_at) if p.created_at else None,
        })

    # Search users
    users = db.query(User).filter(
        (User.nickname.like(keyword)) | (User.username.like(keyword))
    ).limit(10).all()
    user_results = [{"id": u.id, "nickname": u.nickname or u.username, "avatar": u.avatar} for u in users]

    # Search topics
    topic_results = [t for t in COMMUNITY_TOPICS if q.strip() in t["title"] or q.strip() in t["desc"]]

    return {"posts": post_results, "users": user_results, "topics": topic_results}


# ==================== USER PROFILE ====================
@community_router.get("/users/{user_id}")
def get_user_profile(user_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Public user profile page."""
    _, db = user_and_db
    profile_user = db.query(User).filter(User.id == user_id).first()
    if not profile_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # Stats
    post_count = db.query(SleepPost).filter(SleepPost.user_id == user_id).count()
    follower_count = db.query(UserFollow).filter(UserFollow.followee_id == user_id).count()
    following_count = db.query(UserFollow).filter(UserFollow.follower_id == user_id).count()
    total_likes = sum(p.like_count or 0 for p in db.query(SleepPost).filter(
        SleepPost.user_id == user_id).all())

    # Recent posts
    recent_posts = db.query(SleepPost).filter(SleepPost.user_id == user_id).order_by(
        SleepPost.created_at.desc()).limit(10).all()

    return {
        "user": {
            "id": profile_user.id, "nickname": profile_user.nickname or profile_user.username,
            "avatar": profile_user.avatar,
        },
        "stats": {
            "post_count": post_count, "follower_count": follower_count,
            "following_count": following_count, "total_likes": total_likes,
        },
        "recent_posts": [{
            "id": p.id, "content": p.content[:100], "topic_id": p.topic_id,
            "like_count": p.like_count, "comment_count": p.comment_count,
            "sleep_score": p.sleep_score,
            "created_at": str(p.created_at) if p.created_at else None,
        } for p in recent_posts],
    }


# ==================== NOTIFICATIONS ====================
@community_router.get("/notifications")
def get_notifications(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get all notifications for current user."""
    user, db = user_and_db
    notifs = db.query(Notification).filter(Notification.user_id == user.id).order_by(
        Notification.created_at.desc()).limit(50).all()
    unread = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == 0).count()
    return {
        "notifications": [{
            "id": n.id, "type": n.type, "title": n.title, "body": n.body,
            "related_id": n.related_id, "is_read": n.is_read,
            "created_at": str(n.created_at) if n.created_at else None,
        } for n in notifs],
        "unread_count": unread,
    }


@community_router.put("/notifications/read-all")
def mark_all_notifications_read(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read == 0).update(
        {"is_read": 1})
    db.commit()
    return {"message": "全部已读"}


@community_router.put("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    n = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == user.id).first()
    if n:
        n.is_read = 1
        db.commit()
    return {"message": "已读"}


# ==================== BOOKMARKS ====================
@community_router.post("/posts/{post_id}/bookmark")
def bookmark_post(post_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    existing = db.query(PostBookmark).filter(
        PostBookmark.user_id == user.id, PostBookmark.post_id == post_id).first()
    if existing:
        db.delete(existing); db.commit()
        return {"bookmarked": False, "message": "已取消收藏"}
    db.add(PostBookmark(user_id=user.id, post_id=post_id))
    db.commit()
    return {"bookmarked": True, "message": "已收藏"}


@community_router.get("/bookmarks")
def get_bookmarks(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    bms = db.query(PostBookmark).filter(PostBookmark.user_id == user.id).order_by(
        PostBookmark.created_at.desc()).limit(30).all()
    post_ids = [b.post_id for b in bms]
    if not post_ids:
        return {"bookmarks": []}
    posts = db.query(SleepPost).filter(SleepPost.id.in_(post_ids)).all()
    post_map = {}
    for p in posts:
        author = db.query(User).filter(User.id == p.user_id).first()
        post_map[p.id] = {
            "id": p.id, "content": p.content[:100],
            "author": "匿名" if p.is_anonymous else (author.nickname if author else "用户"),
            "like_count": p.like_count, "comment_count": p.comment_count,
            "created_at": str(p.created_at) if p.created_at else None,
        }
    return {"bookmarks": [post_map[b.post_id] for b in bms if b.post_id in post_map]}


# ==================== REPORTS ====================
@community_router.post("/posts/{post_id}/report")
def report_post(post_id: int, data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    reason = data.get("reason", "")
    existing = db.query(PostReport).filter(
        PostReport.user_id == user.id, PostReport.post_id == post_id).first()
    if existing:
        return {"message": "已举报"}
    db.add(PostReport(user_id=user.id, post_id=post_id, reason=reason))
    db.commit()
    return {"message": "举报已提交，我们会尽快处理"}


# ==================== GROUP DETAIL ====================
@community_router.get("/groups/{group_id}")
def get_group_detail(group_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Group detail with members and posts."""
    user, db = user_and_db
    group = db.query(CommunityGroup).filter(CommunityGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="小组不存在")
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id, GroupMember.user_id == user.id).first() is not None
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).limit(20).all()
    member_users = []
    for m in members:
        u = db.query(User).filter(User.id == m.user_id).first()
        if u:
            member_users.append({"id": u.id, "nickname": u.nickname or u.username})

    return {
        "group": {
            "id": group.id, "name": group.name, "icon": group.icon,
            "description": group.description, "member_count": group.member_count or 0,
            "is_member": is_member,
        },
        "members": member_users,
    }


# ==================== PRIVATE MESSAGES ====================
@community_router.get("/messages/conversations")
def get_conversations(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """List all conversations for current user."""
    user, db = user_and_db
    # Find distinct users I've messaged or received from
    sent = db.query(Message.receiver_id).filter(Message.sender_id == user.id).distinct().all()
    received = db.query(Message.sender_id).filter(Message.receiver_id == user.id).distinct().all()
    user_ids = set()
    for r in sent: user_ids.add(r[0])
    for r in received: user_ids.add(r[0])
    # Exclude blocked users
    blocked = set(r[0] for r in db.query(UserBlock.blocked_id).filter(UserBlock.blocker_id == user.id).all())
    blocker = set(r[0] for r in db.query(UserBlock.blocker_id).filter(UserBlock.blocked_id == user.id).all())
    user_ids -= blocked
    user_ids -= blocker

    conversations = []
    for uid in user_ids:
        u = db.query(User).filter(User.id == uid).first()
        if not u: continue
        last_msg = db.query(Message).filter(
            ((Message.sender_id == user.id) & (Message.receiver_id == uid)) |
            ((Message.sender_id == uid) & (Message.receiver_id == user.id))
        ).order_by(Message.created_at.desc()).first()
        unread = db.query(Message).filter(
            Message.sender_id == uid, Message.receiver_id == user.id, Message.is_read == 0
        ).count()
        conversations.append({
            "user_id": uid,
            "nickname": u.nickname or u.username,
            "last_message": last_msg.content[:50] if last_msg else "",
            "last_time": str(last_msg.created_at) if last_msg and last_msg.created_at else None,
            "unread": unread,
        })
    conversations.sort(key=lambda c: c["last_time"] or "", reverse=True)
    return {"conversations": conversations}


@community_router.get("/messages/{user_id}")
def get_messages(user_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get message history with a specific user."""
    user, db = user_and_db
    messages = db.query(Message).filter(
        ((Message.sender_id == user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == user.id))
    ).order_by(Message.created_at).limit(100).all()
    # Mark as read with timestamp
    now = datetime.now()
    for m in messages:
        if m.receiver_id == user.id and m.is_read == 0:
            m.is_read = 1
            m.read_at = now
    db.commit()
    partner = db.query(User).filter(User.id == user_id).first()
    return {
        "messages": [{
            "id": m.id, "content": m.content,
            "sender_id": m.sender_id, "receiver_id": m.receiver_id,
            "is_read": m.is_read, "read_at": str(m.read_at) if m.read_at else None,
            "voice_url": m.voice_url, "voice_duration": m.voice_duration,
            "image_url": m.image_url,
            "created_at": str(m.created_at) if m.created_at else None,
        } for m in messages],
        "partner": {
            "id": user_id,
            "nickname": partner.nickname if partner else "用户",
        } if partner else None,
    }


@community_router.post("/messages/{user_id}")
def send_message(user_id: int, data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Send a private message to a user."""
    user, db = user_and_db
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="不能给自己发消息")
    # Check block
    blocked = db.query(UserBlock).filter(
        (UserBlock.blocker_id == user_id) & (UserBlock.blocked_id == user.id)
    ).first()
    if blocked:
        raise HTTPException(status_code=403, detail="对方已将你屏蔽")
    content = _filter_sensitive(data.get("content", ""))
    image_url = data.get("image_url", "")
    voice_url = data.get("voice_url", "")
    voice_duration = data.get("voice_duration", 0)
    if not content.strip() and not image_url and not voice_url:
        raise HTTPException(status_code=400, detail="消息不能为空")
    msg = Message(sender_id=user.id, receiver_id=user_id, content=content or "",
                  image_url=image_url, voice_url=voice_url, voice_duration=voice_duration)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "message": "已发送"}


@community_router.get("/messages/unread-count")
def get_unread_message_count(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    count = db.query(Message).filter(
        Message.receiver_id == user.id, Message.is_read == 0
    ).count()
    return {"unread_count": count}


# ==================== USER BLOCK ====================
@community_router.post("/block/{user_id}")
def block_user(user_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    existing = db.query(UserBlock).filter(
        UserBlock.blocker_id == user.id, UserBlock.blocked_id == user_id
    ).first()
    if existing:
        return {"message": "已屏蔽"}
    db.add(UserBlock(blocker_id=user.id, blocked_id=user_id))
    db.commit()
    return {"message": "已屏蔽该用户"}


@community_router.delete("/block/{user_id}")
def unblock_user(user_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    db.query(UserBlock).filter(
        UserBlock.blocker_id == user.id, UserBlock.blocked_id == user_id
    ).delete()
    db.commit()
    return {"message": "已取消屏蔽"}


# ==================== POST DETAIL ====================
@community_router.get("/posts/{post_id}")
def get_post_detail(post_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get a single post with full detail."""
    user, db = user_and_db
    p = db.query(SleepPost).filter(SleepPost.id == post_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="帖子不存在")
    author = db.query(User).filter(User.id == p.user_id).first()
    liked = db.query(PostLike).filter(PostLike.post_id == post_id, PostLike.user_id == user.id).first() is not None
    bookmarked = db.query(PostBookmark).filter(PostBookmark.post_id == post_id, PostBookmark.user_id == user.id).first() is not None
    following = db.query(UserFollow).filter(
        UserFollow.follower_id == user.id, UserFollow.followee_id == p.user_id
    ).first() is not None
    return {
        "post": {
            "id": p.id, "content": p.content, "topic_id": p.topic_id,
            "image": p.image or "", "video_url": p.video_url or "",
            "author": "匿名" if p.is_anonymous else (author.nickname if author else "用户"),
            "author_id": p.user_id if not p.is_anonymous else 0,
            "sleep_score": p.sleep_score, "sleep_duration": p.sleep_duration,
            "like_count": p.like_count, "comment_count": p.comment_count,
            "is_liked": liked, "is_bookmarked": bookmarked,
            "is_following_author": following,
            "is_anonymous": p.is_anonymous,
            "created_at": str(p.created_at) if p.created_at else None,
        },
    }


# ==================== REPORT ADMIN ====================
@community_router.get("/admin/reports")
def get_reports(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Admin: list all pending reports."""
    user, db = user_and_db
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    reports = db.query(PostReport).filter(PostReport.status == "pending").order_by(
        PostReport.created_at.desc()).limit(50).all()
    return {"reports": [{
        "id": r.id, "post_id": r.post_id, "reason": r.reason,
        "reporter_id": r.user_id,
        "created_at": str(r.created_at) if r.created_at else None,
    } for r in reports]}


@community_router.put("/admin/reports/{report_id}/resolve")
def resolve_report(report_id: int, data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Admin: resolve or dismiss a report. data: {action: 'delete_post'|'dismiss'}"""
    user, db = user_and_db
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    report = db.query(PostReport).filter(PostReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="举报不存在")
    action = data.get("action", "dismiss")
    if action == "delete_post":
        post = db.query(SleepPost).filter(SleepPost.id == report.post_id).first()
        if post:
            db.query(PostComment).filter(PostComment.post_id == post.id).delete()
            db.query(PostLike).filter(PostLike.post_id == post.id).delete()
            db.delete(post)
        report.status = "resolved"
    else:
        report.status = "dismissed"
    db.commit()
    return {"message": f"已处理: {action}"}


# ==================== VIDEO UPLOAD ====================
@community_router.post("/upload-video")
def upload_video(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Upload a video (base64)."""
    user, db = user_and_db
    video_data = data.get("video", "")
    if not video_data:
        raise HTTPException(status_code=400, detail="请提供视频数据")
    import base64, os
    try:
        if "," in video_data:
            video_data = video_data.split(",")[1]
        video_bytes = base64.b64decode(video_data)
        upload_dir = "uploads/video"
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{user.id}_{int(time.time())}.mp4"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(video_bytes)
        url = f"/uploads/video/{filename}"
        return {"url": url, "message": "上传成功"}
    except Exception:
        raise HTTPException(status_code=400, detail="视频处理失败")


# ==================== VOICE UPLOAD ====================
@community_router.post("/upload-voice")
def upload_voice(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Upload a voice message (base64 audio)."""
    user, db = user_and_db
    voice_data = data.get("voice", "")
    duration = data.get("duration", 0)
    if not voice_data:
        raise HTTPException(status_code=400, detail="请提供语音数据")
    import base64, os
    try:
        if "," in voice_data:
            voice_data = voice_data.split(",")[1]
        audio_bytes = base64.b64decode(voice_data)
        upload_dir = "uploads/voice"
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{user.id}_{int(time.time())}.mp3"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(audio_bytes)
        url = f"/uploads/voice/{filename}"
        return {"url": url, "duration": duration, "message": "上传成功"}
    except Exception:
        raise HTTPException(status_code=400, detail="语音处理失败")


# ==================== GROUP POSTS ====================
@community_router.get("/groups/{group_id}/posts")
def get_group_posts(group_id: int, page: int = 1, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """List posts in a group."""
    user, db = user_and_db
    q = db.query(SleepPost).filter(SleepPost.group_id == group_id)
    total = q.count()
    posts = q.order_by(SleepPost.created_at.desc()).offset((page - 1) * 20).limit(20).all()
    result = []
    for p in posts:
        author = db.query(User).filter(User.id == p.user_id).first()
        liked = db.query(PostReaction).filter(PostReaction.post_id == p.id, PostReaction.user_id == user.id).first() is not None
        result.append({
            "id": p.id, "content": p.content, "topic_id": p.topic_id,
            "image": p.image or "", "video_url": p.video_url or "",
            "author": "匿名" if p.is_anonymous else (author.nickname if author else "用户"),
            "author_id": p.user_id if not p.is_anonymous else 0,
            "sleep_score": p.sleep_score,
            "like_count": p.like_count, "comment_count": p.comment_count,
            "is_liked": liked,
            "created_at": str(p.created_at) if p.created_at else None,
        })
    return {"posts": result, "total": total, "page": page}


# ==================== ADMIN ====================
@community_router.get("/admin/stats")
def get_admin_stats(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Admin dashboard stats overview."""
    user, db = user_and_db
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return {
        "total_users": db.query(User).count(),
        "total_posts": db.query(SleepPost).count(),
        "total_comments": db.query(PostComment).count(),
        "pending_reports": db.query(PostReport).filter(PostReport.status == "pending").count(),
        "total_reactions": db.query(PostReaction).count(),
        "total_messages": db.query(Message).count(),
    }


@community_router.get("/admin/recent-users")
def get_recent_users(limit: int = 10, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Admin: recent registered users."""
    user, db = user_and_db
    if not user.is_admin:
        raise HTTPException(status_code=403)
    users = db.query(User).order_by(User.created_at.desc()).limit(limit).all()
    return {"users": [{"id": u.id, "username": u.username, "nickname": u.nickname or u.username,
                        "created_at": str(u.created_at) if u.created_at else None} for u in users]}


# ==================== USER PROFILE ENHANCEMENTS ====================
@community_router.get("/users/{user_id}/badges")
def get_user_badges(user_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get badges for a user."""
    _, db = user_and_db
    unlocked = {u[0] for u in db.query(BadgeUnlock.badge_id).filter(BadgeUnlock.user_id == user_id).all()}
    return {"badges": [{
        "badge_id": b["id"], "name": b["name"], "icon": b["icon"], "desc": b["desc"],
        "unlocked": b["id"] in unlocked,
    } for b in ALL_BADGES]}


# ==================== KNOWLEDGE ENHANCEMENTS ====================
@wellness_router.get("/knowledge/related/{article_id}")
def get_related_articles(article_id: str):
    """Get related articles based on same category."""
    current = next((a for a in KNOWLEDGE_ARTICLES if a.get("id") == article_id), None)
    if not current:
        return {"articles": []}
    cat = current.get("category", "")
    related = [a for a in KNOWLEDGE_ARTICLES if a.get("id") != article_id and a.get("category") == cat]
    if len(related) < 3:
        related += [a for a in KNOWLEDGE_ARTICLES if a.get("id") != article_id and a.get("category") != cat][:3 - len(related)]
    return {"articles": related[:5], "category": cat}


@wellness_router.get("/knowledge/reading-history")
def get_reading_history(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get user's reading history from audit logs."""
    user, db = user_and_db
    logs = db.query(AuditLog).filter(
        AuditLog.user_id == user.id,
        AuditLog.action.like("read_article:%")
    ).order_by(AuditLog.created_at.desc()).limit(20).all()
    article_ids = []
    for log in logs:
        aid = log.action.split(":", 1)[-1] if ":" in log.action else ""
        if aid: article_ids.append(aid)
    articles = [a for a in KNOWLEDGE_ARTICLES if a.get("id") in article_ids]
    return {"articles": articles, "count": len(articles)}


@wellness_router.post("/knowledge/{article_id}/read")
def mark_article_read(article_id: str, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Mark an article as read."""
    user, db = user_and_db
    db.add(AuditLog(user_id=user.id, action=f"read_article:{article_id}"))
    db.commit()
    return {"message": "已记录"}


# ==================== CONTENT RECOMMENDATION ====================
@community_router.get("/recommended")
def get_recommended_posts(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Recommend posts based on user's interactions and sleep profile."""
    user, db = user_and_db
    # Find topics user engaged with (liked, commented, bookmarked)
    liked_post_ids = [r[0] for r in db.query(PostReaction.post_id).filter(
        PostReaction.user_id == user.id).distinct().all()]
    bookmarked_ids = [r[0] for r in db.query(PostBookmark.post_id).filter(
        PostBookmark.user_id == user.id).all()]
    engaged_ids = set(liked_post_ids + bookmarked_ids)

    # Get topics from engaged posts
    engaged_topics = set()
    if engaged_ids:
        engaged_posts = db.query(SleepPost).filter(SleepPost.id.in_(engaged_ids)).all()
        for p in engaged_posts:
            if p.topic_id:
                engaged_topics.add(p.topic_id)

    # Get user sleep issues for content targeting
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    user_issues = set()
    if profile and profile.sleep_issues:
        user_issues = set(i.strip() for i in profile.sleep_issues.replace("、", ",").split(",") if i.strip())

    # Score and rank posts
    all_posts = db.query(SleepPost).filter(SleepPost.user_id != user.id).order_by(
        SleepPost.created_at.desc()).limit(50).all()

    scored = []
    for p in all_posts:
        score = 0
        if p.topic_id and p.topic_id in engaged_topics:
            score += 3
        if p.like_count:
            score += min(p.like_count / 5, 5)
        if p.comment_count:
            score += min(p.comment_count / 2, 3)
        # Sleep score bonus
        if p.sleep_score and p.sleep_score >= 80:
            score += 2
        # Author quality
        author_posts = db.query(SleepPost).filter(SleepPost.user_id == p.user_id).count()
        if author_posts >= 5:
            score += 1
        scored.append((p, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_posts = scored[:15]

    user_id = user.id
    result = []
    for p, s in top_posts:
        author = db.query(User).filter(User.id == p.user_id).first()
        liked = db.query(PostReaction).filter(PostReaction.post_id == p.id, PostReaction.user_id == user_id).first() is not None
        result.append({
            "id": p.id, "content": p.content[:100], "topic_id": p.topic_id,
            "image": p.image or "", "video_url": p.video_url or "",
            "author": "匿名" if p.is_anonymous else (author.nickname if author else "用户"),
            "sleep_score": p.sleep_score,
            "like_count": p.like_count, "comment_count": p.comment_count,
            "is_liked": liked,
            "recommend_score": round(s, 1),
            "created_at": str(p.created_at) if p.created_at else None,
        })
    return {"posts": result, "based_on": {
        "engaged_topics": list(engaged_topics),
        "user_issues": list(user_issues),
    }}


# ==================== KNOWLEDGE SEARCH & BOOKMARK ====================
@wellness_router.get("/knowledge/search")
def search_knowledge(q: str = ""):
    """Search knowledge articles by title or content."""
    if not q or len(q.strip()) < 1:
        return {"articles": KNOWLEDGE_ARTICLES[:10]}
    keyword = q.strip()
    results = []
    for a in KNOWLEDGE_ARTICLES:
        if keyword in a.get("title", "") or keyword in a.get("summary", "") or keyword in a.get("category", ""):
            results.append(a)
    return {"articles": results[:20], "query": keyword, "total": len(results)}


@wellness_router.post("/knowledge/{article_id}/bookmark")
def bookmark_knowledge(article_id: str, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Toggle bookmark on a knowledge article."""
    user, db = user_and_db
    # Use a simple approach: store bookmarked article IDs in user settings
    settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
    bookmarks = (settings.knowledge_bookmarks or "").split(",") if settings.knowledge_bookmarks else []
    bookmarks = [b for b in bookmarks if b]
    if article_id in bookmarks:
        bookmarks.remove(article_id)
        settings.knowledge_bookmarks = ",".join(bookmarks)
        db.commit()
        return {"bookmarked": False, "message": "已取消收藏"}
    bookmarks.append(article_id)
    settings.knowledge_bookmarks = ",".join(bookmarks)
    db.commit()
    return {"bookmarked": True, "message": "已收藏"}


@wellness_router.get("/knowledge/bookmarks")
def get_knowledge_bookmarks(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get bookmarked knowledge articles."""
    user, db = user_and_db
    from app.models import UserSettings as _US
    settings = db.query(_US).filter(_US.user_id == user.id).first()
    if not settings or not settings.knowledge_bookmarks:
        return {"articles": []}
    bookmark_ids = [b for b in settings.knowledge_bookmarks.split(",") if b]
    articles = [a for a in KNOWLEDGE_ARTICLES if a.get("id") in bookmark_ids]
    return {"articles": articles}


# ==================== SHARE CARD ====================
@community_router.get("/posts/{post_id}/share-card")
def get_share_card_data(post_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Return data for generating a share card image."""
    _, db = user_and_db
    p = db.query(SleepPost).filter(SleepPost.id == post_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="帖子不存在")
    author = db.query(User).filter(User.id == p.user_id).first()
    return {
        "content": p.content[:80],
        "author": "匿名" if p.is_anonymous else (author.nickname if author else "用户"),
        "like_count": p.like_count,
        "comment_count": p.comment_count,
        "sleep_score": p.sleep_score,
        "share_text": f"「梦眠阁社区」{author.nickname if author else '用户'}的分享：{p.content[:60]}...",
    }


# ==================== SENSITIVE WORD FILTER ====================
SENSITIVE_WORDS = set()


def _filter_sensitive(text: str) -> str:
    """Simple sensitive word filter."""
    if not SENSITIVE_WORDS:
        return text
    result = text
    for w in SENSITIVE_WORDS:
        if w in result:
            result = result.replace(w, '*' * len(w))
    return result


# ==================== DATA VISUALIZATION ====================
@sleep_router.get("/viz/heatmap")
def get_sleep_heatmap(days: int = Query(default=90), user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Return sleep data formatted for calendar heatmap."""
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).all()
    heatmap = []
    for r in records:
        score = r.score or 0
        level = 0 if score == 0 else (1 if score < 40 else (2 if score < 60 else (3 if score < 80 else 4)))
        heatmap.append({
            "date": str(r.diary_date),
            "score": score,
            "duration": r.duration_hours,
            "level": level,  # 0-4 for color intensity
        })
    return {"heatmap": heatmap, "days": days}


@sleep_router.get("/viz/radar")
def get_sleep_radar(days: int = Query(default=30), user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Return radar chart data for sleep quality dimensions."""
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).all()
    if not records:
        return {"radar": {"duration": 0, "quality": 0, "consistency": 0, "efficiency": 0, "depth": 0}}

    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    goal = profile.sleep_goal_hours if profile else 8.0

    avg_dur = sum(r.duration_hours or 0 for r in records) / len(records)
    avg_quality = sum(r.quality or 3 for r in records) / len(records)
    cons_mins = calc_consistency_minutes(records)
    efficiency = sum(calc_sleep_efficiency(r.duration_hours or 0, r.bedtime, r.wake_time) for r in records) / len(records)

    # Depth: count "深睡" tag frequency
    depth_count = sum(1 for r in records if "深睡" in (json.loads(r.tags or "[]")))
    depth_score = min(100, depth_count / len(records) * 100)

    return {
        "radar": {
            "duration": min(100, round(avg_dur / goal * 100)),
            "quality": round(avg_quality / 5 * 100),
            "consistency": max(0, round(100 - cons_mins)),
            "efficiency": round(efficiency),
            "depth": round(depth_score),
        }
    }


@sleep_router.get("/viz/compare")
def get_sleep_compare(days: int = Query(default=30), user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Compare current period vs previous period."""
    user, db = user_and_db
    now = datetime.now()
    current_cutoff = now - timedelta(days=days)
    previous_cutoff = current_cutoff - timedelta(days=days)

    curr = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= current_cutoff).all()
    prev = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= previous_cutoff, SleepRecord.bedtime < current_cutoff).all()

    def summarize(recs):
        if not recs: return {"avg_duration": 0, "avg_score": 0, "count": 0}
        return {
            "avg_duration": round(sum(r.duration_hours or 0 for r in recs) / len(recs), 1),
            "avg_score": round(sum(r.score or 0 for r in recs) / len(recs)),
            "count": len(recs),
        }

    curr_sum = summarize(curr)
    prev_sum = summarize(prev)

    changes = {}
    for k in ["avg_duration", "avg_score", "count"]:
        c, p = curr_sum[k], prev_sum[k]
        if p == 0: changes[k] = "+100%" if c > 0 else "0%"
        else: changes[k] = f"{round((c-p)/p*100,1)}%"

    return {"current": curr_sum, "previous": prev_sum, "changes": changes}


# ==================== HEALTH DATA ====================
@wellness_router.post("/health-data")
def sync_health_data(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Sync external health data (steps, heart rate, etc.)."""
    user, db = user_and_db
    date_key = data.get("date_key", datetime.now().strftime("%Y-%m-%d"))
    existing = db.query(HealthData).filter(HealthData.user_id == user.id, HealthData.date_key == date_key).first()
    if existing:
        if "steps" in data: existing.steps = data["steps"]
        if "heart_rate_avg" in data: existing.heart_rate_avg = data["heart_rate_avg"]
        if "source" in data: existing.source = data["source"]
    else:
        db.add(HealthData(user_id=user.id, date_key=date_key,
                          steps=data.get("steps", 0),
                          heart_rate_avg=data.get("heart_rate_avg"),
                          source=data.get("source", "manual")))
    db.commit()
    return {"message": "健康数据已同步"}


@wellness_router.get("/health-data")
def get_health_data(days: int = 7, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    data = db.query(HealthData).filter(HealthData.user_id == user.id, HealthData.created_at >= cutoff).order_by(HealthData.date_key.desc()).all()
    return {"data": [{"date_key": d.date_key, "steps": d.steps, "heart_rate_avg": d.heart_rate_avg, "source": d.source} for d in data]}


@wellness_router.get("/sleep-with-health")
def get_sleep_with_health(days: int = 30, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Correlate sleep data with health data."""
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    sleep_records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).all()
    health_data = db.query(HealthData).filter(HealthData.user_id == user.id, HealthData.date_key >= cutoff.strftime("%Y-%m-%d")).all()
    health_map = {h.date_key: h for h in health_data}

    correlations = []
    for r in sleep_records:
        dk = str(r.diary_date)
        h = health_map.get(dk)
        correlations.append({
            "date": dk,
            "duration": r.duration_hours,
            "score": r.score,
            "steps": h.steps if h else 0,
            "heart_rate": h.heart_rate_avg if h else None,
        })

    # Simple correlation: avg score on high-step days vs low-step days
    if correlations:
        high_step = [c for c in correlations if c["steps"] > 5000]
        low_step = [c for c in correlations if c["steps"] <= 5000]
        avg_high = round(sum(c["score"] for c in high_step) / len(high_step)) if high_step else 0
        avg_low = round(sum(c["score"] for c in low_step) / len(low_step)) if low_step else 0
    else:
        avg_high, avg_low = 0, 0

    return {
        "correlations": correlations,
        "insight": {
            "high_step_avg_score": avg_high,
            "low_step_avg_score": avg_low,
            "message": f"日行5000步以上时平均睡眠评分 {avg_high} 分，不足时 {avg_low} 分" if avg_high and avg_low else "暂无足够数据进行相关性分析",
        },
    }


# ==================== COMMUNITY ====================
from app.models import CommunityGroup, GroupMember, SleepChallenge, ChallengeParticipant, SleepPost, PostComment, PostLike, PostReaction, UserFollow, Notification, PostBookmark, PostReport, PostEditHistory, Message, UserBlock


# ===== Community Hot Topics =====
COMMUNITY_TOPICS = [
    {"id": "t1", "title": "失眠互助", "icon": "🌙", "desc": "分享失眠改善经验，互相鼓励", "posts": 0},
    {"id": "t2", "title": "早睡打卡", "icon": "⏰", "desc": "每天22:30前睡觉，建立规律作息", "posts": 0},
    {"id": "t3", "title": "CBT-I实践", "icon": "🧠", "desc": "CBT-I认知行为疗法学习者交流", "posts": 0},
    {"id": "t4", "title": "饮食与睡眠", "icon": "🍽️", "desc": "分享促眠食谱和饮食习惯", "posts": 0},
    {"id": "t5", "title": "运动助眠", "icon": "🏃", "desc": "通过运动改善睡眠的伙伴们", "posts": 0},
    {"id": "t6", "title": "冥想放松", "icon": "🧘", "desc": "正念冥想、呼吸练习、睡前放松", "posts": 0},
    {"id": "t7", "title": "21天毕业分享", "icon": "🎓", "desc": "完成21天课程的经验分享", "posts": 0},
    {"id": "t8", "title": "睡眠产品评测", "icon": "🛏️", "desc": "床垫、枕头、眼罩等产品体验", "posts": 0},
]


@community_router.get("/topics")
def get_topics():
    """Get community hot topics with post counts."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        topics = []
        for t in COMMUNITY_TOPICS:
            tid = t.get("id", "")
            count = db.query(SleepPost).filter(SleepPost.topic_id == tid).count() if tid else 0
            topics.append({**t, "posts": count})
        return {"topics": topics}
    finally:
        db.close()


@community_router.get("/highlights")
def community_highlights():
    """Get weekly community highlights."""
    from app.database import SessionLocal
    from sqlalchemy import func
    db = SessionLocal()
    try:
        # Top 3 most liked posts this week
        week_ago = datetime.now() - timedelta(days=7)
        top_posts = db.query(SleepPost).filter(
            SleepPost.created_at >= week_ago
        ).order_by(SleepPost.like_count.desc()).limit(3).all()

        highlights = []
        for p in top_posts:
            author = db.query(User).filter(User.id == p.user_id).first()
            highlights.append({
                "id": p.id,
                "content": p.content[:100],
                "author": "匿名" if p.is_anonymous else (author.nickname if author else "用户"),
                "likes": p.like_count,
                "comments": p.comment_count,
                "sleep_score": p.sleep_score,
            })

        # Community stats
        total_posts = db.query(SleepPost).count()
        total_likes = db.query(SleepPost).with_entities(func.sum(SleepPost.like_count)).scalar() or 0
        active_users = db.query(PostComment.user_id).distinct().filter(
            PostComment.created_at >= week_ago
        ).count()

        return {
            "highlights": highlights,
            "stats": {
                "total_posts": total_posts,
                "total_likes": total_likes,
                "active_users_week": active_users,
            }
        }
    finally:
        db.close()


# Groups
@community_router.get("/groups")
def list_groups(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    _, db = user_and_db
    groups = db.query(CommunityGroup).order_by(CommunityGroup.member_count.desc()).all()
    if not groups:
        # Seed default groups
        defaults = [
            ("失眠互助组", "分享失眠改善经验，互相鼓励支持", "🌙"),
            ("早睡打卡群", "每天22:30前睡觉打卡，建立规律作息", "⏰"),
            ("运动助眠", "通过运动改善睡眠的伙伴们", "🏃"),
            ("冥想与放松", "正念冥想、呼吸练习、睡前放松技巧", "🧘"),
            ("新手村", "刚接触睡眠管理？从这里开始", "🌱"),
        ]
        for name, desc, icon in defaults:
            db.add(CommunityGroup(name=name, description=desc, icon=icon, member_count=0, created_by=user_and_db[0].id))
        db.commit()
        groups = db.query(CommunityGroup).order_by(CommunityGroup.member_count.desc()).all()

    user_id = user_and_db[0].id
    member_of = {m.group_id for m in db.query(GroupMember).filter(GroupMember.user_id == user_id).all()}
    return {"groups": [{"id": g.id, "name": g.name, "description": g.description, "icon": g.icon,
                         "member_count": g.member_count, "is_member": g.id in member_of} for g in groups]}


@community_router.post("/groups/{group_id}/join")
def join_group(group_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    existing = db.query(GroupMember).filter(GroupMember.group_id == group_id, GroupMember.user_id == user.id).first()
    if existing:
        return {"message": "已加入"}
    db.add(GroupMember(group_id=group_id, user_id=user.id))
    group = db.query(CommunityGroup).filter(CommunityGroup.id == group_id).first()
    if group:
        group.member_count = (group.member_count or 0) + 1
    db.commit()
    return {"message": "加入成功"}


@community_router.post("/groups/{group_id}/leave")
def leave_group(group_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    db.query(GroupMember).filter(GroupMember.group_id == group_id, GroupMember.user_id == user.id).delete()
    group = db.query(CommunityGroup).filter(CommunityGroup.id == group_id).first()
    if group and group.member_count > 0:
        group.member_count -= 1
    db.commit()
    return {"message": "已退出"}


# Challenges
@community_router.get("/challenges")
def list_challenges(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    _, db = user_and_db
    challenges = db.query(SleepChallenge).order_by(SleepChallenge.start_date.desc()).limit(10).all()
    if not challenges:
        from datetime import date
        today = date.today()
        defaults = [
            ("连续7天早睡挑战", "连续7天在22:30前入睡", "⏰", "early_bed", 7, today, today + timedelta(days=14)),
            ("睡眠评分冲刺", "7天内平均睡眠评分达到80分", "🏆", "score", 80, today, today + timedelta(days=14)),
            ("完美作息周", "连续7天作息规律度达标", "📅", "streak", 7, today, today + timedelta(days=14)),
        ]
        for title, desc, icon, ttype, target, start, end in defaults:
            db.add(SleepChallenge(title=title, description=desc, icon=icon, target_type=ttype,
                                   target_value=target, start_date=start, end_date=end))
        db.commit()
        challenges = db.query(SleepChallenge).order_by(SleepChallenge.start_date.desc()).limit(10).all()

    user_id = user_and_db[0].id
    participations = {p.challenge_id: p for p in db.query(ChallengeParticipant).filter(
        ChallengeParticipant.user_id == user_id).all()}
    return {"challenges": [{
        "id": c.id, "title": c.title, "description": c.description, "icon": c.icon,
        "target_type": c.target_type, "target_value": c.target_value,
        "start_date": str(c.start_date), "end_date": str(c.end_date),
        "participant_count": c.participant_count,
        "joined": c.id in participations,
        "progress": participations[c.id].progress if c.id in participations else 0,
    } for c in challenges]}


@community_router.post("/challenges/{challenge_id}/join")
def join_challenge(challenge_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    existing = db.query(ChallengeParticipant).filter(
        ChallengeParticipant.challenge_id == challenge_id, ChallengeParticipant.user_id == user.id).first()
    if existing:
        return {"message": "已加入"}
    db.add(ChallengeParticipant(challenge_id=challenge_id, user_id=user.id))
    challenge = db.query(SleepChallenge).filter(SleepChallenge.id == challenge_id).first()
    if challenge:
        challenge.participant_count = (challenge.participant_count or 0) + 1
    db.commit()
    return {"message": "加入成功"}


# Leaderboard
@community_router.get("/leaderboard")
def get_leaderboard(period: str = "weekly", user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Leaderboard by avg sleep score."""
    _, db = user_and_db
    days = 7 if period == "weekly" else 30
    cutoff = datetime.now() - timedelta(days=days)
    from sqlalchemy import func as sa_func

    rankings = db.query(
        SleepRecord.user_id,
        sa_func.avg(SleepRecord.score).label("avg_score"),
        sa_func.count(SleepRecord.id).label("record_count"),
    ).filter(SleepRecord.bedtime >= cutoff).group_by(SleepRecord.user_id).having(
        sa_func.count(SleepRecord.id) >= 3
    ).order_by(sa_func.avg(SleepRecord.score).desc()).limit(20).all()

    result = []
    for i, r in enumerate(rankings):
        user = db.query(User).filter(User.id == r[0]).first()
        result.append({
            "rank": i + 1,
            "user_id": r[0],
            "nickname": user.nickname if user else "匿名",
            "avg_score": round(r[1], 1),
            "record_count": r[2],
        })
    return {"leaderboard": result, "period": period}


# Posts (sleep diary sharing)
@community_router.get("/posts")
def list_posts(page: int = 1, topic_id: str = "", group_id: int = 0, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    _, db = user_and_db
    user_id = user_and_db[0].id
    q = db.query(SleepPost).filter(SleepPost.group_id == 0)
    if topic_id:
        q = q.filter(SleepPost.topic_id == topic_id)
    if group_id:
        q = db.query(SleepPost).filter(SleepPost.group_id == group_id)
    total = q.count()
    posts = q.order_by(SleepPost.created_at.desc()).offset((page - 1) * 20).limit(20).all()
    result = []
    for p in posts:
        author = db.query(User).filter(User.id == p.user_id).first()
        liked = db.query(PostLike).filter(PostLike.post_id == p.id, PostLike.user_id == user_id).first() is not None
        result.append({
            "id": p.id, "content": p.content, "topic_id": p.topic_id,
            "image": p.image or "", "video_url": p.video_url or "",
            "author": "匿名" if p.is_anonymous else (author.nickname if author else "用户"),
            "sleep_score": p.sleep_score, "sleep_duration": p.sleep_duration,
            "like_count": p.like_count, "comment_count": p.comment_count,
            "is_liked": liked, "is_anonymous": p.is_anonymous,
            "created_at": str(p.created_at) if p.created_at else None,
        })
    return {"posts": result, "total": total, "page": page}


@community_router.post("/posts")
def create_post(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    content = _filter_sensitive(data.get("content", ""))
    post = SleepPost(
        user_id=user.id, content=content,
        topic_id=data.get("topic_id", ""),
        image=data.get("image", ""),
        video_url=data.get("video_url", ""),
        group_id=data.get("group_id", 0),
        sleep_score=data.get("sleep_score"),
        sleep_duration=data.get("sleep_duration"),
        is_anonymous=data.get("is_anonymous", 0),
    )
    db.add(post); db.commit(); db.refresh(post)
    # Parse @mentions and send notifications
    import re
    mentions = re.findall(r'@(\S{1,20})', content)
    if mentions:
        mentioned_users = db.query(User).filter(User.nickname.in_(mentions)).all()
        for mu in mentioned_users:
            if mu.id != user.id:
                db.add(Notification(user_id=mu.id, type="mention", title="有人@了你",
                                    body=f"{user.nickname or user.username} 在帖子中提到了你",
                                    related_id=post.id))
        db.commit()
    return {"id": post.id, "message": "发布成功"}


@community_router.put("/posts/{post_id}")
def update_post(post_id: int, data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Edit a post (author only). Records edit history."""
    user, db = user_and_db
    post = db.query(SleepPost).filter(SleepPost.id == post_id, SleepPost.user_id == user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在或无权编辑")
    old_content = post.content
    if data.get("content"):
        post.content = _filter_sensitive(data["content"])
    if "is_anonymous" in data:
        post.is_anonymous = data["is_anonymous"]
    if data.get("video_url"):
        post.video_url = data["video_url"]
    # Record edit history if content changed
    if data.get("content") and old_content != post.content:
        db.add(PostEditHistory(post_id=post_id, old_content=old_content, new_content=post.content))
    db.commit()
    return {"message": "已更新"}


@community_router.get("/posts/{post_id}/edit-history")
def get_post_edit_history(post_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get edit history for a post."""
    _, db = user_and_db
    histories = db.query(PostEditHistory).filter(
        PostEditHistory.post_id == post_id
    ).order_by(PostEditHistory.edited_at.desc()).limit(10).all()
    return {"history": [{
        "id": h.id, "old_content": h.old_content[:100], "new_content": h.new_content[:100],
        "edited_at": str(h.edited_at) if h.edited_at else None,
    } for h in histories]}


@community_router.delete("/posts/{post_id}")
def delete_post(post_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Delete a post (author only)."""
    user, db = user_and_db
    post = db.query(SleepPost).filter(SleepPost.id == post_id, SleepPost.user_id == user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在或无权删除")
    db.query(PostComment).filter(PostComment.post_id == post_id).delete()
    db.query(PostLike).filter(PostLike.post_id == post_id).delete()
    db.delete(post)
    db.commit()
    return {"message": "已删除"}


@community_router.post("/upload")
def community_upload(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Upload an image for community posts (base64). Returns URL stub."""
    user, db = user_and_db
    image_data = data.get("image", "")
    if not image_data:
        raise HTTPException(status_code=400, detail="请提供图片数据")
    import base64, os
    try:
        # Strip data URI prefix if present
        if "," in image_data:
            image_data = image_data.split(",")[1]
        img_bytes = base64.b64decode(image_data)
        upload_dir = "uploads/community"
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{user.id}_{int(time.time())}.jpg"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(img_bytes)
        url = f"/uploads/community/{filename}"
        return {"url": url, "message": "上传成功"}
    except Exception:
        raise HTTPException(status_code=400, detail="图片处理失败")


REACTION_EMOJIS = {"like":"👍","love":"❤️","laugh":"😄","sad":"😢","angry":"😡","sleep":"😴","fire":"🔥"}

@community_router.post("/posts/{post_id}/react")
def react_post(post_id: int, data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Add/remove/change a reaction on a post. Send {reaction: 'like'|'love'|...} or {} to remove."""
    user, db = user_and_db
    reaction_type = data.get("reaction", "")
    existing = db.query(PostReaction).filter(
        PostReaction.post_id == post_id, PostReaction.user_id == user.id).first()
    if not reaction_type:
        # Remove reaction
        if existing:
            db.delete(existing)
            post = db.query(SleepPost).filter(SleepPost.id == post_id).first()
            if post and post.like_count > 0: post.like_count -= 1
            db.commit()
        return {"reacted": False, "reaction": None}
    if existing:
        existing.reaction_type = reaction_type
    else:
        db.add(PostReaction(post_id=post_id, user_id=user.id, reaction_type=reaction_type))
        post = db.query(SleepPost).filter(SleepPost.id == post_id).first()
        if post: post.like_count = (post.like_count or 0) + 1
    # Notify if new reaction
    post = db.query(SleepPost).filter(SleepPost.id == post_id).first()
    if post and post.user_id != user.id and not existing:
        emoji = REACTION_EMOJIS.get(reaction_type, "👍")
        db.add(Notification(user_id=post.user_id, type="like", title="新回应",
                            body=f"{user.nickname or user.username} {emoji} 了你的帖子",
                            related_id=post_id))
    db.commit()
    return {"reacted": True, "reaction": reaction_type}


@community_router.get("/posts/{post_id}/reactions")
def get_post_reactions(post_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get reaction summary for a post."""
    user, db = user_and_db
    reactions = db.query(PostReaction).filter(PostReaction.post_id == post_id).all()
    summary = {}
    for r_type in REACTION_EMOJIS:
        summary[r_type] = 0
    user_reaction = None
    for r in reactions:
        summary[r.reaction_type] = summary.get(r.reaction_type, 0) + 1
        if r.user_id == user.id:
            user_reaction = r.reaction_type
    return {"reactions": summary, "user_reaction": user_reaction, "total": len(reactions)}


# Legacy like endpoint (backward compat)
@community_router.post("/posts/{post_id}/like")
def like_post(post_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Legacy like — now uses reactions."""
    user, db = user_and_db
    existing = db.query(PostReaction).filter(
        PostReaction.post_id == post_id, PostReaction.user_id == user.id).first()
    if existing:
        db.delete(existing)
        post = db.query(SleepPost).filter(SleepPost.id == post_id).first()
        if post and post.like_count > 0: post.like_count -= 1
        db.commit()
        return {"liked": False}
    db.add(PostReaction(post_id=post_id, user_id=user.id, reaction_type="like"))
    post = db.query(SleepPost).filter(SleepPost.id == post_id).first()
    if post: post.like_count = (post.like_count or 0) + 1
    if post and post.user_id != user.id:
        db.add(Notification(user_id=post.user_id, type="like", title="新点赞",
                            body=f"{user.nickname or user.username} 赞了你的帖子", related_id=post_id))
    db.commit()
    return {"liked": True}


@community_router.post("/posts/{post_id}/comment")
def comment_post(post_id: int, data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    content = _filter_sensitive(data.get("content", ""))
    parent_id = data.get("parent_id", 0)
    reply_to_user_id = data.get("reply_to_user_id", 0)
    comment = PostComment(post_id=post_id, user_id=user.id, content=content,
                          parent_id=parent_id, reply_to_user_id=reply_to_user_id)
    db.add(comment)
    post = db.query(SleepPost).filter(SleepPost.id == post_id).first()
    if post: post.comment_count = (post.comment_count or 0) + 1
    # Notify post author
    if post and post.user_id != user.id:
        db.add(Notification(user_id=post.user_id, type="comment", title="新评论",
                            body=f"{user.nickname or user.username} 评论了你的帖子",
                            related_id=post_id))
    # Notify parent comment author
    if reply_to_user_id and reply_to_user_id != user.id:
        db.add(Notification(user_id=reply_to_user_id, type="comment", title="新回复",
                            body=f"{user.nickname or user.username} 回复了你的评论",
                            related_id=post_id))
    db.commit(); db.refresh(comment)
    return {"id": comment.id, "message": "评论成功"}


@community_router.get("/posts/{post_id}/comments")
def get_comments(post_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get comments with nested replies."""
    _, db = user_and_db
    comments = db.query(PostComment).filter(
        PostComment.post_id == post_id, PostComment.parent_id == 0
    ).order_by(PostComment.created_at).all()
    result = []
    for c in comments:
        author = db.query(User).filter(User.id == c.user_id).first()
        replies = db.query(PostComment).filter(
            PostComment.parent_id == c.id
        ).order_by(PostComment.created_at).all()
        reply_list = []
        for r in replies:
            ra = db.query(User).filter(User.id == r.user_id).first()
            reply_list.append({
                "id": r.id, "content": r.content,
                "author": ra.nickname if ra else "用户",
                "created_at": str(r.created_at) if r.created_at else None,
            })
        result.append({
            "id": c.id, "content": c.content,
            "author": author.nickname if author else "用户",
            "like_count": c.like_count or 0,
            "created_at": str(c.created_at) if c.created_at else None,
            "replies": reply_list,
        })
    return {"comments": result}


@community_router.post("/comments/{comment_id}/like")
def like_comment(comment_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Like a comment."""
    _, db = user_and_db
    comment = db.query(PostComment).filter(PostComment.id == comment_id).first()
    if comment:
        comment.like_count = (comment.like_count or 0) + 1
        db.commit()
    return {"message": "已点赞"}


# ==================== VOICE & MULTIMEDIA ====================
@voice_router.post("/diary")
def voice_to_diary(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Convert voice transcript to sleep diary entry."""
    user, db = user_and_db
    transcript = data.get("transcript", "")
    if not transcript:
        return {"error": "请提供语音转文字内容"}

    # AI parses the transcript into structured diary data
    prompt = f"""分析以下语音日记内容，提取睡眠相关信息。

内容：{transcript}

返回JSON格式：
{{"diary_date":"YYYY-MM-DD","bedtime":"HH:MM","wake_time":"HH:MM","quality":1-5,"tags":["标签"],"notes":"备注","summary":"一句话总结"}}
如果无法提取时间，使用当前日期和估计时间。"""

    result = _ai_chat("你是睡眠数据提取AI。只返回JSON。", prompt, temperature=0.3, max_tokens=300)
    try:
        parsed = json.loads(result)
        return {"parsed": parsed, "transcript": transcript}
    except:
        return {"transcript": transcript, "raw": True, "message": "已保存语音记录"}


@voice_router.get("/tts")
def text_to_speech(text: str = "", voice: str = "gentle"):
    """Simulate TTS — returns the text and voice settings (production: integrate with TTS API)."""
    voices = {"gentle": "温柔女声", "calm": "平静男声", "whisper": "耳语模式"}
    return {
        "text": text,
        "voice": voice,
        "voice_name": voices.get(voice, "温柔女声"),
        "format": "mp3",
        "note": "生产环境接入阿里云/讯飞TTS服务",
    }


# Sleep Stories
@voice_router.get("/stories")
def list_sleep_stories(category: str = None, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """List sleep stories / guided meditations."""
    from app.models import SleepStory
    _, db = user_and_db
    q = db.query(SleepStory)
    if category:
        q = q.filter(SleepStory.category == category)
    stories = q.order_by(SleepStory.play_count.desc()).all()

    if not stories:
        # Seed default stories
        defaults = [
            ("雨夜森林漫步", "跟随雨声走进静谧的森林，释放一天的疲惫", "冥想", 15, "AI"),
            ("星空下的呼吸", "躺在草地上数星星，配合4-7-8呼吸法入眠", "呼吸", 10, "AI"),
            ("海浪轻语", "聆听海浪拍岸的声音，渐进式肌肉放松引导", "放松", 20, "AI"),
            ("月光花园", "想象自己漫步在银色的月光花园中，正念冥想", "冥想", 12, "AI", 1),
            ("深度睡眠引导", "专业的深度睡眠催眠引导，帮助你快速进入深睡", "催眠", 25, "AI", 1),
        ]
        for title, desc, cat, dur, narrator, *rest in defaults:
            premium = rest[0] if rest else 0
            db.add(SleepStory(title=title, description=desc, category=cat, duration_minutes=dur, narrator=narrator, is_premium=premium))
        db.commit()
        stories = db.query(SleepStory).order_by(SleepStory.play_count.desc()).all()

    from app.models import Membership
    user_tier = db.query(Membership).filter(Membership.user_id == user_and_db[0].id).first()
    tier = user_tier.tier if user_tier else "free"

    return {"stories": [{
        "id": s.id, "title": s.title, "description": s.description,
        "category": s.category, "duration_minutes": s.duration_minutes,
        "narrator": s.narrator, "is_premium": s.is_premium,
        "play_count": s.play_count,
        "accessible": tier != "free" or not s.is_premium,
    } for s in stories]}


@voice_router.post("/stories/{story_id}/play")
def play_story(story_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    from app.models import SleepStory
    _, db = user_and_db
    story = db.query(SleepStory).filter(SleepStory.id == story_id).first()
    if story:
        story.play_count = (story.play_count or 0) + 1
        db.commit()
    return {"message": "playing", "story_id": story_id}


# ==================== PREMIUM / MONETIZATION ====================
from app.models import Membership, MembershipLog

MEMBERSHIP_TIERS = {
    "free": {"name": "免费版", "price": 0, "features": ["基础睡眠记录", "AI助手(每日5次)", "白噪音基础", "每日任务"]},
    "pro": {"name": "专业版", "price": 29, "features": ["无限AI对话", "高级白噪音引擎", "深度睡眠报告", "睡眠预测", "优先支持", "所有改善计划"]},
    "premium": {"name": "尊享版", "price": 59, "features": ["全部Pro功能", "AI深度分析报告", "个性化睡眠教练", "语音日记", "高级睡眠故事", "健康数据同步", "家庭共享(5人)"]},
}


def _get_user_tier(db: Session, user_id: int) -> str:
    m = db.query(Membership).filter(Membership.user_id == user_id).first()
    if not m:
        return "free"
    if m.expires_at and m.expires_at < datetime.now():
        _log_membership_change(user_id, m.tier, "free", None, "expire")
        m.tier = "free"
        m.order_id = None
        db.commit()
        return "free"
    return m.tier


def _log_membership_change(user_id: int, from_tier: str, to_tier: str, order_id: int = None, change_type: str = "upgrade", amount: int = 0):
    """Log membership change in a separate session to avoid polluting parent transaction."""
    from app.database import SessionLocal
    _db = SessionLocal()
    try:
        _db.add(MembershipLog(user_id=user_id, from_tier=from_tier, to_tier=to_tier, order_id=order_id, change_type=change_type, amount=amount))
        _db.commit()
    except Exception:
        _db.rollback()
    finally:
        _db.close()


@premium_router.get("/tiers")
def get_membership_tiers():
    return {"tiers": MEMBERSHIP_TIERS}


@premium_router.get("/status")
def get_premium_status(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    tier = _get_user_tier(db, user.id)
    m = db.query(Membership).filter(Membership.user_id == user.id).first()
    return {
        "tier": tier,
        "tier_info": MEMBERSHIP_TIERS.get(tier, MEMBERSHIP_TIERS["free"]),
        "expires_at": str(m.expires_at) if m and m.expires_at else None,
        "is_premium": tier in ("pro", "premium"),
    }


@premium_router.get("/history")
def get_membership_history(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get membership change history."""
    user, db = user_and_db
    logs = db.query(MembershipLog).filter(
        MembershipLog.user_id == user.id
    ).order_by(MembershipLog.created_at.desc()).limit(20).all()
    return {"history": [{
        "from": l.from_tier, "to": l.to_tier, "type": l.change_type,
        "amount_yuan": round(l.amount / 100, 2) if l.amount else 0,
        "created_at": str(l.created_at) if l.created_at else None,
    } for l in logs]}


@premium_router.post("/upgrade")
def upgrade_membership(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Upgrade membership — requires a PAID payment order_id for security.
    The complete flow is: create_order → pay_order → upgrade (with order_id)."""
    user, db = user_and_db
    order_id = data.get("order_id")
    tier = data.get("tier", "pro")

    if not order_id:
        raise HTTPException(status_code=400, detail="请先完成支付，提供 order_id")
    if tier not in MEMBERSHIP_TIERS or tier == "free":
        raise HTTPException(status_code=400, detail="无效的会员等级")

    # Verify the order exists, belongs to user, and is paid
    from app.models import PaymentOrder
    order = db.query(PaymentOrder).filter(
        PaymentOrder.id == order_id,
        PaymentOrder.user_id == user.id,
        PaymentOrder.status == "paid",
    ).first()
    if not order:
        raise HTTPException(status_code=400, detail="订单无效、不属于你或未支付")
    if order.tier != tier:
        raise HTTPException(status_code=400, detail="订单套餐与升级目标不匹配")

    current_tier = _get_user_tier(db, user.id)
    m = db.query(Membership).filter(Membership.user_id == user.id).first()
    days = 30  # default
    from app.models import PaymentOrder as PO
    for pid, pinfo in PAYMENT_PLANS.items():
        if pinfo["tier"] == tier and pinfo["amount"] == order.amount:
            days = pinfo["days"]
            break

    if not m:
        m = Membership(user_id=user.id, tier=tier, started_at=datetime.utcnow(),
                       expires_at=datetime.utcnow() + timedelta(days=days), order_id=order.id)
        db.add(m)
    else:
        if m.expires_at and m.expires_at > datetime.utcnow():
            m.expires_at = m.expires_at + timedelta(days=days)  # Extend from current expiry
        else:
            m.expires_at = datetime.utcnow() + timedelta(days=days)
        m.tier = tier
        m.started_at = datetime.utcnow()
        m.order_id = order.id

    _log_membership_change( user.id, current_tier, tier, order.id, "upgrade", order.amount)
    db.commit()

    _log_audit(db, user.id, "membership_upgrade", f"Upgraded from {current_tier} to {tier}, order={order.order_no}")
    return {
        "message": f"已升级到{MEMBERSHIP_TIERS[tier]['name']}",
        "tier": tier,
        "expires_at": str(m.expires_at),
        "order_no": order.order_no,
    }


@premium_router.post("/cancel")
def cancel_membership(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    m = db.query(Membership).filter(Membership.user_id == user.id).first()
    if m and m.auto_renew:
        m.auto_renew = 0
        _log_membership_change( user.id, m.tier, m.tier, None, "cancel")
        db.commit()
    return {"message": "已取消自动续费"}


# Premium feature gate middleware
def require_premium(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    tier = _get_user_tier(db, user.id)
    if tier not in ("pro", "premium"):
        raise HTTPException(status_code=403, detail="此功能需要专业版或尊享版会员")
    return user, db


@premium_router.get("/deep-report")
def premium_deep_report(days: int = 30, premium_user: Tuple[User, Session] = Depends(require_premium)):
    """Premium-only deep sleep analysis."""
    user, db = premium_user
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).order_by(SleepRecord.bedtime).all()
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()

    avg_dur = round(sum(r.duration_hours or 0 for r in records) / len(records), 1) if records else 0
    avg_score = round(sum(r.score for r in records) / len(records)) if records else 0

    profile_dict = {"sleep_goal_hours": profile.sleep_goal_hours} if profile else None
    stats = {"avg_duration": avg_dur, "avg_score": avg_score, "avg_efficiency": 0,
             "consistency_minutes": 0, "streak_days": calc_streak(db, user.id)}
    if records:
        effs = [calc_sleep_efficiency(r.duration_hours or 0, r.bedtime, r.wake_time) for r in records]
        stats["avg_efficiency"] = round(sum(effs)/len(effs), 1)
        stats["consistency_minutes"] = round(calc_consistency_minutes(records), 1)

    return ai_deep_sleep_report(user.nickname or user.username, profile_dict, records, stats)


# ==================== PLATFORM INTEGRATION ====================
PLATFORM_CONFIG = {
    "miniprogram": {
        "app_id": "wx551623c01821827f",
        "name": "微信小程序",
        "auth_type": "jwt",
        "api_version": "v1",
        "features": ["auth", "sleep", "chat", "tasks", "noise", "community", "knowledge", "premium"],
    },
    "h5": {
        "name": "H5 Web",
        "auth_type": "jwt",
        "api_version": "v1",
        "pwa_enabled": True,
        "features": ["auth", "sleep", "chat", "tasks", "noise", "community", "knowledge", "premium", "admin", "voice", "health"],
    },
    "flutter": {
        "name": "Flutter App",
        "auth_type": "jwt",
        "api_version": "v1",
        "store_url": {"ios": "", "android": ""},
        "features": ["auth", "sleep", "chat", "tasks", "noise", "community", "knowledge", "premium"],
    },
    "webhook": {
        "supported_events": ["sleep.created", "task.completed", "plan.enrolled", "plan.completed", "badge.unlocked", "chat.message", "user.registered"],
        "signature_header": "X-Mengmian-Signature",
        "retry_count": 3,
    },
}

API_VERSION = {
    "version": "1.0.0",
    "api_version": "v1",
    "total_endpoints": 91,
    "deprecated": [],
    "changelog": [
        {"version": "1.0.0", "date": "2026-05-17", "changes": ["Initial release", "Auth system", "Sleep tracking", "AI chat", "White noise", "Community", "Premium"]},
    ],
}


@platform_router.get("/info")
def platform_info():
    """Public platform info — no auth required."""
    return {
        "app_name": "梦眠阁 - AI智能睡眠管理",
        "api_version": API_VERSION,
        "platforms": PLATFORM_CONFIG,
        "openapi_docs": "/docs",
        "health_check": "/health",
    }


@platform_router.get("/config/{platform}")
def get_platform_config(platform: str):
    """Get configuration for a specific platform."""
    if platform not in PLATFORM_CONFIG:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")
    return {
        "platform": platform,
        "config": PLATFORM_CONFIG[platform],
        "api_base": "/api/v1",
        "auth": {"method": "Bearer JWT", "login_path": "/api/v1/auth/login", "register_path": "/api/v1/auth/register", "refresh_path": "/api/v1/auth/refresh"},
    }


@platform_router.post("/webhooks/register")
def register_webhook(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Register a webhook URL for event notifications."""
    user, db = user_and_db
    url = data.get("url")
    events = data.get("events", [])
    if not url:
        raise HTTPException(status_code=400, detail="webhook URL is required")

    valid_events = PLATFORM_CONFIG["webhook"]["supported_events"]
    for e in events:
        if e not in valid_events:
            raise HTTPException(status_code=400, detail=f"Unsupported event: {e}")

    # In production: store webhook config in DB
    return {"message": "Webhook registered", "url": url, "events": events, "user_id": user.id}


@platform_router.post("/webhooks/test")
def test_webhook(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Send a test webhook event."""
    import requests as req
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="webhook URL is required")

    test_payload = {"event": "test.ping", "timestamp": datetime.now().isoformat(), "message": "This is a test webhook from 梦眠阁", "user_id": user_and_db[0].id}

    try:
        resp = req.post(url, json=test_payload, headers={"X-Mengmian-Signature": "test-sig", "Content-Type": "application/json"}, timeout=5)
        return {"success": True, "response_status": resp.status_code, "response_body": resp.text[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)}


@platform_router.get("/sdks")
def list_sdks():
    """List available SDK/API client configurations."""
    return {
        "sdks": [
            {"name": "JavaScript/TypeScript", "install": "npm install mengmian-sdk", "docs": "/docs/sdk/js"},
            {"name": "Python", "install": "pip install mengmian-sdk", "docs": "/docs/sdk/python"},
            {"name": "Flutter/Dart", "install": "dart pub add mengmian_sdk", "docs": "/docs/sdk/flutter"},
        ],
        "api_base_url": "/api/v1",
        "auth_header": "Authorization: Bearer {token}",
    }


@platform_router.get("/ping")
def ping():
    """Public ping endpoint for connectivity check from any platform."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": API_VERSION["version"],
        "endpoints": API_VERSION["total_endpoints"],
    }


# ==================== PAYMENT ====================
from app.models import PaymentOrder, PaymentRecord, Membership
import hashlib as _hashlib


def _generate_order_no() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(100000, 999999))


PAYMENT_PLANS = {
    "pro_monthly": {"tier": "pro", "name": "专业版月卡", "amount": 2900, "days": 30},
    "pro_yearly": {"tier": "pro", "name": "专业版年卡", "amount": 19900, "days": 365},
    "premium_monthly": {"tier": "premium", "name": "尊享版月卡", "amount": 5900, "days": 30},
    "premium_yearly": {"tier": "premium", "name": "尊享版年卡", "amount": 39900, "days": 365},
}

# Order expires after 30 minutes unpaid
ORDER_EXPIRE_MINUTES = 30


def _cancel_expired_orders(db: Session, user_id: int):
    """Auto-cancel expired pending orders for a user."""
    cutoff = datetime.utcnow() - timedelta(minutes=ORDER_EXPIRE_MINUTES)
    expired = db.query(PaymentOrder).filter(
        PaymentOrder.user_id == user_id,
        PaymentOrder.status == "pending",
        PaymentOrder.created_at < cutoff,
    ).all()
    for o in expired:
        o.status = "cancelled"
    if expired:
        db.commit()


@payment_router.get("/plans")
def get_payment_plans():
    """Get available payment plans with descriptions."""
    return {
        "plans": [{"id": k, **v, "amount_yuan": round(v["amount"] / 100, 2)} for k, v in PAYMENT_PLANS.items()],
        "order_expire_minutes": ORDER_EXPIRE_MINUTES,
    }


def _build_payment_params(order, user, method: str) -> dict:
    """Build payment parameters for different payment methods."""
    if method == "wechat":
        return {
            "appId": "wx551623c01821827f",
            "timeStamp": str(int(time.time())),
            "nonceStr": str(random.randint(100000, 999999)),
            "package": f"prepay_id=prepay_{order.order_no}",
            "signType": "MD5",
            "paySign": _hashlib.md5(f"order_{order.order_no}_salt".encode()).hexdigest()[:32],
        }
    elif method == "alipay":
        return {
            "orderStr": f"alipay_sdk=alipay-sdk-java&out_trade_no={order.order_no}&total_amount={order.amount/100:.2f}",
        }
    else:
        return {"method": "manual", "note": "管理员手动确认"}


@payment_router.post("/orders")
def create_order(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Create a payment order. Supports coupon code for discount."""
    user, db = user_and_db
    plan_id = data.get("plan_id", "pro_monthly")
    method = data.get("method", "wechat")
    coupon_code = data.get("coupon_code", "").strip()

    if plan_id not in PAYMENT_PLANS:
        raise HTTPException(status_code=400, detail="无效的套餐")

    # Cancel user's expired pending orders first
    _cancel_expired_orders(db, user.id)

    # Prevent duplicate pending orders
    existing = db.query(PaymentOrder).filter(
        PaymentOrder.user_id == user.id,
        PaymentOrder.status == "pending",
    ).first()
    if existing:
        # Return existing pending order instead of creating duplicate
        plan = PAYMENT_PLANS.get(plan_id, PAYMENT_PLANS["pro_monthly"])
        return {
            "order_id": existing.id,
            "order_no": existing.order_no,
            "amount": existing.amount,
            "amount_yuan": round(existing.amount / 100, 2),
            "tier": existing.tier,
            "plan_name": plan["name"],
            "status": existing.status,
            "payment_params": _build_payment_params(existing, user, method),
            "created_at": str(existing.created_at),
            "reuse": True,
        }

    plan = PAYMENT_PLANS[plan_id]
    amount = plan["amount"]

    # Apply coupon discount
    coupon_discount = 0
    coupon = None
    if coupon_code:
        from app.models import Coupon
        coupon = db.query(Coupon).filter(
            Coupon.code == coupon_code,
            Coupon.is_active == 1,
        ).first()
        if not coupon:
            raise HTTPException(status_code=400, detail="优惠券无效")
        if coupon.used_count >= coupon.max_uses:
            raise HTTPException(status_code=400, detail="优惠券已被领完")
        if coupon.expires_at and coupon.expires_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="优惠券已过期")
        if amount < (coupon.min_amount or 0):
            raise HTTPException(status_code=400, detail=f"订单金额需满¥{coupon.min_amount/100:.0f}")
        coupon_discount = round(amount * coupon.discount_percent / 100)
        amount = amount - coupon_discount

    order_no = _generate_order_no()
    order = PaymentOrder(
        order_no=order_no, user_id=user.id, tier=plan["tier"],
        amount=amount, payment_method=method,
        expires_at=datetime.utcnow() + timedelta(days=plan["days"]),
    )
    db.add(order); db.commit(); db.refresh(order)

    pay_params = _build_payment_params(order, user, method)

    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "amount": order.amount,
        "amount_yuan": round(order.amount / 100, 2),
        "original_amount": plan["amount"],
        "original_amount_yuan": round(plan["amount"] / 100, 2),
        "coupon_discount_yuan": round(coupon_discount / 100, 2) if coupon_discount else 0,
        "tier": order.tier,
        "plan_name": plan["name"],
        "status": order.status,
        "payment_params": pay_params,
        "expire_minutes": ORDER_EXPIRE_MINUTES,
        "created_at": str(order.created_at),
        "reuse": False,
    }


@payment_router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Cancel a pending order."""
    user, db = user_and_db
    order = db.query(PaymentOrder).filter(
        PaymentOrder.id == order_id, PaymentOrder.user_id == user.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="只能取消待付订单")
    order.status = "cancelled"
    db.commit()
    return {"message": "订单已取消", "order_no": order.order_no}


@payment_router.get("/orders/{order_no}")
def query_order_by_no(order_no: str, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Query payment order by order number (for polling)."""
    user, db = user_and_db
    order = db.query(PaymentOrder).filter(
        PaymentOrder.order_no == order_no,
        PaymentOrder.user_id == user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {
        "order_id": order.id, "order_no": order.order_no,
        "amount": order.amount, "amount_yuan": round(order.amount / 100, 2),
        "tier": order.tier, "status": order.status,
        "payment_method": order.payment_method,
        "paid_at": str(order.paid_at) if order.paid_at else None,
        "created_at": str(order.created_at),
    }


@payment_router.post("/orders/{order_id}/pay")
def process_payment(order_id: int, data: dict = None, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Process payment for an order. In production, this would be called by WeChat/Alipay callback.
    Client-side simulation accepts transaction_id to prevent duplicate payments."""
    user, db = user_and_db
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id, PaymentOrder.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == "paid":
        return {"message": "已支付", "already": True, "order_no": order.order_no, "tier": order.tier}
    if order.status != "pending":
        raise HTTPException(status_code=400, detail=f"订单状态 {order.status} 无法支付")

    # Check order expiry
    if order.created_at and (datetime.utcnow() - order.created_at).total_seconds() > ORDER_EXPIRE_MINUTES * 60:
        order.status = "cancelled"
        db.commit()
        raise HTTPException(status_code=400, detail="订单已过期，请重新创建")

    # Idempotency: check for duplicate transaction
    txn_id = data.get("transaction_id", "") if data else ""
    if txn_id:
        dup = db.query(PaymentRecord).filter(PaymentRecord.transaction_id == txn_id).first()
        if dup:
            # Already processed. If this order is still pending, mark it paid too.
            if order.status == "pending":
                order.status = "paid"; order.paid_at = datetime.utcnow(); db.commit()
            return {"message": "该交易已处理", "already": True, "order_no": order.order_no, "tier": order.tier}

    # Generate simulated transaction ID if not provided
    if not txn_id:
        txn_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

    # Mark order paid
    order.status = "paid"
    order.paid_at = datetime.utcnow()

    # Record payment
    record = PaymentRecord(
        order_id=order.id, user_id=user.id,
        transaction_id=txn_id, amount=order.amount,
        method=order.payment_method, status="success",
        raw_response=json.dumps({"mode": "simulation", "transaction_id": txn_id}),
    )
    db.add(record)

    # Activate/upgrade membership
    m = db.query(Membership).filter(Membership.user_id == user.id).first()
    days = 30  # default
    for pid, pinfo in PAYMENT_PLANS.items():
        if pinfo["tier"] == order.tier and pinfo["amount"] >= order.amount:  # >= because coupon may reduce
            days = pinfo["days"]
            break

    current_tier = _get_user_tier(db, user.id)
    if not m:
        m = Membership(user_id=user.id, tier=order.tier, started_at=datetime.utcnow(),
                       expires_at=datetime.utcnow() + timedelta(days=days), order_id=order.id)
        db.add(m)
    else:
        # Extend from current expiry if still active
        if m.expires_at and m.expires_at > datetime.utcnow():
            m.expires_at = m.expires_at + timedelta(days=days)
        else:
            m.expires_at = datetime.utcnow() + timedelta(days=days)
        m.tier = order.tier
        m.started_at = datetime.utcnow()
        m.order_id = order.id

    _log_membership_change( user.id, current_tier, order.tier, order.id, "upgrade", order.amount)
    db.commit()

    _log_audit(db, user.id, "payment_success", f"Order {order.order_no}, {order.tier}, {order.amount}分")
    return {
        "message": "支付成功",
        "order_no": order.order_no,
        "tier": order.tier,
        "amount": order.amount,
        "amount_yuan": round(order.amount / 100, 2),
        "transaction_id": txn_id,
        "membership_expires": str(m.expires_at) if m else None,
    }


@payment_router.get("/orders")
def get_orders(page: int = 1, status: str = None, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get user's order history with optional status filter."""
    user, db = user_and_db
    q = db.query(PaymentOrder).filter(PaymentOrder.user_id == user.id)
    if status:
        q = q.filter(PaymentOrder.status == status)
    orders = q.order_by(PaymentOrder.created_at.desc()).offset((page - 1) * 20).limit(20).all()
    return {"orders": [{
        "id": o.id, "order_no": o.order_no, "tier": o.tier,
        "amount": o.amount, "amount_yuan": round(o.amount / 100, 2),
        "status": o.status, "payment_method": o.payment_method,
        "paid_at": str(o.paid_at) if o.paid_at else None,
        "created_at": str(o.created_at),
    } for o in orders]}


@payment_router.post("/orders/{order_id}/refund")
def refund_order(order_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Request a refund (within 7 days of payment)."""
    user, db = user_and_db
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id, PaymentOrder.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "paid":
        raise HTTPException(status_code=400, detail="订单未支付或已退款")
    if order.paid_at and (datetime.utcnow() - order.paid_at).days > 7:
        raise HTTPException(status_code=400, detail="超过7天退款期")

    order.status = "refunded"
    db.add(PaymentRecord(order_id=order.id, user_id=user.id,
                         transaction_id=f"REFUND{int(time.time())}",
                         amount=-order.amount, method=order.payment_method, status="refund"))

    # Downgrade membership if this was the active order
    m = db.query(Membership).filter(Membership.user_id == user.id, Membership.order_id == order.id).first()
    if m and m.tier != "free":
        _log_membership_change( user.id, m.tier, "free", order.id, "downgrade", -order.amount)
        m.tier = "free"
        m.expires_at = datetime.utcnow()
        m.order_id = None

    db.commit()
    _log_audit(db, user.id, "payment_refund", f"Order {order.order_no}")
    return {"message": "退款成功", "order_no": order.order_no, "amount_yuan": round(order.amount / 100, 2)}


@payment_router.post("/wechat-notify")
def wechat_pay_notify(data: dict = None, request: Request = None):
    """WeChat Pay callback — production: verify signature, update order."""
    if not data:
        return {"code": "FAIL", "message": "no data"}

    order_no = data.get("out_trade_no", "")
    transaction_id = data.get("transaction_id", "")

    # Production: verify WeChat Pay signature using APIv3 key
    # signature = request.headers.get("Wechatpay-Signature")
    # timestamp = request.headers.get("Wechatpay-Timestamp")
    # nonce = request.headers.get("Wechatpay-Nonce")
    # Verify signature with wechatpay_apiv3_key

    if order_no and transaction_id:
        from app.database import SessionLocal
        _db = SessionLocal()
        try:
            order = _db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).first()
            if order and order.status == "pending":
                order.status = "paid"
                order.paid_at = datetime.utcnow()
                _db.add(PaymentRecord(
                    order_id=order.id, user_id=order.user_id,
                    transaction_id=transaction_id, amount=order.amount,
                    method="wechat", status="success",
                    raw_response=json.dumps(data),
                ))
                # Activate membership
                m = _db.query(Membership).filter(Membership.user_id == order.user_id).first()
                days = 30
                for pid, pinfo in PAYMENT_PLANS.items():
                    if pinfo["tier"] == order.tier:
                        days = pinfo["days"]; break
                if not m:
                    m = Membership(user_id=order.user_id, tier=order.tier,
                                   started_at=datetime.utcnow(),
                                   expires_at=datetime.utcnow() + timedelta(days=days))
                    _db.add(m)
                else:
                    current_tier = _get_user_tier(_db, order.user_id)
                    if m.expires_at and m.expires_at > datetime.utcnow():
                        m.expires_at = m.expires_at + timedelta(days=days)
                    else:
                        m.expires_at = datetime.utcnow() + timedelta(days=days)
                    m.tier = order.tier
                    m.order_id = order.id
                    _log_membership_change(order.user_id, current_tier, order.tier, order.id, "upgrade", order.amount)
                _db.commit()
        finally:
            _db.close()

    return {"code": "SUCCESS", "message": "OK"}


# ==================== SMART ALARM ====================
@sleep_router.get("/smart-alarm")
def smart_alarm(bedtime: str = None, wake_target: str = None, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Calculate optimal sleep/wake times based on 90-min cycles."""
    user, db = user_and_db
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    goal_hours = profile.sleep_goal_hours if profile else 8.0

    # 90-min cycle calculation
    cycles = [4, 5, 6]  # 6h, 7.5h, 9h
    fall_asleep_min = 15  # average time to fall asleep

    if bedtime:
        # Given bedtime → suggest wake times
        try: bh, bm = int(bedtime[:2]), int(bedtime[3:5])
        except: bh, bm = 23, 0
        wake_times = []
        for c in cycles:
            total_min = bh * 60 + bm + c * 90 + fall_asleep_min
            wh = (total_min // 60) % 24
            wm = total_min % 60
            wake_times.append({"cycles": c, "duration_h": c * 1.5, "time": f"{wh:02d}:{wm:02d}", "quality": "excellent" if c in [5] else ("good" if c in [4] else "fair")})
        return {"type": "wake", "bedtime": bedtime, "suggested_wake": wake_times, "fall_asleep_min": fall_asleep_min}
    else:
        # Given desired wake time → suggest bedtimes
        wt = wake_target or "07:00"
        try: wh, wm = int(wt[:2]), int(wt[3:5])
        except: wh, wm = 7, 0
        bedtimes = []
        for c in cycles:
            total_min = wh * 60 + wm - c * 90 - fall_asleep_min
            if total_min < 0: total_min += 24 * 60
            bh = (total_min // 60) % 24
            bm = total_min % 60
            bedtimes.append({"cycles": c, "duration_h": c * 1.5, "time": f"{bh:02d}:{bm:02d}", "quality": "excellent" if c == 5 else ("good" if c in [4, 6] else "fair")})
        return {"type": "sleep", "wake_target": wt, "suggested_bedtime": bedtimes, "fall_asleep_min": fall_asleep_min}


# Parameterized record routes — MUST be at the very end of all sleep_router named routes
@sleep_router.get("/{record_id}", response_model=SleepRecordResponse)
def get_record(record_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    r = db.query(SleepRecord).filter(SleepRecord.id == record_id, SleepRecord.user_id == user.id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    return _to_record_response(r)


@sleep_router.delete("/{record_id}")
def delete_record(record_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    r = db.query(SleepRecord).filter(SleepRecord.id == record_id, SleepRecord.user_id == user.id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(r); db.commit()
    return {"message": "已删除"}


# ==================== SLEEP ASSESSMENTS ====================
ASSESSMENT_SCALES = {
    "PSQI": {
        "name": "匹兹堡睡眠质量指数",
        "desc": "评估近1个月睡眠质量的国际金标准问卷",
        "questions": [
            {"id": 1, "text": "近1个月，晚上通常几点上床睡觉？", "type": "time"},
            {"id": 2, "text": "近1个月，从上床到入睡通常需要多少分钟？", "type": "number"},
            {"id": 3, "text": "近1个月，通常早上几点起床？", "type": "time"},
            {"id": 4, "text": "近1个月，每晚实际睡眠时间约多少小时？", "type": "number"},
            {"id": 5, "text": "入睡困难（30分钟内无法入睡）", "type": "scale", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
            {"id": 6, "text": "夜间易醒或早醒", "type": "scale", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
            {"id": 7, "text": "夜间去厕所", "type": "scale", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
            {"id": 8, "text": "呼吸不畅", "type": "scale", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
            {"id": 9, "text": "咳嗽或鼾声", "type": "scale", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
            {"id": 10, "text": "感觉冷", "type": "scale", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
            {"id": 11, "text": "感觉热", "type": "scale", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
            {"id": 12, "text": "做噩梦", "type": "scale", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
            {"id": 13, "text": "疼痛不适", "type": "scale", "options": ["无", "<1次/周", "1-2次/周", "≥3次/周"]},
            {"id": 14, "text": "近1个月，您认为自己的睡眠质量如何？", "type": "scale", "options": ["很好", "较好", "较差", "很差"]},
        ],
        "scoring": "sum_5_to_14", "max_score": 21, "thresholds": {"mild": 5, "moderate": 10, "severe": 15},
    },
    "ISI": {
        "name": "失眠严重指数",
        "desc": "评估失眠严重程度的7题量表",
        "questions": [
            {"id": 1, "text": "入睡困难的严重程度", "type": "scale", "options": ["无", "轻度", "中度", "重度", "极重度"]},
            {"id": 2, "text": "睡眠维持困难的严重程度", "type": "scale", "options": ["无", "轻度", "中度", "重度", "极重度"]},
            {"id": 3, "text": "早醒问题的严重程度", "type": "scale", "options": ["无", "轻度", "中度", "重度", "极重度"]},
            {"id": 4, "text": "对当前睡眠模式的满意度", "type": "scale", "options": ["很满意", "满意", "一般", "不满意", "很不满意"]},
            {"id": 5, "text": "睡眠问题对日间功能的影响", "type": "scale", "options": ["无", "轻度", "中度", "重度", "极重度"]},
            {"id": 6, "text": "睡眠问题在多大程度上被他人注意到", "type": "scale", "options": ["无", "轻度", "中度", "重度", "极重度"]},
            {"id": 7, "text": "睡眠问题给您带来的困扰/担忧", "type": "scale", "options": ["无", "轻度", "中度", "重度", "极重度"]},
        ],
        "max_score": 28, "thresholds": {"mild": 8, "moderate": 15, "severe": 22},
    },
}


@wellness_router.get("/assessments")
def list_assessments():
    """List available sleep assessment scales."""
    return {
        "scales": [{"id": k, "name": v["name"], "desc": v["desc"], "question_count": len(v["questions"]), "max_score": v["max_score"]} for k, v in ASSESSMENT_SCALES.items()]
    }


@wellness_router.get("/assessments/{scale_id}")
def get_assessment(scale_id: str):
    """Get assessment questions."""
    if scale_id not in ASSESSMENT_SCALES:
        raise HTTPException(status_code=404, detail="评估量表不存在")
    scale = ASSESSMENT_SCALES[scale_id]
    return {"id": scale_id, "name": scale["name"], "desc": scale["desc"], "questions": scale["questions"]}


@wellness_router.post("/assessments/{scale_id}/submit")
def submit_assessment(scale_id: str, data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Submit assessment answers and get score."""
    user, db = user_and_db
    if scale_id not in ASSESSMENT_SCALES:
        raise HTTPException(status_code=404, detail="评估量表不存在")

    scale = ASSESSMENT_SCALES[scale_id]
    answers = data.get("answers", {})

    # Calculate score
    score = 0
    for q in scale["questions"]:
        qid = str(q["id"])
        if qid in answers and q["type"] == "scale":
            ans = int(answers[qid])
            if scale_id == "PSQI" and q["id"] >= 5:
                score += ans  # 0-3
            elif scale_id == "ISI":
                score += ans  # 0-4

    # Severity
    thresholds = scale["thresholds"]
    if score >= thresholds.get("severe", 100): severity = "severe"
    elif score >= thresholds.get("moderate", 100): severity = "moderate"
    elif score >= thresholds.get("mild", 100): severity = "mild"
    else: severity = "normal"

    # AI analysis
    ai_analysis = ""
    try:
        context = f"{scale['name']}评分: {score}分, 严重度: {severity}, 答案: {json.dumps(answers, ensure_ascii=False)}"
        ai_analysis = _ai_chat("你是睡眠医学专家。给出80字以内的专业简短解读和1个建议，不给出诊断。", context, temperature=0.5, max_tokens=150)
    except: pass

    # Save
    from app.models import SleepAssessment
    assessment = SleepAssessment(user_id=user.id, scale_type=scale_id, score=score, severity=severity, answers=json.dumps(answers), ai_analysis=ai_analysis or "")
    db.add(assessment); db.commit()

    return {"scale_id": scale_id, "score": score, "max_score": scale["max_score"], "severity": severity, "ai_analysis": ai_analysis or "请咨询专业医生获取详细解读"}


# ==================== MOOD TRACKING ====================
from app.models import MoodRecord


@mood_router.post("/records")
def create_mood(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    date_key = data.get("date_key", datetime.now().strftime("%Y-%m-%d"))
    existing = db.query(MoodRecord).filter(MoodRecord.user_id == user.id, MoodRecord.date_key == date_key).first()
    if existing:
        for f in ["mood_level", "energy_level", "anxiety_level", "note"]:
            if f in data: setattr(existing, f, data[f])
    else:
        db.add(MoodRecord(user_id=user.id, date_key=date_key, mood_level=data.get("mood_level", 3), energy_level=data.get("energy_level", 3), anxiety_level=data.get("anxiety_level", 3), note=data.get("note", "")))
    db.commit()
    return {"message": "已保存"}


@mood_router.get("/records")
def get_moods(days: int = 7, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(MoodRecord).filter(MoodRecord.user_id == user.id, MoodRecord.date_key >= cutoff.strftime("%Y-%m-%d")).order_by(MoodRecord.date_key.desc()).all()
    return {"moods": [{"date_key": r.date_key, "mood_level": r.mood_level, "energy_level": r.energy_level, "anxiety_level": r.anxiety_level, "note": r.note} for r in records]}


# ==================== GAMIFICATION ====================
from app.models import UserLevel

LEVEL_XP = [0, 100, 250, 500, 850, 1300, 1900, 2700, 3800, 5200, 7000, 9200, 12000, 15500, 20000]
LEVEL_NAMES = ["睡眠新手","浅睡学徒","深睡探索者","快速眼动者","睡眠守护者","梦境旅人","昼夜平衡者","睡眠达人","睡眠大师","睡眠宗师","睡眠传奇","睡眠神话","安眠之神"]


def _award_xp(db, user_id: int, amount: int) -> dict:
    """Award XP and handle level up."""
    ul = db.query(UserLevel).filter(UserLevel.user_id == user_id).first()
    if not ul:
        ul = UserLevel(user_id=user_id, level=1, total_xp=0, current_xp=0)
        db.add(ul)
    ul.total_xp += amount
    ul.current_xp += amount

    # Check level up
    leveled = False
    while ul.level < len(LEVEL_XP) and ul.current_xp >= LEVEL_XP[ul.level]:
        ul.current_xp -= LEVEL_XP[ul.level]
        ul.level += 1
        leveled = True

    db.commit()
    return {"level": ul.level, "level_name": LEVEL_NAMES[min(ul.level - 1, len(LEVEL_NAMES) - 1)], "total_xp": ul.total_xp, "current_xp": ul.current_xp, "xp_needed": LEVEL_XP[ul.level] if ul.level < len(LEVEL_XP) else 99999, "leveled_up": leveled}


@game_router.get("/status")
def get_game_status(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    ul = db.query(UserLevel).filter(UserLevel.user_id == user.id).first()
    if not ul:
        ul = UserLevel(user_id=user.id, level=1, total_xp=0, current_xp=0)
        db.add(ul); db.commit()
    return {"level": ul.level, "level_name": LEVEL_NAMES[min(ul.level - 1, len(LEVEL_NAMES) - 1)], "total_xp": ul.total_xp, "current_xp": ul.current_xp, "xp_needed": LEVEL_XP[ul.level] if ul.level < len(LEVEL_XP) else 99999, "streak_days": ul.streak_days, "max_streak": ul.max_streak, "levels": [{"lvl": i+1, "name": LEVEL_NAMES[i], "xp": LEVEL_XP[i]} for i in range(min(13, ul.level + 2))]}


@game_router.post("/checkin")
def daily_checkin(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Daily check-in bonus."""
    user, db = user_and_db
    today = datetime.now().strftime("%Y-%m-%d")
    existing = db.query(TaskCompletion).filter(TaskCompletion.user_id == user.id, TaskCompletion.task_id == "checkin", TaskCompletion.date_key == today).first()
    if existing:
        return {"message": "今日已签到"}

    db.add(TaskCompletion(user_id=user.id, task_id="checkin", date_key=today, points=10))

    # Update streak
    ul = db.query(UserLevel).filter(UserLevel.user_id == user.id).first()
    if ul:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        had_yesterday = db.query(TaskCompletion).filter(TaskCompletion.user_id == user.id, TaskCompletion.task_id == "checkin", TaskCompletion.date_key == yesterday).first()
        if had_yesterday or ul.streak_days == 0:
            ul.streak_days += 1
        else:
            ul.streak_days = 1
        ul.max_streak = max(ul.max_streak, ul.streak_days)
        db.commit()

    result = _award_xp(db, user.id, 15)
    return {"message": f"签到成功！+15XP", "xp_awarded": 15, "streak": ul.streak_days if ul else 1, **result}


@game_router.get("/leaderboard")
def game_leaderboard(limit: int = 20, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    _, db = user_and_db
    top = db.query(UserLevel).order_by(UserLevel.total_xp.desc()).limit(limit).all()
    return {"leaderboard": [{"rank": i+1, "user_id": u.user_id, "nickname": (db.query(User).filter(User.id == u.user_id).first().nickname or "匿名") if u.user_id else "匿名", "level": u.level, "level_name": LEVEL_NAMES[min(u.level-1, len(LEVEL_NAMES)-1)], "total_xp": u.total_xp, "streak": u.streak_days} for i, u in enumerate(top)]}


# ==================== GAME: DAILY MISSIONS & DASHBOARD ====================
DAILY_MISSIONS = [
    {"key": "record_sleep", "title": "记录今晚睡眠", "desc": "记录入睡时间和起床时间", "icon": "📝", "xp": 10, "category": "daily"},
    {"key": "complete_task", "title": "完成一个每日任务", "desc": "从今日任务中选一个完成", "icon": "✅", "xp": 5, "category": "daily"},
    {"key": "chat_coach", "title": "和AI教练聊一聊", "desc": "发送一条消息咨询睡眠问题", "icon": "💬", "xp": 8, "category": "daily"},
    {"key": "mood_check", "title": "记录今日心情", "desc": "花30秒记录你的情绪状态", "icon": "😊", "xp": 5, "category": "daily"},
    {"key": "read_article", "title": "阅读一篇睡眠知识", "desc": "从知识库中选一篇文章阅读", "icon": "📖", "xp": 8, "category": "daily"},
    {"key": "program_day", "title": "完成今日21天课程", "desc": "学习今天的视频和文章", "icon": "🎓", "xp": 15, "category": "daily"},
    {"key": "white_noise", "title": "使用白噪音15分钟", "desc": "听白噪音或音景帮助放松", "icon": "🎵", "xp": 5, "category": "daily"},
    {"key": "stretch", "title": "睡前拉伸5分钟", "desc": "做一些轻度拉伸释放紧张", "icon": "🧘", "xp": 5, "category": "daily"},
    {"key": "community_post", "title": "在社区发帖互动", "desc": "分享你的睡眠心得或鼓励他人", "icon": "💪", "xp": 10, "category": "daily"},
    {"key": "early_bed", "title": "22:30前上床准备入睡", "desc": "今晚在目标时间前上床", "icon": "🌙", "xp": 15, "category": "daily"},
]

WEEKLY_CHALLENGES = [
    {"key": "streak_7", "title": "连续7天记录睡眠", "desc": "每天记录一次睡眠", "icon": "🔥", "xp": 50, "target": 7},
    {"key": "tasks_20", "title": "完成20个每日任务", "desc": "7天内累计完成20个任务", "icon": "✅", "xp": 60, "target": 20},
    {"key": "score_avg_80", "title": "周平均睡眠评分>80", "desc": "本周睡眠评分平均达到80分以上", "icon": "⭐", "xp": 80, "target": 80},
    {"key": "chat_5", "title": "与AI教练对话5次", "desc": "7天内向睡眠教练咨询5次", "icon": "💬", "xp": 40, "target": 5},
    {"key": "program_5", "title": "完成5天21天课程", "desc": "7天内推进5天课程进度", "icon": "🎓", "xp": 75, "target": 5},
    {"key": "early_5", "title": "5天在23:00前入睡", "desc": "本周有5天在23点前上床", "icon": "🌙", "xp": 70, "target": 5},
]


@game_router.get("/dashboard")
def get_game_dashboard(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Complete game dashboard with XP, missions, challenges, and stats."""
    user, db = user_and_db
    from app.models import ProgramProgress as PP
    from datetime import date

    ul = db.query(UserLevel).filter(UserLevel.user_id == user.id).first()
    if not ul:
        ul = UserLevel(user_id=user.id, level=1, total_xp=0, current_xp=0, streak_days=0, max_streak=0)
        db.add(ul); db.commit()

    _d = date.today()
    today = _d.strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")

    # Today's completions
    today_comps = db.query(TaskCompletion).filter(
        TaskCompletion.user_id == user.id, TaskCompletion.date_key == today
    ).all()
    completed_keys = {c.task_id for c in today_comps}

    # Today's sleep record
    today_record = db.query(SleepRecord).filter(
        SleepRecord.user_id == user.id, SleepRecord.diary_date == _d
    ).first()

    # Today's chat
    today_chat = db.query(ChatMessage).filter(
        ChatMessage.session.has(ChatSession.user_id == user.id),
        ChatMessage.created_at >= datetime.now().date(),
        ChatMessage.role == "user",
    ).count()

    # Today's mood
    today_mood = db.query(MoodRecord).filter(
        MoodRecord.user_id == user.id, MoodRecord.date_key == today
    ).first()

    # Program progress
    pp = db.query(PP).filter(PP.user_id == user.id).first()

    # This week's sleep records
    week_records = db.query(SleepRecord).filter(
        SleepRecord.user_id == user.id, SleepRecord.diary_date >= week_start
    ).all()

    # This week's tasks
    week_tasks = db.query(TaskCompletion).filter(
        TaskCompletion.user_id == user.id, TaskCompletion.date_key >= week_start
    ).count()

    # This week's chats
    week_chats = db.query(ChatMessage).filter(
        ChatMessage.session.has(ChatSession.user_id == user.id),
        ChatMessage.created_at >= datetime.now().date() - timedelta(days=datetime.now().weekday()),
        ChatMessage.role == "user",
    ).count()

    # Daily missions with progress
    daily_missions = []
    for m in DAILY_MISSIONS[:6]:  # Show 6 missions per day
        done = False
        if m["key"] == "record_sleep":
            done = today_record is not None
        elif m["key"] == "complete_task":
            done = any(c.task_id != "checkin" for c in today_comps)
        elif m["key"] == "chat_coach":
            done = today_chat > 0
        elif m["key"] == "mood_check":
            done = today_mood is not None
        elif m["key"] == "program_day":
            done = pp is not None and pp.current_day > 0
        elif m["key"] == "white_noise":
            done = completed_keys and "t8" in completed_keys
        elif m["key"] == "early_bed":
            if today_record:
                done = today_record.bedtime.hour < 23 or (today_record.bedtime.hour == 23 and today_record.bedtime.minute == 0)
        elif m["key"] == "read_article":
            done = completed_keys and "t18" in map(str, completed_keys)
        else:
            done = m["key"].replace("_", "") in completed_keys
        daily_missions.append({**m, "done": done})

    daily_done = sum(1 for m in daily_missions if m["done"])

    # Weekly challenge (rotate based on week number)
    week_num = datetime.now().isocalendar()[1]
    challenge = WEEKLY_CHALLENGES[week_num % len(WEEKLY_CHALLENGES)]
    challenge_progress = 0
    if challenge["key"] == "streak_7":
        challenge_progress = len(set(str(r.diary_date) for r in week_records))
    elif challenge["key"] == "tasks_20":
        challenge_progress = week_tasks
    elif challenge["key"] == "score_avg_80":
        if week_records:
            challenge_progress = round(sum(r.score for r in week_records) / len(week_records))
    elif challenge["key"] == "chat_5":
        challenge_progress = week_chats
    elif challenge["key"] == "program_5":
        challenge_progress = pp.current_day if pp else 0
    elif challenge["key"] == "early_5":
        challenge_progress = sum(1 for r in week_records if r.bedtime and r.bedtime.hour < 23)

    challenge_done = challenge_progress >= challenge["target"]

    # XP breakdown
    xp_sources = [
        {"source": "签到", "icon": "🎁", "xp": 15},
        {"source": "每日任务", "icon": "✅", "xp": sum(c.points for c in today_comps if c.task_id != "checkin")},
        {"source": "21天课程", "icon": "🎓", "xp": 0},  # Tracked via program
        {"source": "睡眠记录", "icon": "📝", "xp": 10 if today_record else 0},
    ]

    # Level perks
    level_perks = {
        3: "解锁高级白噪音引擎",
        5: "解锁深度睡眠报告",
        7: "解锁睡眠预测功能",
        10: "获得「睡眠达人」称号",
        13: "获得「安眠之神」称号",
    }

    return {
        "user": {
            "level": ul.level,
            "level_name": LEVEL_NAMES[min(ul.level - 1, len(LEVEL_NAMES) - 1)],
            "total_xp": ul.total_xp,
            "current_xp": ul.current_xp,
            "xp_needed": LEVEL_XP[ul.level] if ul.level < len(LEVEL_XP) else 99999,
            "xp_pct": round(ul.current_xp / (LEVEL_XP[ul.level] if ul.level < len(LEVEL_XP) else 99999) * 100),
            "streak_days": ul.streak_days,
            "max_streak": ul.max_streak,
            "next_perk": level_perks.get(ul.level + 1),
        },
        "daily_missions": daily_missions,
        "daily_done": daily_done,
        "daily_total": len(daily_missions),
        "weekly_challenge": {
            **challenge,
            "progress": min(challenge_progress, challenge["target"]),
            "done": challenge_done,
            "pct": round(min(challenge_progress / challenge["target"], 1) * 100),
        },
        "xp_sources": xp_sources,
        "levels": [{"lvl": i+1, "name": LEVEL_NAMES[i], "xp": LEVEL_XP[i],
                     "perk": level_perks.get(i+1)} for i in range(min(13, ul.level + 2))],
        "all_levels": [{"lvl": i+1, "name": LEVEL_NAMES[i], "xp": LEVEL_XP[i],
                         "perk": level_perks.get(i+1)} for i in range(13)],
    }


# ==================== SLEEP TREND ANALYSIS ====================
@sleep_router.get("/trends/full")
def get_full_trends(days: int = Query(default=30), user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Comprehensive 30-day sleep trend analysis with weekly breakdowns."""
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(SleepRecord).filter(
        SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff
    ).order_by(SleepRecord.bedtime).all()

    if not records:
        return {"has_data": False, "message": "暂无足够数据，请先记录至少3天睡眠"}

    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    goal = profile.sleep_goal_hours if profile else 8.0

    # Daily data points
    daily = []
    for r in records:
        daily.append({
            "date": str(r.diary_date),
            "score": r.score,
            "duration": r.duration_hours,
            "bedtime": str(r.bedtime)[:16] if r.bedtime else None,
            "wake_time": str(r.wake_time)[:16] if r.wake_time else None,
            "quality": r.quality,
            "tags": json.loads(r.tags or "[]"),
        })

    # Weekly aggregates
    weekly = []
    for w in range(min(4, days // 7)):
        w_end = datetime.now() - timedelta(days=w * 7)
        w_start = w_end - timedelta(days=7)
        w_records = [r for r in records if w_start <= r.bedtime <= w_end]
        if w_records:
            weekly.append({
                "week": f"第{w+1}周",
                "avg_score": round(sum(r.score for r in w_records) / len(w_records)),
                "avg_duration": round(sum(r.duration_hours or 0 for r in w_records) / len(w_records), 1),
                "record_count": len(w_records),
                "best_score": max(r.score for r in w_records),
                "sleep_debt": round(sum(max(0, goal - (r.duration_hours or 0)) for r in w_records), 1),
            })

    # Overall stats
    avg_score_all = round(sum(r.score for r in records) / len(records))
    avg_dur_all = round(sum(r.duration_hours or 0 for r in records) / len(records), 1)
    best = max(records, key=lambda r: r.score)
    worst = min(records, key=lambda r: r.score)
    cons_mins = calc_consistency_minutes(records)
    debt = calc_sleep_debt(records, goal)

    # Score distribution
    dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
    for r in records:
        s = r.score or 0
        if s >= 80: dist["excellent"] += 1
        elif s >= 60: dist["good"] += 1
        elif s >= 40: dist["fair"] += 1
        else: dist["poor"] += 1

    # Bedtime trend
    bedtimes = []
    for r in records:
        if r.bedtime:
            bedtimes.append({"date": str(r.diary_date), "hour": r.bedtime.hour + r.bedtime.minute / 60})

    # AI-generated improvement suggestions
    suggestions = []
    if avg_score_all < 60:
        suggestions.append({"priority": "high", "text": "你的近期平均睡眠评分较低，建议从基础睡眠卫生开始：固定起床时间、睡前1小时远离屏幕、卧室温度18-22°C。"})
    if debt.get("total_debt", 0) > 5:
        suggestions.append({"priority": "medium", "text": f"你有{debt['total_debt']:.1f}小时的睡眠债。建议本周每天提前30分钟上床，逐步偿还睡眠债。"})
    if cons_mins > 60:
        suggestions.append({"priority": "medium", "text": "你的作息不太规律（波动>60分钟）。固定起床时间是改善睡眠的第一法则，即使是周末也不要赖床超过1小时。"})
    if avg_dur_all < goal - 1:
        suggestions.append({"priority": "high", "text": f"你的平均睡眠{avg_dur_all}h，距目标{goal}h差{goal-avg_dur_all:.1f}h。试试睡眠限制疗法，先提高效率再延长时长。"})
    if avg_score_all >= 80:
        suggestions.append({"priority": "positive", "text": "你的睡眠质量很优秀！继续保持当前的规律作息和睡前仪式。可以考虑挑战连续21天达标来解锁成就。"})
    if not suggestions:
        suggestions.append({"priority": "neutral", "text": "保持当前的习惯，继续记录睡眠数据以获得更精准的分析。"})

    return {
        "has_data": True,
        "days": days,
        "record_count": len(records),
        "daily": daily,
        "weekly": weekly,
        "overview": {
            "avg_score": avg_score_all,
            "avg_duration": avg_dur_all,
            "consistency_label": consistency_label(cons_mins),
            "consistency_minutes": round(cons_mins, 1),
            "best": {"date": str(best.diary_date), "score": best.score, "duration": best.duration_hours},
            "worst": {"date": str(worst.diary_date), "score": worst.score, "duration": worst.duration_hours},
            "sleep_debt": debt,
            "streak_days": calc_streak(db, user.id),
            "goal_hours": goal,
        },
        "distribution": dist,
        "bedtime_trend": bedtimes,
        "suggestions": suggestions,
    }


# ==================== HOME DASHBOARD ====================
@wellness_router.get("/dashboard")
def home_dashboard(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Complete home dashboard data in one API call."""
    user, db = user_and_db
    from app.models import ProgramProgress as PP, SleepRecord as SR, UserLevel as UL
    from datetime import date

    today = date.today()
    week_ago = today - timedelta(days=6)

    # Last sleep record
    last = db.query(SR).filter(SR.user_id == user.id).order_by(SR.bedtime.desc()).first()

    # This week's records
    week_records = db.query(SR).filter(
        SR.user_id == user.id, SR.diary_date >= week_ago
    ).order_by(SR.diary_date).all()

    # Stats
    avg_score = round(sum(r.score for r in week_records) / len(week_records)) if week_records else 0
    avg_duration = round(sum(r.duration_hours or 0 for r in week_records) / len(week_records), 1) if week_records else 0
    streak = calc_streak(db, user.id)

    # Today's tasks
    today_key = today.strftime("%Y-%m-%d")
    today_comps = db.query(TaskCompletion).filter(
        TaskCompletion.user_id == user.id, TaskCompletion.date_key == today_key
    ).count()

    # Program progress
    pp = db.query(PP).filter(PP.user_id == user.id).first()
    program_day = pp.current_day if pp else 0

    # Game stats
    ul = db.query(UL).filter(UL.user_id == user.id).first()
    level = ul.level if ul else 1
    level_name = LEVEL_NAMES[min(level - 1, len(LEVEL_NAMES) - 1)] if ul else "睡眠新手"
    total_xp = ul.total_xp if ul else 0

    # Weekly trend (last 7 days scores)
    trend = []
    for i in range(7):
        d = week_ago + timedelta(days=i)
        r = next((r for r in week_records if r.diary_date and r.diary_date == d), None)
        trend.append({"date": d.strftime("%m/%d"), "score": r.score if r else 0, "duration": r.duration_hours if r else 0})

    # Generate personalized daily insight
    daily_insight = generate_daily_insight(last, week_records, streak, avg_score)

    return {
        "last_sleep": {
            "score": last.score if last else None,
            "duration": last.duration_hours if last else None,
            "bedtime": str(last.bedtime)[:16] if last and last.bedtime else None,
            "wake_time": str(last.wake_time)[:16] if last and last.wake_time else None,
            "date": str(last.diary_date) if last else None,
            "quality": last.quality if last else None,
            "feedback": last.ai_feedback[:80] if last and last.ai_feedback else None,
        } if last else None,
        "weekly_stats": {
            "avg_score": avg_score,
            "avg_duration": avg_duration,
            "streak_days": streak,
            "total_records": len(week_records),
            "consistency": consistency_label(calc_consistency_minutes(week_records)) if len(week_records) >= 2 else "--",
        },
        "today_tasks": {
            "completed": today_comps,
            "total": 4,
        },
        "program": {
            "day": program_day,
            "total": 21,
            "pct": round(program_day / 21 * 100),
            "started": program_day > 0,
        },
        "game": {
            "level": level,
            "level_name": level_name,
            "total_xp": total_xp,
        },
        "trend": trend,
        "daily_insight": daily_insight,
    }


# ==================== GAME HALL ====================
GAME_HALL = [
    {
        "id": "garden", "order": 1,
        "name": "梦境花园", "subtitle": "养成 · 每日浇灌",
        "icon": "🌻", "color": "#2ECC71", "bg": "linear-gradient(135deg, #1a3e1a, #0f2e0f)",
        "desc": "完成每日睡眠任务获得水滴和阳光，培育你的梦境植物。好习惯养出好睡眠。",
        "status": "active",
        "stats": {"玩家": "2.3k", "植物": "48种"},
        "features": ["每日浇灌", "收集植物", "花园装饰", "睡眠日记联动"],
    },
    {
        "id": "adventure", "order": 2,
        "name": "睡眠大冒险", "subtitle": "剧情RPG · CBT-I冒险",
        "icon": "⚔️", "color": "#E74C3C", "bg": "linear-gradient(135deg, #2a1a1a, #1a0f0f)",
        "desc": "在失眠王国中探险，用CBT-I技能击败焦虑怪和熬夜龙。将治疗知识融入游戏叙事。",
        "status": "active",
        "stats": {"章节": "第1章", "Boss": "焦虑怪"},
        "features": ["剧情推进", "CBT-I技能", "Boss战", "装备收集"],
    },
    {
        "id": "breathing", "order": 3,
        "name": "呼吸训练", "subtitle": "放松 · 4-7-8呼吸法",
        "icon": "🫁", "color": "#3498DB", "bg": "linear-gradient(135deg, #1a2a3e, #0f1f2e)",
        "desc": "跟随圆环节奏练习腹式呼吸。基础模式引导练习，进阶模式节拍器打分。",
        "status": "active",
        "stats": {"今日练习": "—", "最高分": "—"},
        "features": ["圆环引导", "节拍评分", "4-7-8计时", "心率反馈"],
    },
    {
        "id": "worry", "order": 4,
        "name": "烦恼粉碎机", "subtitle": "心理 · CBT-I技术",
        "icon": "💥", "color": "#9B59B6", "bg": "linear-gradient(135deg, #1e1a2e, #120f1e)",
        "desc": "把焦虑写下来变成气泡，一一戳破。基于CBT-I担忧时间技术，帮你清空睡前烦恼。",
        "status": "active",
        "stats": {"今日粉碎": "—", "累计": "—"},
        "features": ["书写烦恼", "气泡戳破", "焦虑释放", "CBT-I记录"],
    },
    {
        "id": "quiz", "order": 5,
        "name": "睡眠问答", "subtitle": "益智 · 知识拼图",
        "icon": "🧩", "color": "#F39C12", "bg": "linear-gradient(135deg, #2a1e0a, #1e1200)",
        "desc": "回答睡眠科学知识题，解锁拼图碎片。集齐碎片拼出完整的睡眠知识图谱。",
        "status": "active",
        "stats": {"题库": "50+题", "拼图": "12块"},
        "features": ["每日5题", "知识解析", "碎片收集", "图谱拼接"],
    },
    {
        "id": "soundscape", "order": 6,
        "name": "音景工坊", "subtitle": "创意 · 白噪音混音",
        "icon": "🎛️", "color": "#1ABC9C", "bg": "linear-gradient(135deg, #0a2a2a, #051a1a)",
        "desc": "拖动滑杆混音雨声、风声、篝火、溪流，创造你的专属入睡音景并保存。",
        "status": "active",
        "stats": {"音轨": "12种", "预设": "8个"},
        "features": ["多轨混音", "实时播放", "保存预设", "社区分享"],
    },
    {
        "id": "runner", "order": 7,
        "name": "昼夜节律跑酷", "subtitle": "动作 · 即将上线",
        "icon": "🏃", "color": "#E67E22", "bg": "linear-gradient(135deg, #2a1a0a, #1a0f00)",
        "desc": "控制角色在正确的时间做出正确行为，避开咖啡因陷阱和蓝光障碍。强化昼夜节律认知。",
        "status": "coming_soon",
        "stats": {"预计上线": "2026年7月", "预约": "0人"},
        "features": ["昼夜切换", "障碍躲避", "道具收集", "排行榜"],
        "teaser_video": "",
        "teaser_text": "🌅 白天与黑夜交替，你的每一个选择都在塑造你的生物钟。\n\n🏃 躲避咖啡因陷阱，收集阳光能量，在正确的时间做正确的事。\n\n⏰ 昼夜节律跑酷——即将上线，敬请期待！",
    },
]


@game_router.get("/hall")
def get_game_hall(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get the game hall with all games and user's personal stats."""
    user, db = user_and_db
    from app.models import ProgramProgress as PP, SleepRecord as SR

    # User-specific game stats
    today = datetime.now().strftime("%Y-%m-%d")
    record_count = db.query(SR).filter(SR.user_id == user.id).count()
    pp = db.query(PP).filter(PP.user_id == user.id).first()
    program_day = pp.current_day if pp else 0

    # Count today's worry submissions and quiz attempts
    today_comps = db.query(TaskCompletion).filter(
        TaskCompletion.user_id == user.id, TaskCompletion.date_key == today
    ).count()

    user_stats = {
        "garden": {"今日浇灌": "—", "已收集": "—"},
        "adventure": {"当前章节": "第1章" if program_day > 0 else "未开始", "已解锁技能": min(program_day // 3, 5)},
        "breathing": {"今日练习": f"{today_comps}次", "最高分": "—"},
        "worry": {"今日粉碎": "—", "累计": "—"},
        "quiz": {"今日答题": "—", "已解锁碎片": "0/12"},
        "soundscape": {"已保存预设": "0个"},
        "runner": {"预约状态": "未预约"},
    }

    games = []
    for g in GAME_HALL:
        g_with_stats = {**g, "user_stats": user_stats.get(g["id"], {})}
        games.append(g_with_stats)

    return {"games": games, "total_games": len(GAME_HALL), "active_games": sum(1 for g in GAME_HALL if g["status"] == "active")}


@game_router.post("/hall/{game_id}/visit")
def visit_game(game_id: str, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Record a game visit and award XP for first visit."""
    user, db = user_and_db
    game = next((g for g in GAME_HALL if g["id"] == game_id), None)
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    today = datetime.now().strftime("%Y-%m-%d")
    visit_key = f"game_visit_{game_id}"
    existing = db.query(TaskCompletion).filter(
        TaskCompletion.user_id == user.id,
        TaskCompletion.task_id == visit_key,
        TaskCompletion.date_key == today,
    ).first()

    if not existing:
        db.add(TaskCompletion(user_id=user.id, task_id=visit_key, date_key=today, points=3))
        result = _award_xp(db, user.id, 3)
        db.commit()
        return {"message": f"进入{game['name']}", "xp_awarded": 3, "first_visit_today": True, **result}

    return {"message": f"回到{game['name']}", "first_visit_today": False}


# ==================== BREATHING GAME ====================
@game_router.post("/breathing/complete")
def complete_breathing(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Complete a breathing exercise session."""
    user, db = user_and_db
    rounds = data.get("rounds", 4)
    score = data.get("score", 0)  # accuracy score 0-100
    xp = min(rounds * 5 + int(score / 10), 50)

    result = _award_xp(db, user.id, xp)
    return {"message": f"完成{rounds}轮呼吸练习", "xp_awarded": xp, "rounds": rounds, "score": score, **result}


# ==================== WORRY CRUSHER ====================
@game_router.post("/worry/submit")
def submit_worry(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Submit and 'crush' worries."""
    user, db = user_and_db
    count = data.get("count", 0)
    xp = min(count * 3, 30)
    result = _award_xp(db, user.id, xp)
    return {"message": f"粉碎了{count}个烦恼", "xp_awarded": xp, "crushes": count, **result}


# ==================== QUIZ GAME ====================
SLEEP_QUIZ = [
    {"id": 1, "q": "一个完整的睡眠周期大约多长时间？", "opts": ["60分钟", "90分钟", "120分钟", "45分钟"], "ans": 1, "explain": "每个睡眠周期约90分钟，包含浅睡、深睡、REM四个阶段。每晚4-6个完整周期。"},
    {"id": 2, "q": "以下哪项是CBT-I（失眠认知行为疗法）的核心技术？", "opts": ["药物治疗", "刺激控制疗法", "手术介入", "针灸"], "ans": 1, "explain": "刺激控制疗法是CBT-I的核心技术之一，通过重建床与睡眠的条件反射来改善失眠。"},
    {"id": 3, "q": "咖啡因的半衰期大约是多久？", "opts": ["1-2小时", "3-4小时", "5-6小时", "8-10小时"], "ans": 2, "explain": "咖啡因半衰期约5-6小时，下午喝的咖啡到晚上仍有一半在体内。建议下午2点后不摄入咖啡因。"},
    {"id": 4, "q": "最佳卧室温度是多少？", "opts": ["25-28°C", "18-22°C", "10-15°C", "28-30°C"], "ans": 1, "explain": "18-22°C是最佳睡眠温度。核心体温下降是入睡的关键信号，凉爽环境有助于深度睡眠。"},
    {"id": 5, "q": "蓝光对睡眠的主要影响是什么？", "opts": ["促进褪黑素分泌", "抑制褪黑素分泌", "帮助入睡", "没有影响"], "ans": 1, "explain": "蓝光（480nm）抑制松果体分泌褪黑素，延迟生物钟。睡前1-2小时应减少屏幕使用。"},
    {"id": 6, "q": "4-7-8呼吸法中，吸气应该持续几秒？", "opts": ["8秒", "7秒", "4秒", "10秒"], "ans": 2, "explain": "4-7-8呼吸法：鼻子吸气4秒，屏息7秒，嘴巴呼气8秒。缓慢呼气激活迷走神经。"},
    {"id": 7, "q": "REM睡眠的主要功能是什么？", "opts": ["身体修复", "记忆巩固和梦境", "免疫增强", "骨骼生长"], "ans": 1, "explain": "REM（快速眼动）睡眠阶段大脑高度活跃，是梦境发生期，对记忆巩固和情绪调节至关重要。"},
    {"id": 8, "q": "刺激控制疗法的核心原则是什么？", "opts": ["多躺在床上休息", "床只用于睡眠和性生活", "在床上工作提高效率", "躺到睡着为止"], "ans": 1, "explain": "刺激控制疗法六原则之首：床只用于睡眠和性生活。不玩手机、不工作，强化床=睡眠的条件反射。"},
    {"id": 9, "q": "哪种食物天然含有褪黑素？", "opts": ["西红柿", "樱桃", "土豆", "黄瓜"], "ans": 1, "explain": "樱桃是少数天然含有褪黑素的水果。温牛奶、香蕉、杏仁也含有助眠的营养素。"},
    {"id": 10, "q": "睡眠限制疗法的目的是什么？", "opts": ["减少总睡眠时间", "提高睡眠效率", "增加失眠焦虑", "消除所有睡眠"], "ans": 1, "explain": "睡眠限制疗法通过压缩床上时间来增加睡眠驱动力，提高睡眠效率（实际睡眠÷床上时间）。"},
    {"id": 11, "q": "以下哪种行为最有利于建立规律作息？", "opts": ["周末补觉", "固定起床时间", "困了就睡不固定", "每天睡到自然醒"], "ans": 1, "explain": "睡眠专家一致认为：固定起床时间（误差<30分钟）比固定入睡时间更重要。即使在周末也不要赖床超过1小时。"},
    {"id": 12, "q": "酒精对睡眠的实际影响是？", "opts": ["帮助深度睡眠", "破坏REM和深度睡眠", "没有影响", "延长深睡时间"], "ans": 1, "explain": "酒精虽然助入睡，但会破坏REM睡眠和后半段的深度睡眠。借酒助眠得不偿失。"},
    {"id": 13, "q": "人体生物钟的主时钟位于哪个脑区？", "opts": ["松果体", "视交叉上核(SCN)", "下丘脑", "前额叶皮层"], "ans": 1, "explain": "视交叉上核(SCN)是哺乳动物的主生物钟，位于下丘脑，通过视网膜接收的光信号进行校准。"},
    {"id": 14, "q": "睡前多长时间应该避免剧烈运动？", "opts": ["30分钟", "1小时", "2-3小时", "不需要避免"], "ans": 2, "explain": "睡前2-3小时内避免剧烈运动。剧烈运动使心率、体温和皮质醇升高，不利于入睡。轻度瑜伽拉伸例外。"},
    {"id": 15, "q": "慢性失眠的定义是每周至少发生几次，持续至少多久？", "opts": ["每周1次，持续1周", "每周3次，持续3个月", "每周2次，持续1个月", "每天，持续1周"], "ans": 1, "explain": "慢性失眠的临床诊断标准是：每周至少3次，持续至少3个月。急性失眠则短于3个月。"},
    {"id": 16, "q": "哪种食物含有丰富的色氨酸（褪黑素前体）？", "opts": ["苹果", "火鸡肉", "土豆", "生菜"], "ans": 1, "explain": "火鸡肉、鸡肉、牛奶、鸡蛋都富含色氨酸。色氨酸是合成血清素和褪黑素的关键氨基酸。"},
    {"id": 17, "q": "睡眠呼吸暂停的主要症状不包括？", "opts": ["打鼾", "白天过度嗜睡", "睡眠中呼吸暂停", "失眠"], "ans": 3, "explain": "睡眠呼吸暂停的主要症状包括：响亮打鼾、睡眠中呼吸暂停（被目击）、白天过度嗜睡、晨起头痛。虽然可导致失眠，但失眠本身不是主要诊断症状。"},
    {"id": 18, "q": "正念冥想帮助睡眠的核心机制是什么？", "opts": ["强制清空大脑", "减少思维反刍和降低生理唤起", "增加身体疲劳", "改变睡眠周期结构"], "ans": 1, "explain": "正念冥想通过减少思维反刍（反复想同一件事）和降低生理唤起水平（心跳、血压），帮助打破失眠的焦虑循环。"},
    {"id": 19, "q": "睡前使用电子屏幕的蓝光主要影响哪种激素？", "opts": ["皮质醇", "褪黑素", "肾上腺素", "生长激素"], "ans": 1, "explain": "蓝光（波长约480nm）抑制松果体分泌褪黑素。褪黑素是调节睡眠-觉醒节律的关键激素，在黑暗中分泌增加。"},
    {"id": 20, "q": "睡眠效率的计算公式是什么？", "opts": ["实际睡眠时间÷在床上时间×100%", "在床上时间÷实际睡眠时间×100%", "深睡时间÷总睡眠时间×100%", "REM时间÷总睡眠时间×100%"], "ans": 0, "explain": "睡眠效率=实际睡眠时间÷床上时间×100%。正常>85%。睡眠限制疗法通过压缩床上时间来提高睡眠效率。"},
    {"id": 21, "q": "以下关于午睡的建议哪个是正确的？", "opts": ["午睡越长越好", "午睡不超过30分钟", "下午3点后午睡最好", "每天必须午睡"], "ans": 1, "explain": "午睡不超过30分钟（20-30分钟最佳），避免进入深睡导致醒来昏沉。下午2点后不建议午睡以免影响夜间睡眠。"},
    {"id": 22, "q": "渐进式肌肉放松法的操作顺序是？", "opts": ["从脚到头", "从头到脚", "先背部再四肢", "只放松头部"], "ans": 1, "explain": "渐进式肌肉放松法通常从头部/面部开始，逐步向下到脚趾。每个肌群先紧张5秒，再放松15秒。也可从脚开始，顺序不影响效果。"},
    {"id": 23, "q": "褪黑素在人体内主要由哪个器官分泌？", "opts": ["肝脏", "松果体", "肾上腺", "甲状腺"], "ans": 1, "explain": "褪黑素由大脑中的松果体分泌，在黑暗中释放，光线（尤其是蓝光）会抑制其分泌。"},
    {"id": 24, "q": "睡眠限制疗法中，初始床上时间如何确定？", "opts": ["固定6小时", "平均实际睡眠时间+30分钟", "用户自己决定", "8小时"], "ans": 1, "explain": "初始床上时间=过去一周平均实际睡眠时间+30分钟（最少不低于5.5小时）。当睡眠效率>90%连续3天时，增加15分钟。"},
    {"id": 25, "q": "婴儿的睡眠周期约多长？", "opts": ["90分钟", "50-60分钟", "120分钟", "30分钟"], "ans": 1, "explain": "婴儿的睡眠周期约50-60分钟，比成年人的90分钟短。随着年龄增长，睡眠周期逐渐延长至90分钟左右。"},
    {"id": 26, "q": "以下哪个不属于CBT-I的五大核心组件？", "opts": ["刺激控制", "睡眠限制", "药物治疗", "认知疗法"], "ans": 2, "explain": "CBT-I五大核心组件：刺激控制、睡眠限制、认知疗法、放松训练、睡眠卫生教育。药物治疗不属于CBT-I。"},
    {"id": 27, "q": "睡前洗热水澡为什么有助于入睡？", "opts": ["热水使身体疲劳", "体温先升后降触发睡意", "水压按摩作用", "心理安慰"], "ans": 1, "explain": "热水浴使体表血管扩张，离开热水后体表散热，核心体温快速下降。核心体温下降是入睡的关键生理信号。"},
    {"id": 28, "q": "深睡(N3)阶段的主要功能是什么？", "opts": ["梦境发生", "身体修复和免疫增强", "记忆编码", "情绪处理"], "ans": 1, "explain": "深睡期(N3)是身体修复的黄金时间：生长激素分泌、免疫系统增强、细胞修复、能量恢复。梦境主要发生在REM阶段。"},
    {"id": 29, "q": "健康的年轻人REM睡眠占总睡眠的比例约为？", "opts": ["5-10%", "20-25%", "50-60%", "0-5%"], "ans": 1, "explain": "REM睡眠约占成年人总睡眠的20-25%。深睡(N3)占15-25%，浅睡(N2)占45-55%，入睡期(N1)占5%。"},
    {"id": 30, "q": "社交时差指的是什么？", "opts": ["与不同时区的人社交", "周末与工作日起床时间差异超过1小时", "社交媒体使用导致的晚睡", "跨国旅行时差"], "ans": 1, "explain": "社交时差指周末比工作日晚起超过1小时，相当于每周经历一次跨时区旅行。保持固定起床时间是预防社交时差的关键。"},
    {"id": 31, "q": "哪种维生素对褪黑素合成最重要？", "opts": ["维生素C", "维生素B6", "维生素D", "维生素E"], "ans": 1, "explain": "维生素B6是色氨酸转化为血清素、进而合成褪黑素的关键辅酶。富含B6的食物包括香蕉、鸡肉、鱼类。"},
    {"id": 32, "q": "睡眠中的'20分钟法则'是指什么？", "opts": ["睡前锻炼20分钟", "躺下20分钟睡不着就起来", "午睡20分钟", "每天提前20分钟睡觉"], "ans": 1, "explain": "刺激控制疗法的核心原则之一：躺下约20分钟仍无法入睡时，起床去另一个房间做轻松的活动，直到有困意再回床上。"},
    {"id": 33, "q": "腺苷在睡眠调节中的作用是什么？", "opts": ["促进觉醒", "积累睡眠压力", "抑制褪黑素", "增加REM睡眠"], "ans": 1, "explain": "腺苷是睡眠压力(睡眠驱动力)的关键物质。清醒时间越长，大脑中腺苷积累越多，睡眠压力越大。咖啡因通过阻断腺苷受体起作用。"},
    {"id": 34, "q": "身体扫描冥想的正确做法是？", "opts": ["快速浏览全身不思考", "依次将注意力放在每个身体部位，觉察感觉而不评判", "想象自己不在身体里", "用意识控制身体温度"], "ans": 1, "explain": "身体扫描是依次将注意力放在身体各部位（通常从脚开始到头顶），觉察那里的感觉而不试图改变任何东西。"},
    {"id": 35, "q": "以下哪项不是良好的睡眠卫生习惯？", "opts": ["保持卧室凉爽暗静", "睡前使用手机放松", "固定时间起床", "白天运动"], "ans": 1, "explain": "睡前使用手机是常见的睡眠卫生问题。蓝光抑制褪黑素，内容刺激使大脑兴奋，都不利于入睡。"},
    {"id": 36, "q": "REM睡眠的行为特征是什么？", "opts": ["身体完全静止", "快速眼动和肌肉麻痹", "频繁翻身", "梦游"], "ans": 1, "explain": "REM睡眠的特征是：快速眼动(Rapid Eye Movement)、全身骨骼肌麻痹(防止做出梦中动作)、大脑高度活跃、心率呼吸不规则。"},
    {"id": 37, "q": "昼夜节律周期在没有光照的情况下大约多长？", "opts": ["恰好24小时", "略长于24小时(约24.2小时)", "略短于24小时(约23.5小时)", "25-26小时"], "ans": 1, "explain": "人类内源性昼夜节律周期约24.2小时（略长于24小时）。因此每天需要光照信号来「校准」生物钟，否则会逐渐推迟。"},
    {"id": 38, "q": "焦虑和失眠之间的关系通常是？", "opts": ["单向的：焦虑导致失眠", "单向的：失眠导致焦虑", "「双向循环的」", "没有关系"], "ans": 2, "explain": "焦虑和失眠是双向循环关系：焦虑让人睡不着，睡眠不足又增加焦虑。CBT-I通过打破这个循环来改善两者。"},
    {"id": 39, "q": "镁元素对睡眠的主要作用是什么？", "opts": ["刺激肾上腺素", "激活GABA受体，帮助神经放松", "增加心率", "抑制褪黑素"], "ans": 1, "explain": "镁通过激活GABA受体来帮助神经系统放松。富含镁的食物包括：菠菜、杏仁、南瓜籽、黑巧克力。"},
    {"id": 40, "q": "睡眠中的'微觉醒'是什么？", "opts": ["闹钟叫醒", "夜间短暂觉醒（3-15秒），本人通常不记得", "早上半梦半醒状态", "故意设置的短暂觉醒"], "ans": 1, "explain": "微觉醒是睡眠中持续3-15秒的短暂觉醒，每晚正常发生数十次。本人通常不记得，但频繁的微觉醒会降低睡眠质量。"},
    {"id": 41, "q": "以下哪种颜色灯光对褪黑素影响最小？", "opts": ["蓝色", "白色", "红色", "绿色"], "ans": 2, "explain": "红光（波长>600nm）对褪黑素的抑制作用最小。如果需要夜灯，使用红色灯是最佳选择。蓝光(480nm)抑制作用最强。"},
    {"id": 42, "q": "矛盾意向法的操作方式是什么？", "opts": ["强迫自己快速入睡", "保持清醒，不去试图入睡", "吃安眠药", "数羊"], "ans": 1, "explain": "矛盾意向法是CBT-I技术：主动尝试保持清醒而不是努力入睡。这减少了入睡焦虑和表现压力，反而更容易自然入睡。"},
    {"id": 43, "q": "老年人睡眠结构的主要变化是什么？", "opts": ["需要更多睡眠", "深睡(N3)和REM减少，夜间觉醒增多", "睡眠周期变长", "完全不需要REM睡眠"], "ans": 1, "explain": "随着年龄增长，深睡(N3)时间显著减少，REM略有减少，夜间觉醒次数增多。但总睡眠需求(7-8h)变化不大。"},
    {"id": 44, "q": "安眠药(BZD类)对睡眠结构的主要影响是什么？", "opts": ["增加深睡", "减少深睡和REM，改变睡眠结构", "无影响", "增加REM"], "ans": 1, "explain": "苯二氮卓类安眠药虽然缩短入睡时间，但会减少深睡(N3)和REM睡眠，长期使用可能产生依赖和耐受。CBT-I是国际推荐的一线治疗方案。"},
    {"id": 45, "q": "睡眠日记应记录的主要内容不包括？", "opts": ["入睡时间和起床时间", "夜间醒来的次数和时长", "白天的困倦程度", "梦的具体情节"], "ans": 3, "explain": "睡眠日记通常记录：入睡时间、起床时间、入睡所需时间、夜间觉醒次数和时长、白天困倦程度、咖啡因/酒精摄入等。梦的具体情节属于可选内容。"},
    {"id": 46, "q": "光照疗法主要用于治疗哪种睡眠问题？", "opts": ["失眠", "昼夜节律紊乱（如睡眠相位延迟）", "睡眠呼吸暂停", "梦游"], "ans": 1, "explain": "光照疗法主要用于昼夜节律紊乱，如睡眠相位延迟综合征（晚睡晚起）。通过早晨暴露于强光来提前生物钟。"},
    {"id": 47, "q": "孕期睡眠的主要干扰因素不包括？", "opts": ["频繁起夜", "身体不适和胎动", "呼吸变化", "甲状腺功能亢进"], "ans": 3, "explain": "孕期常见睡眠干扰包括：频繁起夜(子宫压迫膀胱)、身体不适和胎动、激素变化、呼吸变化(后期)。甲状腺问题不是普遍因素。"},
    {"id": 48, "q": "持续睡眠不足对免疫系统的影响是？", "opts": ["增强免疫力", "抑制免疫功能，增加感染风险", "没有影响", "只影响老年人"], "ans": 1, "explain": "持续睡眠不足(少于6小时/晚)会抑制免疫系统：减少自然杀伤细胞活性、降低抗体产生、增加炎症因子。充足睡眠是最好的免疫力保障。"},
    {"id": 49, "q": "关于儿童睡眠，以下哪项是错误的？", "opts": ["儿童比成人需要更多睡眠", "睡前固定仪式对儿童很重要", "儿童不需要规律睡眠", "屏幕时间影响儿童入睡"], "ans": 2, "explain": "儿童比成人更需要规律睡眠！固定就寝时间、睡前仪式（洗澡-读书-关灯）、限制屏幕时间，对儿童睡眠至关重要。"},
    {"id": 50, "q": "完成21天睡眠改善计划后，防止复发的最佳策略是？", "opts": ["不再关注睡眠", "守住3项基线（固定起床+睡前仪式+户外活动）+定期记录", "每晚吃安眠药", "完全按计划再来一遍"], "ans": 1, "explain": "长期维持策略：守住不可协商的3项基线（固定起床时间、睡前1小时远离屏幕、每天户外活动）+每月记录一周睡眠日志。不苛求完美，80%的晚上足够好就是成功。"},
]

@game_router.get("/quiz/questions")
def get_quiz_questions():
    """Get 5 random sleep quiz questions."""
    import random as _rand
    questions = _rand.sample(SLEEP_QUIZ, min(5, len(SLEEP_QUIZ)))
    # Return without answers
    return {"questions": [{"id": q["id"], "q": q["q"], "opts": q["opts"]} for q in questions]}

@game_router.post("/quiz/submit")
def submit_quiz(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Submit quiz answers and get score."""
    user, db = user_and_db
    answers = data.get("answers", {})  # {question_id: selected_option_index}
    correct = 0
    results = []
    for qid_str, selected in answers.items():
        qid = int(qid_str)
        q = next((q for q in SLEEP_QUIZ if q["id"] == qid), None)
        if q:
            is_correct = selected == q["ans"]
            if is_correct: correct += 1
            results.append({"id": qid, "correct": is_correct, "explain": q["explain"]})

    xp = correct * 5 + (10 if correct >= 5 else 0)
    result = _award_xp(db, user.id, xp)

    # Award puzzle fragments for correct answers
    fragments = min(correct, 12)

    return {
        "message": f"答对{correct}/{len(answers)}题",
        "correct": correct, "total": len(answers),
        "xp_awarded": xp,
        "fragments_earned": fragments,
        "results": results,
        **result,
    }


# ==================== SOUNDSCAPE GAME ====================
SOUND_LIBRARY = [
    {"id": "rain", "name": "雨声", "icon": "🌧️", "color": "#3498DB",
     "audio_url": "https://cdn.freesound.org/previews/612/612093_11834222-lq.mp3",
     "backup_url": "https://cdn.freesound.org/previews/459/459283_9104818-lq.mp3"},
    {"id": "wind", "name": "风声", "icon": "💨", "color": "#95A5A6",
     "audio_url": "https://cdn.freesound.org/previews/171/171106_2710745-lq.mp3"},
    {"id": "fire", "name": "篝火", "icon": "🔥", "color": "#E67E22",
     "audio_url": "https://cdn.freesound.org/previews/250/250368_4486188-lq.mp3"},
    {"id": "stream", "name": "溪流", "icon": "💧", "color": "#1ABC9C",
     "audio_url": "https://cdn.freesound.org/previews/142/142747_2618409-lq.mp3"},
    {"id": "thunder", "name": "远雷", "icon": "⛈️", "color": "#8E44AD",
     "audio_url": "https://cdn.freesound.org/previews/524/524499_10189792-lq.mp3"},
    {"id": "birds", "name": "鸟鸣", "icon": "🐦", "color": "#2ECC71",
     "audio_url": "https://cdn.freesound.org/previews/542/542087_12499964-lq.mp3"},
    {"id": "waves", "name": "海浪", "icon": "🌊", "color": "#2980B9",
     "audio_url": "https://cdn.freesound.org/previews/173/173283_3470481-lq.mp3"},
    {"id": "crickets", "name": "蟋蟀", "icon": "🦗", "color": "#F39C12",
     "audio_url": "https://cdn.freesound.org/previews/115/115157_249337-lq.mp3"},
    {"id": "white_noise", "name": "白噪音", "icon": "📡", "color": "#7F8C8D",
     "audio_url": "https://cdn.freesound.org/previews/543/543030_1273224-lq.mp3"},
    {"id": "heartbeat", "name": "心跳", "icon": "💓", "color": "#E74C3C",
     "audio_url": "https://cdn.freesound.org/previews/60/60744_721195-lq.mp3"},
    {"id": "bells", "name": "风铃", "icon": "🔔", "color": "#F1C40F",
     "audio_url": "https://cdn.freesound.org/previews/180/180100_1528790-lq.mp3"},
    {"id": "bamboo", "name": "竹林", "icon": "🎋", "color": "#27AE60",
     "audio_url": "https://cdn.freesound.org/previews/414/414629_1505067-lq.mp3"},
]

DEFAULT_PRESETS = [
    {"id": "p1", "name": "温柔入眠", "channels": {"rain": 60, "wind": 30, "birds": 20}, "author": "官方"},
    {"id": "p2", "name": "篝火夜话", "channels": {"fire": 70, "crickets": 40, "wind": 20}, "author": "官方"},
    {"id": "p3", "name": "海边冥想", "channels": {"waves": 65, "wind": 35, "birds": 15}, "author": "官方"},
    {"id": "p4", "name": "深山竹林", "channels": {"bamboo": 55, "stream": 45, "birds": 25, "bells": 15}, "author": "官方"},
    {"id": "p5", "name": "雷雨助眠", "channels": {"rain": 75, "thunder": 25, "wind": 30}, "author": "官方"},
    {"id": "p6", "name": "纯净白噪", "channels": {"white_noise": 50}, "author": "官方"},
]

@game_router.get("/soundscape")
def get_soundscape():
    """Get sound library, default presets, and user presets."""
    return {
        "sounds": SOUND_LIBRARY,
        "presets": DEFAULT_PRESETS,
    }

@game_router.post("/soundscape/save")
def save_soundscape(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Save a custom soundscape preset."""
    user, db = user_and_db
    name = data.get("name", "我的音景")
    channels = data.get("channels", {})
    xp = 10  # Award XP for first save
    result = _award_xp(db, user.id, xp)
    return {
        "message": f"音景「{name}」已保存",
        "preset": {"name": name, "channels": channels, "author": user.nickname or "用户"},
        "xp_awarded": xp,
        **result,
    }


# ==================== DREAM GARDEN ====================
DREAM_PLANTS = [
    {"id": "p1", "name": "薰衣草", "icon": "💜", "unlock_day": 1, "desc": "代表放松——第一株梦境植物"},
    {"id": "p2", "name": "月光花", "icon": "🌙", "unlock_day": 3, "desc": "只在夜晚绽放的神秘花朵"},
    {"id": "p3", "name": "安眠草", "icon": "🌿", "unlock_day": 7, "desc": "古人用于安神的草药"},
    {"id": "p4", "name": "梦之树", "icon": "🌳", "unlock_day": 14, "desc": "梦境花园的中心——茁壮成长的大树"},
    {"id": "p5", "name": "星芒花", "icon": "⭐", "unlock_day": 21, "desc": "21天坚持的奖励——璀璨的星芒"},
]

@game_router.get("/garden")
def get_garden(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get dream garden state."""
    user, db = user_and_db
    from app.models import ProgramProgress as PP, SleepRecord as SR
    from datetime import date

    pp = db.query(PP).filter(PP.user_id == user.id).first()
    program_day = pp.current_day if pp else 0

    _d = date.today()
    today = _d.strftime("%Y-%m-%d")
    today_record = db.query(SR).filter(SR.user_id == user.id, SR.diary_date == _d).first()
    today_tasks = db.query(TaskCompletion).filter(
        TaskCompletion.user_id == user.id, TaskCompletion.date_key == today
    ).count()

    # Resources based on today's activity
    water = (1 if today_record else 0) + (1 if today_tasks >= 2 else 0) + (1 if today_tasks >= 4 else 0)
    sunlight = 1 if today_record and today_record.bedtime and today_record.bedtime.hour < 23 else 0

    # Unlocked plants
    unlocked = [p for p in DREAM_PLANTS if program_day >= p["unlock_day"]]
    locked = [p for p in DREAM_PLANTS if program_day < p["unlock_day"]]

    # Today's garden tasks
    garden_tasks = [
        {"id": "record", "title": "记录今晚睡眠 🛏️", "done": today_record is not None, "reward": "+1💧"},
        {"id": "tasks", "title": "完成2个每日任务 ✅", "done": today_tasks >= 2, "reward": "+1💧"},
        {"id": "all_tasks", "title": "完成全部4个任务 🎯", "done": today_tasks >= 4, "reward": "+1💧"},
        {"id": "early_bed", "title": "23:00前上床入睡 🌙", "done": today_record is not None and today_record.bedtime and today_record.bedtime.hour < 23, "reward": "+1☀️"},
    ]

    return {
        "water": water, "sunlight": sunlight,
        "day": program_day,
        "plants_unlocked": len(unlocked),
        "plants_total": len(DREAM_PLANTS),
        "unlocked_plants": unlocked,
        "locked_plants": [{"id": p["id"], "name": p["name"], "icon": p["icon"], "unlock_day": p["unlock_day"], "desc": p["desc"]} for p in locked],
        "garden_tasks": garden_tasks,
        "tasks_done": sum(1 for t in garden_tasks if t["done"]),
    }


# ==================== SLEEP ADVENTURE ====================
ADVENTURE_CHAPTERS = [
    {"chapter": 1, "title": "失眠森林的入口", "boss": "焦虑怪", "hp": 100,
     "story": "你站在失眠森林的入口，迷雾中传来窸窣的声音。前方的路被一只巨大的「焦虑怪」挡住了——它是由你对睡眠的恐惧和担忧喂养长大的。\n\n要击败它，你需要使用刚刚学到的CBT-I技能：\n\n🔹 **认知重构**：识别并挑战你对睡眠的灾难化想法\n🔹 **刺激控制**：坚定地告诉大脑「床只用于睡觉」\n\n准备好了吗？深呼吸，然后面对你的第一个挑战。",
     "skill_required": "认知重构", "xp_reward": 30,
     "unlock_condition": "完成Day 1 课程"},
    {"chapter": 2, "title": "蓝光沼泽", "boss": "熬夜龙", "hp": 150,
     "story": "穿过森林，你来到了一片泛着诡异蓝光的沼泽。沼泽深处盘踞着「熬夜龙」——它用手机屏幕的蓝光迷惑旅人，让他们不知不觉刷到深夜。\n\n你需要用学到的技能对抗它：\n\n🔹 **数字化排毒**：识破蓝光的陷阱，保护你的褪黑素\n🔹 **睡前仪式**：用放松的仪式抵御屏幕的诱惑",
     "skill_required": "数字排毒", "xp_reward": 50,
     "unlock_condition": "完成Day 8 课程"},
    {"chapter": 3, "title": "咖啡因洞穴", "boss": "咖啡因巨魔", "hp": 200,
     "story": "深入地下，你发现了一座由咖啡杯堆砌的洞穴。洞穴的主人「咖啡因巨魔」用它的半衰期魔法让所有靠近的旅人下午2点后仍然精神亢奋。\n\n用你学到的技能来对抗：\n\n🔹 **饮食管理**：了解咖啡因的半衰期，选择正确的饮品\n🔹 **规律作息**：用固定的起床时间重建生物钟",
     "skill_required": "饮食管理", "xp_reward": 80,
     "unlock_condition": "完成Day 15 课程"},
]

@game_router.get("/adventure")
def get_adventure(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get adventure progress."""
    user, db = user_and_db
    from app.models import ProgramProgress as PP
    pp = db.query(PP).filter(PP.user_id == user.id).first()
    program_day = pp.current_day if pp else 0

    current_chapter = 0
    for ch in ADVENTURE_CHAPTERS:
        day_needed = 1 if ch["chapter"] == 1 else (8 if ch["chapter"] == 2 else 15)
        if program_day >= day_needed:
            current_chapter = ch["chapter"]

    return {
        "current_chapter": current_chapter,
        "total_chapters": len(ADVENTURE_CHAPTERS),
        "chapters": ADVENTURE_CHAPTERS,
        "progress_pct": round(current_chapter / len(ADVENTURE_CHAPTERS) * 100),
        "completed": current_chapter >= len(ADVENTURE_CHAPTERS),
    }

@game_router.post("/adventure/battle")
def adventure_battle(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Complete a boss battle and advance the adventure."""
    user, db = user_and_db
    chapter = data.get("chapter", 1)
    ch = next((c for c in ADVENTURE_CHAPTERS if c["chapter"] == chapter), None)
    if not ch:
        raise HTTPException(status_code=404, detail="章节不存在")

    result = _award_xp(db, user.id, ch["xp_reward"])
    return {
        "message": f"击败了{ch['boss']}！章节「{ch['title']}」完成！",
        "chapter": chapter,
        "boss_defeated": ch["boss"],
        "xp_awarded": ch["xp_reward"],
        **result,
    }


# ==================== RUNNER TEASER ====================
@game_router.post("/runner/reserve")
def reserve_runner(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Reserve/pre-register for the runner game."""
    user, db = user_and_db
    today = datetime.now().strftime("%Y-%m-%d")
    key = "runner_reserved"
    existing = db.query(TaskCompletion).filter(
        TaskCompletion.user_id == user.id, TaskCompletion.task_id == key
    ).first()
    if existing:
        return {"message": "已预约", "already": True}

    db.add(TaskCompletion(user_id=user.id, task_id=key, date_key=today, points=5))
    result = _award_xp(db, user.id, 10)
    db.commit()
    return {"message": "预约成功！上线时你将第一时间收到通知", "xp_awarded": 10, **result}


@game_router.post("/runner/complete")
def complete_runner(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Submit runner game score."""
    user, db = user_and_db
    score = data.get("score", 0)
    xp = min(50, max(5, score // 10))
    today = datetime.now().strftime("%Y-%m-%d")

    db.add(TaskCompletion(user_id=user.id, task_id="g_v_runner", date_key=today, points=5))
    result = _award_xp(db, user.id, xp)
    db.commit()
    return {
        "message": "成绩已记录",
        "score": score,
        "xp_awarded": xp,
        **result,
    }


# ==================== EMAIL VERIFICATION ====================
from app.models import EmailVerification


@auth_router.post("/send-verify-code")
def send_verify_code(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    import random as _random
    code = str(_random.randint(100000, 999999))
    db.query(EmailVerification).filter(EmailVerification.user_id == user.id, EmailVerification.verified == 0).delete()
    db.add(EmailVerification(user_id=user.id, email=user.email, code=code, expires_at=datetime.utcnow() + timedelta(minutes=10)))
    db.commit()
    # Production: send email via SMTP
    return {"message": "验证码已发送", "code": code}


@auth_router.post("/verify-email")
def verify_email(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    code = data.get("code", "")
    ev = db.query(EmailVerification).filter(EmailVerification.user_id == user.id, EmailVerification.code == code, EmailVerification.verified == 0, EmailVerification.expires_at > datetime.utcnow()).first()
    if not ev:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    ev.verified = 1
    user.email_verified = 1 if hasattr(user, 'email_verified') else user.__dict__.get('email_verified', 0)
    db.commit()
    return {"message": "邮箱验证成功"}


# ==================== USER SETTINGS ====================
from app.models import UserSettings as UserSettingsModel


@settings_router.get("")
def get_settings(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    s = db.query(UserSettingsModel).filter(UserSettingsModel.user_id == user.id).first()
    if not s:
        s = UserSettingsModel(user_id=user.id)
        db.add(s); db.commit(); db.refresh(s)
    return {"theme": s.theme, "language": s.language, "font_size": s.font_size, "show_xp_animations": s.show_xp_animations}


@settings_router.put("")
def update_settings(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    s = db.query(UserSettingsModel).filter(UserSettingsModel.user_id == user.id).first()
    if not s:
        s = UserSettingsModel(user_id=user.id)
        db.add(s)
    for f in ["theme", "language", "font_size", "show_xp_animations"]:
        if f in data: setattr(s, f, data[f])
    db.commit()
    return {"message": "设置已保存"}


# ==================== WECHAT OAUTH PREP ====================
@auth_router.post("/wechat-login")
def wechat_login(data: dict, db: Session = Depends(get_db)):
    """WeChat mini-program login via wx.login() code."""
    code = data.get("code", "")
    if not code:
        raise HTTPException(status_code=400, detail="需要微信登录code")

    # Production: exchange code with WeChat API
    wechat_openid = f"wx_openid_{code[:8]}"  # Simulated
    wechat_unionid = f"wx_union_{code[:8]}"

    # Find or create user
    user = db.query(User).filter(User.email == wechat_openid).first()
    if not user:
        user = User(username=f"wx_{code[:8]}", email=wechat_openid, hashed_password=hash_pw(wechat_openid), nickname="微信用户")
        db.add(user); db.commit(); db.refresh(user)

    return TokenPair(access_token=create_access_token({"sub": str(user.id)}), refresh_token=create_refresh_token({"sub": str(user.id)}))


# ==================== SLEEP STORE ====================
from app.models import SleepProduct


@store_router.get("/products")
def list_products(category: str = None):
    from app.database import SessionLocal
    db2 = SessionLocal()
    try:
        q = db2.query(SleepProduct).filter(SleepProduct.is_active == 1)
        if category: q = q.filter(SleepProduct.category == category)
        products = q.order_by(SleepProduct.sales.desc()).all()

        if not products:
            defaults = [
                ("智能遮光眼罩", "3D立体剪裁，零压感100%遮光", 9900, "眼罩", 100, 520),
                ("助眠香薰机", "超声波静音雾化，配薰衣草精油", 19900, "香薰", 50, 320),
                ("重力毯", "科学配重减压，模拟拥抱感", 29900, "寝具", 30, 180),
                ("白噪音音箱", "内置6种自然音景，定时关闭", 15900, "音箱", 40, 250),
                ("记忆棉枕", "慢回弹护颈，透气防螨", 12900, "枕头", 60, 410),
                ("褪黑素软糖", "天然草莓味，3mg/粒", 8900, "补充剂", 200, 680),
                ("睡眠耳塞", "降噪32dB，舒适佩戴", 3900, "耳塞", 300, 920),
                ("床头阅读灯", "暖光2700K，无蓝光设计", 6900, "灯具", 80, 150),
            ]
            for name, desc, price, cat, stock, sales in defaults:
                db2.add(SleepProduct(name=name, desc=desc, price=price, category=cat, stock=stock, sales=sales))
            db2.commit()
            products = db2.query(SleepProduct).order_by(SleepProduct.sales.desc()).all()

        return {"products": [{"id": p.id, "name": p.name, "desc": p.desc, "price": p.price, "price_yuan": round(p.price/100,2), "category": p.category, "stock": p.stock, "sales": p.sales, "rating": p.rating} for p in products]}
    finally:
        db2.close()


# ==================== SLEEP COURSES ====================
from app.models import SleepCourse, CourseEnrollment


@course_router.get("")
def list_courses():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        courses = db.query(SleepCourse).order_by(SleepCourse.enrolled.desc()).all()
        if not courses:
            defaults = [
                ("CBT-I认知行为疗法入门", "系统学习失眠非药物疗法", "王医生", 3.5, 7, 0),
                ("正念睡眠冥想", "8周正念课程改善睡眠", "李冥想导师", 4.0, 8, 0),
                ("睡眠卫生完全指南", "掌握科学睡眠的基础知识", "张教授", 2.0, 5, 0),
                ("深度睡眠的秘密", "如何增加深睡时长和比例", "刘研究员", 2.5, 6, 1),
                ("压力管理与睡眠", "学会压力管理提升睡眠质量", "陈心理师", 3.0, 6, 1),
            ]
            for title, desc, inst, dur, chapters, premium in defaults:
                db.add(SleepCourse(title=title, desc=desc, instructor=inst, duration_hours=dur, chapters=chapters, is_premium=premium))
            db.commit()
            courses = db.query(SleepCourse).order_by(SleepCourse.enrolled.desc()).all()
        return {"courses": [{"id": c.id, "title": c.title, "desc": c.desc, "instructor": c.instructor, "duration_hours": c.duration_hours, "chapters": c.chapters, "price": c.price, "enrolled": c.enrolled, "rating": c.rating, "is_premium": c.is_premium} for c in courses]}
    finally:
        db.close()


@course_router.post("/{course_id}/enroll")
def enroll_course(course_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    course = db.query(SleepCourse).filter(SleepCourse.id == course_id).first()
    if not course: raise HTTPException(status_code=404, detail="课程不存在")
    existing = db.query(CourseEnrollment).filter(CourseEnrollment.user_id == user.id, CourseEnrollment.course_id == course_id).first()
    if existing: return {"message": "已报名"}
    db.add(CourseEnrollment(user_id=user.id, course_id=course_id))
    course.enrolled = (course.enrolled or 0) + 1
    db.commit()
    return {"message": "报名成功"}


# ==================== BI ANALYTICS ====================
@admin_router.get("/bi/overview")
def bi_overview(admin_data: Tuple[User, Session] = Depends(_require_admin)):
    """Business intelligence overview."""
    _, db = admin_data
    from sqlalchemy import func as sa_func
    now = datetime.now()

    total_users = db.query(sa_func.count(User.id)).scalar()
    # Retention: users active in last 30 days vs total
    active_30d = db.query(sa_func.count(sa_func.distinct(SleepRecord.user_id))).filter(SleepRecord.bedtime >= now - timedelta(days=30)).scalar()
    retention = round(active_30d / total_users * 100, 1) if total_users > 0 else 0

    # Revenue
    total_revenue = db.query(sa_func.sum(PaymentOrder.amount)).filter(PaymentOrder.status == "paid").scalar() or 0

    # Premium conversion
    premium_count = db.query(sa_func.count(Membership.id)).filter(Membership.tier.in_(["pro", "premium"])).scalar()
    conversion = round(premium_count / total_users * 100, 1) if total_users > 0 else 0

    # Average sleep score trend (last 12 weeks)
    weekly_scores = []
    for w in range(12):
        w_start = now - timedelta(days=(w+1)*7)
        w_end = now - timedelta(days=w*7)
        avg = db.query(sa_func.avg(SleepRecord.score)).filter(SleepRecord.bedtime >= w_start, SleepRecord.bedtime < w_end).scalar()
        weekly_scores.append({"week": f"W{12-w}", "avg_score": round(avg, 1) if avg else 0})

    return {
        "total_users": total_users, "active_users_30d": active_30d, "retention_rate": retention,
        "total_revenue": total_revenue, "revenue_yuan": round(total_revenue/100, 2),
        "premium_users": premium_count, "conversion_rate": conversion,
        "weekly_score_trend": weekly_scores,
    }


# ==================== REFERRAL ====================
from app.models import ReferralCode, ReferralRecord


@referral_router.get("/code")
def get_referral_code(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    rc = db.query(ReferralCode).filter(ReferralCode.user_id == user.id).first()
    if not rc:
        code = f"M{user.id:04d}{random.randint(100, 999)}"
        rc = ReferralCode(user_id=user.id, code=code)
        db.add(rc); db.commit(); db.refresh(rc)
    return {"code": rc.code, "invite_count": rc.invite_count, "reward_earned": rc.reward_earned, "reward_yuan": round(rc.reward_earned / 100, 2)}


@referral_router.post("/apply")
def apply_referral(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    code = data.get("code", "")
    rc = db.query(ReferralCode).filter(ReferralCode.code == code).first()
    if not rc: raise HTTPException(status_code=404, detail="邀请码无效")
    if rc.user_id == user.id: raise HTTPException(status_code=400, detail="不能邀请自己")

    existing = db.query(ReferralRecord).filter(ReferralRecord.invited_user_id == user.id).first()
    if existing: return {"message": "已被邀请过"}

    db.add(ReferralRecord(inviter_id=rc.user_id, invited_user_id=user.id))
    rc.invite_count += 1
    rc.reward_earned += 1000
    db.commit()

    # Award XP to inviter
    _award_xp(db, rc.user_id, 50)
    return {"message": "邀请码使用成功"}


# ==================== SLEEP DOCTORS ====================
from app.models import SleepDoctor, DoctorAppointment


@doctor_router.get("")
def list_doctors():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        doctors = db.query(SleepDoctor).filter(SleepDoctor.available == 1).all()
        if not doctors:
            defaults = [
                ("张伟明", "主任医师", "失眠症/CBT-I/睡眠呼吸暂停", 15, 19900),
                ("李安宁", "副主任医师", "睡眠障碍/昼夜节律/儿童睡眠", 10, 14900),
                ("王梦洁", "心理咨询师", "失眠CBT-I/焦虑/正念疗法", 8, 12900),
            ]
            for name, title, spec, exp, fee in defaults:
                db.add(SleepDoctor(name=name, title=title, specialty=spec, experience_years=exp, consult_fee=fee))
            db.commit()
            doctors = db.query(SleepDoctor).filter(SleepDoctor.available == 1).all()
        return {"doctors": [{"id": d.id, "name": d.name, "title": d.title, "specialty": d.specialty, "experience_years": d.experience_years, "rating": d.rating, "consult_fee": d.consult_fee, "fee_yuan": round(d.consult_fee/100, 2)} for d in doctors]}
    finally:
        db.close()


@doctor_router.post("/appointments")
def book_appointment(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    doctor_id = data.get("doctor_id")
    date_key = data.get("date_key")
    time_slot = data.get("time_slot")

    doctor = db.query(SleepDoctor).filter(SleepDoctor.id == doctor_id).first()
    if not doctor: raise HTTPException(status_code=404, detail="医生不存在")

    existing = db.query(DoctorAppointment).filter(DoctorAppointment.doctor_id == doctor_id, DoctorAppointment.date_key == date_key, DoctorAppointment.time_slot == time_slot, DoctorAppointment.status != "cancelled").first()
    if existing: raise HTTPException(status_code=400, detail="该时段已被预约")

    appt = DoctorAppointment(user_id=user.id, doctor_id=doctor_id, date_key=date_key, time_slot=time_slot, note=data.get("note", ""))
    db.add(appt); db.commit(); db.refresh(appt)
    return {"id": appt.id, "message": "预约成功", "doctor": doctor.name, "date": date_key, "time": time_slot}


@doctor_router.get("/appointments")
def get_appointments(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    appts = db.query(DoctorAppointment).filter(DoctorAppointment.user_id == user.id).order_by(DoctorAppointment.date_key.desc()).all()
    return {"appointments": [{"id": a.id, "doctor_name": (db.query(SleepDoctor).filter(SleepDoctor.id == a.doctor_id).first().name if a.doctor_id else "未知"), "date": a.date_key, "time": a.time_slot, "status": a.status} for a in appts]}


# ==================== 21天睡眠改善计划 ====================
from app.services import get_21day_course, get_21day_meta, get_day_content


@program_router.get("/21day")
def get_21day_program():
    """Get the full 21-day program overview with meta."""
    meta = get_21day_meta()
    days = get_21day_course()
    return {
        "meta": meta,
        "weeks": [
            {"week": w, "title": f"第{w}周",
             "days": [{"day": d["day"], "title": d["title"], "subtitle": d["subtitle"],
                       "category": d["category"], "video_duration": d["video_duration"],
                       "xp": d["xp"]} for d in days if d["week"] == w]}
            for w in range(1, 4)
        ],
        "total_days": 21,
    }


@program_router.get("/21day/today")
def get_today_program(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get today's program content based on user's progress."""
    user, db = user_and_db
    from app.models import ProgramProgress as PP

    pp = db.query(PP).filter(PP.user_id == user.id).first()
    completed = pp.current_day if pp else 0
    current_day = min(21, completed + 1)

    content = get_day_content(current_day)
    if not content:
        raise HTTPException(status_code=404, detail="课程内容不存在")

    completed_days = []
    if completed > 0:
        all_days = get_21day_course()
        completed_days = [{"day": d["day"], "title": d["title"]} for d in all_days[:completed]]

    return {
        "current_day": current_day,
        "content": content,
        "completed_days": completed_days,
        "completed_count": len(completed_days),
        "total_days": 21,
        "progress_pct": round(len(completed_days) / 21 * 100),
        "is_completed": completed >= 21,
    }


@program_router.post("/21day/start")
def start_program(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Start the 21-day program."""
    return complete_day({"day": 0}, user_and_db)


@program_router.post("/21day/complete")
def complete_day(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Mark today's lesson as complete and advance progress."""
    user, db = user_and_db
    day = data.get("day", 1)

    from app.models import ProgramProgress as PP

    pp = db.query(PP).filter(PP.user_id == user.id).first()
    if not pp:
        pp = PP(user_id=user.id, current_day=0)
        db.add(pp)
        db.commit(); db.refresh(pp)

    if day == 0:
        # Just initializing the program
        return {"message": "计划已启动", "started": True}

    if day > pp.current_day + 1:
        raise HTTPException(status_code=400, detail="请按顺序完成每天课程")

    if day == pp.current_day + 1:
        pp.current_day = day
        if day >= 21:
            pp.completed_at = datetime.utcnow()
        db.commit()

        # Award XP
        course = get_day_content(day)
        xp_amount = course["xp"] if course else 15
        result = _award_xp(db, user.id, xp_amount)

        return {
            "message": f"第{day}天完成！",
            "day": day,
            "xp_awarded": xp_amount,
            "progress_pct": round(day / 21 * 100),
            "is_completed": day >= 21,
            **result,
        }
    else:
        return {"message": "该天已完成", "already": True, "day": day}


@program_router.get("/21day/progress")
def get_program_progress(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get user's 21-day program progress summary."""
    user, db = user_and_db
    from app.models import ProgramProgress as PP
    pp = db.query(PP).filter(PP.user_id == user.id).first()

    if not pp or pp.current_day == 0:
        return {"started": False, "completed": 0, "total": 21, "progress_pct": 0, "current_day": 1}

    return {
        "started": True,
        "completed": pp.current_day,
        "total": 21,
        "progress_pct": round(pp.current_day / 21 * 100),
        "current_day": min(21, pp.current_day + 1),
        "is_completed": pp.current_day >= 21,
        "started_at": str(pp.started_at) if pp.started_at else None,
    }


@program_router.get("/21day/{day}")
def get_day_detail(day: int):
    """Get content for a specific day (1-21)."""
    content = get_day_content(day)
    if not content:
        raise HTTPException(status_code=404, detail="该天课程不存在")
    return content


# ==================== COURSE CHAPTERS ====================
from app.models import CourseChapter


@course_router.get("/{course_id}/chapters")
def get_chapters(course_id: int):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        chapters = db.query(CourseChapter).filter(CourseChapter.course_id == course_id).order_by(CourseChapter.order_num).all()
        if not chapters:
            # Seed chapter content for first 3 courses
            seed = {
                1: [("认识失眠", "失眠是最常见的睡眠障碍...", 15), ("CBT-I理论基础", "认知行为疗法(CBT-I)是国际推荐...", 20), ("刺激控制疗法详解", "床只能用于睡眠和性生活...", 18)],
                2: [("正念入门", "正念(Mindfulness)是一种有意识地...", 12), ("身体扫描练习", "身体扫描是最经典的正念练习...", 15)],
                3: [("睡眠环境优化", "打造理想睡眠环境的第一步...", 10), ("饮食与睡眠", "你吃的东西直接影响睡眠质量...", 10)],
            }
            if course_id in seed:
                for i, (title, content, dur) in enumerate(seed[course_id]):
                    db.add(CourseChapter(course_id=course_id, order_num=i+1, title=title, content=content, duration_minutes=dur))
                db.commit()
            chapters = db.query(CourseChapter).filter(CourseChapter.course_id == course_id).order_by(CourseChapter.order_num).all()
        return {"chapters": [{"id": c.id, "order": c.order_num, "title": c.title, "content": c.content[:200], "duration_minutes": c.duration_minutes} for c in chapters]}
    finally:
        db.close()


@course_router.get("/{course_id}/chapters/{chapter_id}")
def get_chapter_detail(course_id: int, chapter_id: int):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        c = db.query(CourseChapter).filter(CourseChapter.id == chapter_id, CourseChapter.course_id == course_id).first()
        if not c: raise HTTPException(status_code=404, detail="章节不存在")
        return {"id": c.id, "title": c.title, "content": c.content, "video_url": c.video_url, "duration_minutes": c.duration_minutes}
    finally:
        db.close()


# ==================== STORE CART + ORDERS ====================
from app.models import StoreCart, StoreOrder


@store_router.get("/cart")
def get_cart(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    items = db.query(StoreCart).filter(StoreCart.user_id == user.id).all()
    result = []
    for item in items:
        product = db.query(SleepProduct).filter(SleepProduct.id == item.product_id).first()
        if product:
            result.append({"id": item.id, "product": {"id": product.id, "name": product.name, "price": product.price, "price_yuan": round(product.price/100, 2), "image_url": product.image_url}, "quantity": item.quantity})
    total = sum(r["product"]["price"] * r["quantity"] for r in result)
    return {"items": result, "total": total, "total_yuan": round(total/100, 2)}


@store_router.post("/cart")
def add_to_cart(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    pid = data.get("product_id")
    existing = db.query(StoreCart).filter(StoreCart.user_id == user.id, StoreCart.product_id == pid).first()
    if existing:
        existing.quantity += 1
    else:
        db.add(StoreCart(user_id=user.id, product_id=pid))
    db.commit()
    return {"message": "已加入购物车"}


@store_router.delete("/cart/{item_id}")
def remove_from_cart(item_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    db.query(StoreCart).filter(StoreCart.id == item_id, StoreCart.user_id == user.id).delete()
    db.commit()
    return {"message": "已移除"}


@store_router.post("/orders")
def create_store_order(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    items = db.query(StoreCart).filter(StoreCart.user_id == user.id).all()
    if not items: raise HTTPException(status_code=400, detail="购物车为空")

    total = 0
    for item in items:
        p = db.query(SleepProduct).filter(SleepProduct.id == item.product_id).first()
        if p: total += p.price * item.quantity

    order_no = "S" + datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(100, 999))
    order = StoreOrder(order_no=order_no, user_id=user.id, total_amount=total, address=data.get("address", ""))
    db.add(order)
    db.query(StoreCart).filter(StoreCart.user_id == user.id).delete()
    db.commit(); db.refresh(order)
    return {"order_no": order.order_no, "total_amount": total, "total_yuan": round(total/100, 2), "status": order.status}


@store_router.get("/orders")
def get_store_orders(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get user's store order history."""
    user, db = user_and_db
    orders = db.query(StoreOrder).filter(StoreOrder.user_id == user.id).order_by(
        StoreOrder.created_at.desc()).limit(20).all()
    return {"orders": [{
        "id": o.id, "order_no": o.order_no,
        "total_amount": o.total_amount, "total_yuan": round(o.total_amount / 100, 2),
        "status": o.status, "address": o.address,
        "created_at": str(o.created_at) if o.created_at else None,
    } for o in orders]}


# ==================== SLEEP ENVIRONMENT ====================
from app.models import SleepEnvironment


@environment_router.post("/record")
def record_environment(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    dk = data.get("date_key", datetime.now().strftime("%Y-%m-%d"))
    existing = db.query(SleepEnvironment).filter(SleepEnvironment.user_id == user.id, SleepEnvironment.date_key == dk).first()
    if existing:
        for f in ["temperature", "humidity", "light_level", "noise_level", "source"]:
            if f in data: setattr(existing, f, data[f])
    else:
        db.add(SleepEnvironment(user_id=user.id, date_key=dk, temperature=data.get("temperature"), humidity=data.get("humidity"), light_level=data.get("light_level"), noise_level=data.get("noise_level"), source=data.get("source", "manual")))
    db.commit()
    return {"message": "环境数据已保存"}


@environment_router.get("/records")
def get_environment(days: int = 7, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    records = db.query(SleepEnvironment).filter(SleepEnvironment.user_id == user.id, SleepEnvironment.date_key >= cutoff).order_by(SleepEnvironment.date_key.desc()).all()
    return {"records": [{"date": r.date_key, "temperature": r.temperature, "humidity": r.humidity, "light_level": r.light_level, "noise_level": r.noise_level} for r in records]}


@environment_router.get("/insights")
def environment_insights(days: int = 30, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Correlate environment with sleep quality."""
    user, db = user_and_db
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    env_records = db.query(SleepEnvironment).filter(SleepEnvironment.user_id == user.id, SleepEnvironment.date_key >= cutoff).all()

    if not env_records:
        return {"insight": "暂无数据", "ideal": {"temperature": "18-22°C", "humidity": "40-60%", "light": "<5 lux", "noise": "<30 dB"}}

    avg_temp = sum(r.temperature for r in env_records if r.temperature) / max(sum(1 for r in env_records if r.temperature), 1)
    avg_humidity = sum(r.humidity for r in env_records if r.humidity) / max(sum(1 for r in env_records if r.humidity), 1)

    suggestions = []
    if avg_temp > 22: suggestions.append("卧室温度偏高，建议降到18-22°C")
    elif avg_temp < 16: suggestions.append("卧室温度偏低，建议升温到18-22°C")
    if avg_humidity < 30: suggestions.append("空气偏干燥，建议使用加湿器(40-60%)")
    elif avg_humidity > 70: suggestions.append("湿度过高，建议通风除湿")

    return {"avg_temperature": round(avg_temp, 1), "avg_humidity": round(avg_humidity, 1), "suggestions": suggestions or ["环境条件良好"], "ideal": {"temperature": "18-22°C", "humidity": "40-60%"}}


# ==================== DATA EXPORT & SEARCH ====================
from app.models import DataExport, SearchHistory


@data_router.post("/export")
def request_export(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Request full data export (GDPR compliance)."""
    user, db = user_and_db
    export = DataExport(user_id=user.id)
    db.add(export); db.commit()

    # Build export data
    export_data = {"user": {"username": user.username, "email": user.email, "nickname": user.nickname, "created_at": str(user.created_at)}}
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).all()
    export_data["sleep_records"] = [{"date": str(r.diary_date), "duration": r.duration_hours, "score": r.score} for r in records]
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    if profile: export_data["profile"] = {k: v for k, v in profile.__dict__.items() if not k.startswith("_") and k not in ("id", "user_id")}

    export.file_url = f"/exports/user_{user.id}_{datetime.now().strftime('%Y%m%d')}.json"
    export.status = "completed"
    export.completed_at = datetime.utcnow()
    db.commit()

    return {"message": "数据导出成功", "data": export_data, "download_url": export.file_url}


@data_router.post("/delete-account")
def delete_account(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Permanently delete user account and all data (GDPR Right to Erasure)."""
    user, db = user_and_db
    tables = [SleepRecord, HealthProfile, MoodRecord, ChatMessage, ChatSession, TaskCompletion, UserPoints, BadgeUnlock, PlanEnrollment, PlanCheckIn, SleepAssessment, SleepPost, PostComment, PostLike, Membership, PaymentOrder, PaymentRecord, ReferralCode, ReferralRecord, DoctorAppointment, CourseEnrollment, StoreCart, StoreOrder, SleepEnvironment, SearchHistory, UserLevel, UserSettings, EmailVerification, NotificationSetting, DataExport]
    for table in tables:
        db.query(table).filter(table.user_id == user.id).delete()
    db.query(User).filter(User.id == user.id).delete()
    db.commit()
    return {"message": "账户及所有数据已永久删除"}


@data_router.post("/search")
def search(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Global search across knowledge, courses, products."""
    user, db = user_and_db
    q = data.get("q", "").lower()
    if not q: return {"results": []}

    results = []
    # Search knowledge
    for a in KNOWLEDGE_ARTICLES:
        if q in a["title"].lower() or q in a["summary"].lower():
            results.append({"type": "article", "id": a["id"], "title": a["title"], "desc": a["summary"][:60]})

    # Search products
    products = db.query(SleepProduct).all()
    for p in products:
        if q in p.name.lower() or q in (p.desc or "").lower():
            results.append({"type": "product", "id": p.id, "title": p.name, "desc": (p.desc or "")[:60]})

    # Search courses
    courses = db.query(SleepCourse).all()
    for c in courses:
        if q in c.title.lower() or q in (c.desc or "").lower():
            results.append({"type": "course", "id": c.id, "title": c.title, "desc": (c.desc or "")[:60]})

    # Save search
    db.add(SearchHistory(user_id=user.id, query=q, result_count=len(results)))
    db.commit()
    return {"results": results[:20], "total": len(results)}


# ==================== ACHIEVEMENTS ====================
from app.models import Achievement

ACHIEVEMENT_DEFS = [
    {"key": "first_record", "title": "初次记录", "desc": "完成第一次睡眠记录", "icon": "📝"},
    {"key": "week_streak", "title": "连续一周", "desc": "连续7天记录睡眠", "icon": "🔥"},
    {"key": "month_streak", "title": "月度达人", "desc": "连续30天记录睡眠", "icon": "💪"},
    {"key": "score_80", "title": "高分之夜", "desc": "睡眠评分达到80分", "icon": "⭐"},
    {"key": "score_90", "title": "完美睡眠", "desc": "睡眠评分达到90分", "icon": "🌟"},
    {"key": "early_10", "title": "早睡先锋", "desc": "累计10次22:00前入睡", "icon": "🌙"},
    {"key": "chat_10", "title": "AI伙伴", "desc": "与AI对话10次", "icon": "🤖"},
    {"key": "plan_done", "title": "计划达人", "desc": "完成一个改善计划", "icon": "🎯"},
    {"key": "community_5", "title": "社区活跃", "desc": "发布5条社区动态", "icon": "💬"},
    {"key": "knowledge_10", "title": "知识探索者", "desc": "阅读10篇知识文章", "icon": "📚"},
]


@game_router.get("/achievements")
def get_achievements(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    from app.models import Achievement as _Ach
    unlocked = {a.achievement_key for a in db.query(_Ach).filter(_Ach.user_id == user.id).all()}
    return {"achievements": [{"key": a["key"], "title": a["title"], "desc": a["desc"], "icon": a["icon"], "unlocked": a["key"] in unlocked} for a in ACHIEVEMENT_DEFS], "unlocked_count": len(unlocked), "total": len(ACHIEVEMENT_DEFS)}


@game_router.post("/achievements/check")
def check_achievements(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Auto-check and unlock any new achievements."""
    user, db = user_and_db
    unlocked = {a.achievement_key for a in db.query(Achievement).filter(Achievement.user_id == user.id).all()}
    new_unlocks = []

    # Check conditions
    record_count = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).count()
    if "first_record" not in unlocked and record_count >= 1:
        new_unlocks.append("first_record")
    if "week_streak" not in unlocked and record_count >= 7:
        new_unlocks.append("week_streak")
    if "month_streak" not in unlocked and record_count >= 30:
        new_unlocks.append("month_streak")

    max_score = db.query(SleepRecord.score).filter(SleepRecord.user_id == user.id).order_by(SleepRecord.score.desc()).first()
    if max_score and max_score[0]:
        if "score_80" not in unlocked and max_score[0] >= 80: new_unlocks.append("score_80")
        if "score_90" not in unlocked and max_score[0] >= 90: new_unlocks.append("score_90")

    chat_count = db.query(ChatMessage).filter(ChatMessage.session.has(ChatSession.user_id == user.id)).count()
    if "chat_10" not in unlocked and chat_count >= 10: new_unlocks.append("chat_10")

    post_count = db.query(SleepPost).filter(SleepPost.user_id == user.id).count()
    if "community_5" not in unlocked and post_count >= 5: new_unlocks.append("community_5")

    for key in new_unlocks:
        ach = next((a for a in ACHIEVEMENT_DEFS if a["key"] == key), None)
        if ach:
            db.add(Achievement(user_id=user.id, achievement_key=key, title=ach["title"], desc=ach["desc"], icon=ach["icon"]))
    if new_unlocks: db.commit()

    return {"new_unlocks": new_unlocks, "total_unlocked": len(unlocked) + len(new_unlocks)}


# ==================== WEEKLY DIGEST ====================
from app.models import WeeklyDigest


@data_router.get("/digest")
def get_weekly_digest(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    existing = db.query(WeeklyDigest).filter(WeeklyDigest.user_id == user.id, WeeklyDigest.week_start == week_start).first()
    if existing:
        return {"digest": json.loads(existing.content) if existing.content else {}}

    # Generate digest
    cutoff = datetime.now() - timedelta(days=7)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).all()
    if not records:
        return {"digest": {"message": "本周暂无睡眠记录"}}

    avg_dur = round(sum(r.duration_hours or 0 for r in records) / len(records), 1)
    avg_score = round(sum(r.score for r in records) / len(records))
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    goal = profile.sleep_goal_hours if profile else 8.0

    digest = {
        "week": week_start,
        "avg_duration": avg_dur,
        "avg_score": avg_score,
        "goal": goal,
        "records_count": len(records),
        "best_night": max(records, key=lambda r: r.score or 0).diary_date if records else None,
        "message": f"本周平均睡眠{avg_dur}h，评分{avg_score}分。{'继续保持！' if avg_score >= 80 else '下周继续加油！'}",
    }

    db.add(WeeklyDigest(user_id=user.id, week_start=week_start, content=json.dumps(digest, default=str)))
    db.commit()
    return {"digest": digest}


# ==================== INTEGRATIONS ====================
from app.models import Integration


@integration_router.get("")
def list_integrations(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    platforms = ["apple_health", "google_fit", "fitbit", "oura"]
    connected = {i.platform: i for i in db.query(Integration).filter(Integration.user_id == user.id, Integration.is_active == 1).all()}
    return {"integrations": [{"platform": p, "name": {"apple_health": "Apple Health", "google_fit": "Google Fit", "fitbit": "Fitbit", "oura": "Oura Ring"}[p], "connected": p in connected, "last_sync": str(connected[p].last_sync) if p in connected and connected[p].last_sync else None} for p in platforms]}


@integration_router.post("/{platform}/connect")
def connect_integration(platform: str, data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    if platform not in ["apple_health", "google_fit", "fitbit", "oura"]:
        raise HTTPException(status_code=400, detail="不支持的平台")

    existing = db.query(Integration).filter(Integration.user_id == user.id, Integration.platform == platform).first()
    if existing:
        existing.access_token = data.get("access_token", "")
        existing.refresh_token = data.get("refresh_token", "")
        existing.is_active = 1
    else:
        db.add(Integration(user_id=user.id, platform=platform, access_token=data.get("access_token", ""), refresh_token=data.get("refresh_token", "")))
    db.commit()
    return {"message": f"已连接 {platform}"}


# ==================== COUPONS ====================
from app.models import Coupon, UserCoupon


@store_router.get("/coupons")
def list_coupons():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        coupons = db.query(Coupon).filter(Coupon.is_active == 1, Coupon.expires_at > datetime.utcnow() if True else True).all()
        if not coupons:
            defaults = [("SLEEP10", 10, 500), ("DREAM20", 20, 200), ("PREMIUM30", 30, 50)]
            for code, disc, max_u in defaults:
                db.add(Coupon(code=code, discount_percent=disc, max_uses=max_u, expires_at=datetime.utcnow() + timedelta(days=30)))
            db.commit()
            coupons = db.query(Coupon).filter(Coupon.is_active == 1).all()
        return {"coupons": [{"id": c.id, "code": c.code, "discount": c.discount_percent, "used": c.used_count, "max": c.max_uses} for c in coupons]}
    finally:
        db.close()


@store_router.post("/coupons/claim")
def claim_coupon(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    code = data.get("code", "")
    coupon = db.query(Coupon).filter(Coupon.code == code, Coupon.is_active == 1).first()
    if not coupon: raise HTTPException(status_code=404, detail="优惠券无效")
    if coupon.used_count >= coupon.max_uses: raise HTTPException(status_code=400, detail="已被领完")

    existing = db.query(UserCoupon).filter(UserCoupon.user_id == user.id, UserCoupon.coupon_id == coupon.id).first()
    if existing: raise HTTPException(status_code=400, detail="已领取过")

    db.add(UserCoupon(user_id=user.id, coupon_id=coupon.id))
    coupon.used_count += 1
    db.commit()
    return {"message": f"已领取 {coupon.discount_percent}% 折扣券"}


# ==================== AI: RECOMMENDATIONS + RISK ====================
from app.models import AIRecommendation


@wellness_router.get("/ai/recommendations")
def get_ai_recommendations(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """AI personalized recommendations across all categories."""
    user, db = user_and_db
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).order_by(SleepRecord.bedtime.desc()).limit(14).all()

    if not records:
        return {"recommendations": [{"type": "plan", "content": "睡眠卫生基础计划", "reason": "推荐从基础开始改善睡眠"}]}

    avg_score = sum(r.score for r in records) / len(records)
    issues = (profile.sleep_issues or "") if profile else ""

    # Generate recommendations via AI
    context = f"用户平均睡眠评分{avg_score:.0f}，问题：{issues}，压力：{profile.stress_level if profile else '未知'}"
    prompt = f"""基于以下用户数据，推荐2-3个个性化项目。
用户：{context}

返回JSON：{{"items":[{{"type":"plan/product/course/task","title":"名称","reason":"为什么推荐"}}]}}"""

    result = _ai_chat("你是睡眠健康推荐AI，只返回JSON。", prompt, temperature=0.7, max_tokens=300)
    try:
        recs = json.loads(result).get("items", [])
    except:
        recs = [{"type": "plan", "title": "睡眠卫生基础计划", "reason": "适合所有睡眠改善者"}]

    # Save to DB
    for r in recs:
        db.add(AIRecommendation(user_id=user.id, rec_type=r.get("type", "general"), content=r.get("title", ""), reason=r.get("reason", "")))
    db.commit()

    return {"recommendations": recs, "avg_score": round(avg_score, 1), "records_analyzed": len(records)}


@wellness_router.post("/ai/recommendations/{rec_id}/apply")
def apply_recommendation(rec_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Mark an AI recommendation as applied/acted upon."""
    user, db = user_and_db
    rec = db.query(AIRecommendation).filter(
        AIRecommendation.id == rec_id, AIRecommendation.user_id == user.id
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="推荐不存在")
    rec.applied = 1
    db.commit()
    return {"message": "已执行", "rec_id": rec_id}


@sleep_router.get("/ai/risk-assessment")
def sleep_risk_assessment(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """AI sleep disorder risk assessment."""
    user, db = user_and_db
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).order_by(SleepRecord.bedtime.desc()).limit(30).all()
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()

    if not records:
        return {"risk": "unknown", "message": "需要至少7天数据"}

    avg_dur = sum(r.duration_hours or 0 for r in records) / len(records)
    avg_score = sum(r.score for r in records) / len(records)
    issues = (profile.sleep_issues or "") if profile else ""

    # Risk factors
    risks = {}
    if avg_dur < 5: risks["insomnia"] = "high"
    elif avg_dur < 6: risks["insomnia"] = "medium"
    else: risks["insomnia"] = "low"

    if "打鼾" in issues or "呼吸不畅" in issues: risks["sleep_apnea"] = "high"
    else: risks["sleep_apnea"] = "low"

    if avg_score < 40: risks["poor_quality"] = "high"
    elif avg_score < 60: risks["poor_quality"] = "medium"
    else: risks["poor_quality"] = "low"

    # AI analysis
    context = f"平均时长{avg_dur}h，评分{avg_score}，问题：{issues}，风险评估：{json.dumps(risks)}"
    ai_result = _ai_chat("你是睡眠医学AI。给出80字以内风险评估解读，必须注明不是医疗诊断。", context, temperature=0.3, max_tokens=120)

    return {"risks": risks, "avg_duration": round(avg_dur, 1), "avg_score": round(avg_score, 1), "ai_analysis": ai_result or "请咨询医生获取专业评估", "disclaimer": "此为AI初步评估，不构成医疗诊断"}


# ==================== AI PERSONALIZED PLAN GENERATOR ====================
@wellness_router.post("/ai/generate-plan")
def ai_generate_personalized_plan(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """AI generates a fully personalized sleep improvement plan."""
    user, db = user_and_db
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id).order_by(SleepRecord.bedtime.desc()).limit(14).all()
    profile = db.query(HealthProfile).filter(HealthProfile.user_id == user.id).first()

    context = f"用户：{user.nickname or user.username}"
    if profile:
        context += f"，年龄：{profile.age or '未知'}，睡眠问题：{profile.sleep_issues or '无'}，压力：{profile.stress_level or '未知'}"
    if records:
        avg_dur = sum(r.duration_hours or 0 for r in records) / len(records)
        avg_score = sum(r.score for r in records) / len(records)
        context += f"，平均睡眠{avg_dur:.1f}h，评分{avg_score:.0f}"

    prompt = f"""{context}

请生成一个3周个性化睡眠改善计划，每周3个任务。返回JSON：
{{"plan_title":"计划标题","weeks":[{{"week":1,"title":"阶段标题","tasks":["任务1","任务2","任务3"]}}]}}"""

    result = _ai_chat("你是睡眠改善计划设计师。只返回JSON。", prompt, temperature=0.8, max_tokens=500)
    try:
        plan = json.loads(result)
        return {"plan": plan, "ai_generated": True}
    except:
        return {"plan": {"plan_title": "基础改善计划", "weeks": [{"week": 1, "title": "基础阶段", "tasks": ["固定起床时间", "每天记录睡眠", "睡前30分钟放下手机"]}]}, "ai_generated": True}


# ==================== COMPETITIONS ====================
from app.models import SleepCompetition, CompetitionEntry


@competition_router.get("")
def list_competitions():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        comps = db.query(SleepCompetition).order_by(SleepCompetition.start_date.desc()).all()
        if not comps:
            from datetime import date
            today = date.today()
            defaults = [
                ("黄金睡眠周", "连续7天睡眠评分最高者获胜", "🏆", "avg_score", today, today + timedelta(days=7), "专业版月卡"),
                ("早睡王者挑战", "最早入睡且最规律者获胜", "🌙", "early_bed", today, today + timedelta(days=14), "白噪音音箱"),
                ("连胜达人", "最高连续达标天数获胜", "🔥", "streak", today, today + timedelta(days=21), "尊享版月卡"),
            ]
            for title, desc, icon, metric, start, end, prize in defaults:
                db.add(SleepCompetition(title=title, desc=desc, icon=icon, metric=metric, start_date=start, end_date=end, prize=prize))
            db.commit()
            comps = db.query(SleepCompetition).order_by(SleepCompetition.start_date.desc()).all()
        return {"competitions": [{"id": c.id, "title": c.title, "desc": c.desc, "icon": c.icon, "metric": c.metric, "start": str(c.start_date), "end": str(c.end_date), "participants": c.participant_count, "prize": c.prize} for c in comps]}
    finally:
        db.close()


@competition_router.post("/{comp_id}/join")
def join_competition(comp_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    existing = db.query(CompetitionEntry).filter(CompetitionEntry.competition_id == comp_id, CompetitionEntry.user_id == user.id).first()
    if existing: return {"message": "已参加"}
    db.add(CompetitionEntry(competition_id=comp_id, user_id=user.id))
    comp = db.query(SleepCompetition).filter(SleepCompetition.id == comp_id).first()
    if comp: comp.participant_count += 1
    db.commit()
    return {"message": "报名成功"}


@competition_router.get("/{comp_id}/leaderboard")
def competition_leaderboard(comp_id: int):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        entries = db.query(CompetitionEntry).filter(CompetitionEntry.competition_id == comp_id).order_by(CompetitionEntry.score.desc()).limit(20).all()
        return {"leaderboard": [{"rank": i+1, "user_id": e.user_id, "score": e.score} for i, e in enumerate(entries)]}
    finally:
        db.close()


# ==================== RELAXATION SPACES ====================
from app.models import RelaxationSpace


@relax_router.get("/spaces")
def list_spaces():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        spaces = db.query(RelaxationSpace).all()
        if not spaces:
            defaults = [
                ("星空草原", "nature", "pink_drift", "蟋蟀", 0),
                ("深海奇境", "ocean", "cyclic_wave", "气泡", 0),
                ("雨林秘境", "forest", "modulated_rain", "鸟鸣", 0),
                ("极光冰原", "space", "gust_cycle", "远雷", 1),
                ("冥想花园", "nature", "filtered_rustle", "水滴", 1),
            ]
            for name, scene, bgm, amb, premium in defaults:
                db.add(RelaxationSpace(name=name, scene_type=scene, bgm=bgm, ambient=amb, is_premium=premium))
            db.commit()
            spaces = db.query(RelaxationSpace).all()
        return {"spaces": [{"id": s.id, "name": s.name, "scene": s.scene_type, "bgm": s.bgm, "ambient": s.ambient, "is_premium": s.is_premium} for s in spaces]}
    finally:
        db.close()


# ==================== LIVE COURSES ====================
from app.models import LiveCourse, LiveEnrollment


@live_router.get("")
def list_live():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        lives = db.query(LiveCourse).order_by(LiveCourse.scheduled_at).all()
        if not lives:
            defaults = [
                ("CBT-I失眠治疗实操", "王医生", datetime.now() + timedelta(days=2), 60, 0),
                ("正念睡眠冥想训练", "李冥想导师", datetime.now() + timedelta(days=4), 45, 0),
                ("深度睡眠的科学秘密", "刘研究员", datetime.now() + timedelta(days=7), 60, 1),
            ]
            for title, inst, sched, dur, premium in defaults:
                db.add(LiveCourse(title=title, instructor=inst, scheduled_at=sched, duration_minutes=dur, is_premium=premium))
            db.commit()
            lives = db.query(LiveCourse).order_by(LiveCourse.scheduled_at).all()
        return {"lives": [{"id": l.id, "title": l.title, "instructor": l.instructor, "scheduled_at": str(l.scheduled_at), "duration": l.duration_minutes, "enrolled": l.enrolled, "is_premium": l.is_premium} for l in lives]}
    finally:
        db.close()


@live_router.post("/{live_id}/enroll")
def enroll_live(live_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    existing = db.query(LiveEnrollment).filter(LiveEnrollment.user_id == user.id, LiveEnrollment.live_id == live_id).first()
    if existing: return {"message": "已报名"}
    db.add(LiveEnrollment(user_id=user.id, live_id=live_id))
    live = db.query(LiveCourse).filter(LiveCourse.id == live_id).first()
    if live: live.enrolled += 1
    db.commit()
    return {"message": "报名成功"}


# ==================== GROWTH & ANALYTICS ====================
from app.models import LifecycleEmail, ABTest, AnalyticsEvent


@growth_router.get("/emails")
def list_lifecycle_emails():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        emails = db.query(LifecycleEmail).all()
        if not emails:
            triggers = [
                ("welcome", "欢迎加入梦眠阁", "hi {nickname}, 欢迎来到梦眠阁！", 0),
                ("inactive_3d", "你已经3天没记录了哦", "{nickname}, 最近睡得好吗？", 72),
                ("inactive_7d", "一周不见了", "{nickname}, 坚持记录才能看到改善哦", 168),
                ("streak_7", "连续7天达标！", "恭喜 {nickname} 连续7天达标！", 0),
                ("premium_expiring", "会员即将到期", "{nickname}, 你的会员还有3天到期", 0),
            ]
            for trigger, subject, template, delay in triggers:
                db.add(LifecycleEmail(trigger=trigger, subject=subject, template=template, delay_hours=delay))
            db.commit()
            emails = db.query(LifecycleEmail).all()
        return {"emails": [{"id": e.id, "trigger": e.trigger, "subject": e.subject, "delay_hours": e.delay_hours} for e in emails]}
    finally:
        db.close()


@growth_router.get("/ab-tests")
def list_ab_tests():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        tests = db.query(ABTest).filter(ABTest.is_active == 1).all()
        if not tests:
            db.add(ABTest(name="首页布局测试", variant_a='{"layout":"grid"}', variant_b='{"layout":"list"}'))
            db.add(ABTest(name="支付按钮颜色", variant_a='{"color":"purple"}', variant_b='{"color":"teal"}'))
            db.commit()
            tests = db.query(ABTest).filter(ABTest.is_active == 1).all()
        return {"tests": [{"id": t.id, "name": t.name, "a_users": t.a_users, "b_users": t.b_users, "a_conv": t.a_conversions, "b_conv": t.b_conversions} for t in tests]}
    finally:
        db.close()


@growth_router.get("/funnel")
def get_funnel(days: int = 30):
    """User conversion funnel analysis."""
    from app.database import SessionLocal
    from sqlalchemy import func as sa_func
    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=days)
        total_users = db.query(sa_func.count(User.id)).scalar()
        with_profile = db.query(sa_func.count(HealthProfile.id)).scalar()
        with_record = db.query(sa_func.count(sa_func.distinct(SleepRecord.user_id))).scalar()
        with_chat = db.query(sa_func.count(sa_func.distinct(ChatSession.user_id))).scalar()
        premium = db.query(sa_func.count(Membership.id)).filter(Membership.tier != "free").scalar()

        funnel = [
            {"step": "注册", "count": total_users, "rate": 100},
            {"step": "完善档案", "count": with_profile, "rate": round(with_profile/total_users*100, 1) if total_users else 0},
            {"step": "首次记录", "count": with_record, "rate": round(with_record/total_users*100, 1) if total_users else 0},
            {"step": "AI对话", "count": with_chat, "rate": round(with_chat/total_users*100, 1) if total_users else 0},
            {"step": "付费转化", "count": premium, "rate": round(premium/total_users*100, 1) if total_users else 0},
        ]
        return {"funnel": funnel, "days": days}
    finally:
        db.close()


@growth_router.post("/track")
def track_event(data: dict):
    """Track user behavior event for analytics."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.add(AnalyticsEvent(user_id=data.get("user_id"), event=data.get("event", "unknown"), properties=json.dumps(data.get("properties", {}))))
        db.commit()
        return {"message": "事件已记录"}
    finally:
        db.close()


# ==================== WEB3: NFT + TOKEN ECONOMY ====================
from app.models import SleepNFT, SleepToken, TokenTransaction


@web3_router.get("/nfts")
def list_nfts(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    nfts = db.query(SleepNFT).filter(SleepNFT.user_id == user.id).order_by(SleepNFT.minted_at.desc()).all()
    return {"nfts": [{"token_id": n.token_id, "name": n.name, "rarity": n.rarity, "image_url": n.image_url} for n in nfts]}


@web3_router.post("/nfts/mint")
def mint_nft(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Mint a sleep achievement NFT."""
    user, db = user_and_db
    name = data.get("name", "睡眠成就")
    rarity = data.get("rarity", "common")
    token_id = f"SLEEP_{user.id}_{int(time.time())}"
    nft = SleepNFT(user_id=user.id, token_id=token_id, name=name, rarity=rarity, nft_metadata=json.dumps({"achievement": name, "timestamp": str(datetime.now())}))
    db.add(nft); db.commit()
    return {"token_id": token_id, "name": name, "rarity": rarity, "message": "NFT 铸造成功"}


@web3_router.get("/tokens")
def get_token_balance(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    t = db.query(SleepToken).filter(SleepToken.user_id == user.id).first()
    if not t:
        t = SleepToken(user_id=user.id, balance=0)
        db.add(t); db.commit(); db.refresh(t)
    return {"balance": t.balance, "earned_total": t.earned_total, "spent_total": t.spent_total}


@web3_router.post("/tokens/earn")
def earn_tokens(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    amount = data.get("amount", 10)
    desc = data.get("desc", "日常奖励")
    t = db.query(SleepToken).filter(SleepToken.user_id == user.id).first()
    if not t:
        t = SleepToken(user_id=user.id, balance=amount, earned_total=amount)
        db.add(t)
    else:
        t.balance += amount; t.earned_total += amount
    db.add(TokenTransaction(user_id=user.id, amount=amount, tx_type="earn", description=desc))
    db.commit()
    return {"balance": t.balance, "earned": amount}


@web3_router.post("/tokens/spend")
def spend_tokens(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    amount = data.get("amount", 0)
    desc = data.get("desc", "消费")
    t = db.query(SleepToken).filter(SleepToken.user_id == user.id).first()
    if not t or t.balance < amount:
        raise HTTPException(status_code=400, detail="余额不足")
    t.balance -= amount; t.spent_total += amount
    db.add(TokenTransaction(user_id=user.id, amount=amount, tx_type="spend", description=desc))
    db.commit()
    return {"balance": t.balance, "spent": amount}


# ==================== OPEN DATASET ====================
from app.models import OpenDataset


@dataset_router.get("")
def list_datasets():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        datasets = db.query(OpenDataset).order_by(OpenDataset.downloads.desc()).all()
        if not datasets:
            db.add(OpenDataset(data_summary=json.dumps({"avg_age": 32, "avg_score": 68, "sample_size": 1200}), record_count=1200, tags="insomnia,general,adult"))
            db.add(OpenDataset(data_summary=json.dumps({"avg_age": 45, "avg_score": 55, "sample_size": 800}), record_count=800, tags="sleep_apnea,senior"))
            db.commit()
            datasets = db.query(OpenDataset).order_by(OpenDataset.downloads.desc()).all()
        return {"datasets": [{"id": d.id, "summary": json.loads(d.data_summary), "record_count": d.record_count, "tags": d.tags, "downloads": d.downloads} for d in datasets]}
    finally:
        db.close()


@dataset_router.post("/contribute")
def contribute_dataset(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    ds = OpenDataset(contributor_id=user.id, data_summary=json.dumps(data.get("summary", {})), record_count=data.get("record_count", 0), tags=data.get("tags", ""))
    db.add(ds); db.commit()
    return {"message": "数据集提交成功，审核通过后将开放下载"}


# ==================== LOCAL LLM ====================
from app.models import LocalLLM


@llm_router.get("/config")
def get_llm_config(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    llm = db.query(LocalLLM).filter(LocalLLM.user_id == user.id).first()
    return {"llm": {"model": llm.model, "endpoint": llm.endpoint, "is_active": llm.is_active} if llm else None}


@llm_router.post("/connect")
def connect_local_llm(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    existing = db.query(LocalLLM).filter(LocalLLM.user_id == user.id).first()
    if existing:
        existing.model = data.get("model", "llama3"); existing.endpoint = data.get("endpoint", "http://localhost:11434")
    else:
        db.add(LocalLLM(user_id=user.id, model=data.get("model", "llama3"), endpoint=data.get("endpoint", "http://localhost:11434")))
    db.commit()
    return {"message": f"已连接本地大模型 {data.get('model', 'llama3')}"}


# ==================== IoT DEVICES ====================
from app.models import IoTDevice, SmartAlarm


@iot_router.get("/devices")
def list_devices(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    devices = db.query(IoTDevice).filter(IoTDevice.user_id == user.id).all()
    types = {"mattress": "智能床垫", "light": "智能灯", "curtain": "智能窗帘", "watch": "智能手表"}
    return {"devices": [{"id": d.id, "type": d.device_type, "name": d.name or types.get(d.device_type, ""), "status": json.loads(d.status) if d.status else {}, "last_sync": str(d.last_sync) if d.last_sync else None} for d in devices]}


@iot_router.post("/devices")
def add_device(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    device = IoTDevice(user_id=user.id, device_type=data.get("device_type"), device_id=data.get("device_id", ""), name=data.get("name", ""))
    db.add(device); db.commit(); db.refresh(device)
    return {"id": device.id, "message": "设备已添加"}


@iot_router.post("/alarm")
def set_smart_alarm(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Configure smart wake-up alarm with light/sound."""
    user, db = user_and_db
    existing = db.query(SmartAlarm).filter(SmartAlarm.user_id == user.id).first()
    if existing:
        for f in ["target_time", "wake_window", "smart_method", "enabled_days", "is_active"]:
            if f in data: setattr(existing, f, data[f])
    else:
        db.add(SmartAlarm(user_id=user.id, target_time=data.get("target_time", "07:00"), wake_window=data.get("wake_window", 30), smart_method=data.get("smart_method", "light")))
    db.commit()
    return {"message": "智能闹钟已设置"}


@iot_router.get("/alarm")
def get_smart_alarm(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    alarm = db.query(SmartAlarm).filter(SmartAlarm.user_id == user.id).first()
    if not alarm:
        alarm = SmartAlarm(user_id=user.id)
        db.add(alarm); db.commit(); db.refresh(alarm)
    return {"target_time": alarm.target_time, "wake_window": alarm.wake_window, "smart_method": alarm.smart_method, "enabled_days": alarm.enabled_days, "is_active": alarm.is_active}


# ==================== WATCH DATA ====================
from app.models import WatchAppData


@watch_router.post("/sync")
def sync_watch_data(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Sync data from Apple Watch / Huawei Watch."""
    user, db = user_and_db
    dk = data.get("date_key", datetime.now().strftime("%Y-%m-%d"))
    existing = db.query(WatchAppData).filter(WatchAppData.user_id == user.id, WatchAppData.date_key == dk).first()
    if existing:
        for f in ["heart_rate", "hrv", "spo2", "steps", "device"]:
            if f in data: setattr(existing, f, data[f])
    else:
        db.add(WatchAppData(user_id=user.id, date_key=dk, device=data.get("device", "apple_watch"), heart_rate=json.dumps(data.get("heart_rate", [])), hrv=data.get("hrv"), spo2=data.get("spo2"), steps=data.get("steps", 0)))
    db.commit()
    return {"message": "手表数据已同步"}


@watch_router.get("/data")
def get_watch_data(days: int = 7, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    data = db.query(WatchAppData).filter(WatchAppData.user_id == user.id, WatchAppData.date_key >= cutoff).order_by(WatchAppData.date_key.desc()).all()
    return {"records": [{"date": d.date_key, "hrv": d.hrv, "spo2": d.spo2, "steps": d.steps, "device": d.device} for d in data]}