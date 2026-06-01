# -*- coding: utf-8 -*-
"""安全测试 — XSS/CSRF/SQL注入, 权限边界, 输入模糊测试, 安全头"""
import json, sys, os, time, threading, urllib.request, urllib.error, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))

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

TS = int(time.time()); USER = f"secf_{TS}"; EMAIL = f"{USER}@test.com"; PASS = "SecTest789"; TOKEN = ""
USER2 = f"secf2_{TS}"; TOKEN2 = ""

def auth(): return {"Authorization": f"Bearer {TOKEN}"}
def auth2(): return {"Authorization": f"Bearer {TOKEN2}"}

pass_count = 0; fail_count = 0
def check(cond, msg):
    global pass_count, fail_count
    if cond: pass_count += 1; print(f"  PASS {msg}")
    else: fail_count += 1; print(f"  FAIL {msg}")
def eq(a, b, msg): check(a == b, f"{msg}: expected={b}, got={a}")

def setup():
    global TOKEN, TOKEN2
    api("POST", "/api/v1/auth/register", json={"username": USER, "email": EMAIL, "password": PASS, "nickname": "SecUser"})
    s, d = api("POST", "/api/v1/auth/login", json={"username": USER, "password": PASS}); TOKEN = d["access_token"]
    api("POST", "/api/v1/auth/register", json={"username": USER2, "email": f"{USER2}@test.com", "password": PASS, "nickname": "SecUser2"})
    s, d = api("POST", "/api/v1/auth/login", json={"username": USER2, "password": PASS}); TOKEN2 = d["access_token"]
    # User1 creates profile and record
    api("PUT", "/api/v1/profiles", json={"age": 30, "gender": "男", "sleep_goal_hours": 8.0}, headers=auth())
    api("POST", "/api/v1/sleep-records", json={"diary_date": "2026-05-17", "bedtime": "2026-05-17T23:00:00", "wake_time": "2026-05-18T07:00:00", "quality": 4}, headers=auth())

# ==================== XSS 注入测试 ====================
print("\n" + "=" * 60)
print("  XSS 注入测试")
print("=" * 60)

def test_xss_all_fields():
    payloads = [
        '<script>alert(1)</script>',
        'javascript:alert(1)',
        '<img src=x onerror=alert(1)>',
        '<svg/onload=alert(1)>',
        '" onclick="alert(1)"',
        "' onclick='alert(1)'",
        '<iframe src="javascript:alert(1)">',
    ]

    for i, payload in enumerate(payloads):
        # Test in register username
        u = f"xss_u_{TS}_{i}"
        s, d = api("POST", "/api/v1/auth/register", json={
            "username": u + payload[:10],
            "email": f"xss_u_{TS}_{i}@test.com",
            "password": "Test123",
        })
        # Should either sanitize or reject
        check(s in (200, 400, 422), f"XSS username {i}: status={s}")

    # Chat message with XSS
    for payload in payloads[:3]:
        s, d = api("POST", "/api/v1/chat/send", json={"message": payload}, headers=auth())
        eq(s, 200, f"XSS chat: status={s}")

    # Sleep notes with XSS
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-18", "bedtime": "2026-05-18T23:00:00",
        "wake_time": "2026-05-19T07:00:00", "quality": 3,
        "notes": payloads[0],
    }, headers=auth())
    check(s == 200, f"XSS notes: status={s}")

    # Profile fields with XSS
    s, d = api("PUT", "/api/v1/profiles", json={
        "sleep_issues": payloads[1],
    }, headers=auth())
    check(s == 200, f"XSS profile: status={s}")

    print("  XSS: 13 cases")

# moved to main


# ==================== SQL 注入测试 ====================
print("\n" + "=" * 60)
print("  SQL 注入测试")
print("=" * 60)

