"""Comprehensive test suite for 梦眠阁 sleep management platform.
Run: python test_all.py
Tests: unit tests (scoring, tokens, tasks) + integration tests (all 25+ API endpoints).
"""
import json
import math
import sys
import os
import time
import threading
import subprocess

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

# ===================== UNIT TESTS =====================
def test_calc_score():
    """Test sleep scoring algorithm."""
    from app.services import calc_score

    # Perfect: 8h duration, quality 5, good tags, goal 8h
    s = calc_score(8.0, 5, '["深睡"]', 8.0)
    assert 80 <= s <= 100, f"Perfect sleep: expected 80-100, got {s}"

    # Very good: slightly short, quality 4
    s = calc_score(7.0, 4, '[]', 8.0)
    assert 60 <= s <= 80, f"Good sleep: expected 60-80, got {s}"

    # Bad: short, low quality, bad tags, goal high
    s = calc_score(4.0, 2, '["失眠","夜醒"]', 8.0)
    assert s <= 50, f"Bad sleep: expected <=50, got {s}"

    # Edge: near-minimum score (duration=0 gets 10 base + 6 quality - lots of deductions, minimum is capped)
    s = calc_score(0, 1, '["失眠","夜醒","早醒","浅睡"]', 8.0)
    assert 0 <= s <= 20, f"Near-minimum: expected 0-20, got {s}"

    # Edge: quality 1 with short duration (10 base + 6 qual + 15 tag = 31)
    s = calc_score(3.0, 1, '["失眠"]', 8.0)
    assert 30 <= s <= 35, f"Poor sleep: expected 30-35, got {s}"

    print("  PASS test_calc_score (5 cases)")


def test_calc_duration():
    """Test duration calculation."""
    from app.services import calc_duration
    from datetime import datetime

    # Normal: 23:00 -> 06:30 = 7.5h
    d = calc_duration(datetime(2026, 5, 17, 23, 0), datetime(2026, 5, 18, 6, 30))
    assert d == 7.5, f"Expected 7.5, got {d}"

    # Short: 22:00 -> 22:45 = 0.75h
    d = calc_duration(datetime(2026, 5, 17, 22, 0), datetime(2026, 5, 17, 22, 45))
    assert d == 0.8, f"Expected 0.8, got {d}"

    # Same time
    d = calc_duration(datetime(2026, 5, 17, 22, 0), datetime(2026, 5, 17, 22, 0))
    assert d == 0.0, f"Expected 0.0, got {d}"

    print("  PASS test_calc_duration (3 cases)")


def test_token_create_decode():
    """Test JWT token creation and decoding."""
    from app.services import create_access_token, create_refresh_token, decode_token

    # Access token
    at = create_access_token({"sub": "123"})
    assert at, "Access token should not be empty"
    payload = decode_token(at)
    assert payload["sub"] == "123", f"Expected sub=123, got {payload}"
    assert payload["type"] == "access", f"Expected type=access, got {payload}"

    # Refresh token
    rt = create_refresh_token({"sub": "456"})
    payload = decode_token(rt)
    assert payload["sub"] == "456"
    assert payload["type"] == "refresh"

    # Tampered token
    try:
        decode_token("invalid.token.here")
        assert False, "Should have raised"
    except Exception:
        pass

    print("  PASS test_token_create_decode (4 cases)")


def test_password_hash():
    """Test bcrypt password hashing."""
    from app.services import hash_pw, verify_pw

    pw = "test_password_123"
    hashed = hash_pw(pw)
    assert hashed != pw
    assert verify_pw(pw, hashed)
    assert not verify_pw("wrong_password", hashed)

    print("  PASS test_password_hash")


