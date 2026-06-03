# -*- coding: utf-8 -*-
"""功能测试 — E2E 用户流程, CRUD 操作, 状态转换, 边界条件"""
import json, sys, os, time, threading, urllib.request, urllib.error, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))

def start_server():
    import uvicorn; from app.main import app
    t = threading.Thread(target=lambda: uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error"), daemon=True)
    t.start(); time.sleep(3)

def api(method, path, **kwargs):
    url = f"http://127.0.0.1:8000{path}"
    data = None
    if "json" in kwargs:
        data = json.dumps(kwargs["json"], ensure_ascii=False).encode("utf-8")
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

TS = int(time.time()); USER = f"func_{TS}"; EMAIL = f"{USER}@test.com"; PASS = "TestPass123"; TOKEN = ""

def auth(): return {"Authorization": f"Bearer {TOKEN}"}

def setup():
    global TOKEN
    s, d = api("POST", "/api/v1/auth/register", json={"username": USER, "email": EMAIL, "password": PASS, "nickname": "FuncTest"})
    assert s == 200, f"Setup: {d}"
    s, d = api("POST", "/api/v1/auth/login", json={"username": USER, "password": PASS})
    TOKEN = d["access_token"]

pass_count = 0; fail_count = 0
def check(cond, msg):
    global pass_count, fail_count
    if cond: pass_count += 1; print(f"  PASS {msg}")
    else: fail_count += 1; print(f"  FAIL {msg}")

def eq(a, b, msg): check(a == b, f"{msg}: expected={b}, got={a}")

# ================== E2E FLOW 1: 新用户完整流程 ==================
print("\n" + "=" * 60)
print("  E2E FLOW 1: 新用户注册→设置档案→记录睡眠→任务→统计")
print("=" * 60)

def e2e_user_journey():
    u = f"journey_{int(time.time())}"; e = f"{u}@test.com"
    # Step 1: Register
    s, d = api("POST", "/api/v1/auth/register", json={"username": u, "email": e, "password": "Journey1", "nickname": "旅行者"})
    eq(s, 200, "Step1-注册")
    uid = d["id"]

    # Step 2: Login
    s, d = api("POST", "/api/v1/auth/login", json={"username": u, "password": "Journey1"})
    eq(s, 200, "Step2-登录")
    t = d["access_token"]; rt = d["refresh_token"]; hd = {"Authorization": f"Bearer {t}"}

    # Step 3: Check profile status
    s, d = api("GET", "/api/v1/auth/has-profile", headers=hd)
    eq(s, 200, "Step3-检查档案状态")
    check(d["has_profile"] == False, "Step3-无档案")

    # Step 4: Create health profile
    s, d = api("PUT", "/api/v1/profiles", json={
        "age": 28, "gender": "女", "height": 165.0, "weight": 55.0,
        "sleep_goal_hours": 8.0, "bedtime_target": "22:30", "wakeup_target": "06:30",
        "stress_level": "中", "sleep_issues": "入睡困难,浅睡",
        "improvement_priority": "入睡速度,睡眠深度",
        "caffeine_intake": "仅在上午", "exercise_frequency": "每周3次",
    }, headers=hd)
    eq(s, 200, "Step4-创建健康档案")
    eq(d["age"], 28, "Step4-年龄验证")
    eq(d["sleep_goal_hours"], 8.0, "Step4-目标验证")

    # Step 5: Check profile exists now
    s, d = api("GET", "/api/v1/auth/has-profile", headers=hd)
    check(d["has_profile"] == True, "Step5-档案确认存在")

    # Step 6: Record sleep - Day 1
    s, r1 = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-15",
        "bedtime": "2026-05-15T23:30:00", "wake_time": "2026-05-16T06:45:00",
        "quality": 3, "tags": ["失眠"], "notes": "第一天记录，睡得不太好",
    }, headers=hd)
    eq(s, 200, "Step6-记录睡眠Day1")
    check(r1["duration_hours"] == 7.2 or r1["duration_hours"] == 7.3, f"Step6-时长验证: {r1['duration_hours']}h")
    check(0 <= r1["score"] <= 100, "Step6-评分范围")
    check(len(r1["ai_feedback"]) > 0, "Step6-AI反馈非空")
    sid1 = r1["id"]

    # Step 7: Record sleep - Day 2 (better)
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-16",
        "bedtime": "2026-05-16T22:30:00", "wake_time": "2026-05-17T06:30:00",
        "quality": 4, "tags": ["深睡", "做梦"], "notes": "睡得很好！",
    }, headers=hd)
    eq(s, 200, "Step7-记录睡眠Day2")
    check(d["score"] > 50, f"Step7-评分应>50: {d['score']}")

    # Step 8: Record sleep - Day 3
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-17",
        "bedtime": "2026-05-17T22:00:00", "wake_time": "2026-05-18T06:00:00",
        "quality": 5, "tags": ["深睡"],
    }, headers=hd)
    eq(s, 200, "Step8-记录睡眠Day3")

    # Step 9: List all records
    s, d = api("GET", "/api/v1/sleep-records?days=30", headers=hd)
    eq(s, 200, "Step9-列出记录")
    check(d["total"] >= 3, f"Step9-总数≥3: {d['total']}")

    # Step 10: Get stats
    s, d = api("GET", "/api/v1/sleep-records/stats/summary?days=7", headers=hd)
    eq(s, 200, "Step10-获取统计")
    check(d["avg_duration"] > 0, "Step10-平均时长>0")
    check(d["avg_score"] > 0, "Step10-平均评分>0")
    check(d["total_records"] >= 3, f"Step10-记录数≥3: {d['total_records']}")

    # Step 11: Enhanced stats
    s, d = api("GET", "/api/v1/sleep-records/stats/enhanced?days=7", headers=hd)
    eq(s, 200, "Step11-增强统计")
    check("sleep_debt" in d, "Step11-睡眠债存在")
    check(d["avg_efficiency"] > 0, "Step11-效率>0")

    # Step 12: Get today's tasks
    s, tasks_d = api("GET", "/api/v1/tasks/today", headers=hd)
    eq(s, 200, "Step12-获取今日任务")
    check(len(tasks_d["tasks"]) == 4, f"Step12-4个任务: {len(tasks_d['tasks'])}")

    # Step 13: Complete a task
    today = f"{time.localtime().tm_year}-{time.localtime().tm_mon}-{time.localtime().tm_mday}"
    task0 = tasks_d["tasks"][0]["id"]
    s, d = api("POST", "/api/v1/tasks/complete", json={"task_id": task0, "date_key": today}, headers=hd)
    eq(s, 200, "Step13-完成任务")
    eq(d["points"], 5, "Step13-获得5分")

    # Step 14: Complete second task
    task1 = tasks_d["tasks"][1]["id"]
    s, d = api("POST", "/api/v1/tasks/complete", json={"task_id": task1, "date_key": today}, headers=hd)
    eq(s, 200, "Step14-完成第二个任务")

    # Step 15: Check points
    s, d = api("GET", "/api/v1/tasks/points/summary", headers=hd)
    eq(s, 200, "Step15-查询积分")
    check(d["total_points"] >= 10, f"Step15-积分≥10: {d['total_points']}")

    # Step 16: Check badges
    s, d = api("GET", "/api/v1/tasks/badges", headers=hd)
    eq(s, 200, "Step16-徽章列表")
    eq(len(d), 8, "Step16-8个徽章")

    # Step 17: Chat with AI coach
    s, d = api("POST", "/api/v1/chat/send", json={"message": "我最近睡眠有改善，但偶尔还是会失眠"}, headers=hd)
    eq(s, 200, "Step17-发送聊天")
    check(len(d["content"]) > 0, "Step17-AI回复非空")
    sid = d["session_id"]

    # Step 18: Continue chat
    s, d = api("POST", "/api/v1/chat/send", json={"session_id": sid, "message": "谢谢你的建议"}, headers=hd)
    eq(s, 200, "Step18-继续聊天")

    # Step 19: Chat session detail
    s, d = api("GET", f"/api/v1/chat/sessions/{sid}", headers=hd)
    eq(s, 200, "Step19-会话详情")
    check(len(d["messages"]) >= 3, f"Step19-至少3条消息: {len(d['messages'])}")

    # Step 20: Enroll in a plan
    s, d = api("POST", "/api/v1/wellness/plans/plan_insomnia/enroll", headers=hd)
    eq(s, 200, "Step20-注册改善计划")

    # Step 21: Checkin
    s, d = api("POST", "/api/v1/wellness/plans/checkin", json={"date_key": today, "task_index": 0}, headers=hd)
    eq(s, 200, "Step21-计划打卡")

    # Step 22: Mood tracking
    s, d = api("POST", "/api/v1/mood/records", json={"date_key": today, "mood_level": 4, "energy_level": 3, "anxiety_level": 2}, headers=hd)
    eq(s, 200, "Step22-心情记录")

    # Step 23: Get moods
    s, d = api("GET", "/api/v1/mood/records?days=7", headers=hd)
    eq(s, 200, "Step23-获取心情")
    check(len(d["moods"]) >= 1, "Step23-至少1条心情")

    # Step 24: Game status
    s, d = api("GET", "/api/v1/game/status", headers=hd)
    eq(s, 200, "Step24-游戏状态")
    check(d["level"] >= 1, "Step24-等级≥1")

    # Step 25: Daily checkin
    s, d = api("POST", "/api/v1/game/checkin", headers=hd)
    eq(s, 200, "Step25-每日签到")

    # Step 26: Refresh token
    s, d = api("POST", "/api/v1/auth/refresh", json={"refresh_token": rt})
    eq(s, 200, "Step26-刷新Token")
    check("access_token" in d, "Step26-返回access_token")

    # Step 27: Delete sleep record
    s, d = api("DELETE", f"/api/v1/sleep-records/{sid1}", headers=hd)
    eq(s, 200, "Step27-删除记录")

    # Step 28: Verify deleted
    s, d = api("GET", f"/api/v1/sleep-records/{sid1}", headers=hd)
    eq(s, 404, "Step28-确认已删除")

    # Step 29: Logout
    s, d = api("POST", "/api/v1/auth/logout", headers=hd)
    eq(s, 200, "Step29-登出")

    # Step 30: Verify token invalid after logout
    s, d = api("GET", "/api/v1/auth/me", headers=hd)
    eq(s, 401, "Step30-Token已失效")

    print("  E2E Flow 1 Complete: 30 steps")

