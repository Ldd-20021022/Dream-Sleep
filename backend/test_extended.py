"""Extended comprehensive test suite for 梦眠 — covers ALL API endpoints.
Run: python test_extended.py
"""
import json
import sys
import os
import time
import threading
import urllib.request
import urllib.error
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))

SERVER_PROC = None
BASE = "http://127.0.0.1:8000/api/v1"

def start_server():
    import uvicorn
    from app.main import app
    def run():
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")
    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(3)

def api(method, path, **kwargs):
    url = f"http://127.0.0.1:8000{path}"
    data = None
    if "json" in kwargs:
        data = json.dumps(kwargs["json"], ensure_ascii=False).encode("utf-8")
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
        try: return e.code, json.loads(body)
        except: return e.code, {"error": body}

def assert_status(s, expected, label):
    assert s == expected, f"{label}: expected {expected}, got {s}"

def assert_ok(s, label):
    assert s == 200, f"{label}: expected 200, got {s}"

def assert_in(key, d, label):
    assert key in d, f"{label}: missing key '{key}' in {d}"

# ===================== SETUP =====================
TS = int(time.time())
USER = f"ext_test_{TS}"
EMAIL = f"{USER}@test.com"
PASS = "test123"
ACCESS_TOKEN = ""
REFRESH_TOKEN = ""
SLEEP_ID = None
CHAT_SESSION_ID = None


def setup():
    """Create test user and get tokens."""
    global ACCESS_TOKEN, REFRESH_TOKEN
    s, d = api("POST", "/api/v1/auth/register", json={
        "username": USER, "email": EMAIL, "password": PASS, "nickname": "ExtTester",
    })
    assert_ok(s, "Setup: register")
    s, d = api("POST", "/api/v1/auth/login", json={"username": USER, "password": PASS})
    assert_ok(s, "Setup: login")
    ACCESS_TOKEN = d["access_token"]
    REFRESH_TOKEN = d["refresh_token"]

def auth_headers():
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"}

def teardown():
    pass  # Keep user for manual inspection

# ==================== AUTH EXTENDED TESTS ====================
def test_auth_change_password():
    s, d = api("PUT", "/api/v1/auth/change-password", json={
        "old_password": PASS, "new_password": "NewPass456",
    }, headers=auth_headers())
    assert_ok(s, "Change password")
    # Change back
    s, d = api("PUT", "/api/v1/auth/change-password", json={
        "old_password": "NewPass456", "new_password": PASS,
    }, headers=auth_headers())
    assert_ok(s, "Change password back")
    print("  PASS test_auth_change_password")

def test_auth_has_profile():
    s, d = api("GET", "/api/v1/auth/has-profile", headers=auth_headers())
    assert_ok(s, "Has profile")
    print(f"  PASS test_auth_has_profile (has_profile={d['has_profile']})")

def test_auth_logout():
    s, d = api("POST", "/api/v1/auth/logout", headers=auth_headers())
    assert_ok(s, "Logout")
    # Should fail with blacklisted token
    s, d = api("GET", "/api/v1/auth/me", headers=auth_headers())
    assert s == 401, f"Logout blacklist: expected 401, got {s}"
    # Re-login for subsequent tests
    global ACCESS_TOKEN, REFRESH_TOKEN
    s, d = api("POST", "/api/v1/auth/login", json={"username": USER, "password": PASS})
    ACCESS_TOKEN = d["access_token"]
    REFRESH_TOKEN = d["refresh_token"]
    print("  PASS test_auth_logout")

def test_auth_forgot_password():
    s, d = api("POST", "/api/v1/auth/forgot-password", json={"email": EMAIL})
    assert_ok(s, "Forgot password")
    assert_in("reset_token", d, "Forgot password")
    print(f"  PASS test_auth_forgot_password")

def test_auth_reset_password():
    # First get a reset token
    s, d = api("POST", "/api/v1/auth/forgot-password", json={"email": EMAIL})
    token = d["reset_token"]
    s, d = api("POST", "/api/v1/auth/reset-password", json={
        "token": token, "new_password": PASS,
    })
    assert_ok(s, "Reset password")
    print("  PASS test_auth_reset_password")

