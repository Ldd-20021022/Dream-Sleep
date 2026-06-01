"""All business logic — auth, AI, sleep scoring, tasks."""
import json
import math
import random
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.security import is_token_blacklisted

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ===== Auth =====
def hash_pw(password: str) -> str:
    return pwd_context.hash(password)


def verify_pw(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(data: dict, token_type: str) -> str:
    to_encode = data.copy()
    minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES if token_type == "access" else settings.REFRESH_TOKEN_EXPIRE_MINUTES
    to_encode.update({"exp": datetime.utcnow() + timedelta(minutes=minutes), "type": token_type})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(data: dict) -> str:
    return _create_token(data, "access")


def create_refresh_token(data: dict) -> str:
    return _create_token(data, "refresh")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    if is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌已失效，请重新登录")
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id or payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


# ===== AI Service =====
import requests as _requests
AI_MODEL = "deepseek-chat"


def _ai_call(messages: list, temperature: float = 0.8, max_tokens: int = 300) -> str:
    """Unified AI call using requests — no OpenAI SDK dependency."""
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError("AI service not configured")
    try:
        r = _requests.post(
            f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": AI_MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return ""
    except Exception as e:
        if isinstance(e, ValueError):
            raise  # re-raise AI not configured
        return ""


def _ai_chat(system_prompt: str, user_prompt: str, temperature: float = 0.8, max_tokens: int = 300) -> str:
    return _ai_call([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ], temperature, max_tokens)


def get_sleep_feedback(diary_text: str) -> str:
    try:
        result = _ai_chat(
            "你是专业的睡眠陪伴助手，遵循CBT-I原则。用温柔语气给出50字以内的共情反馈，不给出诊断。",
            f"用户睡眠记录：{diary_text}\n请给一句共情反馈：",
            temperature=0.7, max_tokens=80,
        )
        return result or "我收到了你的睡眠记录。别担心，我们一起慢慢来，先保持记录习惯就是进步。"
    except Exception:
        return "我收到了你的睡眠记录。别担心，我们一起慢慢来，先保持记录习惯就是进步。"


def ai_generate_tasks(profile_dict: dict = None, sleep_stats: dict = None, user_name: str = "") -> list:
    """AI generates 4 personalized daily tasks based on user profile and sleep data."""
    context_parts = [f"用户：{user_name}"] if user_name else []

    if profile_dict:
        if profile_dict.get("sleep_goal_hours"):
            context_parts.append(f"目标睡眠：{profile_dict['sleep_goal_hours']}h")
        if profile_dict.get("sleep_issues"):
            context_parts.append(f"睡眠问题：{profile_dict['sleep_issues']}")
        if profile_dict.get("stress_level"):
            context_parts.append(f"压力水平：{profile_dict['stress_level']}")
        if profile_dict.get("improvement_priority"):
            context_parts.append(f"改善优先级：{profile_dict['improvement_priority']}")
        if profile_dict.get("caffeine_intake"):
            context_parts.append(f"咖啡因习惯：{profile_dict['caffeine_intake']}")
        if profile_dict.get("exercise_frequency"):
            context_parts.append(f"运动频率：{profile_dict['exercise_frequency']}")

    if sleep_stats:
        if sleep_stats.get("avg_duration"):
            context_parts.append(f"近期平均睡眠：{sleep_stats['avg_duration']}h")
        if sleep_stats.get("avg_score"):
            context_parts.append(f"平均评分：{sleep_stats['avg_score']}分")
        if sleep_stats.get("consistency"):
            context_parts.append(f"作息规律度：{sleep_stats['consistency']}")

    context = "；".join(context_parts) if context_parts else "新用户，暂无数据"

    prompt = f"""你是睡眠健康专家。根据以下用户数据，生成4个今日个性化任务。

{context}

请生成4个任务，每个任务包含：id(t1-t18参考编号)、title(10字以内简短标题)、desc(15字以内描述)、category(分类)、time_of_day(时段：morning/afternoon/evening)、points(固定5分)。

任务分配原则：
- morning(早晨)：光照、运动、起床习惯类
- afternoon(下午)：咖啡因控制、午睡、学习类
- evening(晚上)：放松、环境、睡前仪式类
- 4个任务中至少包含2个不同时段

任务应针对用户的具体问题。如果用户入睡困难，推荐放松和作息类任务；如果压力高，推荐心理减压类；如果是新用户，推荐基础睡眠卫生任务。

参考分类：作息、习惯、放松、心理、饮食、运动、工具、环境

严格按照以下JSON格式返回，不要其他内容：
{{"tasks":[{{"id":"t1","title":"任务标题","desc":"简短描述","category":"分类","time_of_day":"evening","points":5}}]}}"""

    result = _ai_chat("你是专业的睡眠健康管理AI。只返回JSON，不返回其他内容。", prompt, temperature=0.9, max_tokens=500)

    try:
        data = json.loads(result)
        tasks = data.get("tasks", [])
        # Map to known task IDs where possible, assign new IDs if needed
        valid_tasks = []
        known_ids = {t["id"] for t in ALL_TASKS}
        for i, t in enumerate(tasks[:4]):
            tid = t.get("id", f"ai{i+1}")
            if tid not in known_ids:
                tid = f"ai_{i+1}"
            valid_tasks.append({
                "id": tid,
                "title": str(t.get("title", "放松一下"))[:20],
                "desc": str(t.get("desc", "有助于改善睡眠"))[:30],
                "category": str(t.get("category", "习惯"))[:10],
                "time_of_day": str(t.get("time_of_day", "evening"))[:10],
                "points": 5,
            })
        if valid_tasks:
            return valid_tasks
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    # Fallback: use rule-based tasks
    return generate_today_tasks_rule_based(profile_dict)


def ai_design_soundscape(profile_dict: dict = None, sleep_stats: dict = None, user_preference: str = "") -> dict:
    """AI designs a personalized white noise soundscape mix."""
    context_parts = []
    if profile_dict:
        if profile_dict.get("sleep_issues"):
            context_parts.append(f"睡眠问题：{profile_dict['sleep_issues']}")
        if profile_dict.get("stress_level"):
            context_parts.append(f"压力：{profile_dict['stress_level']}")
        if profile_dict.get("preferred_sounds"):
            context_parts.append(f"偏好声音：{profile_dict['preferred_sounds']}")
    if sleep_stats:
        if sleep_stats.get("avg_score"):
            context_parts.append(f"睡眠评分：{sleep_stats['avg_score']}")
    if user_preference:
        context_parts.append(f"用户想要：{user_preference}")

    context = "；".join(context_parts) if context_parts else "通用放松"

    prompt = f"""你是声音疗愈专家。根据以下用户情况设计个性化白噪音混音方案。

用户情况：{context}

可用声音类型：brown_deep(深棕噪音-低沉)、pink_drift(粉红噪音-柔和)、filtered_rustle(沙沙声)、realistic_chirp(鸟鸣)、rhythmic_pulse(蟋蟀)、cyclic_wave(海浪)、distant_thunder(远雷)、drip_pattern(水滴)、modulated_rain(雨声)、gust_cycle(风声)、fire_roar(火焰)、crackle_burst(噼啪)、sparse_bubble(气泡)

请选择4种声音并设定音量(0-100)，同时给这个混音取个中文名(6字以内)和简短描述。

严格按照JSON返回：
{{"name":"音景名","description":"简短描述","channels":[{{"type":"声音类型","name":"通道名","vol":70}}]}}"""

    result = _ai_chat("你是声音疗愈AI。只返回JSON。", prompt, temperature=0.9, max_tokens=400)

    try:
        data = json.loads(result)
        channels = data.get("channels", [])
        valid_types = {"brown_deep","pink_drift","filtered_rustle","realistic_chirp","rhythmic_pulse",
                       "cyclic_wave","distant_thunder","drip_pattern","modulated_rain","gust_cycle",
                       "fire_roar","crackle_burst","sparse_bubble"}
        valid_channels = []
        for ch in channels[:4]:
            t = ch.get("type", "pink_drift")
            if t not in valid_types:
                t = "pink_drift"
            valid_channels.append({
                "name": str(ch.get("name", "通道"))[:10],
                "type": t,
                "vol": max(0, min(100, int(ch.get("vol", 50)))),
            })
        if valid_channels:
            return {
                "name": str(data.get("name", "AI推荐"))[:10],
                "description": str(data.get("description", ""))[:50],
                "channels": valid_channels,
            }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass

    # Fallback: gentle default
    return {
        "name": "温柔入眠",
        "description": "适合放松的柔和混音",
        "channels": [
            {"name": "粉红噪音", "type": "pink_drift", "vol": 60},
            {"name": "微风轻拂", "type": "gust_cycle", "vol": 30},
            {"name": "远鸟鸣叫", "type": "realistic_chirp", "vol": 20},
            {"name": "稀疏气泡", "type": "sparse_bubble", "vol": 15},
        ],
    }


# ===== AI Deep Optimization =====

def rag_retrieve_knowledge(query: str, top_k: int = 3) -> list:
    """RAG: Retrieve relevant knowledge articles by keyword matching."""
    query_lower = query.lower()
    scored = []
    for article in KNOWLEDGE_ARTICLES:
        score = 0
        search_text = (article["title"] + article["summary"] + " ".join(article.get("tags", []))).lower()
        for word in query_lower.split():
            if word in search_text:
                score += 1
        if query_lower in article["category"].lower():
            score += 3
        if score > 0:
            scored.append((score, article))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:top_k]]


def chat_with_rag(user_message: str, history: list = None, user_context: str = "") -> str:
    """Enhanced chat with RAG knowledge injection."""
    # Retrieve relevant knowledge
    relevant = rag_retrieve_knowledge(user_message, top_k=2)
    knowledge_context = ""
    if relevant:
        knowledge_context = "相关知识：\n" + "\n".join(
            f"- [{a['category']}] {a['title']}: {a['summary']}" for a in relevant
        )

    system = f"""你是一位温柔、专业、遵循认知行为疗法(CBT-I)的睡眠教练。
倾听用户的睡眠困扰，提供科学的睡眠卫生建议，给予共情和鼓励。
绝不提供医疗诊断。回答简洁温暖，每次回复150字以内。严重症状建议就医。

{knowledge_context}

以下是你可以参考的CBT-I专业对话范例：

用户：我躺下好几个小时都睡不着
助手：躺下很久睡不着确实让人烦躁。可以试试「20分钟法则」：如果在床上20分钟还没睡着，就起来去另一个房间，做些轻松的事，等有困意再回来。这样能帮大脑重新建立床和睡眠的关联。

用户：我每天晚上都担心自己睡不着
助手：这种对睡眠的担忧本身就会让人更清醒。试着把担忧写下来，告诉自己「我已经记下来了，明天再处理」。把床留给休息，而不是用来担心。"""

    if user_context:
        system += f"\n\n用户档案：{user_context}"

    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-20:])
    messages.append({"role": "user", "content": user_message})

    try:
        result = _ai_call(messages, temperature=0.8, max_tokens=350)
        return result or "抱歉，我暂时无法回复。请稍后再试，或者记录一下此刻的感受，这本身就有帮助。"
    except Exception:
        return "抱歉，我暂时无法回复。请稍后再试，或者记录一下此刻的感受，这本身就有帮助。"


def ai_sentiment_analysis(text: str) -> dict:
    """Analyze sentiment/emotion in user text."""
    prompt = f"""分析以下睡眠相关文本的情感状态。返回JSON格式。

文本：{text}

返回格式：
{{"emotion":"正面/负面/中性","anxiety_level":1-5,"keywords":["关键词"],"brief_comment":"一句话简短分析"}}"""

    result = _ai_chat("你是情感分析专家。只返回JSON。", prompt, temperature=0.3, max_tokens=150)
    try:
        return json.loads(result)
    except:
        return {"emotion": "中性", "anxiety_level": 3, "keywords": [], "brief_comment": "无法分析"}