# moved to main


# ================== E2E FLOW 2: 社区互动流程 ==================
print("\n" + "=" * 60)
print("  E2E FLOW 2: 社区互动 — 发帖→点赞→评论→加入挑战")
print("=" * 60)

def e2e_community_flow():
    # Join group
    s, d = api("GET", "/api/v1/community/groups", headers=auth())
    eq(s, 200, "获取群组列表")
    gid = d["groups"][0]["id"]
    s, d = api("POST", f"/api/v1/community/groups/{gid}/join", headers=auth())
    eq(s, 200, "加入群组")

    # Verify membership
    s, d = api("GET", "/api/v1/community/groups", headers=auth())
    check(any(g.get("is_member") for g in d["groups"]), "确认已加入群组")

    # Create post
    s, d = api("POST", "/api/v1/community/posts", json={"content": "今天早睡了！记录一下进步", "sleep_score": 85, "sleep_duration": 8.0, "is_anonymous": 0}, headers=auth())
    eq(s, 200, "创建帖子")
    pid = d["id"]

    # Like post
    s, d = api("POST", f"/api/v1/community/posts/{pid}/like", headers=auth())
    eq(s, 200, "点赞帖子")
    check(d["liked"] == True, "liked=True")

    # Unlike
    s, d = api("POST", f"/api/v1/community/posts/{pid}/like", headers=auth())
    eq(s, 200, "取消点赞")
    check(d["liked"] == False, "liked=False")

    # Comment
    s, d = api("POST", f"/api/v1/community/posts/{pid}/comment", json={"content": "加油！继续坚持"}, headers=auth())
    eq(s, 200, "评论帖子")

    # Get comments
    s, d = api("GET", f"/api/v1/community/posts/{pid}/comments", headers=auth())
    eq(s, 200, "获取评论")
    check(len(d["comments"]) >= 1, "至少有一条评论")

    # Join challenge
    s, d = api("GET", "/api/v1/community/challenges", headers=auth())
    cid = d["challenges"][0]["id"]
    s, d = api("POST", f"/api/v1/community/challenges/{cid}/join", headers=auth())
    eq(s, 200, "加入挑战")

    # Check leaderboard
    s, d = api("GET", "/api/v1/community/leaderboard?period=weekly", headers=auth())
    eq(s, 200, "查看排行榜")

    # Leave group
    s, d = api("POST", f"/api/v1/community/groups/{gid}/leave", headers=auth())
    eq(s, 200, "退出群组")

    print("  E2E Flow 2 Complete: 10 steps")

