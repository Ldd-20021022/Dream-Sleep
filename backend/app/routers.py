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
)
from app.schemas import (
    UserRegister, UserLogin, UserResponse, UserProfileBasic, ChangePassword,
    TokenPair, TokenRefresh, TokenRefreshResponse, HasProfileResponse,
    SleepRecordCreate, SleepRecordResponse, SleepStatsResponse,
    HealthProfileCreate, HealthProfileResponse,
    SendMessageRequest, ChatMessageResponse, ChatSessionResponse,
    TaskCompleteRequest, PointsResponse, BadgeUnlockRequest,
)
from app.services import (
    hash_pw, verify_pw,
    create_access_token, create_refresh_token, decode_token,
    get_sleep_feedback, chat_with_sleep_coach,
    calc_score, calc_duration, calc_consistency_minutes, consistency_label,
    calc_streak, get_tag_stats,
    calc_sleep_efficiency, calc_sleep_debt,
    generate_weekly_report, export_records_csv,
    ai_generate_tasks, ai_design_soundscape, generate_today_tasks_rule_based, ALL_BADGES,
    chat_with_rag, ai_sentiment_analysis, ai_deep_sleep_report, ai_predict_sleep_quality, rag_retrieve_knowledge,
    _ai_chat,
    KNOWLEDGE_ARTICLES, KNOWLEDGE_CATEGORIES,
    IMPROVEMENT_PLANS, ONBOARDING_STEPS,
)

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
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

    user = User(username=username, email=email,
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


@auth_router.put("/profile-basic")
def update_profile_basic(data: UserProfileBasic, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    if data.nickname is not None:
        user.nickname = data.nickname
    if data.avatar is not None:
        user.avatar = data.avatar
    db.commit()
    return {"message": "已更新"}


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


# ==================== SLEEP RECORDS ====================
def _to_record_response(r: SleepRecord) -> SleepRecordResponse:
    return SleepRecordResponse.model_validate(r)


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
    record.score = calc_score(duration, data.quality or 3, tags_str, goal)

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


# CSV export
@sleep_router.get("/export")
def export_sleep_csv(days: int = Query(default=30), user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    from fastapi.responses import Response
    user, db = user_and_db
    cutoff = datetime.now() - timedelta(days=days)
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user.id, SleepRecord.bedtime >= cutoff).order_by(SleepRecord.bedtime.desc()).all()
    csv_data = export_records_csv(records)
    return Response(content=csv_data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=sleep_records_{datetime.now().strftime('%Y%m%d')}.csv"})


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
    return {"tasks": tasks, "ai_generated": True}


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
from app.models import PlanEnrollment, PlanCheckIn


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
from app.models import CommunityGroup, GroupMember, SleepChallenge, ChallengeParticipant, SleepPost, PostComment, PostLike


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
def list_posts(page: int = 1, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    _, db = user_and_db
    user_id = user_and_db[0].id
    total = db.query(SleepPost).count()
    posts = db.query(SleepPost).order_by(SleepPost.created_at.desc()).offset((page - 1) * 20).limit(20).all()
    result = []
    for p in posts:
        author = db.query(User).filter(User.id == p.user_id).first()
        liked = db.query(PostLike).filter(PostLike.post_id == p.id, PostLike.user_id == user_id).first() is not None
        result.append({
            "id": p.id, "content": p.content,
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
    post = SleepPost(
        user_id=user.id, content=data.get("content", ""),
        sleep_score=data.get("sleep_score"),
        sleep_duration=data.get("sleep_duration"),
        is_anonymous=data.get("is_anonymous", 0),
    )
    db.add(post); db.commit(); db.refresh(post)
    return {"id": post.id, "message": "发布成功"}


@community_router.post("/posts/{post_id}/like")
def like_post(post_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    existing = db.query(PostLike).filter(PostLike.post_id == post_id, PostLike.user_id == user.id).first()
    if existing:
        db.delete(existing)
        post = db.query(SleepPost).filter(SleepPost.id == post_id).first()
        if post and post.like_count > 0: post.like_count -= 1
        db.commit()
        return {"liked": False}
    db.add(PostLike(post_id=post_id, user_id=user.id))
    post = db.query(SleepPost).filter(SleepPost.id == post_id).first()
    if post: post.like_count = (post.like_count or 0) + 1
    db.commit()
    return {"liked": True}


@community_router.post("/posts/{post_id}/comment")
def comment_post(post_id: int, data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    comment = PostComment(post_id=post_id, user_id=user.id, content=data.get("content", ""))
    db.add(comment)
    post = db.query(SleepPost).filter(SleepPost.id == post_id).first()
    if post: post.comment_count = (post.comment_count or 0) + 1
    db.commit(); db.refresh(comment)
    return {"id": comment.id, "message": "评论成功"}


@community_router.get("/posts/{post_id}/comments")
def get_comments(post_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    _, db = user_and_db
    comments = db.query(PostComment).filter(PostComment.post_id == post_id).order_by(PostComment.created_at).all()
    return {"comments": [{
        "id": c.id, "content": c.content,
        "author": (db.query(User).filter(User.id == c.user_id).first().nickname or "用户") if c.user_id else "用户",
        "created_at": str(c.created_at) if c.created_at else None,
    } for c in comments]}


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
from app.models import Membership

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
        m.tier = "free"
        db.commit()
        return "free"
    return m.tier


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


@premium_router.post("/upgrade")
def upgrade_membership(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Upgrade membership tier (production: integrate with WeChat/Alipay payment)."""
    user, db = user_and_db
    tier = data.get("tier", "pro")
    if tier not in MEMBERSHIP_TIERS:
        raise HTTPException(status_code=400, detail="无效的会员等级")

    m = db.query(Membership).filter(Membership.user_id == user.id).first()
    if not m:
        m = Membership(user_id=user.id, tier=tier, started_at=datetime.utcnow(),
                       expires_at=datetime.utcnow() + timedelta(days=30))
        db.add(m)
    else:
        m.tier = tier
        m.started_at = datetime.utcnow()
        m.expires_at = datetime.utcnow() + timedelta(days=30)
    db.commit()

    _log_audit(db, user.id, "membership_upgrade", f"Upgraded to {tier}")
    return {"message": f"已升级到{MEMBERSHIP_TIERS[tier]['name']}", "tier": tier, "expires_at": str(m.expires_at)}


@premium_router.post("/cancel")
def cancel_membership(user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    user, db = user_and_db
    m = db.query(Membership).filter(Membership.user_id == user.id).first()
    if m:
        m.auto_renew = 0
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
        "app_name": "梦眠 - AI智能睡眠管理",
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

    test_payload = {"event": "test.ping", "timestamp": datetime.now().isoformat(), "message": "This is a test webhook from 梦眠", "user_id": user_and_db[0].id}

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
from app.models import PaymentOrder, PaymentRecord
import hashlib as _hashlib


def _generate_order_no() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(100000, 999999))


PAYMENT_PLANS = {
    "pro_monthly": {"tier": "pro", "name": "专业版月卡", "amount": 2900, "days": 30},
    "pro_yearly": {"tier": "pro", "name": "专业版年卡", "amount": 19900, "days": 365},
    "premium_monthly": {"tier": "premium", "name": "尊享版月卡", "amount": 5900, "days": 30},
    "premium_yearly": {"tier": "premium", "name": "尊享版年卡", "amount": 39900, "days": 365},
}


@payment_router.get("/plans")
def get_payment_plans():
    """Get available payment plans."""
    return {"plans": [{"id": k, **v, "amount_yuan": round(v["amount"] / 100, 2)} for k, v in PAYMENT_PLANS.items()]}


@payment_router.post("/orders")
def create_order(data: dict, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Create a payment order."""
    user, db = user_and_db
    plan_id = data.get("plan_id", "pro_monthly")
    method = data.get("method", "wechat")

    if plan_id not in PAYMENT_PLANS:
        raise HTTPException(status_code=400, detail="无效的套餐")

    plan = PAYMENT_PLANS[plan_id]
    order_no = _generate_order_no()
    order = PaymentOrder(
        order_no=order_no, user_id=user.id, tier=plan["tier"],
        amount=plan["amount"], payment_method=method,
        expires_at=datetime.utcnow() + timedelta(days=plan["days"]),
    )
    db.add(order); db.commit(); db.refresh(order)

    # Build payment params
    pay_params = _build_payment_params(order, user, method)

    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "amount": order.amount,
        "amount_yuan": round(order.amount / 100, 2),
        "tier": order.tier,
        "plan_name": plan["name"],
        "status": order.status,
        "payment_params": pay_params,
        "created_at": str(order.created_at),
    }


def _build_payment_params(order, user, method: str) -> dict:
    """Build payment parameters for different methods."""
    if method == "wechat":
        # Production: call WeChat Pay Unified Order API
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


@payment_router.post("/orders/{order_id}/pay")
def process_payment(order_id: int, data: dict = None, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Simulate/process payment for an order."""
    user, db = user_and_db
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id, PaymentOrder.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="订单已处理")

    transaction_id = data.get("transaction_id", f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}") if data else f"SIM{int(time.time())}"

    # Mark order paid
    order.status = "paid"
    order.paid_at = datetime.utcnow()

    # Record payment
    record = PaymentRecord(
        order_id=order.id, user_id=user.id,
        transaction_id=transaction_id, amount=order.amount,
        method=order.payment_method, status="success",
        raw_response=json.dumps({"mode": "simulation", "transaction_id": transaction_id}),
    )
    db.add(record)

    # Activate/upgrade membership
    from app.models import Membership
    m = db.query(Membership).filter(Membership.user_id == user.id).first()
    days = next((p["days"] for k, p in PAYMENT_PLANS.items() if p["tier"] == order.tier and p["amount"] == order.amount), 30)
    if not m:
        m = Membership(user_id=user.id, tier=order.tier, started_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(days=days))
        db.add(m)
    else:
        if m.expires_at and m.expires_at > datetime.utcnow():
            m.expires_at = m.expires_at + timedelta(days=days)  # Extend
        else:
            m.expires_at = datetime.utcnow() + timedelta(days=days)
        m.tier = order.tier
    db.commit()

    _log_audit(db, user.id, "payment_success", f"Order {order.order_no}, {order.tier}, {order.amount}分")

    return {
        "message": "支付成功",
        "order_no": order.order_no,
        "tier": order.tier,
        "amount": order.amount,
        "transaction_id": transaction_id,
        "membership_expires": str(m.expires_at if m else None),
    }


@payment_router.get("/orders")
def get_orders(page: int = 1, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Get user's order history."""
    user, db = user_and_db
    orders = db.query(PaymentOrder).filter(PaymentOrder.user_id == user.id).order_by(PaymentOrder.created_at.desc()).offset((page - 1) * 20).limit(20).all()
    return {"orders": [{
        "id": o.id, "order_no": o.order_no, "tier": o.tier,
        "amount": o.amount, "amount_yuan": round(o.amount / 100, 2),
        "status": o.status, "payment_method": o.payment_method,
        "paid_at": str(o.paid_at) if o.paid_at else None,
        "created_at": str(o.created_at),
    } for o in orders]}


@payment_router.post("/orders/{order_id}/refund")
def refund_order(order_id: int, user_and_db: Tuple[User, Session] = Depends(current_user_and_db)):
    """Request a refund."""
    user, db = user_and_db
    order = db.query(PaymentOrder).filter(PaymentOrder.id == order_id, PaymentOrder.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "paid":
        raise HTTPException(status_code=400, detail="订单未支付或已退款")
    if order.paid_at and (datetime.utcnow() - order.paid_at).days > 7:
        raise HTTPException(status_code=400, detail="超过7天退款期")

    order.status = "refunded"
    db.add(PaymentRecord(order_id=order.id, user_id=user.id, transaction_id=f"REFUND{int(time.time())}", amount=-order.amount, method=order.payment_method, status="refund"))
    db.commit()

    _log_audit(db, user.id, "payment_refund", f"Order {order.order_no}")
    return {"message": "退款成功", "order_no": order.order_no, "amount": order.amount}


@payment_router.post("/wechat-notify")
def wechat_pay_notify(data: dict = None):
    """WeChat Pay callback — production: verify signature, update order."""
    if not data:
        return {"code": "FAIL", "message": "no data"}
    order_no = data.get("out_trade_no", "")
    transaction_id = data.get("transaction_id", "")
    # Production: verify WeChat Pay signature, update order status
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
    q = db if False else None  # no DB session needed for seed
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
    unlocked = {a.achievement_key for a in db.query(Achievement).filter(Achievement.user_id == user.id).all()}
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
                ("welcome", "欢迎加入梦眠", "hi {nickname}, 欢迎来到梦眠！", 0),
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