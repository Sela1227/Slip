#!/usr/bin/env python3
"""
診間傳遞 - 認證路由
功能：登入 / 首次登入設定密碼 / 登出 / 修改密碼
"""
import os
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form, File, UploadFile
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse, Response

import app.config as config
import app.security as security
import app.storage as storage
import app.usage as usage
from app.database import sync_db_session
from app.dependencies import flash, pop_flash, get_current_user, base_ctx
from app.models import User, Signup
from app.template_env import render

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/inbox", 303)
    return RedirectResponse("/login", 303)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return render("login.html", {"request": request, "flash": pop_flash(request),
                                 "remember_user": request.cookies.get("slip_user", "")})


@router.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...),
                 remember: str = Form(None)):
    with sync_db_session() as db:
        username = username.strip()
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_active:
            flash(request, "帳號不存在或已停用，請洽管理者。", "err")
            return RedirectResponse("/login", 303)

        # 尚未啟用：本人第一次登入，導向設定密碼
        if not user.password_hash:
            return render("set_password.html", {"request": request, "username": user.username})

        if not security.verify_password(password, user.password_hash):
            flash(request, "密碼錯誤。", "err")
            return RedirectResponse("/login", 303)

        user.last_login = datetime.utcnow()
        db.commit()
        request.session.clear()
        request.session["user"] = user.username
        request.session["last_seen"] = datetime.utcnow().isoformat()
        security.purge_old(db)  # 登入時順手清掉過期訊息
        resp = RedirectResponse("/inbox", 303)
        if remember:
            resp.set_cookie("slip_user", user.username, max_age=15552000,
                            httponly=True, samesite="lax", secure=config.COOKIE_SECURE)
        else:
            resp.delete_cookie("slip_user")
        return resp


