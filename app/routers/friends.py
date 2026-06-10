#!/usr/bin/env python3
"""
診間傳遞 - 好友路由
功能：好友頁 / 產生邀請連結 / 作廢邀請 / 接受邀請（加好友）/ 移除好友
"""
import io
import secrets
import qrcode
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, Response

import app.config as config
import app.friends_service as fs
import app.ids as ids
from app.database import sync_db_session
from app.dependencies import flash, get_current_user, base_ctx
from app.models import User, Signup
from app.template_env import render

router = APIRouter()


def _signup_link(request: Request, token: str) -> str:
    base = str(request.base_url).rstrip("/")
    if base.startswith("http://") and "127.0.0.1" not in base and "localhost" not in base:
        base = "https://" + base[len("http://"):]
    return f"{base}/signup/{token}"


def _base(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    if base.startswith("http://") and "127.0.0.1" not in base and "localhost" not in base:
        base = "https://" + base[len("http://"):]
    return base


@router.get("/friend/qr")
def friend_qr(request: Request):
    """本人 ID 的 QR（內含加好友連結，任何相機掃了都能直接開）。"""
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user or not user.friend_id:
            return Response(status_code=404, headers={"Cache-Control": "no-store"})
        url = f"{_base(request)}/friends?add={user.friend_id}"
        img = qrcode.make(url, box_size=8, border=2)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return Response(content=buf.getvalue(), media_type="image/png",
                        headers={"Cache-Control": "no-store"})


@router.post("/signup-link")
def signup_link_create(request: Request):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        db.add(Signup(token=secrets.token_urlsafe(24), created_by=user.username,
                      expires_at=datetime.utcnow() + timedelta(hours=config.SIGNUP_EXPIRE_HOURS)))
        db.commit()
        flash(request, "已產生註冊連結，複製後傳給對方自行建立帳號。", "ok")
        return RedirectResponse("/friends", 303)


@router.post("/signup-link/{sid}/revoke")
def signup_link_revoke(request: Request, sid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        db.query(Signup).filter(Signup.id == sid, Signup.created_by == user.username,
                                Signup.used_at.is_(None)).delete(synchronize_session=False)
        db.commit()
        flash(request, "已作廢該註冊連結。", "ok")
        return RedirectResponse("/friends", 303)


@router.get("/friends", response_class=HTMLResponse)
def friends_page(request: Request):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        names = fs.friends_of(db, user.username)
        friends = (db.query(User).filter(User.username.in_(names)).order_by(User.username).all()
                   if names else [])
        incoming = [{"id": r.id, "from_user": r.from_user} for r in fs.incoming_requests(db, user.username)]
        outgoing = [{"id": r.id, "to_user": r.to_user} for r in fs.outgoing_requests(db, user.username)]
        ctx = base_ctx(request, db, user)
        ctx["friends"] = friends
        ctx["incoming"] = incoming
        ctx["outgoing"] = outgoing
        ctx["my_id"] = ids.fmt(user.friend_id or "")
        add_q = ids.normalize(request.query_params.get("add", ""))
        ctx["prefill_id"] = ids.fmt(add_q) if ids.luhn_valid(add_q) else ""
        now = datetime.utcnow()
        my_signups = (db.query(Signup)
                      .filter(Signup.created_by == user.username, Signup.used_at.is_(None), Signup.expires_at > now)
                      .order_by(Signup.created_at.desc()).all())
        ctx["signups"] = [{"id": s.id, "link": _signup_link(request, s.token),
                           "expires_at": s.expires_at} for s in my_signups]
        return render("friends.html", ctx)


@router.post("/friend/request")
def friend_request(request: Request, friend_id: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        ok, msg = fs.request_by_id(db, user.username, friend_id)
        flash(request, msg, "ok" if ok else "err")
        return RedirectResponse("/friends", 303)


@router.post("/friend/request/{rid}/accept")
def friend_request_accept(request: Request, rid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        ok, msg = fs.accept_request(db, user.username, rid)
        flash(request, msg, "ok" if ok else "err")
        return RedirectResponse("/friends", 303)


@router.post("/friend/request/{rid}/decline")
def friend_request_decline(request: Request, rid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        fs.decline_request(db, user.username, rid)
        flash(request, "已處理該邀請。", "ok")
        return RedirectResponse("/friends", 303)



@router.post("/friend/remove/{username}")
def friend_remove(request: Request, username: str):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        fs.remove_friend(db, user.username, username.strip())
        flash(request, f"已移除好友「{username}」。", "ok")
        return RedirectResponse("/friends", 303)
