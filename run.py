#!/usr/bin/env python3
"""
診間傳遞 - 本機預覽啟動器
功能：用本機友善設定啟動（python run.py），不影響 Railway 部署
適用：本機看畫面用；正式部署走 Procfile 的 uvicorn app.main:app

部署到 Railway 時不會執行這支（Railway 直接跑 uvicorn），所以這裡的預設值
只在本機生效，會用 Railway 上設定的環境變數。
"""
import os

# 本機 http 預覽用的友善預設（已設環境變數時不覆蓋）
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("SESSION_SECRET", "local-dev-only")
os.environ.setdefault("ADMIN_USERNAME", "admin")

if __name__ == "__main__":
    import uvicorn
    print("本機預覽已啟動 → 開瀏覽器到 http://127.0.0.1:8000")
    print("（管理者帳號為 admin，第一次登入時自設密碼）")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
