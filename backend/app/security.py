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


def sanitize_dict(data: dict) -> dict:
    """Recursively sanitize all string values in a dict."""
    if not data:
        return data
    result = {}
    for k, v in data.items():
        if isinstance(v, str):
            result[k] = sanitize_input(v)
        elif isinstance(v, dict):
            result[k] = sanitize_dict(v)
        elif isinstance(v, list):
            result[k] = [sanitize_input(x) if isinstance(x, str) else x for x in v]
        else:
            result[k] = v
    return result


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


# ===== Request Logger =====
def log_request(request: Request, user_id: int = None, action: str = None):
    """Log API request for audit trail."""
    try:
        from app.database import SessionLocal
        from app.models import AuditLog
        db = SessionLocal()
        db.add(AuditLog(
            user_id=user_id,
            action=action or request.url.path,
            ip_address=request.client.host if request.client else "",
            detail=str(request.method),
        ))
        db.commit()
        db.close()
    except Exception:
        pass


# ===== Periodic Cache Cleanup =====
def start_cache_cleanup(interval: int = 300):
    """Periodically clean expired cache entries."""
    def _clean():
        while True:
            time.sleep(interval)
            cache.clear_expired()
    t = threading.Thread(target=_clean, daemon=True)
    t.start()


# Start cleanup on import
start_cache_cleanup()