def test_sql_injection_all():
    sqli_payloads = [
        "'; DROP TABLE users; --",
        "' OR '1'='1",
        "1; UPDATE users SET is_admin=1 WHERE 1=1; --",
        "admin'--",
        "' UNION SELECT * FROM users; --",
        "1' AND 1=(SELECT COUNT(*) FROM users); --",
        "'; SELECT SLEEP(5); --",
    ]

    # Login with SQL injection
    for i, payload in enumerate(sqli_payloads):
        s, d = api("POST", "/api/v1/auth/login", json={"username": payload, "password": "test"})
        check(s in (401, 400, 422), f"SQLi login {i}: status={s} (not 500)")

    # Register with SQL injection in email
    s, d = api("POST", "/api/v1/auth/register", json={
        "username": f"sqli_{int(time.time())}",
        "email": f"x'; DROP TABLE users; --@test.com",
        "password": "Test123",
    })
    check(s in (400, 422, 200), f"SQLi email: status={s} (not 500)")

    # Sleep records notes with SQL injection
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-19",
        "bedtime": "2026-05-19T23:00:00",
        "wake_time": "2026-05-20T07:00:00",
        "notes": "'; DELETE FROM sleep_records WHERE 1=1; --",
    }, headers=auth())
    check(s == 200, f"SQLi notes: status={s} (成功但不应删除数据)")

    # Chat messages with SQL injection
    s, d = api("POST", "/api/v1/chat/send", json={
        "message": "'; DROP TABLE chat_messages; --",
    }, headers=auth())
    eq(s, 200, "SQLi chat: status=200")

    print("  SQL注入: 11 cases")

# moved to main


# ==================== 权限边界测试 ====================
print("\n" + "=" * 60)
print("  权限边界测试")
print("=" * 60)

def test_authorization_boundaries():
    # Create record as user1
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-17", "bedtime": "2026-05-17T22:00:00",
        "wake_time": "2026-05-18T06:00:00", "quality": 5,
    }, headers=auth())
    rid = d["id"]

    # User2 tries to access user1's record
    s, d = api("GET", f"/api/v1/sleep-records/{rid}", headers=auth2())
    eq(s, 404, "用户2不能读取用户1的记录(404)")

    # User2 tries to delete user1's record
    s, d = api("DELETE", f"/api/v1/sleep-records/{rid}", headers=auth2())
    eq(s, 404, "用户2不能删除用户1的记录(404)")

    # User2 tries to access user1's profile
    s, d = api("GET", "/api/v1/profiles", headers=auth2())
    eq(s, 200, "用户2获取自己的档案(200)")
    check(d.get("age") != 30 or d.get("exists") == False, "用户2看不到用户1的档案数据")

    # User2 tries to access user1's chat sessions
    s, d = api("GET", "/api/v1/chat/sessions", headers=auth2())
    eq(s, 200, "用户2获取自己的会话(200)")
    # Should be empty since user2 hasn't chatted
    check(len(d) == 0, f"用户2的会话为空: {len(d)}")

    # User2 tries to update user1's profile (should update own profile instead)
    s, d = api("PUT", "/api/v1/profiles", json={"age": 99}, headers=auth2())
    eq(s, 200, "用户2更新自己的档案")
    s, d = api("GET", "/api/v1/profiles", headers=auth2())
    eq(d.get("age"), 99, "用户2只更新了自己的年龄")

    # User2 tries to get user1's task points
    s, d = api("GET", "/api/v1/tasks/points/summary", headers=auth2())
    eq(s, 200, "用户2只获取自己的积分")

    # User2 with user1's chat session
    s, d = api("POST", "/api/v1/chat/send", json={"message": "test"}, headers=auth())
    csid = d["session_id"]
    s, d = api("GET", f"/api/v1/chat/sessions/{csid}", headers=auth2())
    eq(s, 404, "用户2不能查看用户1的会话(404)")

    # No token access
    s, d = api("GET", "/api/v1/sleep-records")
    eq(s, 401, "无Token→401")

    s, d = api("GET", "/api/v1/auth/me")
    eq(s, 401, "无Token获取个人信息→401")

    print("  权限: 12 cases")

# moved to main


# ==================== Token 安全测试 ====================
print("\n" + "=" * 60)
print("  Token 安全测试")
print("=" * 60)