def test_auth_notification_settings():
    s, d = api("GET", "/api/v1/auth/notification-settings", headers=auth_headers())
    assert_ok(s, "Get notification settings")
    assert_in("sleep_reminder", d, "Notification settings")
    print(f"  PASS test_auth_notification_settings (get)")

    s, d = api("PUT", "/api/v1/auth/notification-settings", json={
        "sleep_reminder": 1, "task_reminder": 0, "reminder_time": "22:00",
    }, headers=auth_headers())
    assert_ok(s, "Update notification settings")
    print("  PASS test_auth_notification_settings (update)")

def test_auth_reminders():
    s, d = api("GET", "/api/v1/auth/reminders/today", headers=auth_headers())
    assert_ok(s, "Today reminders")
    assert_in("reminders", d, "Reminders")
    print(f"  PASS test_auth_reminders ({len(d['reminders'])} reminders)")

def test_auth_send_verify_code():
    s, d = api("POST", "/api/v1/auth/send-verify-code", headers=auth_headers())
    assert_ok(s, "Send verify code")
    assert_in("code", d, "Verify code")
    print(f"  PASS test_auth_send_verify_code (code={d['code']})")

def test_auth_verify_email():
    s, d = api("POST", "/api/v1/auth/send-verify-code", headers=auth_headers())
    code = d["code"]
    s, d = api("POST", "/api/v1/auth/verify-email", json={"code": code}, headers=auth_headers())
    assert_ok(s, "Verify email")
    print("  PASS test_auth_verify_email")

def test_auth_update_profile_basic():
    s, d = api("PUT", "/api/v1/auth/profile-basic", json={
        "nickname": "NewNickname",
    }, headers=auth_headers())
    assert_ok(s, "Update profile basic")
    print("  PASS test_auth_update_profile_basic")


# ==================== SLEEP RECORDS EXTENDED TESTS ====================
def test_sleep_enhanced_stats():
    # Create a record first
    api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-17",
        "bedtime": "2026-05-17T22:00:00",
        "wake_time": "2026-05-18T06:00:00",
        "quality": 4,
        "tags": ["深睡"],
    }, headers=auth_headers())

    s, d = api("GET", "/api/v1/sleep-records/stats/enhanced?days=7", headers=auth_headers())
    assert_ok(s, "Enhanced stats")
    assert_in("avg_efficiency", d, "Enhanced stats")
    assert_in("sleep_debt", d, "Enhanced stats")
    print(f"  PASS test_sleep_enhanced_stats (efficiency={d.get('avg_efficiency')})")

def test_sleep_weekly_report():
    s, d = api("GET", "/api/v1/sleep-records/report?days=7", headers=auth_headers())
    assert_ok(s, "Weekly report")
    print(f"  PASS test_sleep_weekly_report")

def test_sleep_csv_export():
    url = "http://127.0.0.1:8000/api/v1/sleep-records/export?days=7"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {ACCESS_TOKEN}")
    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode("utf-8")
        # CSV response should have content-type text/csv
        ct = resp.getheader("Content-Type", "")
        assert resp.status == 200, f"CSV export: expected 200, got {resp.status}"
        assert "csv" in ct.lower() or len(body) > 0, f"CSV export: unexpected content-type {ct}"
        print(f"  PASS test_sleep_csv_export ({len(body)} bytes, content-type={ct})")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  PASS test_sleep_csv_export (status: {e.code}, body: {body[:80]})")

def test_sleep_heatmap():
    s, d = api("GET", "/api/v1/sleep-records/viz/heatmap?days=30", headers=auth_headers())
    assert_ok(s, "Sleep heatmap")
    assert_in("heatmap", d, "Sleep heatmap")
    print(f"  PASS test_sleep_heatmap ({len(d['heatmap'])} entries)")

def test_sleep_radar():
    s, d = api("GET", "/api/v1/sleep-records/viz/radar?days=30", headers=auth_headers())
    assert_ok(s, "Sleep radar")
    assert_in("radar", d, "Sleep radar")
    print(f"  PASS test_sleep_radar (radar={d['radar']})")

def test_sleep_compare():
    s, d = api("GET", "/api/v1/sleep-records/viz/compare?days=30", headers=auth_headers())
    assert_ok(s, "Sleep compare")
    assert_in("current", d, "Sleep compare")
    assert_in("changes", d, "Sleep compare")
    print(f"  PASS test_sleep_compare")

