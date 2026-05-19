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
    except Exception:
        return ""


def _ai_chat(system_prompt: str, user_prompt: str, temperature: float = 0.8, max_tokens: int = 300) -> str:
    return _ai_call([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ], temperature, max_tokens)


def get_sleep_feedback(diary_text: str) -> str:
    result = _ai_chat(
        "你是专业的睡眠陪伴助手，遵循CBT-I原则。用温柔语气给出50字以内的共情反馈，不给出诊断。",
        f"用户睡眠记录：{diary_text}\n请给一句共情反馈：",
        temperature=0.7, max_tokens=80,
    )
    return result or "我收到了你的睡眠记录。别担心，我们一起慢慢来，先保持记录习惯就是进步。"


def chat_with_sleep_coach(user_message: str, history: list = None, user_context: str = "") -> str:
    system = """你是一位温柔、专业、遵循认知行为疗法(CBT-I)的睡眠教练。
倾听用户的睡眠困扰，提供科学的睡眠卫生建议，给予共情和鼓励。
绝不提供医疗诊断。回答简洁温暖，每次回复150字以内。严重症状建议就医。"""
    if user_context:
        system += f"\n\n用户档案：{user_context}"

    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-20:])
    messages.append({"role": "user", "content": user_message})

    try:
        result = _ai_call(messages, temperature=0.8, max_tokens=300)
        return result or "抱歉，我暂时无法回复。请稍后再试，或者记录一下此刻的感受，这本身就有帮助。"
    except Exception:
        return "抱歉，我暂时无法回复。请稍后再试，或者记录一下此刻的感受，这本身就有帮助。"


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

请生成4个任务，每个任务包含：id(t1-t18参考编号)、title(10字以内简短标题)、desc(15字以内描述)、category(分类)、points(固定5分)。

任务应针对用户的具体问题。如果用户入睡困难，推荐放松和作息类任务；如果压力高，推荐心理减压类；如果是新用户，推荐基础睡眠卫生任务。

参考分类：作息、习惯、放松、心理、饮食、运动、工具、环境

严格按照以下JSON格式返回，不要其他内容：
{{"tasks":[{{"id":"t1","title":"任务标题","desc":"简短描述","category":"分类","points":5}}]}}"""

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
def calc_score(duration: float, quality: int, tags_str: str, goal_hours: float = 8.0) -> int:
    score = 0
    ideal_min, ideal_max = goal_hours, goal_hours + 1.5

    if ideal_min <= duration <= ideal_max:
        score += 50
    elif ideal_min - 1 <= duration < ideal_min:
        score += 35
    elif ideal_max < duration <= ideal_max + 1:
        score += 30
    elif 5 <= duration < ideal_min - 1:
        score += 20
    elif duration < 5:
        score += 10
    else:
        score += 15

    score += (quality or 3) * 6

    tag_bonus = 20
    try:
        tags = json.loads(tags_str or "[]")
    except (json.JSONDecodeError, TypeError):
        tags = []
    for t in ["失眠", "夜醒", "早醒", "浅睡"]:
        if t in tags:
            tag_bonus -= 5
    if "深睡" in tags:
        tag_bonus += 5
    score += min(tag_bonus, 20)

    return min(max(round(score), 0), 100)


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
    {"id": "t1", "title": "22:30前关灯准备入睡", "desc": "建立规律作息，让身体适应固定入睡时间", "points": 5, "category": "作息"},
    {"id": "t2", "title": "睡前30分钟放下手机", "desc": "减少蓝光刺激，帮助褪黑素自然分泌", "points": 5, "category": "习惯"},
    {"id": "t3", "title": "做5分钟冥想或呼吸练习", "desc": "4-7-8呼吸法：吸气4秒、屏息7秒、呼气8秒", "points": 5, "category": "放松"},
    {"id": "t4", "title": "记录3件今天感恩的事", "desc": "减少焦虑反刍，以积极心态入睡", "points": 5, "category": "心理"},
    {"id": "t5", "title": "睡前2小时内不进食", "desc": "避免消化活动干扰睡眠质量", "points": 5, "category": "饮食"},
    {"id": "t6", "title": "下午3点后不喝咖啡/茶", "desc": "咖啡因半衰期约5-6小时，下午摄入影响夜间睡眠", "points": 5, "category": "饮食"},
    {"id": "t7", "title": "户外活动30分钟", "desc": "自然光照有助于调节昼夜节律", "points": 5, "category": "运动"},
    {"id": "t8", "title": "使用白噪音辅助入睡", "desc": "选择适合你的音景，建立入睡声音关联", "points": 5, "category": "工具"},
    {"id": "t9", "title": "保持卧室温度18-22°C", "desc": "凉爽环境更有利于深度睡眠", "points": 5, "category": "环境"},
    {"id": "t10", "title": "睡前热水浴或泡脚", "desc": "体温先升后降的过程有助于入睡", "points": 5, "category": "放松"},
    {"id": "t11", "title": "午睡不超过30分钟", "desc": "短午睡提神，长午睡影响夜间睡眠", "points": 5, "category": "作息"},
    {"id": "t12", "title": "避免睡前饮酒", "desc": "酒精虽助入睡但破坏深度睡眠和REM", "points": 5, "category": "饮食"},
    {"id": "t13", "title": "写睡前日记或担忧清单", "desc": "把焦虑卸载到纸上，减少大脑反刍", "points": 5, "category": "心理"},
    {"id": "t14", "title": "睡前轻度拉伸5分钟", "desc": "释放肌肉紧张，缓解白天久坐压力", "points": 5, "category": "运动"},
    {"id": "t15", "title": "醒来后不赖床超过10分钟", "desc": "快速起床建立清醒节律，减少睡眠惯性", "points": 5, "category": "作息"},
    {"id": "t16", "title": "白天至少20分钟自然光照", "desc": "阳光是调节生物钟最重要的信号", "points": 5, "category": "环境"},
    {"id": "t17", "title": "晚上只开暖色灯", "desc": "暖光(2700K)比冷光对睡眠干扰更小", "points": 5, "category": "环境"},
    {"id": "t18", "title": "与AI助手对话讨论睡眠", "desc": "获取个性化建议和睡眠知识", "points": 5, "category": "工具"},
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


def export_records_csv(records: list) -> str:
    """Export sleep records as CSV string."""
    import io, csv
    output = io.StringIO()
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