# moved to main


# ================== E2E FLOW 3: 支付升级流程 ==================
print("\n" + "=" * 60)
print("  E2E FLOW 3: 付费升级 — 查看套餐→下单→支付→确认状态")
print("=" * 60)

def e2e_payment_flow():
    # Check current tier
    s, d = api("GET", "/api/v1/premium/status", headers=auth())
    eq(s, 200, "当前会员状态")
    check(d["tier"] == "free", f"初始为free: {d['tier']}")

    # View plans
    s, d = api("GET", "/api/v1/payment/plans")
    eq(s, 200, "查看套餐")
    check(len(d["plans"]) == 4, f"4个套餐: {len(d['plans'])}")

    # Create order
    s, d = api("POST", "/api/v1/payment/orders", json={"plan_id": "pro_monthly", "method": "wechat"}, headers=auth())
    eq(s, 200, "创建订单")
    oid = d["order_id"]
    check(d["status"] == "pending", "订单状态pending")

    # Pay order
    s, d = api("POST", f"/api/v1/payment/orders/{oid}/pay", headers=auth())
    eq(s, 200, "支付订单")
    check(d["tier"] == "pro", f"升级为pro: {d['tier']}")

    # Verify premium status
    s, d = api("GET", "/api/v1/premium/status", headers=auth())
    eq(s, 200, "确认会员状态")
    check(d["tier"] == "pro", f"已是pro: {d['tier']}")
    check(d["is_premium"] == True, "is_premium=True")

    # Refund
    s, d = api("POST", f"/api/v1/payment/orders/{oid}/refund", headers=auth())
    eq(s, 200, "退款")

    # Order history
    s, d = api("GET", "/api/v1/payment/orders", headers=auth())
    eq(s, 200, "订单历史")
    check(len(d["orders"]) >= 1, "至少1条订单")

    # Cancel auto-renew
    s, d = api("POST", "/api/v1/premium/cancel", headers=auth())
    eq(s, 200, "取消自动续费")

    print("  E2E Flow 3 Complete: 9 steps")