def test_token_security():
    # No token
    s, d = api("GET", "/api/v1/auth/me")
    eq(s, 401, "无token→401")

    # Empty token
    s, d = api("GET", "/api/v1/auth/me", headers={"Authorization": ""})
    eq(s, 401, "空token→401")

    # Bad format
    s, d = api("GET", "/api/v1/auth/me", headers={"Authorization": "Token abc"})
    eq(s, 401, "错误前缀→401")

    # Malformed JWT
    s, d = api("GET", "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    eq(s, 401, "格式错误→401")

    # Wrong signature
    s, d = api("GET", "/api/v1/auth/me", headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.fakesig"})
    eq(s, 401, "错误签名→401")

    # Refresh token as access token
    s, d = api("POST", "/api/v1/auth/login", json={"username": USER, "password": PASS})
    rt = d["refresh_token"]
    s, d = api("GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {rt}"})
    eq(s, 401, "refresh_token当access_token→401")

    # Token after logout
    s, d = api("POST", "/api/v1/auth/login", json={"username": USER2, "password": PASS})
    temp_tok = d["access_token"]
    api("POST", "/api/v1/auth/logout", headers={"Authorization": f"Bearer {temp_tok}"})
    s, d = api("GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {temp_tok}"})
    eq(s, 401, "logout后token失效→401")

    # Reused logout token
    s, d = api("GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {temp_tok}"})
    eq(s, 401, "再次使用已注销token→401")

    print("  Token: 8 cases")

# moved to main


# ==================== 输入模糊测试 ====================
print("\n" + "=" * 60)
print("  输入模糊测试")
print("=" * 60)

def test_fuzzing():
    # Very long username
    s, d = api("POST", "/api/v1/auth/register", json={
        "username": "a" * 500, "email": f"long_{TS}@test.com", "password": "Test123",
    })
    check(s in (400, 422), f"超长username: {s}")

    # Very long chat message
    s, d = api("POST", "/api/v1/chat/send", json={"message": "测试" * 2000}, headers=auth())
    check(s in (200, 400, 422), f"超长chat: {s}")

    # Negative numbers
    s, d = api("POST", "/api/v1/sleep-records", json={
        "diary_date": "2026-05-20", "bedtime": "2026-05-20T23:00:00",
        "wake_time": "2026-05-21T07:00:00", "quality": -5,
    }, headers=auth())
    check(s in (200, 422), f"负quality: {s}")

    # Null-like values
    s, d = api("POST", "/api/v1/auth/register", json={
        "username": "null", "email": "null@test.com", "password": "nullnull1",
    })
    check(s in (200, 400, 422), f"null字符串: {s}")

    # Unicode special characters
    s, d = api("POST", "/api/v1/auth/register", json={
        "username": f"unicode_{int(time.time())}",
        "email": f"unicode_{int(time.time())}@test.com",
        "password": "Test123",
        "nickname": "UnicodeTest\\u0000\\u0001\\uffff",
    })
    check(s in (200, 400, 422), f"Unicode特殊字符: {s}")

    # Empty body
    req = urllib.request.Request("http://127.0.0.1:8000/api/v1/auth/login", data=b"", method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req)
        check(False, "空body应失败")
    except urllib.error.HTTPError as e:
        check(e.code in (400, 422), f"空body: {e.code}")

    print("  模糊测试: 6 cases")

# moved to main


# ==================== CORS / 安全头测试 ====================
print("\n" + "=" * 60)
print("  CORS / 安全头测试")
print("=" * 60)