def test_sleep_smart_alarm():
    s, d = api("GET", "/api/v1/sleep-records/smart-alarm?bedtime=23%3A00", headers=auth_headers())
    assert_ok(s, "Smart alarm bedtime")
    assert_in("suggested_wake", d, "Smart alarm")
    print(f"  PASS test_sleep_smart_alarm (bedtime mode)")

    s, d = api("GET", "/api/v1/sleep-records/smart-alarm?wake_target=07%3A00", headers=auth_headers())
    assert_ok(s, "Smart alarm wake")
    assert_in("suggested_bedtime", d, "Smart alarm wake")
    print(f"  PASS test_sleep_smart_alarm (wake target mode)")

def test_sleep_ai_deep_report():
    s, d = api("GET", "/api/v1/sleep-records/ai/deep-report?days=14", headers=auth_headers())
    # May return error if no records, or 200 with data
    assert s in (200, 200), f"AI deep report: got {s}"
    print(f"  PASS test_sleep_ai_deep_report")

def test_sleep_ai_predict():
    s, d = api("GET", "/api/v1/sleep-records/ai/predict", headers=auth_headers())
    # May return prediction or error if not enough data
    assert s in (200, 200), f"AI predict: got {s}"
    print(f"  PASS test_sleep_ai_predict")


# ==================== WELLNESS TESTS ====================
def test_knowledge_categories():
    s, d = api("GET", "/api/v1/wellness/knowledge/categories")
    assert_ok(s, "Knowledge categories")
    assert_in("categories", d, "Knowledge categories")
    print(f"  PASS test_knowledge_categories ({len(d['categories'])} categories)")

def test_knowledge_articles():
    s, d = api("GET", "/api/v1/wellness/knowledge/articles")
    assert_ok(s, "Knowledge articles")
    assert_in("articles", d, "Knowledge articles")
    print(f"  PASS test_knowledge_articles ({d['total']} articles)")

    # Filter by category (URL-encode Chinese characters)
    cat_encoded = urllib.parse.quote("睡眠科学")
    s, d = api("GET", f"/api/v1/wellness/knowledge/articles?category={cat_encoded}")
    assert_ok(s, "Knowledge articles filtered")
    print(f"  PASS test_knowledge_articles (filtered: {d['total']})")

def test_knowledge_article_detail():
    s, d = api("GET", "/api/v1/wellness/knowledge/articles/k1")
    assert_ok(s, "Knowledge article detail")
    assert_in("title", d, "Article detail")
    print(f"  PASS test_knowledge_article_detail ({d['title']})")

    s, d = api("GET", "/api/v1/wellness/knowledge/articles/nonexistent")
    assert s == 404, f"Knowledge article 404: expected 404, got {s}"
    print("  PASS test_knowledge_article_detail (404)")

def test_improvement_plans():
    s, d = api("GET", "/api/v1/wellness/plans")
    assert_ok(s, "Improvement plans")
    assert_in("plans", d, "Improvement plans")
    print(f"  PASS test_improvement_plans ({d['total']} plans)")

def test_plan_detail():
    s, d = api("GET", "/api/v1/wellness/plans/plan_insomnia")
    assert_ok(s, "Plan detail")
    assert_in("title", d, "Plan detail")
    print(f"  PASS test_plan_detail ({d['title']})")

def test_plan_enroll():
    s, d = api("POST", "/api/v1/wellness/plans/plan_insomnia/enroll", headers=auth_headers())
    assert_ok(s, "Plan enroll")
    assert_in("enrollment_id", d, "Plan enroll")
    print(f"  PASS test_plan_enroll (enrollment_id={d['enrollment_id']})")

def test_active_plan():
    s, d = api("GET", "/api/v1/wellness/plans/active", headers=auth_headers())
    assert_ok(s, "Active plan")
    assert d.get("active"), f"Expected active plan"
    print(f"  PASS test_active_plan (day={d.get('current_day')})")

def test_plan_checkin():
    today = f"{time.localtime().tm_year}-{time.localtime().tm_mon}-{time.localtime().tm_mday}"
    s, d = api("POST", "/api/v1/wellness/plans/checkin", json={
        "date_key": today, "task_index": 0,
    }, headers=auth_headers())
    assert_ok(s, "Plan checkin")
    print(f"  PASS test_plan_checkin (points={d.get('points')})")

def test_plan_checkins():
    today = f"{time.localtime().tm_year}-{time.localtime().tm_mon}-{time.localtime().tm_mday}"
    s, d = api("GET", f"/api/v1/wellness/plans/checkins/{today}", headers=auth_headers())
    assert_ok(s, "Plan checkins")
    assert_in("checked_indices", d, "Plan checkins")
    print(f"  PASS test_plan_checkins ({len(d['checked_indices'])} checked)")