def ai_deep_sleep_report(user_name: str, profile: dict, records: list, stats: dict, health_data: dict = None) -> dict:
    """AI generates a comprehensive deep sleep analysis report."""
    # Build detailed context
    context_parts = [f"用户：{user_name}"]
    if profile:
        if profile.get("sleep_goal_hours"): context_parts.append(f"目标睡眠：{profile['sleep_goal_hours']}h")
        if profile.get("sleep_issues"): context_parts.append(f"睡眠问题：{profile['sleep_issues']}")
        if profile.get("stress_level"): context_parts.append(f"压力水平：{profile['stress_level']}")
        if profile.get("caffeine_intake"): context_parts.append(f"咖啡因：{profile['caffeine_intake']}")
        if profile.get("exercise_frequency"): context_parts.append(f"运动：{profile['exercise_frequency']}")

    if stats:
        context_parts.append(f"平均时长：{stats.get('avg_duration',0)}h")
        context_parts.append(f"平均评分：{stats.get('avg_score',0)}分")
        context_parts.append(f"睡眠效率：{stats.get('avg_efficiency',0)}%")
        context_parts.append(f"连续达标：{stats.get('streak_days',0)}天")
        if stats.get("sleep_debt"):
            context_parts.append(f"睡眠债：{stats['sleep_debt'].get('total_debt',0)}h")

    if health_data:
        avg_steps = sum(h.get("steps", 0) for h in health_data) / max(len(health_data), 1)
        context_parts.append(f"日均步数：{int(avg_steps)}步")

    # Last 7 days of records
    recent_records = ""
    for r in (records or [])[-7:]:
        tags = ""
        try: tags = ", ".join(json.loads(r.tags or "[]"))
        except: pass
        recent_records += f"- {r.diary_date}: {r.duration_hours}h, 评分{r.score}, {tags}\n"

    prompt = f"""你是顶级睡眠医学专家和数据分析师。请根据以下用户数据，撰写一份专业的睡眠深度分析报告。

用户数据：
{chr(10).join(context_parts)}

近期记录：
{recent_records}

请从以下维度进行分析（每段100字以内，共5段）：
1. 📊 整体趋势：睡眠质量和时长的变化趋势
2. 🎯 核心问题：当前最突出的睡眠问题
3. 🏃 生活方式：运动、饮食、压力对睡眠的影响
4. 💡 改善建议：3个具体可行的改善行动
5. 🌟 积极发现：用户的进步和优势

语气温暖专业，不给出医疗诊断。"""

    analysis = _ai_chat(
        "你是顶级睡眠医学专家。用温暖专业的语气撰写分析报告。",
        prompt, temperature=0.7, max_tokens=800,
    )

    return {
        "user_name": user_name,
        "report_type": "deep_analysis",
        "context": context_parts,
        "analysis": analysis or "AI分析暂时不可用",
        "generated_at": datetime.now().isoformat(),
    }


def ai_predict_sleep_quality(records: list, profile: dict = None) -> dict:
    """AI predicts tonight's sleep quality based on patterns."""
    if not records or len(records) < 3:
        return {"prediction": "数据不足", "confidence": 0, "tips": ["开始记录更多睡眠数据以获得预测"]}

    # Summarize recent patterns
    recent = records[-7:]
    avg_score = sum(r.score for r in recent) / len(recent)
    avg_dur = sum(r.duration_hours or 0 for r in recent) / len(recent)
    scores_trend = [r.score for r in recent]
    trend = "上升" if len(scores_trend) >= 2 and scores_trend[-1] > scores_trend[0] else ("下降" if len(scores_trend) >= 2 and scores_trend[-1] < scores_trend[0] else "稳定")

    prompt = f"""基于用户近期睡眠数据，预测今晚睡眠质量并给出建议。

近期平均评分：{avg_score}，趋势：{trend}
近期平均时长：{avg_dur}h
目标时长：{profile.get('sleep_goal_hours', 8)}h if profile else '8h'

返回JSON：
{{"prediction":"今晚睡眠评分预计XX分左右","confidence":0-100,"trend":"{trend}","tips":["建议1","建议2","建议3"]}}"""

    result = _ai_chat("你是睡眠预测AI。只返回JSON。", prompt, temperature=0.5, max_tokens=250)
    try:
        return json.loads(result)
    except:
        return {"prediction": "今晚睡眠质量预计在平均水平", "confidence": 60, "trend": trend, "tips": ["保持固定入睡时间", "睡前1小时减少屏幕使用", "尝试4-7-8呼吸法"]}


# ===== Sleep Scoring =====
def calc_score(duration: float, quality: int, tags_str: str, goal_hours: float = 8.0) -> tuple:
    """Calculate sleep score 0-100 and return (score, breakdown).
    Adjusted for positive reinforcement — base raised to 20, duration widened.
    """
    base = 20
    ideal_min, ideal_max = goal_hours, goal_hours + 1.5

    # Duration score: 0-40 points
    if ideal_min <= duration <= ideal_max:
        dur_score = 40
        dur_label = "达标"
    elif ideal_min - 1 <= duration < ideal_min:
        dur_score = 32
        dur_label = "接近目标"
    elif ideal_max < duration <= ideal_max + 1:
        dur_score = 28
        dur_label = "稍多"
    elif duration >= goal_hours * 0.5:
        dur_score = 12 + int((duration / goal_hours) * 16)
        dur_label = "偏少"
    elif duration > 0:
        dur_score = 6
        dur_label = "严重不足"
    else:
        dur_score = 0
        dur_label = "无数据"

    # Quality: 0-30 points (6 per level)
    qual_score = (quality or 3) * 6
    qual_labels = {1: "很差", 2: "较差", 3: "一般", 4: "良好", 5: "优秀"}
    qual_label = qual_labels.get(quality, "一般")

    # Tag bonus: -10 to +15
    tag_bonus = 15
    try:
        tags = json.loads(tags_str or "[]")
    except (json.JSONDecodeError, TypeError):
        tags = []
    pos_tags = []
    neg_tags = []
    for t in ["失眠", "夜醒", "早醒", "浅睡"]:
        if t in tags:
            tag_bonus -= 4
            neg_tags.append(t)
    if "深睡" in tags:
        tag_bonus += 4
        pos_tags.append("深睡")
    tag_bonus = max(-10, min(tag_bonus, 15))

    score = base + dur_score + qual_score + tag_bonus
    score = min(max(round(score), 0), 100)

    breakdown = {
        "base": base,
        "duration": {"score": dur_score, "max": 40, "label": dur_label, "hours": round(duration, 1)},
        "quality": {"score": qual_score, "max": 30, "label": qual_label, "level": quality or 3},
        "tags": {"score": tag_bonus, "max": 15, "positive": pos_tags, "negative": neg_tags},
        "total": score,
    }
    return score, breakdown


def calc_duration(bedtime: datetime, wake_time: datetime) -> float:
    h = (wake_time - bedtime).total_seconds() / 3600
    return round(h + 24 if h < 0 else h, 1)


def calc_consistency_minutes(records: list) -> float:
    if not records or len(records) < 2:
        return 0
    bedtimes = [r.bedtime.hour * 60 + r.bedtime.minute for r in records]
    avg = sum(bedtimes) / len(bedtimes)
    return math.sqrt(sum((t - avg) ** 2 for t in bedtimes) / len(bedtimes))


def consistency_label(m: float) -> str:
    return "regular" if m < 30 else ("moderate" if m < 60 else "irregular")


def calc_streak(db: Session, user_id: int) -> int:
    from app.models import SleepRecord
    records = db.query(SleepRecord).filter(SleepRecord.user_id == user_id).order_by(SleepRecord.bedtime.desc()).all()
    streak, seen = 0, set()
    for r in records:
        d = r.bedtime.date() if r.bedtime else None
        if not d or d in seen:
            continue
        if r.score >= 60:
            seen.add(d); streak += 1
        else:
            break
    return streak


def get_week_streak_days(db: Session, user_id: int) -> list:
    """Return a list of 7 booleans for the past 7 days ( today is index 6 )."""
    from app.models import TaskCompletion
    from datetime import date, timedelta
    today = date.today()
    result = []
    for i in range(7):
        d = today - timedelta(days=6 - i)
        dk = d.strftime("%Y-%m-%d")
        count = db.query(TaskCompletion).filter(
            TaskCompletion.user_id == user_id, TaskCompletion.date_key == dk
        ).count()
        result.append(count >= 1)
    return result


def generate_daily_insight(last_sleep, week_records, streak_days, avg_score):
    """Generate a personalized daily insight with priority and action."""
    insights = []

    # Check if no data at all
    if not last_sleep:
        return {
            "priority": "info",
            "priority_label": "开始",
            "title": "欢迎来到梦眠阁",
            "body": "记录你的第一晚睡眠，开启个性化睡眠改善之旅。",
            "action": {"label": "立即记录", "route": "/pages/record/record"},
        }

    score = last_sleep.score if last_sleep else 0
    duration = last_sleep.duration_hours if last_sleep else 0
    quality = last_sleep.quality if last_sleep else ""

    # 1. Score-based insights
    if score >= 85:
        insights.append({
            "priority": "success",
            "title": "昨晚睡眠质量优秀",
            "body": f"评分 {score} 分，睡眠 {duration}h。保持当前的作息节奏，你的身体正在感谢你。",
            "action": None,
        })
    elif score >= 70:
        insights.append({
            "priority": "info",
            "title": "睡眠质量良好，还有提升空间",
            "body": f"评分 {score} 分。试试睡前做5分钟呼吸练习，帮助进入更深层的睡眠。",
            "action": {"label": "试试呼吸训练", "route": "/pages/game/breathing/breathing"},
        })
    elif score >= 50:
        insights.append({
            "priority": "warning",
            "title": "睡眠需要关注",
            "body": f"评分 {score} 分。建议今晚提前30分钟上床，减少睡前屏幕时间。",
            "action": {"label": "设置闹钟提醒", "route": "/pages/alarm/alarm"},
        })
    elif score > 0:
        insights.append({
            "priority": "critical",
            "title": "昨晚睡眠质量较差",
            "body": f"评分 {score} 分，仅睡 {duration}h。今晚试试白噪音辅助入睡，如果持续低分建议咨询医生。",
            "action": {"label": "打开白噪音", "route": "/pages/noise/noise"},
        })
    else:
        insights.append({
            "priority": "info",
            "title": "昨晚还没有记录",
            "body": "记录睡眠是改善的第一步，现在去记录吧。",
            "action": {"label": "去记录", "route": "/pages/record/record"},
        })

    insight = insights[0]

    # 2. Trend-based additional insight (overrides if trend is significant)
    if len(week_records) >= 3:
        recent_scores = [r.score for r in week_records[-3:]]
        if len(recent_scores) >= 3 and all(recent_scores[i] < recent_scores[i + 1] for i in range(len(recent_scores) - 1)):
            insight = {
                "priority": "success",
                "title": "连续上升趋势！",
                "body": f"近3天睡眠评分持续上升，你的努力正在见效。继续保持！",
                "action": None,
            }
        elif len(recent_scores) >= 3 and all(recent_scores[i] > recent_scores[i + 1] for i in range(len(recent_scores) - 1)):
            insight = {
                "priority": "warning",
                "title": "评分连续下滑",
                "body": "近3天睡眠评分持续下降。检查一下：是否最近压力变大？咖啡因摄入增加？作息被打乱？",
                "action": {"label": "和AI教练聊聊", "route": "/pages/chat/chat"},
            }

    # 3. Streak-based motivation
    if streak_days >= 7:
        insight = {
            "priority": "success",
            "title": f"连续 {streak_days} 天达标！",
            "body": f"你已经连续 {streak_days} 天保持良好的睡眠习惯，这是了不起的成就！",
            "action": None,
        }
    elif streak_days == 0 and score > 0:
        insight = {
            "priority": "warning",
            "title": "连续记录中断了",
            "body": "没关系，重新开始永远不晚。今天记录睡眠，重新点燃连续记录的火苗。",
            "action": {"label": "记录睡眠", "route": "/pages/record/record"},
        }

    # 4. Duration-specific check
    if duration > 0 and duration < 5:
        insight = {
            "priority": "critical",
            "title": "睡眠严重不足",
            "body": f"昨晚仅睡 {duration} 小时，远低于推荐的7-9小时。长期睡眠不足会增加健康风险。今天请务必早点休息。",
            "action": {"label": "设置早睡闹钟", "route": "/pages/alarm/alarm"},
        }
    elif duration > 0 and duration > 10:
        insight = {
            "priority": "warning",
            "title": "睡眠时间偏长",
            "body": f"昨晚睡了 {duration} 小时，超过推荐范围。过长的睡眠有时也暗示睡眠质量不佳。",
            "action": {"label": "查看分析", "route": "/pages/analysis/analysis"},
        }

    return insight


def get_tag_stats(records: list) -> dict:
    stats = {}
    for r in records:
        try:
            tags = json.loads(r.tags or "[]")
        except Exception:
            tags = []
        for t in tags:
            stats[t] = stats.get(t, 0) + 1
    return stats


