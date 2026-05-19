import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.database import engine, Base
from app.models import *  # noqa
from app.routers import auth_router, sleep_router, profile_router, chat_router, task_router, wellness_router, admin_router, community_router, voice_router, premium_router, platform_router, payment_router, game_router, mood_router, settings_router, store_router, course_router, program_router, referral_router, doctor_router, environment_router, data_router, integration_router, competition_router, relax_router, live_router, growth_router, web3_router, dataset_router, llm_router, iot_router, watch_router
from app.config import settings as _settings
from app.security import rate_limit, get_rate_limit_key, sanitize_input

app = FastAPI(
    title="梦眠 - AI智能睡眠管理",
    version="1.0.0",
    docs_url=None if _settings.PRODUCTION else "/docs",
    redoc_url=None if _settings.PRODUCTION else "/redoc",
)

Base.metadata.create_all(bind=engine)

# CORS — tightened for production
if _settings.PRODUCTION:
    _origins = os.getenv("ALLOWED_ORIGINS", "https://your-domain.com").split(",")
else:
    _origins = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000", "http://localhost:5173", "null"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    # Skip static files and health
    if not path.startswith("/api/"):
        return await call_next(request)

    key = get_rate_limit_key(request)
    if not rate_limit(key, max_requests=60, window=60):
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})
    return await call_next(request)


# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(auth_router)
app.include_router(sleep_router)
app.include_router(profile_router)
app.include_router(chat_router)
app.include_router(task_router)
app.include_router(wellness_router)
app.include_router(admin_router)
app.include_router(community_router)
app.include_router(voice_router)
app.include_router(premium_router)
app.include_router(platform_router)
app.include_router(payment_router)
app.include_router(game_router)
app.include_router(mood_router)
app.include_router(settings_router)
app.include_router(store_router)
app.include_router(course_router)
app.include_router(program_router)
app.include_router(referral_router)
app.include_router(doctor_router)
app.include_router(environment_router)
app.include_router(data_router)
app.include_router(integration_router)
app.include_router(competition_router)
app.include_router(relax_router)
app.include_router(live_router)
app.include_router(growth_router)
app.include_router(web3_router)
app.include_router(dataset_router)
app.include_router(llm_router)
app.include_router(iot_router)
app.include_router(watch_router)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/admin")
async def admin_page():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))


@app.get("/dashboard")
async def dashboard_page():
    return FileResponse(os.path.join(STATIC_DIR, "dashboard.html"))


@app.get("/health")
async def health():
    from sqlalchemy import text
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}
    finally:
        db.close()
