#!/usr/bin/env python3
"""
診間傳遞 - 共用 templates 實例
功能：單一 Jinja2Templates 實例 + render 包裝
適用：FastAPI + Starlette 1.x

共用一個實例（坑 #32：多 router 各自建 templates 會讓 filter 註冊散落而壞）。
render() 統一處理 Starlette 1.x 的 TemplateResponse 簽名（坑 #46）。
"""
from datetime import timezone, timedelta

from fastapi.templating import Jinja2Templates

import app.config as config
import app.storage as storage

# 顯示用時區：資料庫存的是 UTC（datetime.utcnow），畫面要換成在地時間。
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(config.APP_TZ)
except Exception:
    _TZ = timezone(timedelta(hours=8))   # 後備：固定 +8（台灣無日光節約，等價）


def localtime(dt):
    """把 UTC 時間轉成設定時區的時間，給模板 strftime 用。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ)


templates = Jinja2Templates(directory="templates")

# 所有頁面都可用的全域變數與工具
templates.env.globals["app_name"] = config.APP_NAME
templates.env.globals["app_version"] = config.VERSION
templates.env.globals["is_image"] = storage.is_image
templates.env.globals["human_size"] = storage.human_size
templates.env.globals["localtime"] = localtime


def render(name: str, ctx: dict):
    """Starlette 1.x 的 TemplateResponse 需要 request 為第一參數，這裡統一處理（坑 #46）。"""
    return templates.TemplateResponse(ctx["request"], name, ctx)
