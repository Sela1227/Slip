#!/usr/bin/env python3
"""
診間傳遞 - 安全與共用工具
功能：密碼雜湊（bcrypt）/ 閒置登出判斷 / 過期清除 / 容量統計
適用：bcrypt 4.x

直接用 bcrypt，不用 passlib：少一層相依、且避開坑 #28（bcrypt 4.1+ 砸壞 passlib）。
"""
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import func

import app.config as config
from app.models import Message, SendLog


# === 密碼：以 bcrypt 雜湊儲存，永遠不存明文 ===
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# === 閒置自動登出：在 session 記錄最後活動時間 ===
def session_expired(last_seen_iso: str) -> bool:
    if not last_seen_iso:
        return True
    try:
        last = datetime.fromisoformat(last_seen_iso)
    except ValueError:
        return True
    return datetime.utcnow() - last > timedelta(minutes=config.IDLE_TIMEOUT_MIN)


# === 過期清除：刪掉超過保留天數的訊息與寄件紀錄（每次開頁面順手做） ===
def _pair_key(a, b):
    return (a, b) if a < b else (b, a)


def is_private(db, a, b) -> bool:
    """此配對是否為私密對話（僅保留 1 天）。"""
    from app.models import PrivatePair
    if a == b:
        return False
    lo, hi = _pair_key(a, b)
    return db.query(PrivatePair).filter(
        PrivatePair.user_low == lo, PrivatePair.user_high == hi
    ).first() is not None


def purge_old(db) -> None:
    import app.storage as storage
    from app.models import PrivatePair
    now = datetime.utcnow()
    normal_cutoff = now - timedelta(days=config.RETENTION_DAYS)
    private_cutoff = now - timedelta(days=1)          # 私密對話：保留 1 天
    private = {(p.user_low, p.user_high) for p in db.query(PrivatePair).all()}
    # 取所有「超過 1 天」的訊息逐筆判定（1 天是較寬的界線，涵蓋所有候選）
    rows = db.query(Message).filter(Message.created_at < private_cutoff).all()
    for m in rows:
        is_priv = (m.sender != m.recipient) and (_pair_key(m.sender, m.recipient) in private)
        if is_priv:
            drop = True                                # 私密：滿 1 天即刪，無視標籤（私密優先）
        elif m.created_at < normal_cutoff and not (m.tags and m.tags.strip()):
            drop = True                                # 一般：滿保留天數且未加標籤
        else:
            drop = False
        if drop:
            for a in m.attachments:
                storage.delete_file(a.path)
            db.delete(m)
    db.query(SendLog).filter(SendLog.created_at < normal_cutoff).delete(synchronize_session=False)
    db.commit()


# === 容量統計：所有訊息（內容 + 附件）佔用的位元組 ===
def used_bytes(db) -> int:
    total = db.query(func.coalesce(func.sum(Message.size_bytes), 0)).scalar()
    return int(total or 0)


def capacity_info(db) -> dict:
    used = used_bytes(db)
    limit = config.CAPACITY_LIMIT_BYTES
    pct = min(100, round(used / limit * 100, 1)) if limit else 0
    return {
        "used_mb": round(used / 1024 / 1024, 1),
        "limit_mb": round(limit / 1024 / 1024, 1),
        "pct": pct,
        "over": used >= limit,
    }
