#!/usr/bin/env python3
"""
診間傳遞 - 統一認證
功能：取得目前登入者（含閒置逾時處理）/ 共用頁面 context / flash 訊息
適用：FastAPI

統一在這裡實作，不讓每個 router 各自寫 get_current_user（坑 #5：散落會修一邊忘一邊）。
"""
from datetime import datetime

import app.config as config
import app.security as security
from app.models import User, Message, FriendRequest


def flash(request, message: str, kind: str = "ok"):
    request.session["flash"] = {"message": message, "kind": kind}


def pop_flash(request):
    return request.session.pop("flash", None)


def get_current_user(request, db):
    """目前登入者；同時處理閒置逾時並更新活動時間。逾時或未登入回傳 None。"""
    username = request.session.get("user")
    if not username:
        return None
    if security.session_expired(request.session.get("last_seen")):
        request.session.clear()
        return None
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user:
        request.session.clear()
        return None
    request.session["last_seen"] = datetime.utcnow().isoformat()
    return user


def avatar_set(db, names):
    """回傳『有頭像（上傳圖或內建頭像）』的 username 集合，給 template 決定顯示圖片或字首。"""
    names = [n for n in set(names) if n]
    if not names:
        return set()
    rows = db.query(User.username).filter(
        User.username.in_(names),
        (User.avatar_path.isnot(None)) | (User.avatar_preset.isnot(None))
    ).all()
    return {r[0] for r in rows}


def base_ctx(request, db, user):
    """每個登入後頁面共用的資料：使用者、容量、提示訊息、設定值。"""
    unread_total = (db.query(Message)
                    .filter(Message.recipient == user.username, Message.is_read == False)
                    .count())
    pending_requests = db.query(FriendRequest).filter(FriendRequest.to_user == user.username).count()
    from app.models import Announcement
    ann = (db.query(Announcement).filter(Announcement.active == True)
           .order_by(Announcement.id.desc()).first())
    return {
        "request": request,
        "user": user,
        "capacity": security.capacity_info(db),
        "flash": pop_flash(request),
        "idle_min": config.IDLE_TIMEOUT_MIN,
        "retention_days": config.RETENTION_DAYS,
        "max_file_mb": config.MAX_FILE_MB,
        "theme": user.theme or "navy",
        "dark": bool(user.dark),
        "unread_total": unread_total,
        "pending_requests": pending_requests,
        "announcement": ann.text if ann else "",
    }