# ===== Task Generation =====
ALL_TASKS = [
    {"id": "t1", "title": "22:30前关灯准备入睡", "desc": "建立规律作息，让身体适应固定入睡时间", "points": 5, "category": "作息", "time_of_day": "evening"},
    {"id": "t2", "title": "睡前30分钟放下手机", "desc": "减少蓝光刺激，帮助褪黑素自然分泌", "points": 5, "category": "习惯", "time_of_day": "evening"},
    {"id": "t3", "title": "做5分钟冥想或呼吸练习", "desc": "4-7-8呼吸法：吸气4秒、屏息7秒、呼气8秒", "points": 5, "category": "放松", "time_of_day": "evening"},
    {"id": "t4", "title": "记录3件今天感恩的事", "desc": "减少焦虑反刍，以积极心态入睡", "points": 5, "category": "心理", "time_of_day": "evening"},
    {"id": "t5", "title": "睡前2小时内不进食", "desc": "避免消化活动干扰睡眠质量", "points": 5, "category": "饮食", "time_of_day": "evening"},
    {"id": "t6", "title": "下午3点后不喝咖啡/茶", "desc": "咖啡因半衰期约5-6小时，下午摄入影响夜间睡眠", "points": 5, "category": "饮食", "time_of_day": "afternoon"},
    {"id": "t7", "title": "户外活动30分钟", "desc": "自然光照有助于调节昼夜节律", "points": 5, "category": "运动", "time_of_day": "morning"},
    {"id": "t8", "title": "使用白噪音辅助入睡", "desc": "选择适合你的音景，建立入睡声音关联", "points": 5, "category": "工具", "time_of_day": "evening"},
    {"id": "t9", "title": "保持卧室温度18-22°C", "desc": "凉爽环境更有利于深度睡眠", "points": 5, "category": "环境", "time_of_day": "evening"},
    {"id": "t10", "title": "睡前热水浴或泡脚", "desc": "体温先升后降的过程有助于入睡", "points": 5, "category": "放松", "time_of_day": "evening"},
    {"id": "t11", "title": "午睡不超过30分钟", "desc": "短午睡提神，长午睡影响夜间睡眠", "points": 5, "category": "作息", "time_of_day": "afternoon"},
    {"id": "t12", "title": "避免睡前饮酒", "desc": "酒精虽助入睡但破坏深度睡眠和REM", "points": 5, "category": "饮食", "time_of_day": "evening"},
    {"id": "t13", "title": "写睡前日记或担忧清单", "desc": "把焦虑卸载到纸上，减少大脑反刍", "points": 5, "category": "心理", "time_of_day": "evening"},
    {"id": "t14", "title": "睡前轻度拉伸5分钟", "desc": "释放肌肉紧张，缓解白天久坐压力", "points": 5, "category": "运动", "time_of_day": "evening"},
    {"id": "t15", "title": "醒来后不赖床超过10分钟", "desc": "快速起床建立清醒节律，减少睡眠惯性", "points": 5, "category": "作息", "time_of_day": "morning"},
    {"id": "t16", "title": "白天至少20分钟自然光照", "desc": "阳光是调节生物钟最重要的信号", "points": 5, "category": "环境", "time_of_day": "morning"},
    {"id": "t17", "title": "晚上只开暖色灯", "desc": "暖光(2700K)比冷光对睡眠干扰更小", "points": 5, "category": "环境", "time_of_day": "evening"},
    {"id": "t18", "title": "与AI助手对话讨论睡眠", "desc": "获取个性化建议和睡眠知识", "points": 5, "category": "工具", "time_of_day": "afternoon"},
]

ALL_BADGES = [
    {"id": "b1", "name": "初心者", "icon": "🌱", "desc": "完成第一个任务"},
    {"id": "b2", "name": "规律达人", "icon": "📈", "desc": "连续7天作息达标"},
    {"id": "b3", "name": "冥想大师", "icon": "🌴", "desc": "完成10次冥想任务"},
    {"id": "b4", "name": "早睡先锋", "icon": "🌙", "desc": "累计20次22:30前入睡"},
    {"id": "b5", "name": "满月", "icon": "🌝", "desc": "一天完成全部4个任务"},
    {"id": "b6", "name": "白噪音达人", "icon": "♫", "desc": "使用白噪音7次"},
    {"id": "b7", "name": "百日修行", "icon": "★", "desc": "累计积分50分"},
    {"id": "b8", "name": "睡眠博士", "icon": "📘", "desc": "与AI对话5次"},
]


def generate_today_tasks_rule_based(profile_data: Optional[dict] = None) -> list:
    """Rule-based task generation — used as fallback when AI is unavailable."""
    selected = []
    if profile_data:
        priorities = [p.strip() for p in (profile_data.get("improvement_priority") or "").split(",") if p.strip()]
        preferred = [p.strip() for p in (profile_data.get("preferred_tasks") or "").split(",") if p.strip()]
        issues = [p.strip() for p in (profile_data.get("sleep_issues") or "").split(",") if p.strip()]
        stress = profile_data.get("stress_level", "")

        if "入睡速度" in priorities: selected.extend(["t1", "t3"])
        if "睡眠深度" in priorities: selected.extend(["t9", "t8"])
        if "减少夜醒" in priorities: selected.extend(["t2", "t12"])
        if "作息规律" in priorities: selected.extend(["t1", "t15"])
        if "精力恢复" in priorities: selected.extend(["t7", "t16"])
        if "冥想放松" in preferred: selected.append("t3")
        if "习惯调整" in preferred: selected.append("t2")
        if "运动锻炼" in preferred: selected.append("t14")
        if "饮食调整" in preferred: selected.append("t6")
        if "环境优化" in preferred: selected.append("t9")
        if "知识学习" in preferred: selected.append("t18")
        if "入睡困难" in issues: selected.extend(["t1", "t10"])
        if "夜间醒来" in issues: selected.extend(["t2", "t9"])
        if "早醒" in issues: selected.append("t15")
        if "睡眠浅" in issues: selected.extend(["t8", "t9"])
        if stress in ("高", "极高"): selected.extend(["t4", "t13"])

    selected = list(dict.fromkeys(selected))
    while len(selected) < 4:
        remaining = [t for t in ALL_TASKS if t["id"] not in selected]
        if not remaining:
            break
        selected.append(random.choice(remaining)["id"])
    selected = selected[:4]
    random.shuffle(selected)
    return [next(t for t in ALL_TASKS if t["id"] == tid) for tid in selected]


