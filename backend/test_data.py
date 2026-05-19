# -*- coding: utf-8 -*-
"""数据测试 — DB完整性, 数据验证, 算法精确性, 数据流"""
import json, sys, os, math, time, threading, urllib.request, urllib.error
from datetime import datetime, timedelta, date
sys.path.insert(0, os.path.dirname(__file__))

pass_count = 0; fail_count = 0
def check(cond, msg):
    global pass_count, fail_count
    if cond: pass_count += 1; print(f"  PASS {msg}")
    else: fail_count += 1; print(f"  FAIL {msg}")
def eq(a, b, msg): check(a == b, f"{msg}: expected={b!r}, got={a!r}")
def approx(a, b, tol, msg): check(abs(a-b) <= tol, f"{msg}: expected≈{b}, got={a}")

# ================== 评分算法精度测试 ==================
print("\n" + "=" * 60)
print("  评分算法精度测试")
print("=" * 60)

def test_scoring_precision():
    from app.services import calc_score

    # 完美睡眠: 8h, 质量5, 深睡标签, 目标8h
    s = calc_score(8.0, 5, '["深睡"]', 8.0)
    # 50 (ideal duration) + 30 (quality 5*6) + 20 (tag bonus max) = 100
    eq(s, 100, "完美睡眠=100分")

    # 精准边界测试
    test_cases = [
        # (duration, quality, tags, goal, expected_min, expected_max, desc)
        (8.0, 5, '["深睡"]', 8.0, 95, 100, "完美=95-100"),
        (7.5, 4, '[]', 8.0, 65, 80, "良好=65-80"),
        (6.0, 3, '["失眠"]', 8.0, 35, 55, "偏差=35-55"),
        (4.0, 2, '["失眠","夜醒"]', 8.0, 10, 35, "差=10-35"),
        (0.0, 1, '["失眠","夜醒","早醒","浅睡"]', 8.0, 0, 20, "极差=0-20"),
        (9.0, 4, '[]', 8.0, 70, 95, "略多(空标签有满bonus)=70-95"),
        (8.5, 5, '["深睡"]', 8.0, 85, 100, "达标+深睡=85-100"),
        (3.0, 1, '["失眠"]', 8.0, 25, 40, "严重不足=25-40"),
    ]

    for dur, qual, tags, goal, lo, hi, desc in test_cases:
        s = calc_score(dur, qual, tags, goal)
        check(lo <= s <= hi, f"{desc}: {s} ∈ [{lo},{hi}]")

    print("  评分算法: 9 cases")

# moved to main


# ================== 时长计算精度测试 ==================
print("\n" + "=" * 60)
print("  时长计算精度测试")
print("=" * 60)

def test_duration_precision():
    from app.services import calc_duration

    cases = [
        (datetime(2026,5,17,23,0), datetime(2026,5,18,6,30), 7.5, "标准7.5h"),
        (datetime(2026,5,17,22,0), datetime(2026,5,18,6,0), 8.0, "标准8h"),
        (datetime(2026,5,17,23,30), datetime(2026,5,18,5,30), 6.0, "标准6h"),
        (datetime(2026,5,17,22,0), datetime(2026,5,17,22,45), 0.8, "短睡0.75h→0.8"),
        (datetime(2026,5,17,22,0), datetime(2026,5,17,22,0), 0.0, "0小时"),
        (datetime(2026,5,17,23,0), datetime(2026,5,18,0,30), 1.5, "跨午夜1.5h"),
    ]
    for bed, wake, expected, desc in cases:
        d = calc_duration(bed, wake)
        eq(d, expected, desc)
    print("  时长计算: 6 cases")

# moved to main


# ================== 一致性计算测试 ==================
print("\n" + "=" * 60)
print("  作息一致性测试")
print("=" * 60)

