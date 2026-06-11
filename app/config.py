#!/usr/bin/env python3
"""
診間傳遞 - 集中設定
功能：版本號 / 環境變數 / 保留天數 / 閒置時間 / 容量上限
適用：FastAPI + PostgreSQL（Railway）/ Python 3.12
"""
import os

VERSION = "V1.12.0"
# 顯示用時區（資料庫存 UTC）
APP_TZ = os.environ.get("APP_TZ", "Asia/Taipei")

# 畫面顯示名稱
APP_NAME = "Slip 絲利普"

# 管理者帳號名稱。Railway 環境變數設 ADMIN_USERNAME（例如醫師代號）。
# 此帳號第一次登入時自設密碼，名稱不寫死在程式碼。
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")

# 簽署登入 cookie 的祕密字串。Railway 設一組長亂碼。
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-insecure-change-me-in-railway")

# 資料庫連線字串。Railway 加 PostgreSQL 後自動提供 DATABASE_URL。
# 本機沒設定時退回 SQLite 檔，方便先看畫面。
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local.db")

# Railway 給的是 postgres://，SQLAlchemy 需要 postgresql+psycopg2://，自動轉換（坑 P3）。
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

# 訊息保留天數，超過自動清除。
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "15"))

# 閒置自動登出（分鐘）。共用電腦安全用。
IDLE_TIMEOUT_MIN = int(os.environ.get("IDLE_TIMEOUT_MIN", "15"))

# 容量上限（MB）。畫面顯示「已用 / 上限」。
CAPACITY_LIMIT_BYTES = int(os.environ.get("CAPACITY_LIMIT_MB", "500")) * 1024 * 1024

# 加好友邀請連結的有效時數（一次性 + 過期）。
INVITE_EXPIRE_HOURS = int(os.environ.get("INVITE_EXPIRE_HOURS", "24"))
# 自助註冊連結有效時數（管理者產生，給人自己開帳號用）
SIGNUP_EXPIRE_HOURS = int(os.environ.get("SIGNUP_EXPIRE_HOURS", "72"))

# 附件儲存資料夾。Railway 請掛一個 Volume 並把 UPLOAD_DIR 設成 Volume 的掛載路徑
# （例如 /data/uploads），否則檔案會在重啟後消失（同 SQLite 的道理，坑 P1）。
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")

# 縮網址用的網域；綁了短的自訂網域後設此環境變數，短連結就改用它（否則用目前網址）
SHORT_BASE = os.environ.get("SHORT_BASE", "").rstrip("/")

# 單一附件的硬性上限（MB）。0 = 不設固定上限，只受總容量（Volume）限制。
# Railway 本身對上傳大小沒有限制（僅 5 分鐘逾時），所以預設交給總容量把關。
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "0"))


# === 使用者等級（管理者獨立，不在此軸）。1=銀 2=金 3=白金 ===
def _envint(key, default):
    return int(os.environ.get(key, str(default)))

TIER_NAME = {1: "銀", 2: "金", 3: "白金"}
TIER_FILE_MB = {1: _envint("SILVER_MAX_FILE_MB", 5),
                2: _envint("GOLD_MAX_FILE_MB", 25),
                3: _envint("PLATINUM_MAX_FILE_MB", 200)}       # 單檔上限（MB）
TIER_QUOTA_MB = {1: _envint("SILVER_QUOTA_MB", 300),
                 2: _envint("GOLD_QUOTA_MB", 500),
                 3: _envint("PLATINUM_QUOTA_MB", 1024)}        # 每月上傳額度（MB）
TIER_IMAGES_ONLY = {1: True, 2: False, 3: False}              # 銀：只能文字＋圖片

# Railway 費用估算用（給附件區顯示成本警語）。費率隨方案/時間會變，可用 env 微調。
EGRESS_USD_PER_GB = float(os.environ.get("EGRESS_USD_PER_GB", "0.10"))          # 下載流量（取較高的方案費率較保守）
STORAGE_USD_PER_GB_MONTH = float(os.environ.get("STORAGE_USD_PER_GB_MONTH", "0.25"))  # 存放
USD_TWD = float(os.environ.get("USD_TWD", "32"))                                # 美元兌台幣概略匯率

# cookie 是否要求 HTTPS。Railway 有 HTTPS，正式環境設 true；本機 http 測試設 false。
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