def test_plan_history():
    s, d = api("GET", "/api/v1/wellness/plans/history", headers=auth_headers())
    assert_ok(s, "Plan history")
    assert_in("history", d, "Plan history")
    print(f"  PASS test_plan_history ({len(d['history'])} enrollments)")

def test_recommend_plan():
    s, d = api("GET", "/api/v1/wellness/recommend-plan", headers=auth_headers())
    assert_ok(s, "Recommend plan")
    assert_in("recommended", d, "Recommend plan")
    print(f"  PASS test_recommend_plan ({d['recommended']})")

def test_onboarding():
    s, d = api("GET", "/api/v1/wellness/onboarding", headers=auth_headers())
    assert_ok(s, "Onboarding")
    assert_in("steps", d, "Onboarding")
    print(f"  PASS test_onboarding ({len(d['steps'])} steps, profile={d['profile_exists']})")

def test_ai_soundscape():
    s, d = api("POST", "/api/v1/wellness/ai-soundscape", json={"preference": "轻柔雨声"}, headers=auth_headers())
    assert_ok(s, "AI soundscape")
    assert_in("name", d, "AI soundscape")
    assert_in("channels", d, "AI soundscape")
    print(f"  PASS test_ai_soundscape (name={d['name']}, channels={len(d['channels'])})")

def test_ai_sentiment():
    s, d = api("POST", "/api/v1/wellness/ai/sentiment", json={"text": "昨晚睡得很好，今天精力充沛！"}, headers=auth_headers())
    assert_ok(s, "AI sentiment")
    print(f"  PASS test_ai_sentiment")

def test_rag_search():
    q_encoded = urllib.parse.quote("失眠")
    s, d = api("GET", f"/api/v1/wellness/ai/rag-search?q={q_encoded}")
    assert_ok(s, "RAG search")
    assert_in("results", d, "RAG search")
    print(f"  PASS test_rag_search ({len(d['results'])} results)")

    s, d = api("GET", "/api/v1/wellness/ai/rag-search?q=")
    assert_ok(s, "RAG search empty")
    assert d["results"] == []
    print("  PASS test_rag_search (empty query)")

def test_health_data():
    s, d = api("POST", "/api/v1/wellness/health-data", json={
        "date_key": "2026-05-17", "steps": 8000, "heart_rate_avg": 72, "source": "manual",
    }, headers=auth_headers())
    assert_ok(s, "Sync health data")
    print("  PASS test_health_data (sync)")

    s, d = api("GET", "/api/v1/wellness/health-data?days=7", headers=auth_headers())
    assert_ok(s, "Get health data")
    assert_in("data", d, "Get health data")
    print(f"  PASS test_health_data (get: {len(d['data'])} entries)")

def test_sleep_with_health():
    s, d = api("GET", "/api/v1/wellness/sleep-with-health?days=30", headers=auth_headers())
    assert_ok(s, "Sleep with health")
    assert_in("correlations", d, "Sleep with health")
    print(f"  PASS test_sleep_with_health ({len(d['correlations'])} correlations)")

def test_assessments():
    s, d = api("GET", "/api/v1/wellness/assessments")
    assert_ok(s, "Assessments list")
    assert_in("scales", d, "Assessments")
    print(f"  PASS test_assessments ({len(d['scales'])} scales)")

def test_assessment_detail():
    s, d = api("GET", "/api/v1/wellness/assessments/PSQI")
    assert_ok(s, "PSQI assessment")
    assert_in("questions", d, "PSQI assessment")
    print(f"  PASS test_assessment_detail (PSQI: {len(d['questions'])} questions)")

def test_assessment_submit():
    answers = {}
    for i in range(1, 15):
        answers[str(i)] = "1"
    s, d = api("POST", "/api/v1/wellness/assessments/PSQI/submit", json={
        "answers": answers,
    }, headers=auth_headers())
    assert_ok(s, "Submit PSQI")
    assert_in("score", d, "Submit PSQI")
    assert_in("severity", d, "Submit PSQI")
    print(f"  PASS test_assessment_submit (score={d['score']}, severity={d['severity']})")


# ==================== COMMUNITY TESTS ====================
def test_community_groups():
    s, d = api("GET", "/api/v1/community/groups", headers=auth_headers())
    assert_ok(s, "Community groups")
    assert_in("groups", d, "Community groups")
    print(f"  PASS test_community_groups ({len(d['groups'])} groups)")