@router.post("/activate")
def activate(request: Request, username: str = Form(...),
             password: str = Form(...), confirm: str = Form(...)):
    with sync_db_session() as db:
        user = db.query(User).filter(User.username == username.strip()).first()
        if not user or not user.is_active or user.password_hash:
            flash(request, "無法設定密碼，請重新登入或洽管理者。", "err")
            return RedirectResponse("/login", 303)
        if len(password) < 6:
            return render("set_password.html", {"request": request, "username": user.username,
                                                "error": "密碼至少 6 個字元。"})
        if password != confirm:
            return render("set_password.html", {"request": request, "username": user.username,
                                                "error": "兩次輸入的密碼不一致。"})
        user.password_hash = security.hash_password(password)
        user.last_login = datetime.utcnow()
        db.commit()
        request.session.clear()
        request.session["user"] = user.username
        request.session["last_seen"] = datetime.utcnow().isoformat()
        flash(request, "密碼設定完成，已登入。", "ok")
        return RedirectResponse("/inbox", 303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    flash(request, "已登出。", "ok")
    return RedirectResponse("/login", 303)


@router.get("/settings", response_class=HTMLResponse)
def settings_form(request: Request):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        import app.avatars as avatars
        ctx = base_ctx(request, db, user)
        ctx["month_upload"] = usage.month_bytes(db, user.username)
        _tier = user.level or 1
        ctx["tier_name"] = "管理者" if user.is_admin else config.TIER_NAME.get(_tier, "銀")
        ctx["quota_mb"] = None if user.is_admin else config.TIER_QUOTA_MB.get(_tier)
        ctx["presets"] = [{"i": i, "svg": avatars.preset_svg(i)} for i in range(avatars.PRESET_COUNT)]
        ctx["themes"] = THEMES
        ctx["fx"], ctx["fy"] = _parse_pos(user.avatar_pos)
        return render("settings.html", ctx)


THEMES = [
    {"key": "navy", "name": "靛藍", "color": "#304073"},
    {"key": "sage", "name": "霧綠", "color": "#5a7a5d"},
    {"key": "terracotta", "name": "陶土", "color": "#a96b4f"},
    {"key": "plum", "name": "梅紫", "color": "#6f5a82"},
    {"key": "pikmin", "name": "皮克敏", "color": "#5fa345"},
]
_THEME_KEYS = {t["key"] for t in THEMES}


def _parse_pos(pos):
    try:
        x, y = (pos or "50,50").split(",")
        return int(x), int(y)
    except Exception:
        return 50, 50


@router.post("/darkmode")
def set_darkmode(request: Request, dark: str = Form(None)):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        user.dark = 1 if dark else None
        db.commit()
        flash(request, "已切換為暗色模式。" if user.dark else "已切換為淺色模式。", "ok")
        return RedirectResponse("/settings", 303)


@router.post("/theme")
def set_theme(request: Request, theme: str = Form("navy")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        if theme in _THEME_KEYS:
            user.theme = theme
            db.commit()
            flash(request, "已更換介面配色。", "ok")
        return RedirectResponse("/settings", 303)


@router.post("/avatar")
def avatar_upload(request: Request, avatar: UploadFile = File(None)):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        orig = storage.save_avatar_original(avatar)
        if not orig:
            flash(request, "請選擇圖片檔（png / jpg / gif / webp）。", "err")
            return RedirectResponse("/settings", 303)
        disp = storage.crop_square(orig, 50, 50)
        if not disp:
            storage.delete_file(orig)
            flash(request, "圖片無法處理，請換一張。", "err")
            return RedirectResponse("/settings", 303)
        # 清掉舊的（圖片 / 內建頭像）
        storage.delete_file(user.avatar_path)
        storage.delete_file(user.avatar_orig)
        user.avatar_path = disp
        user.avatar_orig = orig
        user.avatar_pos = "50,50"
        user.avatar_preset = None
        db.commit()
        flash(request, "頭像已更新，可在下方調整中心位置。", "ok")
        return RedirectResponse("/settings", 303)


@router.post("/avatar/position")
def avatar_position(request: Request, fx: int = Form(50), fy: int = Form(50)):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        if not user.avatar_orig:
            return RedirectResponse("/settings", 303)
        fx = max(0, min(int(fx), 100))
        fy = max(0, min(int(fy), 100))
        disp = storage.crop_square(user.avatar_orig, fx, fy)
        if disp:
            storage.delete_file(user.avatar_path)
            user.avatar_path = disp
            user.avatar_pos = f"{fx},{fy}"
            db.commit()
            flash(request, "已更新頭像中心位置。", "ok")
        return RedirectResponse("/settings", 303)


@router.post("/avatar/preset/{idx}")
def avatar_preset(request: Request, idx: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        import app.avatars as avatars
        if 0 <= idx < avatars.PRESET_COUNT:
            storage.delete_file(user.avatar_path)
            storage.delete_file(user.avatar_orig)
            user.avatar_path = None
            user.avatar_orig = None
            user.avatar_pos = None
            user.avatar_preset = idx
            db.commit()
            flash(request, "已選用內建頭像。", "ok")
        return RedirectResponse("/settings", 303)


@router.post("/avatar/remove")
def avatar_remove(request: Request):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        storage.delete_file(user.avatar_path)
        storage.delete_file(user.avatar_orig)
        user.avatar_path = None
        user.avatar_orig = None
        user.avatar_pos = None
        user.avatar_preset = None
        db.commit()
        flash(request, "已移除頭像。", "ok")
        return RedirectResponse("/settings", 303)


@router.get("/avatar/original")
def avatar_original(request: Request):
    """提供本人的原圖給設定頁的中心點預覽用。"""
    NS = {"Cache-Control": "no-store"}
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.avatar_orig:
            return Response(status_code=404, headers=NS)
        path = storage.file_path(user.avatar_orig)
        if not os.path.exists(path):
            return Response(status_code=404, headers=NS)
        return FileResponse(path, media_type=storage.guess_type(user.avatar_orig), headers=NS)


@router.get("/avatar/{username}")
def avatar_image(request: Request, username: str):
    # 頭像網址固定（/avatar/帳號），內容卻會變；一律 no-store，避免瀏覽器拿到舊圖或
    # 把「還沒有頭像」的 404 也快取起來，導致別人換了頭像你卻一直看不到。
    NS = {"Cache-Control": "no-store"}
    with sync_db_session() as db:
        viewer = get_current_user(request, db)
        if not viewer:
            return Response(status_code=404, headers=NS)
        target = db.query(User).filter(User.username == username).first()
        if not target:
            return Response(status_code=404, headers=NS)
        # 1) 上傳的頭像（已裁切）
        if target.avatar_path:
            path = storage.file_path(target.avatar_path)
            if os.path.exists(path):
                return FileResponse(path, media_type=storage.guess_type(target.avatar_path), headers=NS)
        # 2) 內建人物頭像
        if target.avatar_preset is not None:
            import app.avatars as avatars
            return Response(content=avatars.preset_svg(target.avatar_preset),
                            media_type="image/svg+xml", headers=NS)
        return Response(status_code=404, headers=NS)


@router.post("/password")
def password_submit(request: Request, old: str = Form(...),
                    new: str = Form(...), confirm: str = Form(...)):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        if not security.verify_password(old, user.password_hash):
            flash(request, "目前密碼錯誤。", "err")
            return RedirectResponse("/settings", 303)
        if len(new) < 6:
            flash(request, "新密碼至少 6 個字元。", "err")
            return RedirectResponse("/settings", 303)
        if new != confirm:
            flash(request, "兩次輸入的新密碼不一致。", "err")
            return RedirectResponse("/settings", 303)
        user.password_hash = security.hash_password(new)
        db.commit()
        flash(request, "密碼已更新。", "ok")
        return RedirectResponse("/settings", 303)


# ── 自助註冊（管理者產生一次性連結，對方自己開帳號）─────────────────
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{2,32}$")


def _valid_signup(db, token):
    s = db.query(Signup).filter(Signup.token == token).first()
    if not s or s.used_at is not None or s.expires_at < datetime.utcnow():
        return None
    return s


@router.get("/signup/{token}", response_class=HTMLResponse)
def signup_form(request: Request, token: str):
    with sync_db_session() as db:
        s = _valid_signup(db, token)
        ctx = {"request": request, "token": token, "valid": s is not None,
               "app_name": config.APP_NAME, "app_version": config.VERSION,
               "flash": pop_flash(request)}
        return render("signup.html", ctx)


@router.post("/signup/{token}")
def signup_submit(request: Request, token: str, username: str = Form(...),
                  password: str = Form(...), confirm: str = Form(...)):
    with sync_db_session() as db:
        s = _valid_signup(db, token)
        if not s:
            flash(request, "這個註冊連結無效或已使用 / 過期。", "err")
            return RedirectResponse("/signup/" + token, 303)
        username = username.strip()
        if not USERNAME_RE.match(username):
            flash(request, "帳號只能用英數字與底線，長度 2–32。", "err")
            return RedirectResponse("/signup/" + token, 303)
        if db.query(User).filter(User.username == username).first():
            flash(request, "這個帳號名稱已被使用，請換一個。", "err")
            return RedirectResponse("/signup/" + token, 303)
        if len(password) < 6:
            flash(request, "密碼至少 6 個字。", "err")
            return RedirectResponse("/signup/" + token, 303)
        if password != confirm:
            flash(request, "兩次密碼不一致。", "err")
            return RedirectResponse("/signup/" + token, 303)
        # 建立帳號（銀級、已啟用、密碼已設）
        import app.friends_service as fs
        db.add(User(username=username, password_hash=security.hash_password(password),
                    is_active=True, is_admin=False, level=1, friend_id=fs.unique_friend_id(db)))
        s.used_at = datetime.utcnow()
        s.used_by = username
        # 透過某帳號的邀請連結註冊 → 直接與邀請人成為好友
        inviter = db.query(User).filter(User.username == s.created_by, User.is_active == True).first()
        friend_msg = ""
        if inviter and inviter.username != username:
            fs.add_friend(db, username, inviter.username)
            friend_msg = f"，並已與 {inviter.username} 成為好友"
        new_user = db.query(User).filter(User.username == username).first()
        if new_user:
            new_user.last_login = datetime.utcnow()
        db.commit()
        # 直接登入
        request.session.clear()
        request.session["user"] = username
        request.session["last_seen"] = datetime.utcnow().isoformat()
        flash(request, f"帳號建立完成{friend_msg}，已為你登入。", "ok")
        return RedirectResponse("/inbox", 303)
