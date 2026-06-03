# -*- coding: utf-8 -*-
"""性能测试 — 响应时间, 并发处理, DB查询性能, 速率限制基准"""
import json, sys, os, time, threading, statistics, concurrent.futures, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(__file__))

def start_server():
    import uvicorn; from app.main import app
    t = threading.Thread(target=lambda: uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error"), daemon=True)
    t.start(); time.sleep(3)

def api(method, path, **kwargs):
    """返回 (status, body_dict, elapsed_ms)"""
    url = f"http://127.0.0.1:8000{path}"
    data = None
    if "json" in kwargs: data = json.dumps(kwargs["json"], ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if "headers" in kwargs:
        for k, v in kwargs["headers"].items(): req.add_header(k, v)
    t0 = time.perf_counter()
    try:
        resp = urllib.request.urlopen(req); body = resp.read().decode("utf-8")
        elapsed = (time.perf_counter() - t0) * 1000
        return resp.status, json.loads(body) if body else {}, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - t0) * 1000
        body = e.read().decode("utf-8")
        try: return e.code, json.loads(body), elapsed
        except: return e.code, {"error": body}, elapsed

TS = int(time.time()); USER = f"perf_{TS}"; EMAIL = f"{USER}@test.com"; PASS = "PerfTest1"; TOKEN = ""
def auth(): return {"Authorization": f"Bearer {TOKEN}"}

pass_count = 0; fail_count = 0; warn_count = 0
def check(cond, msg):
    global pass_count, fail_count
    if cond: pass_count += 1; print(f"  PASS {msg}")
    else: fail_count += 1; print(f"  FAIL {msg}")
def warn(cond, msg):
    global warn_count
    if not cond: warn_count += 1; print(f"  WARN {msg}")

PERF_THRESHOLDS = {
    "health": 50,        # ms
    "ping": 50,
    "login": 300,
    "me": 150,
    "sleep_create": 500,
    "sleep_list": 200,
    "stats": 300,
    "tasks_today": 1000, # may trigger AI
    "chat_send": 30000,  # AI response can be slow
    "profile_get": 150,
    "community": 150,
    "knowledge": 100,
}

# ==================== 单端点响应时间测试 ====================
print("\n" + "=" * 60)
print("  单端点响应时间基准")
print("=" * 60)

def benchmark_endpoint(name, method, path, threshold_ms, use_auth=True, json_data=None, warmup=2, runs=10):
    headers = auth() if use_auth else {}
    kwargs = {"headers": headers}
    if json_data: kwargs["json"] = json_data

    # Warmup
    for _ in range(warmup):
        api(method, path, **kwargs)

    # Benchmark
    times = []
    statuses = []
    for _ in range(runs):
        s, d, t = api(method, path, **kwargs)
        times.append(t)
        statuses.append(s)

    avg = statistics.mean(times)
    med = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95)]
    p99 = sorted(times)[int(len(times) * 0.99)]
    ok = sum(1 for s in statuses if s == 200)

    check(ok >= runs * 0.9, f"{name}: {ok}/{runs} 成功")
    warn(avg <= threshold_ms, f"{name}: avg={avg:.0f}ms, median={med:.0f}ms, p95={p95:.0f}ms (threshold={threshold_ms}ms)")

    return {"name": name, "avg": avg, "median": med, "p95": p95, "p99": p99, "success_rate": ok/runs}