# ===== Knowledge Base =====
KNOWLEDGE_ARTICLES = [
    {"id": "k1", "category": "睡眠科学", "title": "睡眠周期：了解你的90分钟节律",
     "summary": "每个睡眠周期约90分钟，包含浅睡、深睡和REM阶段。成年人每晚需要4-6个完整周期。",
     "content": "睡眠不是均匀的过程，而是由多个周期组成。每个周期约90分钟，包含：\n\n1. **入睡期（N1）**：浅睡，容易被唤醒，占5%\n2. **浅睡期（N2）**：体温下降，心率减慢，占45-55%\n3. **深睡期（N3）**：身体修复、免疫增强，占15-25%\n4. **REM睡眠**：梦境阶段，记忆巩固，占20-25%\n\n💡 在周期结束时醒来（而非深睡中被唤醒）会让你感觉更清醒。试着在90分钟的倍数（6h/7.5h/9h）后起床。",
     "tags": ["睡眠周期", "REM", "深睡"]},
    {"id": "k2", "category": "睡眠科学", "title": "褪黑素：你的天然安眠药",
     "summary": "褪黑素是调节睡眠-觉醒节律的关键激素。光线是最强的褪黑素抑制剂。",
     "content": "褪黑素由大脑松果体分泌，在黑暗中释放，帮助你入睡。\n\n**褪黑素的关键事实**：\n- 通常在睡前2小时开始升高\n- 蓝光（手机/电脑屏幕）会显著抑制褪黑素分泌\n- 随着年龄增长，褪黑素分泌减少\n\n**自然促进褪黑素的方法**：\n- 睡前1-2小时减少屏幕使用\n- 白天接受至少30分钟自然光照\n- 保持规律的作息时间\n- 晚上使用暖色灯光（2700K以下）",
     "tags": ["褪黑素", "昼夜节律", "蓝光"]},
    {"id": "k3", "category": "睡眠科学", "title": "生物钟：你的体内时钟如何工作",
     "summary": "视交叉上核是身体的主时钟，通过光照信号同步。不规律的作息会打乱生物钟。",
     "content": "**生物钟（昼夜节律）的关键点**：\n\n- 主时钟位于大脑视交叉上核（SCN）\n- 通过视网膜接收的光信号进行校准\n- 调控体温、激素分泌、警觉性\n\n**维持健康生物钟的策略**：\n- 每天在同一时间起床（比固定入睡时间更重要）\n- 早晨第一时间接触自然光\n- 避免周末「社交时差」（比平时晚起超过1小时）\n- 晚上10点后避免高强度运动\n\n⚠️ 轮班工作者和经常跨时区旅行者最容易出现生物钟紊乱。",
     "tags": ["生物钟", "昼夜节律", "时差"]},
    {"id": "k4", "category": "CBT-I疗法", "title": "刺激控制疗法：重建床与睡眠的连接",
     "summary": "CBT-I的核心技术之一，通过限制床上的非睡眠活动来强化「床=睡眠」的条件反射。",
     "content": "**刺激控制疗法六原则**：\n\n1. 只有感到困倦时才上床\n2. 床只用于睡眠和性生活（不玩手机、不工作）\n3. 躺下20分钟仍无法入睡，起床去另一个房间\n4. 做轻松的事（阅读、听轻音乐），直到感到困倦\n5. 如果回床上仍睡不着，重复步骤3\n6. 每天在同一时间起床，无论前一晚睡了多久\n\n💡 刚开始几天可能更难入睡，但坚持1-2周后效果显著。这是最有效的非药物失眠疗法之一。",
     "tags": ["CBT-I", "刺激控制", "失眠"]},
    {"id": "k5", "category": "CBT-I疗法", "title": "睡眠限制疗法：压缩床上时间以提高效率",
     "summary": "暂时限制在床上的时间，以提高睡眠效率（实际睡眠时间/卧床时间）。",
     "content": "**睡眠限制疗法步骤**：\n\n1. 记录一周的睡眠日记\n2. 计算平均实际睡眠时间\n3. 将卧床时间限制为该平均值（不低于5小时）\n4. 固定起床时间\n5. 每周根据睡眠效率调整：\n   - 效率 > 90%：增加15分钟卧床时间\n   - 效率 < 80%：减少15分钟\n   - 效率 80-90%：保持不变\n\n⚠️ 此方法应在专业人士指导下进行，不适合有双相障碍或癫痫病史的人群。",
     "tags": ["CBT-I", "睡眠限制", "睡眠效率"]},
    {"id": "k6", "category": "CBT-I疗法", "title": "认知重构：改变对睡眠的错误信念",
     "summary": "识别并挑战关于睡眠的非理性想法，减少对失眠的灾难化思维。",
     "content": "**常见的睡眠错误信念及替代想法**：\n\n❌ 「我今晚肯定又睡不着」\n✅ 「我可能需要一些时间入睡，但这很正常」\n\n❌ 「睡不够8小时会对身体造成严重伤害」\n✅ 「7-9小时是推荐范围，偶尔少睡一些不会有长期影响」\n\n❌ 「失眠会毁了我的明天」\n✅ 「即使没睡好，我依然可以完成大部分事情」\n\n❌ 「躺在床上休息也算浪费时间」\n✅ 「安静休息也有恢复效果，焦虑才最消耗精力」\n\n💡 练习：写下你的睡眠担忧，逐条用更理性的想法替代。",
     "tags": ["CBT-I", "认知重构", "焦虑"]},
    {"id": "k7", "category": "睡眠卫生", "title": "打造理想睡眠环境的10个要素",
     "summary": "卧室环境对睡眠质量有巨大影响。温度、光线、噪音是最关键的三个因素。",
     "content": "**卧室优化清单**：\n\n1. 🌡 **温度**：18-22°C是最佳睡眠温度\n2. 🌑 **光线**：尽可能全黑，使用遮光窗帘或眼罩\n3. 🔇 **噪音**：低于30分贝，使用白噪音掩盖突发声响\n4. 🛏 **床垫**：每7-10年更换，选择适合你睡姿的硬度\n5. 📱 **电子设备**：移出卧室或至少放在看不见的地方\n6. 🕰 **时钟**：把钟面转过去，避免频繁看时间\n7. 🌿 **空气质量**：保持通风，适度湿度\n8. 🐾 **宠物**：如果宠物影响睡眠，考虑让它睡在别的房间\n9. 🎨 **颜色**：柔和暖色调有助于放松\n10. 📚 **功能分区**：床只用于睡眠，强化条件反射",
     "tags": ["睡眠环境", "卧室", "卫生"]},
    {"id": "k8", "category": "睡眠卫生", "title": "咖啡因、酒精与睡眠的真相",
     "summary": "咖啡因半衰期5-6小时，下午摄入影响夜间睡眠。酒精助入睡但破坏深度睡眠。",
     "content": "**咖啡因**：\n- 半衰期：5-6小时（200mg下午3点摄入→晚上9点仍有100mg在体内）\n- 影响：延迟入睡、减少深睡、增加夜醒\n- 建议：下午2点后不摄入咖啡因\n\n**酒精**：\n- 初期效果：镇静，加速入睡\n- 后期影响：\n  - 抑制REM睡眠（梦境阶段）\n  - 增加后半段夜醒\n  - 加重打鼾和睡眠呼吸暂停\n- 建议：睡前3小时内不饮酒\n\n**尼古丁**：\n- 是兴奋剂，增加入睡时间和夜醒次数\n- 尼古丁戒断也会在夜间唤醒吸烟者",
     "tags": ["咖啡因", "酒精", "饮食"]},
    {"id": "k9", "category": "睡眠卫生", "title": "运动对睡眠的影响：时机很重要",
     "summary": "规律运动是最有效的非药物睡眠改善方法之一，但运动时机很关键。",
     "content": "**运动如何改善睡眠**：\n- 增加深睡时间\n- 降低入睡所需时间\n- 减少夜间醒来次数\n- 减轻压力和焦虑\n\n**最佳运动时机**：\n- 上午/下午：最适合，可帮助调节生物钟\n- 傍晚（睡前3-4小时）：中等强度可以\n- 睡前1-2小时：避免高强度运动，可能提高核心体温\n\n**推荐运动类型**：\n- 有氧运动（快走、慢跑、游泳）：每周150分钟\n- 瑜伽和太极：有助于放松和正念\n- 力量训练：改善整体健康",
     "tags": ["运动", "睡眠质量", "深睡"]},
    {"id": "k10", "category": "放松技巧", "title": "4-7-8呼吸法：60秒入眠技巧",
     "summary": "源于瑜伽的调息法，通过调节呼吸激活副交感神经系统。",
     "content": "**4-7-8呼吸法步骤**：\n\n1. 舒服地躺下，舌尖抵住上颚前部\n2. 用嘴完全呼气，发出「呼」的声音\n3. 闭嘴，用鼻子**吸气4秒**\n4. **屏住呼吸7秒**\n5. 用嘴**缓慢呼气8秒**（发出「呼」声）\n6. 重复3-5轮\n\n**为什么有效**：\n- 延长呼气激活副交感神经（放松反应）\n- 屏息增加血液中CO2浓度，有轻微镇静效果\n- 专注计数分散了对焦虑思维的注意力\n\n💡 每天练习2次，连续4-6周效果最佳。",
     "tags": ["呼吸法", "放松", "入眠技巧"]},
    {"id": "k11", "category": "放松技巧", "title": "渐进式肌肉放松法",
     "summary": "依次紧张再放松身体各肌肉群，释放累积的紧张感。",
     "content": "**逐步练习**（每个部位紧张5秒→放松10秒）：\n\n1. 脚：脚趾向下弯曲→放松\n2. 小腿：脚尖向上勾→放松\n3. 大腿：收紧大腿肌肉→放松\n4. 腹部：收紧腹肌→放松\n5. 手：握紧拳头→放松\n6. 手臂：弯曲手臂收紧二头肌→放松\n7. 肩膀：耸肩靠近耳朵→放松\n8. 面部：皱眉、紧闭眼睛、咬紧牙关→放松\n\n💡 配合深呼吸效果更佳。可以在床上进行，做完后通常会感到明显的身体放松。",
     "tags": ["肌肉放松", "身体扫描", "放松"]},
    {"id": "k12", "category": "放松技巧", "title": "睡前冥想：5分钟正念练习",
     "summary": "正念冥想帮助你从白天的思绪中抽离，为睡眠做准备。",
     "content": "**5分钟睡前正念冥想**：\n\n1. 舒服躺下，闭上眼睛\n2. 把注意力放在呼吸上，感受腹部的起伏\n3. 思绪飘走是正常的，温柔地把注意力带回来\n4. 做一次「身体扫描」：从脚趾到头顶，注意每个部位的感受\n5. 想象每个「杂念」是一片云，让它飘过去即可\n\n**常见误区**：\n- ❌ 「我必须清空大脑」→ ✅ 允许思绪存在，不与之纠缠\n- ❌ 「我做不好冥想」→ ✅ 分心后再回来就是练习本身\n\n📱 推荐入门APP：潮汐、Headspace、Calm",
     "tags": ["冥想", "正念", "放松"]},
    {"id": "k13", "category": "特殊人群", "title": "倒班工作者的睡眠策略",
     "summary": "轮班工作者患睡眠障碍的风险更高，但可以通过策略性补觉来减轻影响。",
     "content": "**对倒班工作者的建议**：\n\n1. 下夜班回家途中戴墨镜，减少早晨光照信号\n2. 回家后立即睡觉，使用遮光窗帘\n3. 将睡眠分成「核心睡眠（4-5小时）+ 小睡（20-90分钟）」\n4. 轮班方向：顺时针（早→中→夜）比逆时针更容易适应\n5. 夜班期间：工作环境中使用明亮灯光\n6. 补充褪黑素（遵医嘱）\n\n⚠️ 长期夜班工作者应定期进行健康检查。",
     "tags": ["倒班", "夜班", "补觉"]},
    {"id": "k14", "category": "特殊人群", "title": "老年人睡眠变化：正常衰老还是睡眠障碍？",
     "summary": "随年龄增长深睡减少是正常现象，但频繁早醒和日间嗜睡需要关注。",
     "content": "**正常年龄相关变化**：\n- 深睡比例减少（从20%降至5-10%）\n- 入睡时间稍延长\n- 夜间醒来次数增加（1-2次正常）\n\n**需要就医的信号**：\n- 每周3次以上严重失眠\n- 日间过度嗜睡\n- 打鼾声响亮且不规律（可能是睡眠呼吸暂停）\n- 腿部不自主抽动\n\n**老年人睡眠策略**：\n- 固定作息，即使睡得少也按时起床\n- 增加日间光照和活动量\n- 限制午睡在30分钟以内\n- 减少利尿剂类药物的睡前服用",
     "tags": ["老年人", "睡眠障碍", "衰老"]},
    {"id": "k15", "category": "睡眠误区", "title": "关于睡眠的5个常见误区",
     "summary": "科学辟谣：打鼾≠睡得好、补觉完全有用、睡前饮酒助眠等都是误区。",
     "content": "**误区1：打鼾说明睡得香**\n✅ 打鼾可能是睡眠呼吸暂停的信号，需要医学评估\n\n**误区2：周末补觉可以抵消一周的睡眠债**\n✅ 补觉有帮助但不能完全抵消。规律的作息更重要\n\n**误区3：睡前喝酒有助于睡眠**\n✅ 酒精加速入睡但破坏后半段睡眠质量和REM\n\n**误区4：我可以「训练」自己少睡**\n✅ 基因决定了你的睡眠需求。少于5小时会增加健康风险\n\n**误区5：躺在床上闭眼休息和睡着差不多**\n✅ 安静休息有价值，但无法替代睡眠中的记忆巩固和代谢清除功能",
     "tags": ["误区", "科普", "辟谣"]},
    {"id": "k16", "category": "饮食与睡眠", "title": "助眠食物指南：吃什么帮助入睡",
     "summary": "富含色氨酸、镁、褪黑素的食物有助于改善睡眠。",
     "content": "**助眠营养素及食物来源**：\n\n- **色氨酸**（合成褪黑素的原料）：牛奶、香蕉、坚果、火鸡\n- **镁**（放松神经和肌肉）：深绿色蔬菜、南瓜籽、黑巧克力\n- **褪黑素**（直接补充）：酸樱桃、核桃、番茄\n- **B6**：鱼类、鸡肉、土豆\n\n**睡前推荐小食**：\n- 一小杯温牛奶\n- 香蕉+少量杏仁\n- 全麦饼干+奶酪\n\n**睡前应避免**：\n- 大量进食、辛辣食物、含糖饮料",
     "tags": ["饮食", "助眠食物", "营养"]},
    {"id": "k17", "category": "饮食与睡眠", "title": "什么时候吃晚餐对睡眠最好？",
     "summary": "睡前2-3小时完成晚餐，避免消化活动干扰睡眠。",
     "content": "**晚餐时间与睡眠质量**：\n\n- 理想：睡前3小时完成晚餐\n- 至少：睡前2小时\n- 如果睡前饿了：少量轻食（见助眠食物指南）\n\n**为什么时间重要**：\n- 消化过程提高核心体温（与入睡需要的降温相反）\n- 胃食管反流可能在躺下时加重\n- 血糖波动影响睡眠稳定性",
     "tags": ["饮食", "晚餐", "消化"]},
    {"id": "k18", "category": "压力与睡眠", "title": "焦虑反刍：为什么一躺下就开始胡思乱想",
     "summary": "床上是大脑「无事可做」的时刻，焦虑的想法容易趁虚而入。学习管理睡前反刍的技巧。",
     "content": "**为什么睡前容易胡思乱想**：\n- 白天用忙碌分散了注意力\n- 安静环境中，未解决的问题浮现出来\n- 对失眠的焦虑本身成为新的压力源\n\n**应对技巧**：\n1. **担忧时间**：白天安排15分钟专门「担心的时间」\n2. **担忧清单**：睡前记下所有担心的事，告诉自己「已经记下来了」\n3. **感恩日记**：写下3件今天感恩的事\n4. **认知脱钩**：告诉自己「这只是想法，不等于事实」\n5. **感官锚定**：把注意力放在呼吸或身体感受上",
     "tags": ["焦虑", "反刍", "睡前思维"]},
    {"id": "k19", "category": "压力与睡眠", "title": "睡眠与心理健康：双向影响",
     "summary": "睡眠问题和心理健康问题经常共存，改善其中一个有助于另一个。",
     "content": "**睡眠与心理健康的双向关系**：\n\n😰 **压力→睡眠**：皮质醇升高→入睡困难、睡眠变浅\n😴 **睡眠不足→情绪**：情绪调节能力下降、易怒、焦虑\n🔄 **恶性循环**：失眠→焦虑→更严重的失眠\n\n**打断循环的策略**：\n- 同时处理睡眠和心理健康问题\n- CBT-I 已被证明对失眠和抑郁共病有效\n- 如果情绪问题持续超过2周，请寻求专业帮助\n\n📞 心理援助热线：12320-5（全国公共卫生公益热线）",
     "tags": ["心理健康", "焦虑", "抑郁"]},
    {"id": "k20", "category": "科技与睡眠", "title": "睡眠追踪设备的准确性如何？",
     "summary": "消费级睡眠追踪器可以反映趋势，但不能替代专业睡眠监测。",
     "content": "**设备类型与准确性**：\n\n- **可穿戴设备**（手表/手环）：心率+运动数据估算，对深睡/浅睡分类准确率约60-70%\n- **床垫下传感器**：检测运动和呼吸，准确度中等\n- **手机APP**：仅靠声音和运动，准确度较低\n- **PSG多导睡眠监测**：金标准，需要医院进行\n\n**使用建议**：\n- 关注趋势而非绝对值\n- 不要为「睡眠评分」过度焦虑\n- 结合主观感受（晨起精力）综合判断",
     "tags": ["睡眠追踪", "可穿戴设备", "科技"]},
]

KNOWLEDGE_CATEGORIES = sorted(set(a["category"] for a in KNOWLEDGE_ARTICLES))