# moved to main


# ================== CRUD 边界测试 ==================
print("\n" + "=" * 60)
print("  CRUD 边界测试")
print("=" * 60)

def crud_edge_cases():
    # GET non-existent record
    s, d = api("GET", "/api/v1/sleep-records/99999", headers=auth())
    eq(s, 404, "GET不存在的记录→404")

    # DELETE non-existent record
    s, d = api("DELETE", "/api/v1/sleep-records/99999", headers=auth())
    eq(s, 404, "DELETE不存在的记录→404")

    # Create record with missing fields (no quality)
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-18",
        "bedtime": "2026-05-18T23:00:00",
        "wake_time": "2026-05-19T07:00:00",
    }, headers=auth())
    eq(s, 200, "创建记录(无quality)")

    # Create record with edge-case duration (same time)
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-19",
        "bedtime": "2026-05-19T22:00:00",
        "wake_time": "2026-05-19T22:00:00",
        "quality": 1,
    }, headers=auth())
    eq(s, 200, "创建记录(相同时刻)")

    # Create record with wake before bed (cross-midnight)
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-20",
        "bedtime": "2026-05-20T23:00:00",
        "wake_time": "2026-05-20T01:00:00",
        "quality": 1,
    }, headers=auth())
    eq(s, 200, "创建记录(起床早于入睡)")

    # Get non-existent knowledge article
    s, d = api("GET", "/api/v1/wellness/knowledge/articles/nonexistent_id")
    eq(s, 404, "GET不存在文章→404")

    # Non-existent plan
    s, d = api("GET", "/api/v1/wellness/plans/nonexistent")
    eq(s, 404, "GET不存在计划→404")

    # Enroll in non-existent plan
    s, d = api("POST", "/api/v1/wellness/plans/nonexistent/enroll", headers=auth())
    eq(s, 404, "ENROLL不存在计划→404")

    # Chat with non-existent session
    s, d = api("POST", "/api/v1/chat/send", json={"session_id": 99999, "message": "hello"}, headers=auth())
    eq(s, 404, "CHAT不存在会话→404")

    # Delete non-existent chat session
    s, d = api("DELETE", "/api/v1/chat/sessions/99999", headers=auth())
    eq(s, 404, "DELETE不存在会话→404")

    # Non-existent assessment
    s, d = api("GET", "/api/v1/wellness/assessments/INVALID")
    eq(s, 404, "GET不存在评估→404")

    # Non-existent platform config
    s, d = api("GET", "/api/v1/platform/config/unknown_platform")
    eq(s, 404, "GET不存在平台→404")

    # Invalid payment plan
    s, d = api("POST", "/api/v1/payment/orders", json={"plan_id": "invalid_plan"}, headers=auth())
    eq(s, 400, "POST无效套餐→400")

    print("  CRUD Edge Cases Complete: 13 tests")

