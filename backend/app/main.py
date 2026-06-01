import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import engine, Base
from app.models import *  # noqa
from app.routers import auth_router, sleep_router, chat_router, task_router, wellness_router, admin_router, community_router, voice_router, premium_router, payment_router, game_router, mood_router, store_router, course_router, program_router, referral_router, doctor_router, environment_router, data_router, integration_router, competition_router, relax_router, _public_config_router
# 空壳/无人使用，暂注释:
from app.routers import profile_router
# from app.routers import settings_router  # 只有 theme/language 两个字段，价值不大
# from app.routers import platform_router
# from app.routers import growth_router
# from app.routers import web3_router
# from app.routers import dataset_router
# from app.routers import llm_router
# from app.routers import live_router
# from app.routers import iot_router
# from app.routers import watch_router
from app.config import settings as _settings
from app.security import rate_limit, get_rate_limit_key, sanitize_input

app = FastAPI(
    title="梦眠阁 - AI智能睡眠管理",
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
app.include_router(profile_router)   # 健康档案 CRUD（routes在routers.py中定义）
app.include_router(chat_router)
app.include_router(task_router)
app.include_router(wellness_router)
app.include_router(admin_router)
app.include_router(community_router)
app.include_router(voice_router)
app.include_router(premium_router)
# app.include_router(platform_router)  # 空壳
app.include_router(payment_router)
app.include_router(game_router)
app.include_router(mood_router)
# app.include_router(settings_router)  # 空壳 — 仅 theme/language 两个字段
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
app.include_router(_public_config_router)  # 公共配置端点 (无鉴权)
# app.include_router(live_router)      # 无人使用
# app.include_router(growth_router)     # 空壳
# app.include_router(web3_router)       # 无人使用
# app.include_router(dataset_router)    # 无人使用
# app.include_router(llm_router)        # 无人使用
# app.include_router(iot_router)        # 前端无入口
# app.include_router(watch_router)      # 前端无入口

# Static files removed (SPA removed, API only)


# SPA index removed


# 管理后台入口 — 需要时取消注释
# @app.get("/admin")
# async def admin_page():


# Dashboard removed with SPA


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