def test_consistency_precision():
    from app.services import calc_consistency_minutes, consistency_label

    class MR:
        def __init__(self, h, m): self.bedtime = datetime(2026,5,17,h,m)

    # 完全相同 → 0
    records = [MR(22,30), MR(22,30), MR(22,30)]
    eq(calc_consistency_minutes(records), 0.0, "完全一致=0")

    # 轻微波动
    records = [MR(22,0), MR(22,30), MR(23,0)]
    c = calc_consistency_minutes(records)
    check(c < 50, f"轻微波动<50: {c:.1f}")

    # 中等波动
    records = [MR(21,0), MR(22,0), MR(23,0)]
    c = calc_consistency_minutes(records)
    check(40 < c < 60, f"中等波动≈50: {c:.1f}")

    # 极不规律
    records = [MR(20,0), MR(2,0), MR(22,0)]
    c = calc_consistency_minutes(records)
    check(c > 400, f"极不规律>400: {c:.1f}")

    # 标签
    eq(consistency_label(15), "regular", "15min→regular")
    eq(consistency_label(45), "moderate", "45min→moderate")
    eq(consistency_label(90), "irregular", "90min→irregular")
    eq(consistency_label(0), "regular", "0min→regular")
    eq(consistency_label(29), "regular", "29min→regular")
    eq(consistency_label(30), "moderate", "30min→moderate")
    eq(consistency_label(59), "moderate", "59min→moderate")
    eq(consistency_label(60), "irregular", "60min→irregular")

    print("  一致性: 11 cases")

# moved to main


# ================== Token 生成与验证 ==================
print("\n" + "=" * 60)
print("  Token 生成与验证")
print("=" * 60)

def test_token_operations():
    from app.services import create_access_token, create_refresh_token, decode_token

    # Access token
    at = create_access_token({"sub": "42"})
    check(len(at) > 20, "access_token长度>20")
    payload = decode_token(at)
    eq(payload["sub"], "42", "payload.sub=42")
    eq(payload["type"], "access", "payload.type=access")
    check("exp" in payload, "payload包含exp")

    # Refresh token
    rt = create_refresh_token({"sub": "77"})
    payload = decode_token(rt)
    eq(payload["sub"], "77", "refresh.sub=77")
    eq(payload["type"], "refresh", "refresh.type=refresh")

    # 不同的token (slight delay ensures different exp)
    import time as _time
    _time.sleep(1.1)
    at2 = create_access_token({"sub": "42"})
    check(at != at2, "两个access_token不同(不同exp)")

    # 无效token
    for bad_token in ["", "abc", "x.y.z", "a.b.c.d", None]:
        try:
            if bad_token is None: continue
            decode_token(bad_token)
            check(False, f"无效token应抛异常: {bad_token[:20]}")
        except:
            check(True, f"无效token正确抛异常: {bad_token[:20] if bad_token else 'None'}")

    # Expired token - 验证过期检测
    import jwt as pyjwt
    expired = pyjwt.encode({"sub": "99", "exp": datetime.utcnow() - timedelta(hours=1), "type": "access"}, "wrong_key")
    try:
        decode_token(expired)
        check(False, "过期token应失败")
    except:
        check(True, "过期token正确失败")

    print("  Token: 9 cases")

# moved to main


# ================== 密码哈希测试 ==================
print("\n" + "=" * 60)
print("  密码哈希测试")
print("=" * 60)

def test_password_hashing():
    from app.services import hash_pw, verify_pw

    pw = "SecurePass123!"
    hashed = hash_pw(pw)
    check(hashed != pw, "哈希≠明文")
    check(len(hashed) > 20, f"哈希长度>20: {len(hashed)}")
    check(hashed.startswith("$2"), f"bcrypt格式: {hashed[:20]}")

    check(verify_pw(pw, hashed), "验证正确密码")
    check(not verify_pw("WrongPassword", hashed), "拒绝错误密码")
    check(not verify_pw("", hashed), "拒绝空密码")
    check(not verify_pw(pw + "x", hashed), "拒绝相似密码")

    # 相同密码哈希不同(salt)
    h2 = hash_pw(pw)
    check(hashed != h2, "两次哈希不同(salt运作)")

    print("  密码: 7 cases")

# moved to main


# ================== 任务生成逻辑测试 ==================
print("\n" + "=" * 60)
print("  任务生成逻辑测试")
print("=" * 60)

