#!/usr/bin/env python3
"""
診間傳遞 - FastAPI 入口
功能：組裝 app（lifespan 建表 / session 中介層 / 靜態檔 / 三個 router）
適用：uvicorn app.main:app（Railway 用 Procfile 啟動）

本機預覽請跑根目錄的 run.py（python run.py），會自動套用本機友善設定。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

import app.config as config
from app.database import init_db
from app.routers import auth, messages, admin, friends, tools


@asynccontextmanager
async def lifespan(_app):
    init_db()   # 啟動時建表並確保管理者帳號存在
    yield


app = FastAPI(title=config.APP_NAME, version=config.VERSION, lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    https_only=config.COOKIE_SECURE,   # Railway HTTPS 設 true；本機 http 設 false
    same_site="lax",
    max_age=config.IDLE_TIMEOUT_MIN * 60,
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # 從根路徑提供 service worker，讓 scope 涵蓋整個 App（PWA 安裝用）
    return FileResponse("static/sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


app.include_router(auth.router)
app.include_router(messages.router)
app.include_router(friends.router)
app.include_router(admin.router)
app.include_router(tools.router)