# ===== Sleep Improvement Plans =====
IMPROVEMENT_PLANS = [
    {
        "id": "plan_insomnia",
        "title": "入睡困难改善计划",
        "icon": "🌙",
        "target": "入睡困难",
        "duration_days": 21,
        "description": "基于CBT-I刺激控制疗法，帮助你在3周内缩短入睡时间。",
        "phases": [
            {"week": 1, "title": "建立基线", "tasks": [
                "每天记录入睡时间（从关灯到睡着）",
                "固定起床时间（即使是周末）",
                "睡前1小时放下手机",
            ]},
            {"week": 2, "title": "强化训练", "tasks": [
                "只有困了才上床",
                "躺下20分钟睡不着就起来",
                "做4-7-8呼吸练习",
            ]},
            {"week": 3, "title": "巩固习惯", "tasks": [
                "保持固定作息",
                "加入睡前放松仪式（冥想/阅读）",
                "回顾进展，调整目标",
            ]},
        ],
    },
    {
        "id": "plan_early_wake",
        "title": "早醒问题改善计划",
        "icon": "🌅",
        "target": "早醒",
        "duration_days": 14,
        "description": "针对凌晨醒后无法再入睡的情况，通过光照和作息调整来改善。",
        "phases": [
            {"week": 1, "title": "调整阶段", "tasks": [
                "推迟入睡时间30-60分钟",
                "早晨醒来后立即拉开窗帘接触自然光",
                "避免白天长时间午睡（不超过20分钟）",
            ]},
            {"week": 2, "title": "巩固阶段", "tasks": [
                "保持固定起床时间",
                "睡前进行放松练习",
                "如果早醒，不要看时间，尝试回到放松状态",
            ]},
        ],
    },
    {
        "id": "plan_irregular",
        "title": "作息规律化计划",
        "icon": "📅",
        "target": "作息不规律",
        "duration_days": 14,
        "description": "通过固定起床时间和光照管理来重新校准你的生物钟。",
        "phases": [
            {"week": 1, "title": "固定锚点", "tasks": [
                "每天同一时间起床（误差不超过30分钟）",
                "起床后30分钟内接触自然光15分钟",
                "晚上固定时间进行放松活动",
            ]},
            {"week": 2, "title": "规律作息", "tasks": [
                "根据起床时间反推入睡时间（保证7-9小时）",
                "建立睡前1小时「放松缓冲」仪式",
                "周末作息偏差不超过1小时",
            ]},
        ],
    },
    {
        "id": "plan_shallow_sleep",
        "title": "深度睡眠提升计划",
        "icon": "💪",
        "target": "睡眠浅",
        "duration_days": 21,
        "description": "通过运动、环境和饮食优化来增加深睡比例。",
        "phases": [
            {"week": 1, "title": "基础优化", "tasks": [
                "保持卧室温度在18-22°C",
                "每天30分钟有氧运动（上午或下午）",
                "晚餐在睡前3小时完成",
            ]},
            {"week": 2, "title": "深度促进", "tasks": [
                "尝试睡前热水浴或泡脚（睡前1.5小时）",
                "使用白噪音或耳塞减少环境干扰",
                "限制晚间咖啡因和酒精",
            ]},
            {"week": 3, "title": "习惯巩固", "tasks": [
                "坚持运动习惯",
                "记录并反思睡眠质量变化",
                "微调方案找到最适合自己的模式",
            ]},
        ],
    },
    {
        "id": "plan_stress",
        "title": "压力性失眠缓解计划",
        "icon": "🧘",
        "target": "压力",
        "duration_days": 14,
        "description": "通过压力管理技巧和睡前放松仪式来打断「焦虑→失眠」循环。",
        "phases": [
            {"week": 1, "title": "减压入门", "tasks": [
                "每天写「担忧清单」，把焦虑卸载到纸上",
                "睡前做5分钟正念呼吸练习",
                "记录3件今天感恩的事",
            ]},
            {"week": 2, "title": "深化练习", "tasks": [
                "练习渐进式肌肉放松法",
                "白天安排15分钟「担忧时间」",
                "培养替代性放松活动（阅读、音乐、温水浴）",
            ]},
        ],
    },
    {
        "id": "plan_sleep_hygiene",
        "title": "睡眠卫生基础计划",
        "icon": "🏠",
        "target": "通用",
        "duration_days": 7,
        "description": "适合所有想要改善睡眠的人，涵盖最基础的睡眠卫生原则。",
        "phases": [
            {"week": 1, "title": "7天挑战", "tasks": [
                "每天同一时间起床",
                "优化睡眠环境（温度/光线/噪音）",
                "下午2点后不喝咖啡",
                "睡前30分钟放下电子设备",
                "记录睡眠日志",
                "加入一项放松练习",
                "回顾一周进展，设定长期目标",
            ]},
        ],
    },
]

ONBOARDING_STEPS = [
    {"step": 1, "title": "基本信息", "question": "请告诉我们你的基本情况", "fields": ["age", "gender"]},
    {"step": 2, "title": "睡眠目标", "question": "你理想的睡眠是什么样的？", "fields": ["sleep_goal_hours", "bedtime_target", "wakeup_target"]},
    {"step": 3, "title": "睡眠困扰", "question": "你目前面临哪些睡眠问题？", "fields": ["sleep_issues", "sleep_issue_duration"]},
    {"step": 4, "title": "生活习惯", "question": "你的日常习惯如何影响睡眠？", "fields": ["caffeine_intake", "exercise_frequency", "stress_level"]},
    {"step": 5, "title": "改善目标", "question": "你最想改善什么？", "fields": ["improvement_priority", "primary_goal"]},
]


# ===== Sleep Metrics & Reports =====
def calc_sleep_efficiency(duration: float, bedtime: datetime, wake_time: datetime) -> float:
    """Sleep efficiency = actual sleep / time in bed * 100."""
    time_in_bed = (wake_time - bedtime).total_seconds() / 3600
    if time_in_bed < 0:
        time_in_bed += 24
    if time_in_bed <= 0:
        return 0
    return round(min(duration / time_in_bed * 100, 100), 1)


def calc_sleep_debt(records: list, goal_hours: float) -> dict:
    """Calculate cumulative sleep debt over the period."""
    if not records:
        return {"total_debt": 0, "avg_deficit": 0, "days_in_debt": 0}
    total_debt = 0
    days_in_debt = 0
    for r in records:
        dur = r.duration_hours or 0
        deficit = goal_hours - dur
        if deficit > 0:
            total_debt += deficit
            days_in_debt += 1
    return {
        "total_debt": round(total_debt, 1),
        "avg_deficit": round(total_debt / len(records), 1) if records else 0,
        "days_in_debt": days_in_debt,
    }


def generate_weekly_report(user_name: str, profile: dict, records: list, stats: dict) -> dict:
    """Generate a structured weekly sleep report with AI insights."""
    avg_dur = stats.get("avg_duration", 0)
    avg_score = stats.get("avg_score", 0)
    streak = stats.get("streak_days", 0)
    consistency = stats.get("consistency", "--")
    tag_counts = stats.get("tag_counts", {})
    debt = stats.get("sleep_debt", {})
    goal = profile.get("sleep_goal_hours", 8) if profile else 8

    # Build summary
    summary_parts = []
    if avg_dur >= goal - 0.5:
        summary_parts.append(f"本周平均睡眠 {avg_dur}h，达到目标水平")
    elif avg_dur > 0:
        summary_parts.append(f"本周平均睡眠 {avg_dur}h，距目标 {goal}h 还差 {round(goal-avg_dur,1)}h")
    else:
        summary_parts.append("本周暂无睡眠记录")

    if avg_score >= 80:
        summary_parts.append("睡眠质量优秀")
    elif avg_score >= 60:
        summary_parts.append("睡眠质量良好")
    elif avg_score > 0:
        summary_parts.append("睡眠质量有待改善")

    if streak >= 5:
        summary_parts.append(f"已连续 {streak} 天达标，表现很棒！")
    elif streak > 0:
        summary_parts.append(f"已连续 {streak} 天达标")

    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    if top_tags:
        summary_parts.append(f"主要标签: {', '.join(f'{t}({c}次)' for t,c in top_tags)}")

    # AI-powered analysis
    ai_analysis = ""
    if records:
        try:
            record_summary = "\n".join(
                f"- {r.diary_date}: {r.duration_hours}h, 评分{r.score}, 标签{r.tags}, 备注:{r.notes or '无'}"
                for r in records[-7:]
            )
            prompt = f"""你是专业的睡眠分析师。根据用户本周的睡眠数据，写一段150字以内的总结分析，包含：
1. 整体趋势判断
2. 最突出的问题（如果有）
3. 一个具体可行的改善建议
语气温暖鼓励，不给出医疗诊断。

用户名：{user_name}
睡眠目标：{goal}h
本周数据：
{record_summary}
平均时长：{avg_dur}h，平均评分：{avg_score}，规律度：{consistency}"""
            ai_analysis = _ai_call([
                {"role": "system", "content": "你是专业的睡眠分析师，回答简洁温暖。"},
                {"role": "user", "content": prompt},
            ], temperature=0.7, max_tokens=200)
        except Exception:
            ai_analysis = ""

    # Action items
    action_items = []
    if avg_dur > 0 and avg_dur < goal - 0.5:
        action_items.append(f"每天提前15分钟上床，逐步将睡眠时长从 {avg_dur}h 提升至 {goal}h")
    if stats.get("consistency_minutes", 0) > 60:
        action_items.append("固定起床时间有助于提高作息规律度")
    if "失眠" in tag_counts or "早醒" in tag_counts:
        action_items.append("尝试刺激控制疗法：只有困了才上床，躺下20分钟睡不着就起来")
    if debt.get("days_in_debt", 0) > 3:
        action_items.append("本周多天睡眠不足，周末可以适当补觉但不要超过1小时")
    if not action_items:
        action_items.append("保持当前良好的睡眠习惯！")

    return {
        "user_name": user_name,
        "period": "weekly",
        "summary": "。".join(summary_parts) + "。",
        "ai_analysis": ai_analysis,
        "metrics": {
            "avg_duration": avg_dur,
            "avg_score": avg_score,
            "consistency": consistency,
            "streak_days": streak,
            "sleep_debt": debt,
            "sleep_efficiency": stats.get("avg_efficiency", 0),
            "tag_counts": tag_counts,
        },
        "action_items": action_items,
        "records_count": len(records),
    }