# moved to main


# ================== 状态转换测试 ==================
print("\n" + "=" * 60)
print("  状态转换测试")
print("=" * 60)

def state_transitions():
    # Task: complete → complete again (idempotent)
    today = f"{time.localtime().tm_year}-{time.localtime().tm_mon}-{time.localtime().tm_mday}"
    s, d = api("POST", "/api/v1/tasks/complete", json={"task_id": "t3", "date_key": today}, headers=auth())
    eq(s, 200, "首次完成t3")
    s, d = api("POST", "/api/v1/tasks/complete", json={"task_id": "t3", "date_key": today}, headers=auth())
    eq(s, 200, "重复完成t3(幂等)")
    check(d.get("already") == True, "返回already=True")

    # Task: complete → uncomplete → uncomplete again
    s, d = api("DELETE", "/api/v1/tasks/complete", json={"task_id": "t3", "date_key": today}, headers=auth())
    eq(s, 200, "取消完成t3")
    s, d = api("DELETE", "/api/v1/tasks/complete", json={"task_id": "t3", "date_key": today}, headers=auth())
    eq(s, 200, "重复取消(优雅处理)")

    # Badge: unlock → unlock again
    s, d = api("POST", "/api/v1/tasks/badges/unlock", json={"badge_id": "b1"}, headers=auth())
    eq(s, 200, "解锁徽章b1")
    s, d = api("POST", "/api/v1/tasks/badges/unlock", json={"badge_id": "b1"}, headers=auth())
    eq(s, 200, "重复解锁b1(幂等)")
    check(d.get("already") == True, "已解锁=True")

    # Payment: pay already paid order
    s, d = api("POST", "/api/v1/payment/orders", json={"plan_id": "pro_monthly", "method": "manual"}, headers=auth())
    oid = d["order_id"]
    s, d = api("POST", f"/api/v1/payment/orders/{oid}/pay", headers=auth())
    eq(s, 200, "首次支付")
    s, d = api("POST", f"/api/v1/payment/orders/{oid}/pay", headers=auth())
    eq(s, 400, "重复支付→400")

    # Game: checkin → checkin again
    s, d = api("POST", "/api/v1/game/checkin", headers=auth())
    check(s in (200, 200), "签到")
    s, d = api("POST", "/api/v1/game/checkin", headers=auth())
    eq(s, 200, "重复签到(幂等)")

    # Mood: create → update
    s, d = api("POST", "/api/v1/mood/records", json={"date_key": today, "mood_level": 3, "energy_level": 2, "anxiety_level": 4}, headers=auth())
    eq(s, 200, "创建心情")
    s, d = api("POST", "/api/v1/mood/records", json={"date_key": today, "mood_level": 5, "energy_level": 5, "anxiety_level": 1}, headers=auth())
    eq(s, 200, "更新心情")

    # Health data: upsert
    s, d = api("POST", "/api/v1/wellness/health-data", json={"date_key": today, "steps": 5000, "heart_rate_avg": 70}, headers=auth())
    eq(s, 200, "同步健康数据")
    s, d = api("POST", "/api/v1/wellness/health-data", json={"date_key": today, "steps": 12000}, headers=auth())
    eq(s, 200, "更新健康数据")

    print("  State Transitions Complete: 13 tests")