def test_generate_tasks():
    """Test task generation with and without profile."""
    from app.services import generate_today_tasks_rule_based, ALL_TASKS

    # No profile: should return 4 random tasks
    tasks = generate_today_tasks_rule_based(None)
    assert len(tasks) == 4, f"Expected 4 tasks, got {len(tasks)}"
    ids = {t["id"] for t in tasks}
    assert len(ids) == 4, "Tasks should be unique"

    # Profile with priorities
    profile = {
        "improvement_priority": "入睡速度,睡眠深度",
        "sleep_issues": "入睡困难",
        "stress_level": "高",
        "preferred_tasks": "冥想放松,环境优化",
    }
    tasks = generate_today_tasks_rule_based(profile)
    assert len(tasks) == 4
    # High stress + sleep priority should generate 4 unique tasks
    task_ids = {t["id"] for t in tasks}
    assert len(task_ids) == 4, "Should return 4 unique tasks"

    print("  PASS test_generate_tasks (2 cases)")


def test_consistency():
    """Test sleep consistency calculation."""
    from app.services import calc_consistency_minutes, consistency_label
    from datetime import datetime

    # Create mock record objects
    class MockRecord:
        def __init__(self, h, m):
            self.bedtime = datetime(2026, 5, 17, h, m)

    # Very consistent: all at 22:30
    records = [MockRecord(22, 30), MockRecord(22, 30), MockRecord(22, 30)]
    c = calc_consistency_minutes(records)
    assert c == 0.0, f"Expected 0.0, got {c}"

    # Some spread
    records = [MockRecord(22, 0), MockRecord(23, 0), MockRecord(21, 0)]
    c = calc_consistency_minutes(records)
    assert 45 < c < 55, f"Expected ~50, got {c}"

    # Irregular
    records = [MockRecord(20, 0), MockRecord(2, 0), MockRecord(22, 0)]
    c = calc_consistency_minutes(records)
    assert c > 300, f"Expected >300, got {c}"

    # Labels
    assert consistency_label(15) == "regular"
    assert consistency_label(45) == "moderate"
    assert consistency_label(90) == "irregular"

    print("  PASS test_consistency (4 cases)")


def test_tag_stats():
    """Test tag frequency aggregation."""
    from app.services import get_tag_stats

    class MockRecord:
        def __init__(self, tags_str):
            self.tags = tags_str

    records = [
        MockRecord('["深睡","做梦"]'),
        MockRecord('["深睡"]'),
        MockRecord('["失眠","早醒"]'),
    ]
    stats = get_tag_stats(records)
    assert stats["深睡"] == 2
    assert stats["失眠"] == 1
    assert stats["早醒"] == 1
    assert stats["做梦"] == 1

    print("  PASS test_tag_stats")


# ===================== INTEGRATION TESTS =====================
SERVER_PROC = None
BASE = "http://127.0.0.1:8000/api/v1"


def start_server():
    """Start uvicorn in a thread."""
    import uvicorn
    from app.main import app

    def run():
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(3)


def api(method, path, **kwargs):
    """Helper: make API call."""
    import urllib.request
    import urllib.error

    url = f"http://127.0.0.1:8000{path}"
    data = None
    if "json" in kwargs:
        data = json.dumps(kwargs["json"]).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if "headers" in kwargs:
        for k, v in kwargs["headers"].items():
            req.add_header(k, v)

    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}


TEST_USER = f"tester_{int(time.time())}"
TEST_EMAIL = f"{TEST_USER}@test.com"


def test_api_register():
    """Test register endpoint."""
    s, d = api("POST", "/api/v1/auth/register", json={
        "username": TEST_USER, "email": TEST_EMAIL,
        "password": "pass123", "nickname": "Tester",
    })
    assert s == 200, f"Register: expected 200, got {s}: {d}"
    assert d["username"] == TEST_USER
    print("  PASS test_api_register")


def test_api_register_duplicate():
    """Test duplicate registration rejected."""
    s, d = api("POST", "/api/v1/auth/register", json={
        "username": TEST_USER, "email": f"{TEST_USER}b@test.com",
        "password": "pass123", "nickname": "Tester",
    })
    assert s == 400, f"Duplicate: expected 400, got {s}: {d}"
    print("  PASS test_api_register_duplicate")