def test_security_headers_full():
    req = urllib.request.Request("http://127.0.0.1:8000/api/v1/auth/login", data=json.dumps({"username": "test", "password": "test"}).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    resp = urllib.request.urlopen(req)
    h = resp.headers

    check(h.get("X-Content-Type-Options") == "nosniff", "X-Content-Type-Options")
    check(h.get("X-Frame-Options") == "DENY", "X-Frame-Options=DENY")
    check(h.get("Referrer-Policy") == "strict-origin-when-cross-origin", "Referrer-Policy")
    check("max-age=" in h.get("Strict-Transport-Security", ""), "HSTS已设置")

    # Check CORS headers on preflight-like request
    req = urllib.request.Request("http://127.0.0.1:8000/health")
    resp = urllib.request.urlopen(req)
    # CORS headers might not appear on simple GET, but ensure no leaking
    check("Access-Control-Allow-Origin" not in resp.headers or
          resp.headers["Access-Control-Allow-Origin"] in ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000", "http://localhost:5173", "null"],
          "CORS origin受限")

    print("  安全头: 5 cases")

# moved to main


# ==================== 路径遍历测试 ====================
print("\n" + "=" * 60)
print("  路径遍历测试")
print("=" * 60)

def test_path_traversal():
    paths = [
        "/../../etc/passwd",
        "/api/v1/sleep-records/../../../etc/passwd",
        "/api/v1/../../../etc/passwd",
        "/api/v1/wellness/knowledge/articles/../../",
        "/api/v1/../v1/auth/me",
    ]
    for p in paths:
        s, d = api("GET", p)
        check(s in (401, 404, 422), f"路径遍历 {p[:50]}: {s}")

    print("  路径: 5 cases")

# moved to main


# ==================== 速率限制验证 ====================
print("\n" + "=" * 60)
print("  速率限制验证")
print("=" * 60)

def test_rate_limit_boundaries():
    # API rate limit at 60 req/min
    limit_triggered = False
    for i in range(80):
        s, d = api("GET", "/api/v1/platform/ping")
        if s == 429:
            limit_triggered = True
            check(i >= 55, f"速率限制在合理范围内触发: 第{i+1}次")
            break
    check(limit_triggered, "速率限制已触发")

    # Health endpoint should NOT be rate limited
    req = urllib.request.Request("http://127.0.0.1:8000/health")
    for _ in range(70):
        resp = urllib.request.urlopen(req)
        check(resp.status == 200, "health不受速率限制")

    print("  速率限制: 3 cases")

# moved to main


# ==================== PASSWORD STRENGTH ====================
print("\n" + "=" * 60)
print("  密码强度验证")
print("=" * 60)

def test_password_strength():
    passes = [
        ("p1_" + str(TS), "Ab1", 400, "密码太短"),
        ("p2_" + str(TS), "abcdefg", 400, "无数字"),
        ("p3_" + str(TS), "12345678", 400, "无字母"),
        ("p4_" + str(TS), "A" * 200 + "1", 400, "密码太长"),
        ("p5_" + str(TS), "", 400, "空密码"),
        ("p6_" + str(TS), "a", 400, "用户名太短"),
    ]
    for uname, pw, expected, desc in passes:
        import time as _t
        s, d = api("POST", "/api/v1/auth/register", json={
            "username": uname + str(int(_t.time() * 1000) % 100000),
            "email": f"{uname}_{int(_t.time()*1000)}@test.com",
            "password": pw, "nickname": "PW",
        })
        check(s == expected, f"{desc}: expected {expected}, got {s}")
    print("  密码强度: 6 cases")


# ==================== LOGIN BRUTE FORCE ====================
print("\n" + "=" * 60)
print("  登录暴力破解防护")
print("=" * 60)

def test_login_brute_force():
    # Make 6 failed attempts
    for i in range(6):
        api("POST", "/api/v1/auth/login", json={
            "username": USER, "password": f"wrong_pass_{i}",
        })
    # Now try correct password — should be rate limited
    s, d = api("POST", "/api/v1/auth/login", json={
        "username": USER, "password": PASS,
    })
    check(s in (429,), f"6次失败后应被限流: got {s}")
    print(f"  暴力破解: status={s}")


# ==================== SUMMARY ==================
print("\n" + "=" * 60)
print(f"  安全测试: {pass_count} passed, {fail_count} failed")
if fail_count == 0: print("  ALL SECURITY TESTS PASSED")
else: print(f"  {fail_count} SECURITY TESTS FAILED")
print("=" * 60)

if __name__ == "__main__":
    print("=" * 60)
    print("  梦眠阁 - 安全测试套件")
    print("=" * 60)
    print("\n  Starting server...")
    start_server()
    print("  Setting up test users...")
    setup()
    test_xss_all_fields()
    test_sql_injection_all()
    test_authorization_boundaries()
    test_token_security()
    test_fuzzing()
    test_security_headers_full()
    test_path_traversal()
    test_rate_limit_boundaries()
    test_password_strength()
    test_login_brute_force()
    sys.exit(fail_count)