# moved to main


# ================== 并发操作测试 ==================
print("\n" + "=" * 60)
print("  并发操作测试")
print("=" * 60)

def concurrent_operations():
    import concurrent.futures

    def create_record(i):
        s, d = api("POST", "/api/v1/sleep-records", json={
            "diary_date": f"2026-05-{10+(i%10):02d}",
            "bedtime": f"2026-05-{10+(i%10):02d}T23:00:00",
            "wake_time": f"2026-05-{11+(i%10):02d}T06:30:00",
            "quality": 3 + (i % 3),
        }, headers=auth())
        return s

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(create_record, range(10)))

    success = sum(1 for r in results if r == 200)
    check(success == 10, f"并发创建10条记录: {success}/10 成功")
    print(f"  并发测试: {success}/10 通过")

# moved to main


# ================== 统计验证 ==================
print("\n" + "=" * 60)
print("  数据统计验证")
print("=" * 60)

def stats_validation():
    s, d = api("GET", "/api/v1/sleep-records/stats/summary?days=30", headers=auth())
    eq(s, 200, "获取统计")
    check(d["total_records"] >= 10, f"总记录数≥10: {d['total_records']}")
    check(d["avg_duration"] >= 0, "平均时长非负")
    check(0 <= d["avg_score"] <= 100, "平均评分在0-100")
    check(d["consistency"] in ("regular", "moderate", "irregular", "--"), f"一致性有效值: {d['consistency']}")

    # Visualizations
    s, d = api("GET", "/api/v1/sleep-records/viz/heatmap?days=30", headers=auth())
    eq(s, 200, "热力图数据")
    check(len(d["heatmap"]) > 0, "热力图有数据")

    s, d = api("GET", "/api/v1/sleep-records/viz/radar?days=30", headers=auth())
    eq(s, 200, "雷达图数据")
    for k in ("duration", "quality", "consistency", "efficiency", "depth"):
        check(k in d["radar"], f"雷达图包含{k}")

    s, d = api("GET", "/api/v1/sleep-records/viz/compare?days=7", headers=auth())
    eq(s, 200, "对比数据")
    check("current" in d and "previous" in d, "有current和previous")

    print("  Stats Validation Complete: 9 tests")

# moved to main


# ================== KNOWLEDGE & WELLNESS ==================
print("\n" + "=" * 60)
print("  知识库 & 健康功能")
print("=" * 60)