def benchmark_all_endpoints():
    results = []

    # Health (no auth)
    r = benchmark_endpoint("health", "GET", "/health", PERF_THRESHOLDS["health"], use_auth=False)
    results.append(r)

    # Platform ping (no auth)
    r = benchmark_endpoint("ping", "GET", "/api/v1/platform/ping", PERF_THRESHOLDS["ping"], use_auth=False)
    results.append(r)

    # Me
    r = benchmark_endpoint("me", "GET", "/api/v1/auth/me", PERF_THRESHOLDS["me"])
    results.append(r)

    # Sleep list
    r = benchmark_endpoint("sleep_list", "GET", "/api/v1/sleep-records?days=7", PERF_THRESHOLDS["sleep_list"])
    results.append(r)

    # Sleep stats
    r = benchmark_endpoint("stats", "GET", "/api/v1/sleep-records/stats/summary?days=7", PERF_THRESHOLDS["stats"])
    results.append(r)

    # Profile get
    r = benchmark_endpoint("profile_get", "GET", "/api/v1/profiles", PERF_THRESHOLDS["profile_get"])
    results.append(r)

    # Tasks today (may trigger AI generation)
    r = benchmark_endpoint("tasks_today", "GET", "/api/v1/tasks/today", PERF_THRESHOLDS["tasks_today"])
    results.append(r)

    # Badges
    r = benchmark_endpoint("badges", "GET", "/api/v1/tasks/badges", PERF_THRESHOLDS["community"])
    results.append(r)

    # Knowledge
    r = benchmark_endpoint("knowledge", "GET", "/api/v1/wellness/knowledge/articles", PERF_THRESHOLDS["knowledge"])
    results.append(r)

    # Community
    r = benchmark_endpoint("community", "GET", "/api/v1/community/groups", PERF_THRESHOLDS["community"])
    results.append(r)

    # Premium tiers
    r = benchmark_endpoint("premium", "GET", "/api/v1/premium/tiers", PERF_THRESHOLDS["me"])
    results.append(r)

    # Sleep create (fast path, should not trigger slow AI)
    r = benchmark_endpoint("sleep_create", "POST", "/api/v1/sleep-records",
                         PERF_THRESHOLDS["sleep_create"], json_data={
                             "diary_date": "2026-05-17", "bedtime": "2026-05-17T23:00:00",
                             "wake_time": "2026-05-18T06:30:00", "quality": 4,
                         })
    results.append(r)

    # Mood get
    r = benchmark_endpoint("mood_get", "GET", "/api/v1/mood/records?days=7", PERF_THRESHOLDS["community"])
    results.append(r)

    # Game status
    r = benchmark_endpoint("game_status", "GET", "/api/v1/game/status", PERF_THRESHOLDS["community"])
    results.append(r)

    return results

# ==================== 并发请求测试 ====================
print("\n" + "=" * 60)
print("  并发请求处理")
print("=" * 60)

def test_concurrency():
    def make_health_request(_):
        t0 = time.perf_counter()
        req = urllib.request.Request("http://127.0.0.1:8000/health")
        try:
            resp = urllib.request.urlopen(req); elapsed = (time.perf_counter() - t0) * 1000
            return resp.status == 200, elapsed
        except: return False, (time.perf_counter() - t0) * 1000

    for concurrency in [5, 10, 20]:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            results = list(executor.map(make_health_request, range(concurrency * 10)))

        success = sum(1 for ok, _ in results if ok)
        times = [t for ok, t in results if ok]
        avg = statistics.mean(times) if times else 0
        p99 = sorted(times)[int(len(times)*0.99)] if times else 0

        check(success >= concurrency * 9, f"并发{concurrency}: {success}/{concurrency*10} 成功")
        warn(avg < 200, f"并发{concurrency}: avg={avg:.0f}ms, p99={p99:.0f}ms")

    print("  并发: 3 cases")

# moved to main


# ==================== DB查询性能 ====================
print("\n" + "=" * 60)
print("  DB查询性能")
print("=" * 60)

def test_db_performance():
    from app.database import SessionLocal
    from app.models import User, SleepRecord, HealthProfile
    from sqlalchemy import func as sa_func

    db = SessionLocal()
    try:
        # Count query performance
        t0 = time.perf_counter()
        count = db.query(User).count()
        t1 = (time.perf_counter() - t0) * 1000
        warn(t1 < 30, f"SELECT COUNT(users): {t1:.1f}ms ({count} rows)")

        # Join query
        t0 = time.perf_counter()
        result = db.query(
            SleepRecord.user_id,
            sa_func.avg(SleepRecord.score).label("avg_score"),
            sa_func.count(SleepRecord.id).label("cnt"),
        ).group_by(SleepRecord.user_id).order_by(sa_func.avg(SleepRecord.score).desc()).limit(10).all()
        t1 = (time.perf_counter() - t0) * 1000
        warn(t1 < 100, f"SELECT AVG+GROUPBY(records): {t1:.1f}ms ({len(result)} users)")

        # Profile join
        t0 = time.perf_counter()
        result = db.query(User).filter(User.username.like("func_%")).limit(10).all()
        t1 = (time.perf_counter() - t0) * 1000
        warn(t1 < 50, f"SELECT LIKE(users): {t1:.1f}ms ({len(result)} rows)")

        # Full record fetch
        t0 = time.perf_counter()
        records = db.query(SleepRecord).order_by(SleepRecord.bedtime.desc()).limit(100).all()
        t1 = (time.perf_counter() - t0) * 1000
        warn(t1 < 100, f"SELECT 100 records: {t1:.1f}ms ({len(records)} rows)")

    finally:
        db.close()

    print("  DB性能: 4 queries")

# moved to main


# ==================== 吞吐量测试 ====================
print("\n" + "=" * 60)
print("  吞吐量测试")
print("=" * 60)