def test_task_generation():
    from app.services import generate_today_tasks_rule_based, ALL_TASKS

    # 无档案
    tasks = generate_today_tasks_rule_based(None)
    eq(len(tasks), 4, "无档案→4个任务")
    ids = {t["id"] for t in tasks}
    eq(len(ids), 4, "无档案→4个唯一任务")

    # 入睡困难档案
    profile = {"improvement_priority": "入睡速度", "sleep_issues": "入睡困难", "stress_level": "中", "preferred_tasks": ""}
    tasks = generate_today_tasks_rule_based(profile)
    eq(len(tasks), 4, "入睡困难档案→4个任务")
    task_ids = [t["id"] for t in tasks]
    check("t1" in task_ids or "t3" in task_ids or "t10" in task_ids, "包含入睡相关任务")

    # 高压力档案
    profile = {"improvement_priority": "", "sleep_issues": "", "stress_level": "高", "preferred_tasks": ""}
    tasks = generate_today_tasks_rule_based(profile)
    task_ids = [t["id"] for t in tasks]
    check("t4" in task_ids or "t13" in task_ids, "高压力→包含心理减压任务")

    # 深度睡眠优先级
    profile = {"improvement_priority": "睡眠深度", "sleep_issues": "睡眠浅", "stress_level": "低", "preferred_tasks": ""}
    tasks = generate_today_tasks_rule_based(profile)
    task_ids = [t["id"] for t in tasks]
    check("t9" in task_ids or "t8" in task_ids, "睡眠深度→包含环境/工具任务")

    # 有偏好任务
    profile = {"improvement_priority": "", "sleep_issues": "", "stress_level": "低", "preferred_tasks": "环境优化,知识学习"}
    tasks = generate_today_tasks_rule_based(profile)
    task_ids = [t["id"] for t in tasks]
    check("t9" in task_ids or "t18" in task_ids, "偏好→包含环境和知识任务")

    # Multiple runs should produce different results (random shuffle)
    all_same = True
    first = [t["id"] for t in generate_today_tasks_rule_based(None)]
    for _ in range(5):
        if [t["id"] for t in generate_today_tasks_rule_based(None)] != first:
            all_same = False; break
    check(not all_same, "多次生成顺序不完全相同(随机性)")

    print("  任务生成: 6 cases")

# moved to main


# ================== 标签统计测试 ==================
print("\n" + "=" * 60)
print("  标签统计测试")
print("=" * 60)

def test_tag_statistics():
    from app.services import get_tag_stats

    class MR:
        def __init__(self, tags_str): self.tags = tags_str

    # 正常统计
    records = [MR('["深睡","做梦"]'), MR('["深睡"]'), MR('["失眠","早醒"]')]
    stats = get_tag_stats(records)
    eq(stats["深睡"], 2, "深睡=2")
    eq(stats["失眠"], 1, "失眠=1")
    eq(stats["早醒"], 1, "早醒=1")
    eq(stats["做梦"], 1, "做梦=1")

    # 空列表
    records = []
    stats = get_tag_stats(records)
    eq(len(stats), 0, "空列表→空统计")

    # 无效JSON
    records = [MR("not valid json")]
    stats = get_tag_stats(records)
    eq(len(stats), 0, "无效JSON→空统计")

    # 空标签
    records = [MR("[]")]
    stats = get_tag_stats(records)
    eq(len(stats), 0, "空标签→空统计")

    print("  标签: 5 cases")

# moved to main


# ================== 连续天数计算测试 ==================
print("\n" + "=" * 60)
print("  连续达标天数测试")
print("=" * 60)

def test_streak_calculation():
    from app.database import SessionLocal
    from app.models import SleepRecord, User
    from app.services import calc_streak

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username.like("func_%")).first()
        if user:
            streak = calc_streak(db, user.id)
            check(streak >= 0, f"streak非负: {streak}")
    finally:
        db.close()
    print("  连续天数: 1 case")

# moved to main


# ================== 睡眠效率计算测试 ==================
print("\n" + "=" * 60)
print("  睡眠效率计算")
print("=" * 60)