def knowledge_and_wellness():
    # All knowledge endpoints
    s, d = api("GET", "/api/v1/wellness/knowledge/categories")
    eq(s, 200, "知识分类")
    check(len(d["categories"]) >= 5, f"≥5个分类: {len(d['categories'])}")

    for cat in ["睡眠科学", "CBT-I疗法"]:
        encoded = urllib.parse.quote(cat)
        s, d = api("GET", f"/api/v1/wellness/knowledge/articles?category={encoded}")
        eq(s, 200, f"分类筛选: {cat}")
        check(d["total"] >= 1, f"分类{cat}有文章")

    # RAG search
    for q in ["失眠", "褪黑素", "CBT-I"]:
        encoded = urllib.parse.quote(q)
        s, d = api("GET", f"/api/v1/wellness/ai/rag-search?q={encoded}")
        eq(s, 200, f"RAG搜索: {q}")

    # Assessments
    s, d = api("GET", "/api/v1/wellness/assessments")
    eq(s, 200, "评估列表")
    for scale in ["PSQI", "ISI"]:
        s, d = api("GET", f"/api/v1/wellness/assessments/{scale}")
        eq(s, 200, f"评估详情: {scale}")

    # Submit ISI
    s, d = api("POST", "/api/v1/wellness/assessments/ISI/submit", json={
        "answers": {"1": "0", "2": "1", "3": "0", "4": "2", "5": "1", "6": "0", "7": "1"}
    }, headers=auth())
    eq(s, 200, "提交ISI评估")
    check("severity" in d, "有严重度评估")

    # Plan recommendations
    s, d = api("GET", "/api/v1/wellness/recommend-plan", headers=auth())
    eq(s, 200, "推荐计划")
    check("recommended" in d, "有推荐结果")

    # Onboarding
    s, d = api("GET", "/api/v1/wellness/onboarding", headers=auth())
    eq(s, 200, "新手指引")

    # AI soundscape
    s, d = api("POST", "/api/v1/wellness/ai-soundscape", json={}, headers=auth())
    eq(s, 200, "AI音景")
    check(len(d["channels"]) == 4, "4条音轨")

    # AI recommendations
    s, d = api("GET", "/api/v1/wellness/ai/recommendations", headers=auth())
    eq(s, 200, "AI推荐")

    # Risk assessment
    s, d = api("GET", "/api/v1/sleep-records/ai/risk-assessment", headers=auth())
    eq(s, 200, "风险评估")
    check("risks" in d, "有风险数据")

    # AI generate plan
    s, d = api("POST", "/api/v1/wellness/ai/generate-plan", headers=auth())
    eq(s, 200, "AI生成计划")
    check(d["ai_generated"] == True, "标记为AI生成")

    print("  Knowledge & Wellness Complete: 18 tests")

# moved to main


# ================== 通知 & 提醒 ==================
print("\n" + "=" * 60)
print("  通知 & 提醒功能")
print("=" * 60)

def notifications_and_more():
    s, d = api("GET", "/api/v1/auth/reminders/today", headers=auth())
    eq(s, 200, "今日提醒")

    s, d = api("GET", "/api/v1/auth/notification-settings", headers=auth())
    eq(s, 200, "通知设置-get")

    s, d = api("PUT", "/api/v1/auth/notification-settings", json={"sleep_reminder": 1, "reminder_time": "21:30"}, headers=auth())
    eq(s, 200, "通知设置-update")

    # Change password
    s, d = api("PUT", "/api/v1/auth/change-password", json={"old_password": PASS, "new_password": "NewPass456"}, headers=auth())
    eq(s, 200, "修改密码")
    # Change back
    s, d = api("PUT", "/api/v1/auth/change-password", json={"old_password": "NewPass456", "new_password": PASS}, headers=auth())
    eq(s, 200, "改回密码")

    # Wrong old password
    s, d = api("PUT", "/api/v1/auth/change-password", json={"old_password": "wrong", "new_password": "NewPass789"}, headers=auth())
    eq(s, 400, "原密码错误→400")

    print("  Notifications Complete: 6 tests")

# moved to main


# ================== SUMMARY ==================
print("\n" + "=" * 60)
print(f"  功能测试: {pass_count} passed, {fail_count} failed")
if fail_count == 0: print("  ALL FUNCTIONAL TESTS PASSED")
else: print(f"  {fail_count} FUNCTIONAL TESTS FAILED")
print("=" * 60)

if __name__ == "__main__":
    print("=" * 60)
    print("  梦眠阁 - 功能测试套件")
    print("=" * 60)
    print("\n  Starting server...")
    start_server()
    print("  Setting up test user...")
    setup()
    e2e_user_journey()
    e2e_community_flow()
    e2e_payment_flow()
    crud_edge_cases()
    state_transitions()
    concurrent_operations()
    stats_validation()
    knowledge_and_wellness()
    notifications_and_more()
    print(f"\n  TOTAL: {pass_count} passed, {fail_count} failed")
    if fail_count == 0: print("  ALL FUNCTIONAL TESTS PASSED")
    sys.exit(fail_count)