# ===== 21天睡眠改善课程 =====
def _21_day_course() -> list:
    """21天系统睡眠改善课程 — 每天视频+文章+任务."""
    return [
        # ===== 第一周：睡眠基础 =====
        {"day": 1, "video_url": "//player.bilibili.com/player.html?bvid=BV1gTSwYDEum&page=1&autoplay=0", "video_bvid": "BV1gTSwYDEum", "video_title": "CBT-I教程：睡眠的阶段和周期", "week": 1, "week_title": "睡眠基础",
         "title": "了解你的睡眠", "subtitle": "掌握睡眠周期与生物钟的科学原理",
         "category": "睡眠科学",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1gTSwYDEum&page=1&autoplay=0", "video_bvid": "BV1gTSwYDEum", "video_title": "CBT-I教程：睡眠的阶段和周期", "video_duration": "8分钟",
         "article": """## 你的睡眠不是均匀的

每个晚上，你的大脑会经历 4-6 个完整的睡眠周期，每个周期大约 90 分钟。

### 一个完整的睡眠周期包括：

**入睡期（N1）** — 占 5%
身体开始放松，脑波放缓。这个阶段你很容易被叫醒，有时会有"坠落感"。

**浅睡期（N2）** — 占 45-55%
体温下降，心率减慢，眼球停止运动。这是睡眠中占比最大的阶段，对记忆巩固很重要。

**深睡期（N3）** — 占 15-25%
身体修复的黄金时间！生长激素分泌，免疫系统增强，细胞修复加速。

**快速眼动期（REM）** — 占 20-25%
大脑高度活跃，梦境发生的阶段。对情绪调节和创造力至关重要。

### 关键洞察

> 💡 在睡眠周期结束时（而非深睡中）被唤醒，你会感觉更清醒。这就是为什么有时睡 6 小时比 8 小时醒来更精神。

**今日金句：睡眠不是浪费时间的空白期，而是大脑的"夜间维护程序"。**""",
         "task": "今晚记录你的入睡时间和起床时间，计算你大约完成了几个90分钟周期。观察你是在哪个阶段醒来的。",
         "xp": 15,
         "tips": ["保持卧室完全黑暗，温度在 18-22°C", "同一时间起床比同一时间入睡更重要"]},

        {"day": 2, "video_url": "//player.bilibili.com/player.html?bvid=BV14UUZYKEFh&page=1&autoplay=0", "video_bvid": "BV14UUZYKEFh", "video_title": "CBT-I教程：认知行为疗法概述", "week": 1, "week_title": "睡眠基础",
         "title": "打造理想睡眠环境", "subtitle": "温度、光线、噪音——睡眠的三大环境因素",
         "category": "睡眠环境",
         "video_url": "//player.bilibili.com/player.html?bvid=BV14UUZYKEFh&page=1&autoplay=0", "video_bvid": "BV14UUZYKEFh", "video_title": "CBT-I教程：认知行为疗法概述", "video_duration": "10分钟",
         "article": """## 你的卧室是睡眠圣地还是清醒牢房？

### 温度：凉爽是关键

人体核心温度在入睡前自然下降，这是身体发出的"该睡了"信号。

- **最佳温度**：18-22°C
- 太热会导致频繁醒来，减少深睡和 REM 睡眠
- 睡前 1-2 小时洗个热水澡：体温先升后降，正好触发睡意

### 光线：黑暗是最好的安眠药

视网膜中的 ipRGC 细胞对蓝光（480nm）最敏感，直接连接你的生物钟中枢。

- **睡前 1 小时**：换成暖色灯光（2700K 以下）
- **窗帘**：使用遮光窗帘或眼罩
- **电子设备**：开启夜间模式，或干脆放另一个房间
- **夜灯**：如果需要，用红色灯（对褪黑素影响最小）

### 噪音：稳定比安静更重要

突然的声音变化比持续的噪音更打扰睡眠。

- 白噪音可以帮助掩盖突发的环境噪音
- 风扇、空气净化器的稳定声音是不错的选择
- 耳塞适合对声音敏感的人

**今日金句：你的卧室环境就是你的睡眠质量的硬件基础。**""",
         "task": "今晚做三件事：(1) 调低卧室温度到 20°C 左右；(2) 睡前 1 小时把灯光调成暖色；(3) 把所有电子屏幕移出卧室或开启夜间模式。记录你的感受。",
         "xp": 15,
         "tips": ["遮光窗帘是最值得投资的睡眠用品", "睡前 1 小时避免所有屏幕"]},

        {"day": 3, "week": 1, "week_title": "睡眠基础",
         "title": "建立规律作息", "subtitle": "固定起床时间是改善睡眠的第一法则",
         "category": "作息规律",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1DL411D7nc&page=1&autoplay=0", "video_bvid": "BV1DL411D7nc", "video_title": "规律作息的神秘力量：太阳光", "video_duration": "7分钟",
         "article": """## 为什么生物钟如此重要？

你的大脑中有一个"主时钟"——视交叉上核（SCN），它通过光线信号校准，调控你的体温、激素分泌和睡眠-觉醒节律。

### 起床时间 > 入睡时间

睡眠专家一致认为：**固定起床时间比固定入睡时间更重要。**

- 每天早上在同一时间起床（误差不超过 30 分钟）
- 起床后立刻接触自然光 15-30 分钟
- 即使在周末也不要"补觉"超过 1 小时

### 社交时差

> 周末比平时晚起 2 小时以上，相当于每周经历一次"跨时区旅行"。这在睡眠医学中被称为"社交时差"，是破坏生物钟的头号元凶。

### 困了再上床

- 只有真正感到困倦时才上床
- 如果躺下 20 分钟还没睡着，起来去另一个房间
- 做轻松的事（阅读、听轻音乐），等有困意再回去

**今日金句：规律不是刻板，而是给身体一个可预测的安全信号。**""",
         "task": "设定一个固定的起床时间（建议比现在早 30 分钟），连续 3 天坚持在同一时间起床（包括周末）。记录起床时间和你白天的精力状态。",
         "xp": 15,
         "tips": ["把闹钟放在房间另一端", "醒来后立即拉开窗帘"]},

        {"day": 4, "video_url": "//player.bilibili.com/player.html?bvid=BV1Ka411N7nx&page=1&autoplay=0", "video_bvid": "BV1Ka411N7nx", "video_title": "杨定一：睡前一小时正念冥想", "week": 1, "week_title": "睡眠基础",
         "title": "创造睡前仪式", "subtitle": "用仪式感告诉你的大脑：该关机了",
         "category": "放松技巧",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1Ka411N7nx&page=1&autoplay=0", "video_bvid": "BV1Ka411N7nx", "video_title": "杨定一：睡前一小时正念冥想", "video_duration": "9分钟",
         "article": """## 你的大脑需要"关机程序"

就像电脑不能直接拔电源一样，你的大脑也需要一个从"白天模式"切换到"睡眠模式"的过渡过程。

### 什么是好的睡前仪式？

睡前仪式是一系列固定的、放松的活动，每天在同一时间、以相同顺序进行。

### 推荐睡前仪式（30-45 分钟）

1. **关闭电子设备**（睡前 1 小时）
2. **轻度拉伸或瑜伽**（5-10 分钟）— 释放肌肉紧张
3. **写下明天的待办清单** — 把焦虑"卸载"到纸上
4. **感恩日记**（3 件事）
5. **阅读纸质书**（10-15 分钟）— 选轻松的内容
6. **冥想或深呼吸**（5 分钟）

### 避免

- 剧烈运动（睡前 2 小时内）
- 工作相关的讨论或思考
- 刺激性内容（新闻、社交媒体争论）
- 大量饮水（减少起夜）

**今日金句：仪式感不是矫情，而是用行为告诉大脑——安全了，可以休息了。**""",
         "task": "今晚创建你的睡前仪式：选择 3 个放松活动，按顺序执行。记录执行后的入睡速度和睡眠感受。",
         "xp": 15,
         "tips": ["睡前仪式至少持续 20 分钟才有效果", "保持每天仪式的顺序一致"]},

        {"day": 5, "week": 1, "week_title": "睡眠基础",
         "title": "饮食与睡眠", "subtitle": "你的晚餐决定了你的睡眠质量",
         "category": "饮食习惯",
         "video_url": "//player.bilibili.com/player.html?bvid=BV16k5X6sEkW&page=1&autoplay=0", "video_bvid": "BV16k5X6sEkW", "video_title": "健康生活方式：饮食运动与睡眠", "video_duration": "10分钟",
         "article": """## 睡眠友好饮食指南

### 你应该吃的（促眠食物）

- **香蕉**：富含镁和钾，帮助肌肉放松
- **温牛奶**：含有色氨酸，是褪黑素的前体
- **杏仁**：富含镁
- **全麦面包/燕麦**：复合碳水帮助色氨酸进入大脑
- **樱桃**：少数天然含褪黑素的水果
- **洋甘菊茶**：含有芹菜素，有镇静作用

### 你应该避免的（睡眠杀手）

- **咖啡因**（下午 2 点后）：半衰期 5-6 小时
- **酒精**：虽帮入睡，但破坏深睡和 REM
- **高糖食物**：导致血糖波动，引起夜间醒来
- **辛辣食物**：可能引起烧心和体温升高
- **大餐**（睡前 2 小时内）：消化活动干扰睡眠

### 晚餐黄金法则

- 睡前 2-3 小时完成晚餐
- 晚餐不宜过饱（七分饱）
- 如果睡前饿了，吃一小份助眠零食

**今日金句：好的睡眠从白天的选择开始，尤其是你放进嘴里的东西。**""",
         "task": "今天下午 2 点后不摄入任何咖啡因（咖啡、茶、可乐）。睡前 3 小时内不吃东西。记录你今晚入睡的速度和睡眠质量。",
         "xp": 15,
         "tips": ["用洋甘菊茶替代下午的咖啡", "晚餐吃含色氨酸的食物"]},

        {"day": 6, "week": 1, "week_title": "睡眠基础",
         "title": "运动与睡眠", "subtitle": "找到适合你的运动方式与时间",
         "category": "运动健康",
         "video_url": "//player.bilibili.com/player.html?bvid=BV13m42137NL&page=1&autoplay=0", "video_bvid": "BV13m42137NL", "video_title": "提升10倍睡眠质量的终极指南", "video_duration": "8分钟",
         "article": """## 运动是最被低估的"安眠药"

规律运动者比不运动者入睡快 12 分钟，总睡眠时长多 42 分钟。

### 什么时间运动最好？

**早晨运动（6-9 点）**
- 接触自然光，校准生物钟
- 提升白天的精力和专注力
- 对深睡有显著帮助

**下午运动（15-18 点）**
- 这是体温和肌肉力量的峰值时段
- 运动表现最佳
- 对入睡速度帮助最大

**晚上运动需注意**
- 睡前 1-2 小时内避免高强度运动
- 轻度瑜伽和拉伸是例外（有助放松）

### 运动处方

- **有氧运动**（快走、游泳）：每周 150 分钟
- **力量训练**：每周 2 次
- **简单开始**：每天 30 分钟户外散步

**今日金句：白天的每一滴汗水，都是今晚每一分钟深睡的预付款。**""",
         "task": "今天进行至少 30 分钟的户外活动（散步、跑步、骑行都可以），最好在上午或下午进行。记录运动后的睡眠感受。",
         "xp": 15,
         "tips": ["户外运动额外获得自然光照", "运动后不要马上睡觉"]},

        {"day": 7, "week": 1, "week_title": "睡眠基础",
         "title": "第一周回顾", "subtitle": "检查习惯养成，调整计划",
         "category": "复习总结",
         "video_url": "", "video_duration": "6分钟",
         "article": """## 恭喜完成第一周！回顾你的收获

### 本周我们学习了：

1. **睡眠周期** — 了解了 90 分钟的睡眠节律
2. **睡眠环境** — 优化了温度、光线和噪音
3. **规律作息** — 固化了起床时间
4. **睡前仪式** — 创建了关机程序
5. **饮食调整** — 调整了促眠饮食习惯
6. **运动习惯** — 开始了规律运动

### 自我检查

请诚实回答以下问题：

- ✅ 你是否每天都在同一时间起床？
- ✅ 你的卧室温度是否在 18-22°C？
- ✅ 你是否在睡前 1 小时减少了屏幕使用？
- ✅ 你是否建立了睡前仪式？
- ✅ 你是否减少了咖啡因和酒精的摄入？
- ✅ 你是否开始规律运动？

### 第二周预告

下周我们将进入**心理调节**阶段，学习 CBT-I 认知行为疗法的核心技术，包括刺激控制疗法和认知重构。

**今日金句：进步不一定是线性的，但每天微小的坚持，就是改变的开始。**""",
         "task": "回顾本周的 6 个习惯目标，给自己打分（1-10 分）。选择做得最好的一项继续坚持，选择最需要改进的一项作为下周重点。",
         "xp": 20,
         "tips": ["不要把未完成的目标视为失败，而是看作数据", "下周从最想做的一项开始"]},

        # ===== 第二周：心理调节 =====
        {"day": 8, "video_url": "//player.bilibili.com/player.html?bvid=BV1BDapzbEB6&page=1&autoplay=0", "video_bvid": "BV1BDapzbEB6", "video_title": "彻夜没睡是一种假象——三招改善睡眠", "week": 2, "week_title": "心理调节",
         "title": "认识失眠", "subtitle": "打破对失眠的恐惧循环",
         "category": "CBT-I疗法",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1BDapzbEB6&page=1&autoplay=0", "video_bvid": "BV1BDapzbEB6", "video_title": "彻夜没睡是一种假象——三招改善睡眠", "video_duration": "10分钟",
         "article": """## 失眠的恶性循环

失眠不仅仅是"睡不着"，而是一个由**生理因素、心理因素和行为因素**共同维持的恶性循环。

### 失眠的 3P 模型

**易感因素（Predisposing）**
- 天生睡眠浅、容易焦虑
- 家族中有失眠史

**诱发因素（Precipitating）**
- 压力事件（工作、关系、健康）
- 生活变化（搬家、时差、新工作）

**维持因素（Perpetuating）**
- 对睡眠的过度担忧
- 在床上玩手机/工作
- 白天补觉

### 关键认知

> 🔑 急性失眠和慢性失眠的区别不在于严重程度，而在于**维持因素**。大多数人的失眠之所以持续，是因为发展出了"睡眠焦虑"——越是担心睡不着，就越是睡不着。

### 打破循环的第一步

今晚试试这个实验：告诉自己"我不需要努力去睡，睡眠是身体的本能，不能强迫。我只是躺在床上休息。" — 这个态度转变本身就能减少入睡压力。

**今日金句：失眠不是你的一部分，而是一个可以被改变的模式。**""",
         "task": "今晚如果躺在床上睡不着，不要看时钟，不要计算「还剩几小时能睡」。只是安静地躺着，告诉自己「休息也很好」。记录你的焦虑水平变化。",
         "xp": 15,
         "tips": ["把钟表转过去看不见", "睡眠不能被强迫，只能被允许"]},

        {"day": 9, "video_url": "//player.bilibili.com/player.html?bvid=BV1YTndzmEWD&page=1&autoplay=0", "video_bvid": "BV1YTndzmEWD", "video_title": "矛盾睡眠法——失眠朋友终于睡踏实了", "week": 2, "week_title": "心理调节",
         "title": "刺激控制疗法", "subtitle": "CBT-I 最核心的技术：重建床与睡眠的连接",
         "category": "CBT-I疗法",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1YTndzmEWD&page=1&autoplay=0", "video_duration": "12分钟",
         "article": """## 你的大脑把床和什么联系在一起？

如果你的床同时是办公室、电影院、餐厅和焦虑室，那大脑就不会把"床"和"睡眠"联系起来。

### 刺激控制疗法六原则

1. **只有困倦时才上床**
2. **床只用于睡眠和性生活**（不玩手机、不工作、不吃东西）
3. **躺下 20 分钟无法入睡，起床去另一个房间**
4. **做轻松的事**（阅读、听轻音乐），直到感到困倦
5. **如果回到床上还是睡不着，重复步骤 3**
6. **每天同一时间起床**，无论前一晚睡了多久

### 初期可能更难

> ⚠️ 前 3-5 天可能更难入睡。这是正常的！你的大脑正在重新学习"床 = 睡眠"的条件反射。坚持 1-2 周，效果显著。

### 为什么有效？

这是巴甫洛夫的条件反射原理。当你的大脑反复经历"困 → 上床 → 睡着"，床就成了强大的睡眠触发器。

**今日金句：床是睡觉的地方，不是思考人生的地方。**""",
         "task": "今晚严格执行刺激控制疗法的前三条原则。如果躺下 20 分钟睡不着，果断起床去客厅。记录你执行了几次，以及最终入睡的时间。",
         "xp": 15,
         "tips": ["准备一个舒适的'起床去处'", "不要看时间！把钟表藏起来"]},

        {"day": 10, "week": 2, "week_title": "心理调节",
         "title": "睡眠限制疗法", "subtitle": "减少床上时间来增加实际睡眠",
         "category": "CBT-I疗法",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1ZHszetEYn&page=1&autoplay=0", "video_bvid": "BV1ZHszetEYn", "video_title": "睡眠压力与昼夜节律：科学午睡指南", "video_duration": "10分钟",
         "article": """## 听起来矛盾，但非常有效

睡眠限制疗法的核心思想：**通过压缩你在床上的时间，来提高睡眠效率。**

### 什么是睡眠效率？

睡眠效率 = 实际睡眠时间 ÷ 在床上时间 × 100%

- 正常：> 85%
- 失眠者通常：< 70%（在床上 10 小时，只睡了 6 小时）

### 操作方法

1. 记录一周的睡眠日志
2. 计算平均实际睡眠时间
3. **将床上时间限制为平均睡眠时间 + 30 分钟**（最少不低于 5.5 小时）
4. 例如：平均睡 6 小时 → 床上时间 6.5 小时
5. 当睡眠效率连续 3 天 > 90%，增加 15 分钟床上时间
6. 当睡眠效率 < 85%，减少 15 分钟

### 初期感受

> 前几天你会感觉睡得少了，你可能更困。但这是正常的！轻度睡眠剥夺会增加"睡眠驱动力"，让你更容易入睡、睡得更深。

**今日金句：不是床上时间长就是睡得好，睡得高效才是真正的休息。**""",
         "task": "计算你过去 3 天的平均睡眠效率和实际睡眠时间。设定一个目标床上时间（实际睡眠时间 + 30 分钟）。今晚严格在这个时间窗口内睡觉。",
         "xp": 15,
         "tips": ["固定起床时间是睡眠限制的关键", "白天不要小睡超过 20 分钟"]},

        {"day": 11, "week": 2, "week_title": "心理调节",
         "title": "认知重构", "subtitle": "改变对睡眠的错误信念",
         "category": "CBT-I疗法",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1d9Ls6TEtH&page=1&autoplay=0", "video_bvid": "BV1d9Ls6TEtH", "video_title": "斯坦福专家：重启你的睡眠系统", "video_duration": "11分钟",
         "article": """## 你对睡眠有哪些错误信念？

认知重构是 CBT-I 的第三步，识别并改变那些让你更焦虑的睡眠相关错误信念。

### 常见错误信念及替代想法

**错误信念 1**：我必须睡满 8 小时，否则第二天会很糟糕。

- 替代想法：睡眠需求因人而异（6-9 小时都正常）。即使睡少了，大多数日常活动我仍能完成。

**错误信念 2**：如果今晚睡不好，明天一定会搞砸。

- 替代想法：一晚糟糕的睡眠不会毁掉一整天。我曾有很多次睡眠不足但仍然完成了工作。

**错误信念 3**：躺在床上休息不够，只有睡着才算数。

- 替代想法：安静的休息本身就是恢复性的。身体在放松状态下也有修复功能。

**错误信念 4**：失眠会毁了我的健康。

- 替代想法：偶尔失眠是正常的。慢性失眠可以改善，不会造成永久伤害。

### 练习方法

每次出现"灾难性睡眠想法"时，写下来，然后理性地写出替代想法。

**今日金句：你对睡眠的想法，往往比睡眠本身更让你疲惫。**""",
         "task": "今天留意你对睡眠的自动负面想法。每当出现时，写下它，然后用一个更理性的替代想法来回应。至少练习 3 次。",
         "xp": 15,
         "tips": ["用笔记本记录'想法-替代想法'对照表", "对替代想法保持温和，不需要完全相信"]},

        {"day": 12, "video_url": "//player.bilibili.com/player.html?bvid=BV1yRmEB5EHj&page=1&autoplay=0", "video_bvid": "BV1yRmEB5EHj", "video_title": "雨声助眠×渐进式肌肉放松法", "week": 2, "week_title": "心理调节",
         "title": "渐进式肌肉放松", "subtitle": "释放身体的紧张，大脑自然会放松",
         "category": "放松技巧",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1yRmEB5EHj&page=1&autoplay=0", "video_duration": "15分钟",
         "article": """## 身体放松了，大脑才能放松

渐进式肌肉放松法（PMR）由美国医生 Edmund Jacobson 于 1920 年代研发，是循证有效的放松技术。

### 基本原理

通过**有意识地先紧张、再放松**每个肌肉群，你能学会识别"紧张"和"放松"之间的差异。很多人长期处于无意识的肌肉紧张状态而不自知。

### 15 分钟完整流程

准备：平躺，深呼吸 3 次。

1. **手和前臂**：握紧双拳 5 秒 → 突然放松 15 秒
2. **上臂和二头肌**：弯曲手臂，收紧肌肉 5 秒 → 放松 15 秒
3. **面部**：皱紧眉头、紧闭眼睛、咬紧牙关 5 秒 → 放松 15 秒
4. **颈部和肩膀**：耸肩到耳朵 5 秒 → 放松 15 秒
5. **胸部和背部**：深吸气收紧胸部 5 秒 → 呼气放松 15 秒
6. **腹部**：收紧腹部 5 秒 → 放松 15 秒
7. **臀部和大腿**：收紧臀部和腿 5 秒 → 放松 15 秒
8. **小腿和脚**：脚趾向下弯曲 5 秒 → 放松 15 秒

### 注意事项

- 紧张时不要到疼痛的程度（7-8 分力即可）
- 放松时仔细体会"松弛感"
- 每天练习，效果逐渐增强

**今日金句：身体是一扇门，放松它，睡眠自然会走进来。**""",
         "task": "今晚睡前在床上的时候，做一次完整的渐进式肌肉放松练习（从头到脚，每个部位 5 秒紧张 + 15 秒放松）。记录你的紧张程度变化。",
         "xp": 15,
         "tips": ["如果中间睡着了，说明效果很好！", "可以配合舒缓的音乐"]},

        {"day": 13, "video_url": "//player.bilibili.com/player.html?bvid=BV1imdLYHEpy&page=1&autoplay=0", "video_bvid": "BV1imdLYHEpy", "video_title": "10分钟睡前冥想：放下控制，安心入睡", "week": 2, "week_title": "心理调节",
         "title": "正念入门", "subtitle": "观察而不评判——让思绪如云朵飘过",
         "category": "正念冥想",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1imdLYHEpy&page=1&autoplay=0", "video_duration": "12分钟",
         "article": """## 正念不是"什么都不想"

很多人误以为冥想就是"清空大脑"，结果越努力越焦虑。正念的核心是**观察而不评判**。

### 三个关键态度

1. **不评判**：对任何出现的想法，不论好坏，只是注意到它
2. **不执着**：想法和情绪会来，也会走。你不需要抓住或推开它们
3. **回到呼吸**：当发现自己走神了（这很正常），温柔地把注意力带回呼吸

### 5 分钟呼吸正念

1. 找个舒适的坐姿或躺姿
2. 闭上眼睛，正常呼吸
3. 把注意力放在鼻孔气息进出的感觉上
4. 当你发现走神了（一定会），只是注意到"哦，我刚才在想事情"，然后温柔地回到呼吸
5. 不需要数呼吸，不需要控制呼吸深度

### 正念与睡眠

正念帮助睡眠的机制：
- 减少"思维反刍"（反复想同一件事）
- 降低生理唤起水平（心跳、血压）
- 打破"睡不着 → 焦虑 → 更睡不着"的循环

**今日金句：你不需要停止思维，只需要改变你和思维的关系。**""",
         "task": "睡前做 5 分钟呼吸正念练习。不要期望「做对」，只是观察。如果走神 100 次，就温柔地回来 100 次。记录你的体验。",
         "xp": 15,
         "tips": ["走神不是失败，是练习的一部分", "可以从 3 分钟开始，逐步延长"]},

        {"day": 14, "week": 2, "week_title": "心理调节",
         "title": "第二周回顾", "subtitle": "CBT-I 核心技巧整合与巩固",
         "category": "复习总结",
         "video_url": "", "video_duration": "8分钟",
         "article": """## 第二周完成！你已经掌握了 CBT-I 的核心工具

### 本周学习的四项核心技术

1. **认识失眠** — 理解 3P 模型，打破恐惧循环
2. **刺激控制疗法** — 床 = 睡眠，20 分钟法则
3. **睡眠限制疗法** — 提高睡眠效率的精准工具
4. **认知重构** — 改变灾难化睡眠想法
5. **渐进式放松** — 身体放松带动大脑放松
6. **正念入门** — 观察而不评判的练习

### CBT-I 整合使用建议

| 如果你的问题是 | 优先使用 |
|-----------|---------|
| 躺下很久睡不着 | 刺激控制疗法 |
| 早醒无法再入睡 | 刺激控制 + 认知重构 |
| 睡眠很浅 | 睡眠限制 + 放松训练 |
| 对睡眠过度焦虑 | 认知重构 + 正念 |
| 半夜频繁醒来 | 刺激控制 + 正念 |

### 第三周预告

下周我们将进入**深度优化**阶段：呼吸法、身体扫描、压力管理、昼夜节律优化。

**今日金句：掌握了这些工具，你就拥有了改善睡眠的主动权。**""",
         "task": "从本周的 6 项技术中，选择 2 项对你最有效的，制定下周继续练习的计划。记录为什么这两项对你有用。",
         "xp": 20,
         "tips": ["不需要用所有技术，选择最适合你的", "长期坚持比短期密集更有效"]},

        # ===== 第三周：深度优化 =====
        {"day": 15, "video_url": "//player.bilibili.com/player.html?bvid=av586333123&page=1&autoplay=0", "video_bvid": "av586333123", "video_title": "深度放松：腹式呼吸快速缓解紧张焦虑", "week": 3, "week_title": "深度优化",
         "title": "4-7-8 呼吸法", "subtitle": "哈佛医生的60秒入眠呼吸术",
         "category": "呼吸技巧",
         "video_url": "//player.bilibili.com/player.html?bvid=av586333123&page=1&autoplay=0", "video_duration": "8分钟",
         "article": """## 4-7-8 呼吸法：最强大的放松工具

由哈佛大学 Dr. Andrew Weil 推广的 4-7-8 呼吸法，源自瑜伽调息法（Pranayama），能在 60 秒内激活副交感神经系统。

### 原理

- **4 秒吸气**：通过鼻子，充分吸入氧气
- **7 秒屏息**：让氧气在肺部充分交换，轻微升高 CO2 有助于血管扩张
- **8 秒呼气**：通过嘴巴，缓慢、完全地呼出，激活迷走神经

> 缓慢的呼气直接刺激迷走神经（副交感神经的主要通路），向全身发出"安全"信号。

### 操作步骤

1. 舒适地坐着或躺着
2. 舌尖抵住上颚前部（门牙后方）
3. 完全呼出肺里的空气
4. 闭嘴，鼻子吸气，默数 **4** 秒
5. 屏住呼吸，默数 **7** 秒
6. 嘴巴呼气（发出"呼—"的声音），默数 **8** 秒
7. 这是一轮，重复 **4 轮**

### 何时使用

- 入睡困难时
- 半夜醒来后
- 白天感到焦虑时
- 需要快速平静下来时

**今日金句：你不需要控制你的睡眠，只需要控制你的呼吸。**""",
         "task": "今晚睡前做 4 轮 4-7-8 呼吸法（约 2 分钟）。如果在床上睡不着，再做 4 轮。记录你做完后的身体感受和入睡情况。",
         "xp": 15,
         "tips": ["初学者可能头晕，减为 3-3-6 开始", "呼气一定要慢，越长越好"]},

        {"day": 16, "video_url": "//player.bilibili.com/player.html?bvid=BV1rurkYwEMc&page=1&autoplay=0", "video_bvid": "BV1rurkYwEMc", "video_title": "睡前身体扫描正念冥想练习", "week": 3, "week_title": "深度优化",
         "title": "身体扫描冥想", "subtitle": "从头到脚的系统性深度放松",
         "category": "正念冥想",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1rurkYwEMc&page=1&autoplay=0", "video_duration": "15分钟",
         "article": """## 身体扫描：最温柔的睡眠引导

身体扫描（Body Scan）是正念减压（MBSR）课程中最受欢迎的技术之一，特别适合在睡前进行。

### 基本方法

按顺序将注意力依次放在身体的每个部位，感受那里的感觉——温度、压力、脉动、紧张或放松。不需要改变任何东西，只是**觉察**。

### 15 分钟身体扫描指南

**准备**：平躺，双手放在身体两侧，闭上眼睛。

1. **左脚趾** → 感受脚趾之间的接触
2. **左脚掌** → 脚底的感觉
3. **左脚踝** → 觉察踝关节
4. **左小腿** → 从脚踝到膝盖
5. **左膝盖** → 腿弯的感觉
6. **左大腿** → 从膝盖到髋部
7. **右脚趾** → 重复右侧
8. **右脚掌** → ...
9. （继续右侧到右大腿）
10. **臀部** → 身体与床接触的压力
11. **下背部** → 是否感到紧张？
12. **腹部** → 随着呼吸的起伏
13. **胸部** → 心跳的感觉
14. **上背部** → 肩胛骨的位置
15. **手指和手掌** → 左右分别
16. **手腕和前臂** → 是否在握紧？
17. **上臂** → 肩膀的沉重感
18. **脖子和喉咙** → 是否有紧绷？
19. **面部和下巴** → 有意识地放松
20. **头顶** → 从头顶到全身的整合感受

**今日金句：身体的每个部位都在说话，只是我们很少去听。**""",
         "task": "今晚做一个完整的身体扫描冥想。不需要严格按照顺序，可以上下反复。关键是在每个部位停留 10-20 秒，只是觉察感觉。",
         "xp": 15,
         "tips": ["如果扫描时睡着了，说明身体需要休息", "把注意力当作手电筒的光束"]},

        {"day": 17, "video_url": "//player.bilibili.com/player.html?bvid=BV1m3411J7aC&page=1&autoplay=0", "video_bvid": "BV1m3411J7aC", "video_title": "打破焦虑——八拍呼吸法", "week": 3, "week_title": "深度优化",
         "title": "睡眠与压力管理", "subtitle": "白天如何管理压力来保护夜晚的睡眠",
         "category": "压力管理",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1m3411J7aC&page=1&autoplay=0", "video_duration": "11分钟",
         "article": """## 压力是睡眠的头号敌人

你的身体并不知道"工作截止日期"和"被老虎追赶"的区别。当压力激活了 HPA 轴（下丘脑-垂体-肾上腺），皮质醇升高，直接抑制睡眠。

### 关键在于白天，不是夜晚

很多人犯的错误：白天压榨自己，晚上期待"自动切换"到放松模式。

### 白天的压力管理工具箱

**早晨（设定基调）**
- 起床后不要立刻看手机
- 10 分钟清晨散步（顺便获得光照）
- 写下今天最重要的 3 件事

**白天（主动调节）**
- 每隔 90 分钟休息 5-10 分钟
- 午餐后散步 15 分钟
- 感到压力时，做 3 轮 4-7-8 呼吸

**傍晚（过渡期）**
- 在回家路上做"角色切换"仪式
- 写下今天完成了什么（而不是没完成什么）
- 把未完成的任务写进明天的清单

### "担忧时间"技术

每天固定 15 分钟（建议下午 4-5 点）专门用来"担忧"：把所有的烦恼写下来，思考解决方案。除此之外的时间，当担忧出现时，告诉自己"留到担忧时间处理"。

**今日金句：最好的睡眠准备不是晚上的仪式，而是白天的压力管理。**""",
         "task": "今天设置一个「担忧时间」（15 分钟），把所有焦虑写下来。除此之外，当担忧出现时，告诉自己「留到担忧时间」。睡前回顾这个技术是否有效。",
         "xp": 15,
         "tips": ["担忧时间不要设在睡前 2 小时内", "写下担忧本身就能减轻焦虑"]},

        {"day": 18, "week": 3, "week_title": "深度优化",
         "title": "昼夜节律深度优化", "subtitle": "光照、体温与褪黑素的精妙配合",
         "category": "睡眠科学",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1KY4y1Q7NA&page=1&autoplay=0", "video_bvid": "BV1KY4y1Q7NA", "video_title": "人的昼夜节律是怎么回事？如何改变生物钟", "video_duration": "10分钟",
         "article": """## 你的生物钟比你想象的更精确

昼夜节律是内置于你身体每个细胞中的 24 小时时钟，由"主时钟"SCN（视交叉上核）统一协调。

### 光照：最强的时间信号

- **早晨（6-9 点）**：接触明亮自然光 20-30 分钟 → 抑制褪黑素，设置"白天开始"信号
- **中午**：继续获得自然光，维持节律
- **晚上（20 点后）**：逐步降低光照强度，换成暖光 → 允许褪黑素升高

### 体温节律

你的核心体温在一天中有约 1°C 的波动：
- 白天：较高（37°C 左右）
- 入睡前：开始下降（−0.5°C）
- 凌晨 4-5 点：最低点
- 醒来前：开始回升

> 睡前热水浴通过"先升后降"的体温变化促进睡眠。

### 褪黑素：黑暗的信号

- 通常在睡前 2 小时开始分泌
- 峰值在凌晨 2-4 点
- 蓝光（480nm）是最强的褪黑素抑制剂

### 优化行动清单

- 早晨 30 分钟户外光（不用直视太阳）
- 白天工作区保持明亮
- 傍晚开始使用暖光灯
- 睡前 1-2 小时屏幕开启夜间模式
- 保持就寝和起床时间恒定（误差 <30 分钟）

**今日金句：你不是在对抗失眠，你是在教会你的身体什么时间该做什么。**""",
         "task": "今天做三件事：(1) 早晨起床后 30 分钟内接触户外自然光 20 分钟；(2) 傍晚后使用暖光灯；(3) 睡前 1 小时开启所有屏幕的夜间模式。",
         "xp": 15,
         "tips": ["早上不需要盯着太阳，只需在户外", "防蓝光眼镜也是有效工具"]},

        {"day": 19, "week": 3, "week_title": "深度优化",
         "title": "数字化排毒", "subtitle": "减少蓝光与信息过载对睡眠的侵蚀",
         "category": "生活习惯",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1G9ndzjEtR&page=1&autoplay=0", "video_bvid": "BV1G9ndzjEtR", "video_title": "手机蓝光：睡前屏幕时间的隐形影响", "video_duration": "9分钟",
         "article": """## 你的手机正在偷走你的睡眠

2019 年的一项研究显示，睡前使用手机的人比不用的人入睡时间晚 21 分钟，深睡时间少 25%。

### 问题不只是蓝光

- **蓝光抑制褪黑素**：延迟睡眠时间 1-2 小时
- **信息刺激**：社交媒体算法设计为让你停不下来
- **FOMO 焦虑**：害怕错过信息，反复检查
- **被动消耗**：刷手机时你不会意识到时间流逝

### 数字化排毒计划

**日落模式（睡前 1 小时）**
- 所有屏幕开启夜间模式
- 手机调成勿扰模式
- 不查看社交媒体、邮件、新闻
- 用纸质书、播客、轻音乐替代

**卧室无手机**
- 把充电器放在卧室外面
- 使用传统闹钟
- 把床恢复为只用于睡眠和性生活

**早晨延迟看手机**
- 起床后 30 分钟内不碰手机
- 先做：光照、喝水、轻微活动
- 再检查消息

### 本周实验

挑战自己：连续 3 天，睡前 1 小时不碰手机。观察你的入睡速度和睡眠质量的变化。

**今日金句：你的注意力是宝贵的资源，不要把它免费送给算法。**""",
         "task": "今晚睡前 1 小时把所有电子设备放在卧室外面。阅读纸质书或做放松练习。记录你今晚的入睡时间和睡眠质量。",
         "xp": 15,
         "tips": ["准备好替代活动：书、杂志、拼图、日记本", "告诉家人这是你的睡眠实验"]},

        {"day": 20, "week": 3, "week_title": "深度优化",
         "title": "长期维持策略", "subtitle": "防止复发：如何把这个计划变成永久习惯",
         "category": "习惯养成",
         "video_url": "//player.bilibili.com/player.html?bvid=BV1uuSABmEhY&page=1&autoplay=0", "video_bvid": "BV1uuSABmEhY", "video_title": "如何增加深度睡眠时间 | 醒来神清气爽", "video_duration": "9分钟",
         "article": """## 如何不让 21 天的努力付诸东流

睡眠改善不是一次性的修复，而是一种持续的生活方式。以下是防止退步的长期策略。

### 1. 建立不可协商的基线

即使生活忙碌，以下三项必须守住：

- **固定起床时间**（误差 < 1 小时）
- **睡前 1 小时远离屏幕**
- **每天至少 15 分钟户外活动**

### 2. 识别你的"触发事件"

提前知道什么情况可能导致你的睡眠退步：

- 出差/旅行 → 准备眼罩耳塞
- 工作压力期 → 增加放松练习频率
- 社交活动 → 事先设定离开时间
- 生病 → 允许更多睡眠，但保持起床时间

### 3. 坚持睡眠日志

保持每月至少记录一周的睡眠日志。数据不会骗你，趋势变化能提前预警。

### 4. 定期"重置"

每 3 个月做一次"睡眠重置周"——重新严格按 21 天计划执行一周。就像软件需要定期重启一样。

### 5. 庆祝进步，不苛求完美

> 睡眠改善的关键指标不是"每晚都完美"，而是"80% 的晚上足够好"。

**今日金句：生活不会完美，睡眠也不会。但你拥有了工具，可以随时回到轨道上。**""",
         "task": "写下你的「睡眠保护计划」：你的 3 项不可协商的基线、5 个可能导致退步的触发事件，以及每个事件的应对策略。",
         "xp": 15,
         "tips": ["把计划放在看得见的地方", "和信任的人分享你的计划"]},

        {"day": 21, "week": 3, "week_title": "深度优化",
         "title": "毕业总结", "subtitle": "21天后的你：建立终身受益的睡眠习惯",
         "category": "复习总结",
         "video_url": "", "video_duration": "10分钟",
         "article": """## 🎉 恭喜你完成了 21 天睡眠改善计划！

### 你学到了什么

**第一周：睡眠基础**
- 理解睡眠周期（90 分钟节律）
- 优化睡眠环境（温度、光线、噪音）
- 建立规律作息（固定起床时间）
- 创造睡前仪式
- 调整饮食和运动习惯

**第二周：心理调节**
- 认识失眠的 3P 模型
- 掌握刺激控制疗法
- 应用睡眠限制疗法
- 实践认知重构
- 学会渐进式肌肉放松和正念

**第三周：深度优化**
- 掌握 4-7-8 呼吸法
- 体验身体扫描冥想
- 学会压力管理
- 优化昼夜节律
- 制定长期维持策略

### 接下来做什么

1. **坚持基线**：固定起床时间 + 睡前仪式 + 户外活动
2. **每月回顾**：用一周时间记录睡眠日志
3. **定期重置**：有需要时重新执行 21 天计划
4. **帮助他人**：把学到的知识分享给需要的朋友

### 最后的寄语

睡眠是身体与生俱来的能力，不是需要努力争取的奖品。你现在拥有的不是"完美的睡眠"，而是**在任何情况下都能让自己休息下来的能力**。

有时候你会睡得不好，这是完全正常的。关键是，你知道为什么，也知道该怎么办。你已经不是那个被失眠困扰而无能为力的人了。

**今日金句：21 天不是终点，而是一个新起点。所有的改变，从今天开始。晚安，好梦。🌙**""",
         "task": "写下你完成 21 天课程的感受和最大的收获。写下你接下来 3 个月的睡眠目标。把这个课程推荐给一个可能需要的朋友。",
         "xp": 50,
         "tips": ["你已经完成了 21 天的旅程，今晚好好奖励自己", "睡眠是一辈子的朋友，善待它"]},
    ]


