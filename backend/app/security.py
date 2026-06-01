"""Security & Performance — cache, rate limit, JWT blacklist, logging, sanitization."""
import time
import hashlib
import re
import threading
from datetime import datetime
from fastapi import Request, HTTPException


# ===== In-Memory TTL Cache =====
class TTLCache:
    """Simple TTL cache — swap with Redis in production."""
    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry and entry["expires"] > time.time():
                return entry["value"]
            if entry:
                del self._store[key]
            return None

    def set(self, key: str, value, ttl: int = 300):
        with self._lock:
            self._store[key] = {"value": value, "expires": time.time() + ttl}

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def incr(self, key: str, ttl: int = 60) -> int:
        with self._lock:
            entry = self._store.get(key)
            if entry and entry["expires"] > time.time():
                entry["value"] += 1
                return entry["value"]
            self._store[key] = {"value": 1, "expires": time.time() + ttl}
            return 1

    def clear_expired(self):
        with self._lock:
            now = time.time()
            expired = [k for k, v in self._store.items() if v["expires"] <= now]
            for k in expired:
                del self._store[k]

    def size(self):
        return len(self._store)


cache = TTLCache()
jwt_blacklist = set()  # Production: use Redis SET


# ===== Rate Limiter =====
def rate_limit(key: str, max_requests: int = 30, window: int = 60) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    count = cache.incr(f"rate:{key}", ttl=window)
    return count <= max_requests


def get_rate_limit_key(request: Request) -> str:
    """Generate rate limit key from IP + path."""
    ip = request.client.host if request.client else "unknown"
    path = request.url.path
    return f"{ip}:{path}"