def test_api_login():
    """Test login and tokens."""
    global ACCESS_TOKEN, REFRESH_TOKEN
    s, d = api("POST", "/api/v1/auth/login", json={
        "username": TEST_USER, "password": "pass123",
    })
    assert s == 200, f"Login: expected 200, got {s}: {d}"
    assert "access_token" in d
    assert "refresh_token" in d
    assert d["token_type"] == "bearer"
    ACCESS_TOKEN = d["access_token"]
    REFRESH_TOKEN = d["refresh_token"]
    print("  PASS test_api_login")


ACCESS_TOKEN = ""
REFRESH_TOKEN = ""


def test_api_me():
    """Test get current user."""
    s, d = api("GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Me: expected 200, got {s}: {d}"
    assert d["username"] == TEST_USER
    print("  PASS test_api_me")


def test_api_refresh_token():
    """Test token refresh."""
    s, d = api("POST", "/api/v1/auth/refresh", json={"refresh_token": REFRESH_TOKEN})
    assert s == 200, f"Refresh: expected 200, got {s}: {d}"
    assert "access_token" in d
    global ACCESS_TOKEN
    ACCESS_TOKEN = d["access_token"]
    print("  PASS test_api_refresh_token")


def test_api_login_wrong_password():
    """Test login with wrong password."""
    s, d = api("POST", "/api/v1/auth/login", json={
        "username": TEST_USER, "password": "wrong",
    })
    assert s == 401, f"Wrong pw: expected 401, got {s}"
    print("  PASS test_api_login_wrong_password")


def test_api_create_sleep_record():
    """Test sleep record creation with scoring."""
    global SLEEP_ID
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-17",
        "bedtime": "2026-05-17T23:00:00",
        "wake_time": "2026-05-18T06:30:00",
        "quality": 4,
        "tags": ["深睡", "做梦"],
        "notes": "睡得很好",
    }, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Create sleep: expected 200, got {s}: {d}"
    assert d["duration_hours"] == 7.5
    assert 0 <= d["score"] <= 100
    assert d["ai_feedback"] != ""
    SLEEP_ID = d["id"]
    print(f"  PASS test_api_create_sleep_record (score={d['score']}, duration={d['duration_hours']}h)")


SLEEP_ID = None