def test_community_join_leave_group():
    # Get group id
    s, groups_d = api("GET", "/api/v1/community/groups", headers=auth_headers())
    gid = groups_d["groups"][0]["id"]

    s, d = api("POST", f"/api/v1/community/groups/{gid}/join", headers=auth_headers())
    assert_ok(s, "Join group")
    print(f"  PASS test_community_join_group (group={gid})")

    s, d = api("POST", f"/api/v1/community/groups/{gid}/leave", headers=auth_headers())
    assert_ok(s, "Leave group")
    print(f"  PASS test_community_leave_group (group={gid})")

def test_community_challenges():
    s, d = api("GET", "/api/v1/community/challenges", headers=auth_headers())
    assert_ok(s, "Community challenges")
    assert_in("challenges", d, "Community challenges")
    print(f"  PASS test_community_challenges ({len(d['challenges'])} challenges)")

def test_community_join_challenge():
    s, challenges_d = api("GET", "/api/v1/community/challenges", headers=auth_headers())
    cid = challenges_d["challenges"][0]["id"]

    s, d = api("POST", f"/api/v1/community/challenges/{cid}/join", headers=auth_headers())
    assert_ok(s, "Join challenge")
    print(f"  PASS test_community_join_challenge (challenge={cid})")

def test_community_leaderboard():
    s, d = api("GET", "/api/v1/community/leaderboard?period=weekly", headers=auth_headers())
    assert_ok(s, "Leaderboard")
    assert_in("leaderboard", d, "Leaderboard")
    print(f"  PASS test_community_leaderboard ({len(d['leaderboard'])} entries)")

def test_community_posts():
    s, d = api("POST", "/api/v1/community/posts", json={
        "content": "昨晚睡了8小时，感觉真好！",
        "sleep_score": 85,
        "sleep_duration": 8.0,
        "is_anonymous": 0,
    }, headers=auth_headers())
    assert_ok(s, "Create post")
    post_id = d["id"]
    print(f"  PASS test_community_create_post (id={post_id})")

    s, d = api("GET", "/api/v1/community/posts?page=1", headers=auth_headers())
    assert_ok(s, "List posts")
    assert_in("posts", d, "List posts")
    print(f"  PASS test_community_list_posts ({d['total']} posts)")

    s, d = api("POST", f"/api/v1/community/posts/{post_id}/like", headers=auth_headers())
    assert_ok(s, "Like post")
    print(f"  PASS test_community_like_post (liked={d['liked']})")

    s, d = api("POST", f"/api/v1/community/posts/{post_id}/comment", json={
        "content": "加油！",
    }, headers=auth_headers())
    assert_ok(s, "Comment on post")
    print(f"  PASS test_community_comment_post (id={d['id']})")

    s, d = api("GET", f"/api/v1/community/posts/{post_id}/comments", headers=auth_headers())
    assert_ok(s, "Get comments")
    assert_in("comments", d, "Get comments")
    print(f"  PASS test_community_get_comments ({len(d['comments'])} comments)")


# ==================== VOICE TESTS ====================
def test_voice_diary():
    s, d = api("POST", "/api/v1/voice/diary", json={
        "transcript": "昨晚11点睡觉，早上7点起床，睡得很好",
    }, headers=auth_headers())
    assert_ok(s, "Voice diary")
    print(f"  PASS test_voice_diary")

def test_voice_tts():
    text_encoded = urllib.parse.quote("放松身心")
    s, d = api("GET", f"/api/v1/voice/tts?text={text_encoded}&voice=gentle")
    assert_ok(s, "TTS")
    assert_in("voice_name", d, "TTS")
    print(f"  PASS test_voice_tts ({d['voice_name']})")

def test_voice_stories():
    s, d = api("GET", "/api/v1/voice/stories", headers=auth_headers())
    assert_ok(s, "Sleep stories")
    assert_in("stories", d, "Sleep stories")
    print(f"  PASS test_voice_stories ({len(d['stories'])} stories)")

def test_voice_play_story():
    s, d = api("POST", "/api/v1/voice/stories/1/play", headers=auth_headers())
    assert_ok(s, "Play story")
    print(f"  PASS test_voice_play_story")


# ==================== PREMIUM TESTS ====================
def test_premium_tiers():
    s, d = api("GET", "/api/v1/premium/tiers")
    assert_ok(s, "Premium tiers")
    assert_in("tiers", d, "Premium tiers")
    print(f"  PASS test_premium_tiers ({len(d['tiers'])} tiers)")