# ===== JWT Blacklist =====
def blacklist_token(token: str, ttl: int = 604800):  # 7 days
    """Add JWT to blacklist (on logout)."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
    jwt_blacklist.add(token_hash)
    cache.set(f"bl:{token_hash}", True, ttl)


def is_token_blacklisted(token: str) -> bool:
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
    return token_hash in jwt_blacklist or cache.get(f"bl:{token_hash}") is not None


# ===== Input Sanitization =====
XSS_PATTERNS = [
    (re.compile(r'<script[^>]*>.*?</script>', re.I | re.S), '[script]'),
    (re.compile(r'javascript\s*:', re.I), ''),
    (re.compile(r'on\w+\s*=\s*"[^"]*"', re.I), ''),
    (re.compile(r'on\w+\s*=\s*\'[^\']*\'', re.I), ''),
    (re.compile(r'<[^>]*>'), ''),
]


def sanitize_input(text: str) -> str:
    """Strip XSS vectors from input text."""
    if not text:
        return ""
    for pattern, replacement in XSS_PATTERNS:
        text = pattern.sub(replacement, text)
    return text.strip()


# ===== Password Strength =====
def validate_password_strength(password: str) -> dict:
    """Check password strength. Returns {valid, errors, strength}."""
    errors = []
    if len(password) < 6:
        errors.append("密码至少6位")
    if len(password) > 128:
        errors.append("密码不能超过128位")
    if not re.search(r'[a-zA-Z]', password):
        errors.append("需包含字母")
    if not re.search(r'[0-9]', password):
        errors.append("需包含数字")

    strength = 0
    if len(password) >= 8: strength += 1
    if len(password) >= 12: strength += 1
    if re.search(r'[a-z]', password) and re.search(r'[A-Z]', password): strength += 1
    if re.search(r'[^a-zA-Z0-9]', password): strength += 1

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "strength": min(strength, 4),  # 0-4
        "strength_label": ["很弱", "弱", "中", "强", "很强"][strength] if strength <= 4 else "很强",
    }


# ===== Periodic Cache Cleanup =====
def start_cache_cleanup(interval: int = 300):
    """Periodically clean expired cache entries."""
    def _clean():
        while True:
            time.sleep(interval)
            cache.clear_expired()
    t = threading.Thread(target=_clean, daemon=True)
    t.start()


# Start cleanup on import (only in dev — prod should use Redis)
from app.config import settings as _sec_settings
if not _sec_settings.PRODUCTION:
    start_cache_cleanup()


# ===== WeChat Push Notification =====
WECHAT_APPID = ""
WECHAT_SECRET = ""
WECHAT_TEMPLATE_ID = ""


def set_wechat_config(appid: str, secret: str, template_id: str = ""):
    global WECHAT_APPID, WECHAT_SECRET, WECHAT_TEMPLATE_ID
    WECHAT_APPID = appid
    WECHAT_SECRET = secret
    WECHAT_TEMPLATE_ID = template_id


def _get_wechat_access_token() -> str:
    """Get WeChat access token from cache or refresh."""
    cached = cache.get("wx_access_token")
    if cached:
        return cached
    if not WECHAT_APPID or not WECHAT_SECRET:
        return ""
    try:
        import urllib.request, json
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={WECHAT_APPID}&secret={WECHAT_SECRET}"
        resp = urllib.request.urlopen(url, timeout=10)
        data = json.loads(resp.read())
        token = data.get("access_token", "")
        if token:
            cache.set("wx_access_token", token, ttl=7000)  # 2 hours minus buffer
        return token
    except Exception:
        return ""


def send_wechat_template_message(openid: str, template_id: str, data: dict, page: str = "") -> bool:
    """Send a WeChat template message to a user."""
    token = _get_wechat_access_token()
    if not token or not openid:
        return False
    try:
        import urllib.request, json
        payload = json.dumps({
            "touser": openid,
            "template_id": template_id,
            "page": page,
            "data": data,
        }).encode()
        url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={token}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        return result.get("errcode") == 0
    except Exception:
        return False


# ===== Push Notification Scheduler =====
def start_push_scheduler(interval: int = 60):
    """Periodically check and send push reminders via WeChat (only if configured)."""
    def _check():
        while True:
            time.sleep(interval)
            if not WECHAT_APPID or not WECHAT_SECRET:
                continue
            try:
                from app.database import SessionLocal
                from app.models import NotificationSetting, TaskCompletion, User
                from datetime import datetime, timedelta
                db = SessionLocal()
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                ch, cm = now.hour, now.minute
                settings_list = db.query(NotificationSetting).filter(NotificationSetting.push_enabled == 1).all()
                for ns in settings_list:
                    if not ns.reminder_time: continue
                    try:
                        rh, rm = int(ns.reminder_time[:2]), int(ns.reminder_time[3:5])
                        if abs((ch * 60 + cm) - (rh * 60 + rm)) <= 5:
                            already = db.query(TaskCompletion).filter(
                                TaskCompletion.user_id == ns.user_id,
                                TaskCompletion.task_id == "push_reminder",
                                TaskCompletion.date_key == today).first()
                            if not already:
                                db.add(TaskCompletion(user_id=ns.user_id, task_id="push_reminder", date_key=today, points=0))
                                # Actually send WeChat template message
                                if WECHAT_APPID and WECHAT_SECRET:
                                    user = db.query(User).filter(User.id == ns.user_id).first()
                                    if user and user.openid:
                                        send_wechat_template_message(
                                            user.openid,
                                            WECHAT_TEMPLATE_ID or "",
                                            {
                                                "thing1": {"value": "梦眠阁提醒"},
                                                "thing2": {"value": "该准备睡觉了，好的睡眠是健康的基础"},
                                                "time3": {"value": ns.reminder_time},
                                            },
                                            page="/pages/index/index",
                                        )
                    except: pass
                db.commit()
                db.close()
            except: pass
    t = threading.Thread(target=_check, daemon=True)
    t.start()


# 推送调度器 — 微信密钥配置后自动启用
if _sec_settings.WECHAT_SECRET:
    start_push_scheduler()