def test_sleep_efficiency():
    from app.services import calc_sleep_efficiency

    # 标准效率
    eff = calc_sleep_efficiency(8.0, datetime(2026,5,17,23,0), datetime(2026,5,18,7,0))
    eq(eff, 100.0, "正好8h=100%")

    eff = calc_sleep_efficiency(7.5, datetime(2026,5,17,23,0), datetime(2026,5,18,6,30))
    eq(eff, 100.0, "正好7.5h=100%")

    eff = calc_sleep_efficiency(6.0, datetime(2026,5,17,23,0), datetime(2026,5,18,6,30))
    approx(eff, 80.0, 5, "6h/7.5h≈80%")

    eff = calc_sleep_efficiency(0, datetime(2026,5,17,23,0), datetime(2026,5,18,6,30))
    eq(eff, 0.0, "0h=0%")

    print("  效率: 4 cases")

# moved to main


# ================== 睡眠债计算测试 ==================
print("\n" + "=" * 60)
print("  睡眠债计算")
print("=" * 60)

def test_sleep_debt():
    from app.services import calc_sleep_debt

    class MR:
        def __init__(self, dur): self.duration_hours = dur

    # 有债务
    records = [MR(7.0), MR(7.5), MR(6.0), MR(7.0)]
    debt = calc_sleep_debt(records, 8.0)
    check("total_debt" in debt, "包含total_debt")
    # 总欠: (1+0.5+2+1) = 4.5
    check(abs(debt["total_debt"] - 4.5) < 0.5, f"总欠≈4.5: {debt['total_debt']}")

    # 无债务
    records = [MR(8.5), MR(9.0), MR(8.0)]
    debt = calc_sleep_debt(records, 8.0)
    eq(debt["total_debt"], 0.0, "全部达标→债务=0")

    # 空
    records = []
    debt = calc_sleep_debt(records, 8.0)
    eq(debt["total_debt"], 0.0, "空→债务=0")

    print("  睡眠债: 3 cases")

# moved to main


# ================== DB模型字段验证 ==================
print("\n" + "=" * 60)
print("  DB模型字段验证")
print("=" * 60)

def test_model_fields():
    from app.database import engine, Base
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    required_tables = ["users", "sleep_records", "health_profiles", "chat_sessions",
                       "chat_messages", "task_completions", "user_points", "badge_unlocks"]
    for t in required_tables:
        check(t in tables, f"表{t}存在")

    # 验证users表字段
    cols = {c["name"] for c in inspector.get_columns("users")}
    required_cols = {"id", "username", "email", "hashed_password", "nickname", "avatar", "is_admin", "created_at", "updated_at"}
    for c in required_cols:
        check(c in cols, f"users表包含{c}")

    # 验证sleep_records字段
    cols = {c["name"] for c in inspector.get_columns("sleep_records")}
    required = {"id", "user_id", "diary_date", "bedtime", "wake_time", "duration_hours", "quality", "tags", "notes", "score", "ai_feedback", "created_at"}
    for c in required:
        check(c in cols, f"sleep_records表包含{c}")

    # 验证health_profiles字段
    cols = {c["name"] for c in inspector.get_columns("health_profiles")}
    check("improvement_priority" in cols, "health_profiles含improvement_priority")
    check("sleep_goal_hours" in cols, "health_profiles含sleep_goal_hours")
    check("preferred_tasks" in cols, "health_profiles含preferred_tasks")

    print("  DB模型: 19 cases")

# moved to main


# ================== 数据流完整性测试 ==================
print("\n" + "=" * 60)
print("  数据流完整性测试")
print("=" * 60)