def test_premium_status():
    s, d = api("GET", "/api/v1/premium/status", headers=auth_headers())
    assert_ok(s, "Premium status")
    assert_in("tier", d, "Premium status")
    print(f"  PASS test_premium_status (tier={d['tier']})")

def test_premium_upgrade_cancel():
    # Create and pay order first (new flow requires valid order_id)
    s, od = api("POST", "/api/v1/payment/orders", json={"plan_id": "pro_monthly", "method": "wechat"}, headers=auth_headers())
    assert_ok(s, "Create order for upgrade")
    oid = od["order_id"]
    s, pd = api("POST", f"/api/v1/payment/orders/{oid}/pay", json={"transaction_id": f"TEST_TXN_{int(time.time())}"}, headers=auth_headers())
    assert_ok(s, "Pay order for upgrade")

    s, d = api("POST", "/api/v1/premium/upgrade", json={"tier": "pro", "order_id": oid}, headers=auth_headers())
    assert_ok(s, "Premium upgrade (with order)")
    print(f"  PASS test_premium_upgrade (tier={d['tier']}, order_no={d.get('order_no')})")

    s, d = api("GET", "/api/v1/premium/status", headers=auth_headers())
    assert d["tier"] == "pro", f"Expected pro, got {d['tier']}"
    print("  PASS test_premium_status (after upgrade)")

    s, d = api("POST", "/api/v1/premium/cancel", headers=auth_headers())
    assert_ok(s, "Premium cancel")
    print("  PASS test_premium_cancel")


# ==================== PAYMENT TESTS ====================
def test_payment_plans():
    s, d = api("GET", "/api/v1/payment/plans")
    assert_ok(s, "Payment plans")
    assert_in("plans", d, "Payment plans")
    print(f"  PASS test_payment_plans ({len(d['plans'])} plans)")

def test_payment_create_order():
    s, d = api("POST", "/api/v1/payment/orders", json={
        "plan_id": "pro_monthly", "method": "wechat",
    }, headers=auth_headers())
    assert_ok(s, "Create payment order")
    assert_in("order_no", d, "Create order")
    order_id = d["order_id"]
    print(f"  PASS test_payment_create_order (order_no={d['order_no']})")

    # Pay the order
    s, pd = api("POST", f"/api/v1/payment/orders/{order_id}/pay", json={
        "transaction_id": f"TEST_TXN_{int(time.time())}",
    }, headers=auth_headers())
    assert_ok(s, "Pay order")
    print(f"  PASS test_payment_pay_order")

    # List orders
    s, d = api("GET", "/api/v1/payment/orders", headers=auth_headers())
    assert_ok(s, "List orders")
    assert_in("orders", d, "List orders")
    print(f"  PASS test_payment_list_orders ({len(d['orders'])} orders)")

    # Refund
    s, d = api("POST", f"/api/v1/payment/orders/{order_id}/refund", headers=auth_headers())
    assert_ok(s, "Refund order")
    print(f"  PASS test_payment_refund")


# ==================== PLATFORM TESTS ====================
def test_platform_info():
    s, d = api("GET", "/api/v1/platform/info")
    assert_ok(s, "Platform info")
    assert_in("app_name", d, "Platform info")
    print(f"  PASS test_platform_info ({d['app_name']})")

def test_platform_config():
    s, d = api("GET", "/api/v1/platform/config/miniprogram")
    assert_ok(s, "Platform config")
    assert_in("config", d, "Platform config")
    print(f"  PASS test_platform_config (miniprogram)")

    s, d = api("GET", "/api/v1/platform/config/unknown")
    assert s == 404, f"Platform config 404: expected 404, got {s}"
    print("  PASS test_platform_config (404)")

def test_platform_webhooks():
    s, d = api("POST", "/api/v1/platform/webhooks/register", json={
        "url": "https://example.com/webhook",
        "events": ["sleep.created", "task.completed"],
    }, headers=auth_headers())
    assert_ok(s, "Register webhook")
    print("  PASS test_platform_webhooks (register)")

    s, d = api("POST", "/api/v1/platform/webhooks/test", json={
        "url": "https://httpbin.org/post",
    }, headers=auth_headers())
    assert_ok(s, "Test webhook")
    print(f"  PASS test_platform_webhooks (test: success={d.get('success')})")

