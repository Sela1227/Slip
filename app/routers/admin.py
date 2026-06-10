#!/usr/bin/env python3
"""
診間傳遞 - 管理者路由
功能：列出帳號 / 新增帳號 / 停用啟用 / 重設密碼（清空 hash，由本人重設）
只有 is_admin 帳號可進。
"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse

import app.config as config
from app.database import sync_db_session
import app.friends_service as fs
import app.usage as usage
import app.ids as ids
from app.dependencies import flash, get_current_user, base_ctx
from app.models import User, Message, SendLog, Signup
from app.template_env import render

router = APIRouter()


def _signup_link(request: Request, token: str) -> str:
    """組自助註冊連結，並強制 https（Railway 代理後 base_url 會是 http）。"""
    base = str(request.base_url).rstrip("/")
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    return f"{base}/signup/{token}"


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        if not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        users = db.query(User).order_by(User.is_admin.desc(), User.username).all()
        # 有效（未用、未過期）的自助註冊連結
        now = datetime.utcnow()
        active = (db.query(Signup).filter(Signup.used_at.is_(None), Signup.expires_at > now)
                  .order_by(Signup.created_at.desc()).all())
        ctx = base_ctx(request, db, user)
        ctx["users"] = users
        ctx["acct_ids"] = {u.username: (ids.fmt(u.friend_id) if u.friend_id else "—") for u in users}
        # 與管理者本人為私密對話（1天）的帳號
        from app.models import PrivatePair
        me = user.username
        pp = db.query(PrivatePair).filter(
            (PrivatePair.user_low == me) | (PrivatePair.user_high == me)).all()
        ctx["priv_users"] = {(p.user_high if p.user_low == me else p.user_low) for p in pp}
        ctx["uploads"] = usage.month_all(db)
        from app.models import Announcement
        cur = (db.query(Announcement).filter(Announcement.active == True)
               .order_by(Announcement.id.desc()).first())
        ctx["cur_announcement"] = cur.text if cur else ""
        from app.template_env import localtime as _lt
        ctx["last_logins"] = {u.username: (_lt(u.last_login).strftime("%Y/%m/%d %H:%M") if u.last_login else "—") for u in users}
        ctx["signups"] = [{"id": s.id, "link": _signup_link(request, s.token),
                           "expires_at": s.expires_at} for s in active]
        return render("admin.html", ctx)


@router.post("/admin/signup")
def admin_signup_create(request: Request):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        token = secrets.token_urlsafe(24)
        db.add(Signup(token=token, created_by=user.username,
                      expires_at=datetime.utcnow() + timedelta(hours=config.SIGNUP_EXPIRE_HOURS)))
        db.commit()
        flash(request, "已產生一次性註冊連結，把它傳給要開帳號的人。", "ok")
        return RedirectResponse("/admin", 303)


@router.post("/admin/signup/{sid}/revoke")
def admin_signup_revoke(request: Request, sid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        db.query(Signup).filter(Signup.id == sid, Signup.used_at.is_(None)).delete(synchronize_session=False)
        db.commit()
        flash(request, "已撤銷該註冊連結。", "ok")
        return RedirectResponse("/admin", 303)


@router.post("/admin/user/{uid}/private")
def admin_private(request: Request, uid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        target = db.query(User).filter(User.id == uid).first()
        if not target or target.username == user.username:
            flash(request, "無法設定。", "err")
            return RedirectResponse("/admin", 303)
        from app.models import PrivatePair
        lo, hi = (user.username, target.username) if user.username < target.username else (target.username, user.username)
        existing = db.query(PrivatePair).filter(
            PrivatePair.user_low == lo, PrivatePair.user_high == hi).first()
        if existing:
            db.delete(existing)
            db.commit()
            flash(request, f"已關閉與 {target.username} 的私密對話。", "ok")
        else:
            db.add(PrivatePair(user_low=lo, user_high=hi))
            db.commit()
            flash(request, f"已開啟與 {target.username} 的私密對話（雙方訊息僅保留 1 天）。", "ok")
        return RedirectResponse("/admin", 303)


@router.post("/admin/announce")
def admin_announce(request: Request, text: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        from app.models import Announcement
        db.query(Announcement).filter(Announcement.active == True).update({"active": False})
        text = (text or "").strip()
        if text:
            db.add(Announcement(text=text[:1000], active=True, created_by=user.username))
            flash(request, "公告已發布。", "ok")
        else:
            flash(request, "公告已清除。", "ok")
        db.commit()
        return RedirectResponse("/admin", 303)


@router.post("/admin/befriend")
def admin_befriend(request: Request, user_a: str = Form(""), user_b: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        a = db.query(User).filter(User.username == (user_a or "").strip(), User.is_active == True).first()
        b = db.query(User).filter(User.username == (user_b or "").strip(), User.is_active == True).first()
        if not a or not b or a.username == b.username:
            flash(request, "請選擇兩個不同且有效的帳號。", "err")
        elif fs.are_friends(db, a.username, b.username):
            flash(request, f"{a.username} 與 {b.username} 已經是好友。", "ok")
        else:
            fs.add_friend(db, a.username, b.username)
            db.commit()
            flash(request, f"已讓 {a.username} 與 {b.username} 成為好友。", "ok")
        return RedirectResponse("/admin", 303)


@router.post("/admin/add")
def admin_add(request: Request, username: str = Form(...)):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        username = username.strip()
        if not username:
            flash(request, "帳號名稱不可空白。", "err")
            return RedirectResponse("/admin", 303)
        if db.query(User).filter(User.username == username).first():
            flash(request, "此帳號已存在。", "err")
            return RedirectResponse("/admin", 303)
        db.add(User(username=username, password_hash=None, is_active=True, is_admin=False, level=1, friend_id=fs.unique_friend_id(db)))
        db.commit()
        flash(request, f"已新增帳號「{username}」，請通知本人首次登入設定密碼。", "ok")
        return RedirectResponse("/admin", 303)


@router.post("/admin/user/{uid}/toggle")
def admin_toggle(request: Request, uid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        target = db.query(User).filter(User.id == uid).first()
        if target and target.username != user.username:  # 不能停用自己
            target.is_active = not target.is_active
            db.commit()
        return RedirectResponse("/admin", 303)


@router.post("/admin/user/{uid}/level")
def admin_set_level(request: Request, uid: int, level: int = Form(1)):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        target = db.query(User).filter(User.id == uid).first()
        if target and not target.is_admin:
            lv = int(level)
            target.level = lv if lv in (1, 2, 3) else 1
            db.commit()
            flash(request, f"已將「{target.username}」設為{config.TIER_NAME.get(target.level, '銀')}等級。", "ok")
        return RedirectResponse("/admin", 303)


@router.post("/admin/user/{uid}/reset")
def admin_reset(request: Request, uid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        target = db.query(User).filter(User.id == uid).first()
        if target:
            target.password_hash = None  # 清空 = 下次登入由本人重新設定
            db.commit()
            flash(request, f"已重設「{target.username}」的密碼，請本人重新登入設定。", "ok")
        return RedirectResponse("/admin", 303)


@router.post("/admin/user/{uid}/delete")
def admin_delete(request: Request, uid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.is_admin:
            flash(request, "沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        target = db.query(User).filter(User.id == uid).first()
        if not target:
            return RedirectResponse("/admin", 303)
        if target.username == user.username:   # 不能刪自己
            flash(request, "不能刪除自己的帳號。", "err")
            return RedirectResponse("/admin", 303)
        # 連同這個帳號相關的訊息、寄件紀錄、好友關係與邀請一起清掉，不留孤兒資料
        import app.storage as storage
        own_msgs = db.query(Message).filter(
            (Message.recipient == target.username) | (Message.sender == target.username)
        ).all()
        for m in own_msgs:
            for a in m.attachments:
                storage.delete_file(a.path)
            db.delete(m)
        db.query(SendLog).filter(
            (SendLog.sender == target.username) | (SendLog.recipient == target.username)
        ).delete(synchronize_session=False)
        fs.cleanup_user(db, target.username)
        from app.models import Favorite
        db.query(Favorite).filter(Favorite.username == target.username).delete(synchronize_session=False)
        name = target.username
        db.delete(target)
        db.commit()
        flash(request, f"已刪除帳號「{name}」及其相關訊息。", "ok")
        return RedirectResponse("/admin", 303)