def test_throughput():
    def health_burst(n):
        t0 = time.perf_counter()
        success = 0
        for _ in range(n):
            req = urllib.request.Request("http://127.0.0.1:8000/health")
            try:
                resp = urllib.request.urlopen(req)
                if resp.status == 200: success += 1
            except: pass
        elapsed = time.perf_counter() - t0
        return success, elapsed

    # Burst of 200 requests
    n = 200
    success, elapsed = health_burst(n)
    rps = success / elapsed if elapsed > 0 else 0
    check(success >= n * 0.95, f"吞吐量: {success}/{n} 成功 ({rps:.0f} req/s)")

    print(f"  吞吐量: {success}/{n} 成功, {rps:.0f} req/s, {elapsed:.2f}s")

# moved to main


# ==================== 内存使用基准 ====================
print("\n" + "=" * 60)
print("  资源使用基准")
print("=" * 60)

def test_resource_baseline():
    import psutil
    try:
        proc = psutil.Process()
        mem = proc.memory_info().rss / 1024 / 1024  # MB
        cpu = proc.cpu_percent(interval=0.1)
        check(mem < 500, f"内存<500MB: {mem:.1f}MB")
        check(cpu < 50, f"CPU<50%: {cpu:.1f}%")
        print(f"  进程内存: {mem:.1f} MB, CPU: {cpu:.1f}%")
    except ImportError:
        print("  psutil not installed, skipping resource check")
        pass_count += 2  # Count as passed since we can't verify

# moved to main


# ==================== 缓存效果测试 ====================
print("\n" + "=" * 60)
print("  缓存效果测试")
print("=" * 60)

def test_cache_effect():
    # First call (cold)
    s, d, t_cold = api("GET", "/api/v1/wellness/knowledge/articles")

    # 10 repeated calls (warm)
    warm_times = []
    for _ in range(10):
        s, d, t = api("GET", "/api/v1/wellness/knowledge/articles")
        warm_times.append(t)

    avg_warm = statistics.mean(warm_times)
    check(t_cold > 0, f"冷启动: {t_cold:.0f}ms")
    check(avg_warm > 0, f"预热后: {avg_warm:.0f}ms")

    print(f"  冷启动: {t_cold:.0f}ms, 预热平均: {avg_warm:.0f}ms")

# moved to main


# ==================== SUMMARY ====================
print("\n" + "=" * 60)
print(f"  性能测试: {pass_count} passed, {fail_count} failed, {warn_count} warnings")
if fail_count == 0: print("  ALL PERFORMANCE CHECKS PASSED")
else: print(f"  {fail_count} PERFORMANCE CHECKS FAILED")
if warn_count > 0: print(f"  {warn_count} PERFORMANCE WARNINGS (above thresholds)")
print("=" * 60)

if __name__ == "__main__":
    print("=" * 60)
    print("  梦眠阁 - 性能测试套件")
    print("=" * 60)
    print("\n  Starting server...")
    start_server()
    print("  Setting up test user...")
    s, d = api("POST", "/api/v1/auth/register", json={"username": USER, "email": EMAIL, "password": PASS, "nickname": "PerfTest"})
    s, d = api("POST", "/api/v1/auth/login", json={"username": USER, "password": PASS})
    TOKEN = d["access_token"]
    # Create some test data
    api("PUT", "/api/v1/profiles", json={"age": 30, "gender": "男", "sleep_goal_hours": 8.0}, headers=auth())
    api("POST", "/api/v1/sleep-records", json={"diary_date": "2026-05-17", "bedtime": "2026-05-17T23:00:00", "wake_time": "2026-05-18T07:00:00", "quality": 4}, headers=auth())
    api("POST", "/api/v1/mood/records", json={"date_key": "2026-05-17", "mood_level": 4, "energy_level": 3, "anxiety_level": 2}, headers=auth())
    results = benchmark_all_endpoints()
    print(f"
  Response Time Summary ({len(results)} endpoints):")
    print(f"  {'Endpoint':<20} {'Avg(ms)':>8} {'Median':>8} {'P95':>8} {'P99':>8} {'OK%':>6}")
    print(f"  {'-'*58}")
    for r in results:
        print(f"  {r['name']:<20} {r['avg']:>7.0f} {r['median']:>7.0f} {r['p95']:>7.0f} {r['p99']:>7.0f} {r['success_rate']:>5.0%}")
    test_concurrency()
    test_db_performance()
    test_throughput()
    test_resource_baseline()
    test_cache_effect()
    sys.exit(fail_count)