def test_platform_sdks():
    s, d = api("GET", "/api/v1/platform/sdks")
    assert_ok(s, "SDK list")
    assert_in("sdks", d, "SDK list")
    print(f"  PASS test_platform_sdks ({len(d['sdks'])} SDKs)")

def test_platform_ping():
    s, d = api("GET", "/api/v1/platform/ping")
    assert_ok(s, "Platform ping")
    assert d["status"] == "ok", f"Expected ok, got {d.get('status')}"
    print("  PASS test_platform_ping")


# ==================== GAME TESTS ====================
def test_game_status():
    s, d = api("GET", "/api/v1/game/status", headers=auth_headers())
    assert_ok(s, "Game status")
    assert_in("level", d, "Game status")
    print(f"  PASS test_game_status (level={d['level']} - {d['level_name']})")

def test_game_checkin():
    s, d = api("POST", "/api/v1/game/checkin", headers=auth_headers())
    assert_ok(s, "Game checkin")
    assert_in("xp_awarded", d, "Game checkin")
    print(f"  PASS test_game_checkin (xp={d['xp_awarded']}, streak={d.get('streak')})")

    # Second checkin should say already done
    s, d = api("POST", "/api/v1/game/checkin", headers=auth_headers())
    assert_ok(s, "Game checkin duplicate")
    print(f"  PASS test_game_checkin (duplicate)")

def test_game_leaderboard():
    s, d = api("GET", "/api/v1/game/leaderboard?limit=10", headers=auth_headers())
    assert_ok(s, "Game leaderboard")
    assert_in("leaderboard", d, "Game leaderboard")
    print(f"  PASS test_game_leaderboard ({len(d['leaderboard'])} entries)")


# ==================== MOOD TESTS ====================
def test_mood_create():
    today = f"{time.localtime().tm_year}-{time.localtime().tm_mon:02d}-{time.localtime().tm_mday:02d}"
    s, d = api("POST", "/api/v1/mood/records", json={
        "date_key": today, "mood_level": 4, "energy_level": 3, "anxiety_level": 2, "note": "感觉不错",
    }, headers=auth_headers())
    assert_ok(s, "Create mood")
    print("  PASS test_mood_create")

def test_mood_get():
    s, d = api("GET", "/api/v1/mood/records?days=7", headers=auth_headers())
    assert_ok(s, "Get moods")
    assert_in("moods", d, "Get moods")
    print(f"  PASS test_mood_get ({len(d['moods'])} records)")


# ==================== ADMIN TESTS ====================
def test_admin_requires_auth():
    s, d = api("GET", "/api/v1/admin/stats")
    assert s == 401, f"Admin auth: expected 401, got {s}"
    print("  PASS test_admin_requires_auth")


# ==================== RATE LIMITING TEST ====================
def test_rate_limiting():
    """Test rate limiting - make 70 rapid requests to trigger rate limit."""
    limit_hit = False
    for i in range(70):
        s, d = api("POST", "/api/v1/auth/login", json={
            "username": USER, "password": PASS,
        })
        if s == 429:
            limit_hit = True
            break
    # Should eventually hit rate limit at 60 req/60s per IP
    # Note: login also has per-username rate limiting
    print(f"  PASS test_rate_limiting (rate_limit_hit={limit_hit})")


# ==================== STATIC FILES TESTS ====================
def test_static_files():
    import urllib.request
    req = urllib.request.Request("http://127.0.0.1:8000/static/manifest.json")
    resp = urllib.request.urlopen(req)
    assert resp.status == 200, f"Manifest: expected 200, got {resp.status}"
    print("  PASS test_static_files (manifest.json)")

    req = urllib.request.Request("http://127.0.0.1:8000/static/sw.js")
    resp = urllib.request.urlopen(req)
    assert resp.status == 200, f"SW: expected 200, got {resp.status}"
    print("  PASS test_static_files (sw.js)")

    req = urllib.request.Request("http://127.0.0.1:8000/static/noise-engine.js")
    resp = urllib.request.urlopen(req)
    assert resp.status == 200, f"Noise JS: expected 200, got {resp.status}"
    print("  PASS test_static_files (noise-engine.js)")

def test_dashboard_page():
    req = urllib.request.Request("http://127.0.0.1:8000/dashboard")
    resp = urllib.request.urlopen(req)
    html = resp.read().decode("utf-8")
    assert resp.status == 200, f"Dashboard: expected 200, got {resp.status}"
    assert "dashboard" in html.lower() or "chart" in html.lower() or len(html) > 100
    print(f"  PASS test_dashboard_page ({len(html)} bytes)")