# Program metadata
_21_DAY_META = {
    "id": "21day_sleep_program",
    "title": "21天睡眠改善计划",
    "subtitle": "每天10分钟，三周养成终身受益的睡眠习惯",
    "description": "基于CBT-I认知行为疗法的系统化睡眠改善课程。21天，每天包含视频讲解、深度文章和每日任务，从睡眠基础到心理调节再到深度优化，循序渐进地帮助你改善睡眠。",
    "instructor": "睡眠教练AI",
    "total_days": 21,
    "weeks": 3,
    "week_titles": ["第一周：睡眠基础", "第二周：心理调节", "第三周：深度优化"],
    "category": "睡眠改善",
    "difficulty": "初学者友好",
}


def get_21day_course() -> list:
    return _21_day_course()


def get_21day_meta() -> dict:
    return _21_DAY_META


def get_day_content(day: int):
    """Get content for a specific day (1-indexed)."""
    if day < 1 or day > 21:
        return None
    courses = _21_day_course()
    return courses[day - 1] if day <= len(courses) else None


def export_records_csv(records: list) -> str:
    """Export sleep records as CSV string."""
    import io, csv
    output = io.StringIO()
    output.write('﻿')  # UTF-8 BOM，Excel 认这个
    writer = csv.writer(output)
    writer.writerow(["日期", "入睡时间", "起床时间", "时长(h)", "质量(1-5)", "评分", "标签", "备注", "AI反馈"])
    for r in records:
        tags = ""
        try:
            tags = ", ".join(json.loads(r.tags or "[]"))
        except Exception:
            tags = r.tags or ""
        writer.writerow([
            str(r.diary_date or ""), str(r.bedtime or ""), str(r.wake_time or ""),
            r.duration_hours or 0, r.quality or "", r.score or 0,
            tags, r.notes or "", r.ai_feedback or "",
        ])
    return output.getvalue()