def test_api_list_sleep_records():
    """Test listing sleep records."""
    s, d = api("GET", "/api/v1/sleep-records?days=7",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"List: expected 200, got {s}"
    assert d["total"] >= 1
    assert len(d["records"]) >= 1
    print(f"  PASS test_api_list_sleep_records ({d['total']} records)")


def test_api_get_last_sleep():
    """Test getting last sleep record."""
    s, d = api("GET", "/api/v1/sleep-records/last",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200
    assert d is not None
    assert d["score"] is not None
    print(f"  PASS test_api_get_last_sleep (score={d['score']})")


def test_api_get_sleep_by_id():
    """Test getting specific sleep record."""
    s, d = api("GET", f"/api/v1/sleep-records/{SLEEP_ID}",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Get by ID: expected 200, got {s}"
    assert d["id"] == SLEEP_ID
    print("  PASS test_api_get_sleep_by_id")


def test_api_delete_sleep():
    """Test deleting a sleep record."""
    # Create one to delete
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-16",
        "bedtime": "2026-05-16T22:00:00",
        "wake_time": "2026-05-17T05:00:00",
        "quality": 2,
        "tags": ["失眠"],
    }, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200
    del_id = d["id"]

    s, d = api("DELETE", f"/api/v1/sleep-records/{del_id}",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Delete: expected 200, got {s}"
    assert "已删除" in d["message"]
    print("  PASS test_api_delete_sleep")


def test_api_sleep_stats():
    """Test sleep statistics endpoint."""
    s, d = api("GET", "/api/v1/sleep-records/stats/summary?days=7",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Stats: expected 200, got {s}: {d}"
    assert "avg_duration" in d
    assert "avg_score" in d
    assert "consistency" in d
    assert "streak_days" in d
    assert "tag_counts" in d
    print(f"  PASS test_api_sleep_stats (avg={d['avg_duration']}h, score={d['avg_score']}, streak={d['streak_days']})")


def test_api_profile_upsert():
    """Test health profile upsert."""
    s, d = api("PUT", "/api/v1/profiles", json={
        "age": 30,
        "gender": "男",
        "height": 175.0,
        "weight": 70.0,
        "sleep_goal_hours": 8.0,
        "bedtime_target": "22:30",
        "wakeup_target": "06:30",
        "caffeine_intake": "仅在上午",
        "stress_level": "中",
        "sleep_issues": "入睡困难,浅睡",
        "improvement_priority": "入睡速度,睡眠深度",
    }, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Profile upsert: expected 200, got {s}: {d}"
    assert d["age"] == 30
    assert d["gender"] == "男"
    assert d["sleep_goal_hours"] == 8.0
    print("  PASS test_api_profile_upsert")


def test_api_profile_get():
    """Test getting health profile."""
    s, d = api("GET", "/api/v1/profiles",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Profile get: expected 200, got {s}: {d}"
    assert d["age"] == 30
    assert d["caffeine_intake"] == "仅在上午"
    print("  PASS test_api_profile_get")


def test_api_tasks_today():
    """Test getting today's tasks."""
    s, d = api("GET", "/api/v1/tasks/today",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Tasks today: expected 200, got {s}: {d}"
    assert "tasks" in d
    assert len(d["tasks"]) == 4
    # Should include sleep depth tasks since we set that as priority
    task_ids = [t["id"] for t in d["tasks"]]
    print(f"  PASS test_api_tasks_today (tasks: {task_ids})")


def test_api_tasks_complete():
    """Test completing a task."""
    from datetime import datetime
    now = datetime.now()
    dk = f"{now.year}-{now.month}-{now.day}"
    s, d = api("POST", "/api/v1/tasks/complete", json={
        "task_id": "t1", "date_key": dk,
    }, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Complete task: expected 200, got {s}: {d}"
    assert d["points"] == 5
    print("  PASS test_api_tasks_complete")


def test_api_tasks_uncomplete():
    """Test uncompleting a task."""
    from datetime import datetime
    now = datetime.now()
    dk = f"{now.year}-{now.month}-{now.day}"
    s, d = api("DELETE", "/api/v1/tasks/complete", json={
        "task_id": "t1", "date_key": dk,
    }, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Uncomplete: expected 200, got {s}: {d}"
    print("  PASS test_api_tasks_uncomplete")


def test_api_tasks_badges():
    """Test getting badges."""
    s, d = api("GET", "/api/v1/tasks/badges",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200
    assert len(d) == 8
    # No badges unlocked yet
    unlocked = sum(1 for b in d if b["unlocked"])
    print(f"  PASS test_api_tasks_badges (8 badges, {unlocked} unlocked)")


def test_api_tasks_points():
    """Test getting points."""
    s, d = api("GET", "/api/v1/tasks/points/summary",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200
    assert d["total_points"] >= 0
    print(f"  PASS test_api_tasks_points ({d['total_points']} pts)")


def test_api_chat_send():
    """Test sending a chat message."""
    global CHAT_SESSION_ID
    s, d = api("POST", "/api/v1/chat/send", json={
        "message": "我最近总是失眠，有什么建议吗？",
    }, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200, f"Chat send: expected 200, got {s}: {d}"
    assert d["role"] == "assistant"
    assert d["content"] != ""
    assert d["session_id"] is not None
    CHAT_SESSION_ID = d["session_id"]
    print(f"  PASS test_api_chat_send (reply: {d['content'][:50]}...)")


CHAT_SESSION_ID = None


def test_api_chat_sessions():
    """Test listing chat sessions."""
    s, d = api("GET", "/api/v1/chat/sessions",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200
    assert len(d) >= 1
    print(f"  PASS test_api_chat_sessions ({len(d)} sessions)")


def test_api_chat_session_detail():
    """Test getting a specific session."""
    s, d = api("GET", f"/api/v1/chat/sessions/{CHAT_SESSION_ID}",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200
    assert d["id"] == CHAT_SESSION_ID
    assert len(d["messages"]) >= 2  # user + assistant
    print(f"  PASS test_api_chat_session_detail ({len(d['messages'])} messages)")


def test_api_chat_continue():
    """Test continuing a chat in existing session."""
    s, d = api("POST", "/api/v1/chat/send", json={
        "session_id": CHAT_SESSION_ID,
        "message": "谢谢你的建议",
    }, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200
    assert d["role"] == "assistant"
    print(f"  PASS test_api_chat_continue (session_id={CHAT_SESSION_ID})")


def test_api_chat_delete():
    """Test deleting a chat session."""
    # Create a fresh session to delete
    s, d = api("POST", "/api/v1/chat/send", json={
        "message": "删除测试",
    }, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    del_sid = d["session_id"]

    s, d = api("DELETE", f"/api/v1/chat/sessions/{del_sid}",
               headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    assert s == 200
    print("  PASS test_api_chat_delete")


def test_api_health():
    """Test health check."""
    import urllib.request
    req = urllib.request.Request("http://127.0.0.1:8000/health")
    resp = urllib.request.urlopen(req)
    body = json.loads(resp.read().decode())
    assert body["status"] == "healthy"
    print("  PASS test_api_health")


def test_api_frontend():
    """Test frontend HTML is served."""
    import urllib.request
    req = urllib.request.Request("http://127.0.0.1:8000/")
    resp = urllib.request.urlopen(req)
    html = resp.read().decode()
    assert "梦眠阁" in html
    assert "vue@" in html
    assert "#app" in html
    assert resp.status == 200
    print(f"  PASS test_api_frontend ({len(html)} bytes)")


def test_api_unauthorized():
    """Test that protected endpoints require auth."""
    s, d = api("GET", "/api/v1/auth/me")
    assert s == 401, f"Unauthorized: expected 401, got {s}"
    print("  PASS test_api_unauthorized")


# ===================== MAIN =====================
def run_unit_tests():
    print("\n" + "="*60)
    print("  UNIT TESTS")
    print("="*60)
    tests = [
        test_calc_score, test_calc_duration, test_token_create_decode,
        test_password_hash, test_generate_tasks, test_consistency, test_tag_stats,
    ]
    passed = 0; failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n  Unit tests: {passed} passed, {failed} failed")
    return failed


def run_integration_tests():
    print("\n" + "="*60)
    print("  INTEGRATION TESTS")
    print("="*60)

    # Start server
    print("\n  Starting server...")
    start_server()

    tests = [
        test_api_register, test_api_register_duplicate, test_api_login,
        test_api_login_wrong_password, test_api_refresh_token, test_api_me,
        test_api_create_sleep_record, test_api_list_sleep_records,
        test_api_get_last_sleep, test_api_get_sleep_by_id, test_api_delete_sleep,
        test_api_sleep_stats,
        test_api_profile_upsert, test_api_profile_get,
        test_api_tasks_today, test_api_tasks_complete, test_api_tasks_uncomplete,
        test_api_tasks_badges, test_api_tasks_points,
        test_api_chat_send, test_api_chat_sessions, test_api_chat_session_detail,
        test_api_chat_continue, test_api_chat_delete,
        test_api_health, test_api_frontend, test_api_unauthorized,
    ]

    passed = 0; failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            import traceback
            print(f"  FAIL {t.__name__}: {e}")
            traceback.print_exc()

    print(f"\n  Integration tests: {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    print("="*60)
    print("  梦眠阁 - AI智能睡眠管理 测试套件")
    print("="*60)

    unit_fails = run_unit_tests()
    int_fails = run_integration_tests()

    total = unit_fails + int_fails

    print("\n" + "="*60)
    if total == 0:
        print("  ALL TESTS PASSED")
    else:
        print(f"  {total} TESTS FAILED")
    print("="*60)

    sys.exit(total)