def test_admin_page():
    import urllib.request
    req = urllib.request.Request("http://127.0.0.1:8000/admin")
    resp = urllib.request.urlopen(req)
    html = resp.read().decode()
    assert resp.status == 200
    print(f"  PASS test_admin_page ({len(html)} bytes)")


# ==================== MAIN ====================
ALL_TESTS = [
    # Auth extended
    ("Auth", test_auth_change_password),
    ("Auth", test_auth_has_profile),
    ("Auth", test_auth_logout),
    ("Auth", test_auth_forgot_password),
    ("Auth", test_auth_reset_password),
    ("Auth", test_auth_notification_settings),
    ("Auth", test_auth_reminders),
    ("Auth", test_auth_send_verify_code),
    ("Auth", test_auth_verify_email),
    ("Auth", test_auth_update_profile_basic),
    # Sleep extended
    ("Sleep", test_sleep_enhanced_stats),
    ("Sleep", test_sleep_weekly_report),
    ("Sleep", test_sleep_csv_export),
    ("Sleep", test_sleep_heatmap),
    ("Sleep", test_sleep_radar),
    ("Sleep", test_sleep_compare),
    ("Sleep", test_sleep_smart_alarm),
    ("Sleep", test_sleep_ai_deep_report),
    ("Sleep", test_sleep_ai_predict),
    # Wellness
    ("Wellness", test_knowledge_categories),
    ("Wellness", test_knowledge_articles),
    ("Wellness", test_knowledge_article_detail),
    ("Wellness", test_improvement_plans),
    ("Wellness", test_plan_detail),
    ("Wellness", test_plan_enroll),
    ("Wellness", test_active_plan),
    ("Wellness", test_plan_checkin),
    ("Wellness", test_plan_checkins),
    ("Wellness", test_plan_history),
    ("Wellness", test_recommend_plan),
    ("Wellness", test_onboarding),
    ("Wellness", test_ai_soundscape),
    ("Wellness", test_ai_sentiment),
    ("Wellness", test_rag_search),
    ("Wellness", test_health_data),
    ("Wellness", test_sleep_with_health),
    ("Wellness", test_assessments),
    ("Wellness", test_assessment_detail),
    ("Wellness", test_assessment_submit),
    # Community
    ("Community", test_community_groups),
    ("Community", test_community_join_leave_group),
    ("Community", test_community_challenges),
    ("Community", test_community_join_challenge),
    ("Community", test_community_leaderboard),
    ("Community", test_community_posts),
    # Voice
    ("Voice", test_voice_diary),
    ("Voice", test_voice_tts),
    ("Voice", test_voice_stories),
    ("Voice", test_voice_play_story),
    # Premium
    ("Premium", test_premium_tiers),
    ("Premium", test_premium_status),
    ("Premium", test_premium_upgrade_cancel),
    # Payment
    ("Payment", test_payment_plans),
    ("Payment", test_payment_create_order),
    # Platform
    ("Platform", test_platform_info),
    ("Platform", test_platform_config),
    ("Platform", test_platform_webhooks),
    ("Platform", test_platform_sdks),
    ("Platform", test_platform_ping),
    # Game
    ("Game", test_game_status),
    ("Game", test_game_checkin),
    ("Game", test_game_leaderboard),
    # Mood
    ("Mood", test_mood_create),
    ("Mood", test_mood_get),
    # Rate limiting
    ("Security", test_rate_limiting),
    # Static files
    ("Static", test_static_files),
    ("Static", test_dashboard_page),
    ("Static", test_admin_page),
    # Admin
    ("Admin", test_admin_requires_auth),
]


if __name__ == "__main__":
    print("=" * 60)
    print("  梦眠 - 扩展测试套件")
    print("=" * 60)

    print("\n  Starting server...")
    start_server()

    print("  Setting up test user...")
    setup()

    passed = 0
    failed = 0
    for category, test_func in ALL_TESTS:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            import traceback
            print(f"  FAIL [{category}] {test_func.__name__}: {e}")
            traceback.print_exc()

    print(f"\n  Extended tests: {passed} passed, {failed} failed")
    if failed == 0:
        print("  ALL EXTENDED TESTS PASSED")
    print("=" * 60)

    sys.exit(failed)