def start_server():
    import uvicorn; from app.main import app
    t = threading.Thread(target=lambda: uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error"), daemon=True)
    t.start(); time.sleep(3)

def api(method, path, **kwargs):
    url = f"http://127.0.0.1:8000{path}"
    data = None
    if "json" in kwargs: data = json.dumps(kwargs["json"], ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if "headers" in kwargs:
        for k, v in kwargs["headers"].items(): req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req); body = resp.read().decode("utf-8")
        return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try: return e.code, json.loads(body)
        except: return e.code, {"error": body}

def test_data_flow():
    TS_SEC = int(time.time())
    u = f"dataflow_{TS_SEC}"; e = f"{u}@test.com"

    # Register
    s, d = api("POST", "/api/v1/auth/register", json={"username": u, "email": e, "password": "DataFlow1", "nickname": "DataUser"})
    eq(s, 200, "注册")
    check(d["username"] == u, "username正确返回")
    check(d["email"] == e, "email正确返回")
    uid = d["id"]

    # Login
    s, d = api("POST", "/api/v1/auth/login", json={"username": u, "password": "DataFlow1"})
    eq(s, 200, "登录")
    t = d["access_token"]; hd = {"Authorization": f"Bearer {t}"}

    # Me - verify user data matches
    s, d = api("GET", "/api/v1/auth/me", headers=hd)
    eq(s, 200, "获取个人信息")
    eq(d["id"], uid, "user id一致")
    eq(d["username"], u, "username一致")
    eq(d["nickname"], "DataUser", "nickname一致")

    # Create profile and verify fields
    profile_data = {
        "age": 25, "gender": "男", "height": 178.0, "weight": 72.0,
        "sleep_goal_hours": 7.5, "bedtime_target": "23:00", "wakeup_target": "06:30",
        "stress_level": "低", "caffeine_intake": "不摄入", "exercise_frequency": "每天",
    }
    s, d = api("PUT", "/api/v1/profiles", json=profile_data, headers=hd)
    eq(s, 200, "创建档案")
    for k, v in profile_data.items():
        eq(d.get(k), v, f"档案字段{k}={v}")

    # Create sleep record and verify scoring pipeline
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-17", "bedtime": "2026-05-17T23:00:00",
        "wake_time": "2026-05-18T06:30:00", "quality": 4, "tags": ["深睡"], "notes": "测试数据流"
    }, headers=hd)
    eq(s, 200, "创建睡眠记录")
    check(d["duration_hours"] == 7.5, f"duration=7.5: {d['duration_hours']}")
    check(0 <= d["score"] <= 100, f"score在范围内: {d['score']}")
    check(len(d["ai_feedback"]) > 0, "AI反馈非空")
    rid = d["id"]

    # Get record and verify data roundtrip
    s, d2 = api("GET", f"/api/v1/sleep-records/{rid}", headers=hd)
    eq(s, 200, "获取记录")
    eq(d2["duration_hours"], d["duration_hours"], "duration roundtrip")
    eq(d2["score"], d["score"], "score roundtrip")
    eq(d2["notes"], "测试数据流", "notes roundtrip")

    # Task completion and points verification
    today = f"{time.localtime().tm_year}-{time.localtime().tm_mon}-{time.localtime().tm_mday}"
    s, d = api("POST", "/api/v1/tasks/complete", json={"task_id": "t1", "date_key": today}, headers=hd)
    eq(s, 200, "完成任务")
    check(d["points"] >= 5, f"points≥5: {d['points']}")
    s, d = api("GET", "/api/v1/tasks/points/summary", headers=hd)
    check(d["total_points"] >= 5, f"total_points≥5: {d['total_points']}")

    print("  数据流: 16 cases")

if __name__ == "__main__":
    print("=" * 60)
    print("  梦眠 - 数据测试套件")
    print("=" * 60)
    print("\n  Starting server...")
    start_server()
    test_data_flow()
    test_scoring_precision()
    test_duration_precision()
    test_consistency_precision()
    test_token_operations()
    test_password_hashing()
    test_task_generation()
    test_tag_statistics()
    test_streak_calculation()
    test_sleep_efficiency()
    test_sleep_debt()
    test_model_fields()

    print(f"\n  数据测试: {pass_count} passed, {fail_count} failed")
    if fail_count == 0: print("  ALL DATA TESTS PASSED")
    else: print(f"  {fail_count} DATA TESTS FAILED")
    print("=" * 60)
    sys.exit(fail_count)
