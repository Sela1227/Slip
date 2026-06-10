#!/usr/bin/env python3
"""
診間傳遞 - 訊息路由
功能：訊息夾（對話列表，自己置頂）/ 對話內訊息 / 撰寫傳送（多檔附件）
      / 下載附件（授權 + 瀏覽器快取）/ 單筆刪除 / 清除對話 / 寄件紀錄
"""
import os
from datetime import datetime

from fastapi import APIRouter, Request, Form, File, UploadFile
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse, Response

import app.security as security
import app.friends_service as fs
import app.storage as storage
import app.usage as usage
import app.stickers as stickers
from app.database import sync_db_session
from app.dependencies import flash, get_current_user, base_ctx, avatar_set
from app.models import User, Message, SendLog, Attachment, Favorite, Snippet
from app.template_env import render

router = APIRouter()


def _counterpart(me: str, m: Message) -> str:
    """這則訊息對「我」而言的對話對象（自己傳自己 → 自己）。"""
    if m.sender == me and m.recipient == me:
        return me
    return m.recipient if m.sender == me else m.sender


@router.get("/inbox", response_class=HTMLResponse)
def inbox(request: Request):
    """聊天列表：自己置頂第一項，接著所有好友與曾來往的對象。點進去就是對話。"""
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        security.purge_old(db)   # 順手清過期訊息（含私密對話的 1 天保留）
        me = user.username
        security.purge_old(db)
        msgs = (db.query(Message)
                .filter((Message.sender == me) | (Message.recipient == me))
                .order_by(Message.created_at.desc()).all())

        convos = {}  # other -> dict
        for m in msgs:
            other = _counterpart(me, m)
            c = convos.get(other)
            if not c:
                c = {"other": other, "last_at": m.created_at, "preview": "", "unread": 0}
                convos[other] = c
                c["preview"] = ("［貼圖］" if m.sticker else (m.body[:38] if m.body else "")) or ("（附件）" if m.attachments else "")
            if m.recipient == me and m.sender != me and not m.is_read:
                c["unread"] += 1

        # 把所有好友也補進列表（即使還沒對話過，點了就能開始聊）
        for fname in fs.friends_of(db, me):
            convos.setdefault(fname, {"other": fname, "last_at": None, "preview": "", "unread": 0})

        others = [c for k, c in convos.items() if k != me]
        # 有訊息的按最新在前；都沒訊息的（純好友）排後面，依名字
        others.sort(key=lambda c: (c["last_at"] is not None, c["last_at"] or c["other"]), reverse=True)

        self_c = convos.get(me) or {"other": me, "last_at": None, "preview": "", "unread": 0}

        ctx = base_ctx(request, db, user)
        ctx["self_convo"] = self_c
        ctx["convos"] = others
        ctx["user_note"] = user.note
        ctx["avset"] = avatar_set(db, [c["other"] for c in others] + [me])
        return render("inbox.html", ctx)


@router.get("/inbox/{other}", response_class=HTMLResponse)
def thread(request: Request, other: str):
    """第二層：我與某對象之間的訊息（最新在上）。"""
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        me = user.username
        other = other.strip()
        target = db.query(User).filter(User.username == other).first()
        if not target:
            flash(request, "找不到這個對象。", "err")
            return RedirectResponse("/inbox", 303)

        if other == me:
            q = db.query(Message).filter(Message.sender == me, Message.recipient == me)
        else:
            q = db.query(Message).filter(
                ((Message.sender == me) & (Message.recipient == other)) |
                ((Message.sender == other) & (Message.recipient == me)))
        msgs = q.order_by(Message.created_at.asc()).all()

        # 開啟對話即標記已讀（並記錄已讀時間，供寄件者看「已讀回條」）
        changed = False
        for m in msgs:
            if m.recipient == me and not m.is_read:
                m.is_read = True
                if m.read_at is None:
                    m.read_at = datetime.utcnow()
                changed = True
        if changed:
            db.commit()

        import app.config as config
        ctx = base_ctx(request, db, user)
        ctx["messages"] = msgs
        ctx["other"] = other
        ctx["other_user"] = target
        ctx["avset"] = avatar_set(db, [other, me])
        ctx["cost_dl_100mb"] = round(0.1 * config.EGRESS_USD_PER_GB * config.USD_TWD, 1)
        ctx["can_files"] = bool(user.is_admin or not config.TIER_IMAGES_ONLY.get(user.level or 1, True))
        if user.is_admin:
            ctx["quota_left_h"] = None
        else:
            _t = user.level or 1
            _q = config.TIER_QUOTA_MB.get(_t, 0) * 1024 * 1024
            _left = max(0, _q - usage.month_bytes(db, user.username))
            ctx["quota_left_h"] = storage.human_size(_left)
            ctx["tier_name"] = config.TIER_NAME.get(_t, "銀")
        ids = [m.id for m in msgs]
        ctx["fav_ids"] = ({f.message_id for f in db.query(Favorite.message_id)
                           .filter(Favorite.username == me, Favorite.message_id.in_(ids)).all()}
                          if ids else set())
        ctx["is_self"] = (other == me)
        ctx["private_convo"] = (other != me) and security.is_private(db, me, other)
        ctx["sticker_packs"] = stickers.packs()
        return render("thread.html", ctx)


@router.post("/message/{mid}/delete")
def delete_message(request: Request, mid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        me = user.username
        m = db.query(Message).filter(Message.id == mid).first()
        back = "/inbox"
        if m and me in (m.sender, m.recipient):
            back = "/inbox/" + _counterpart(me, m)
            for a in m.attachments:
                storage.delete_file(a.path)
            db.delete(m)
            db.commit()
        return RedirectResponse(back, 303)


@router.post("/inbox/{other}/clear")
def clear_thread(request: Request, other: str):
    """清除我與某對象之間的全部訊息（雙向）。"""
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        me = user.username
        other = other.strip()
        if other == me:
            q = db.query(Message).filter(Message.sender == me, Message.recipient == me)
        else:
            q = db.query(Message).filter(
                ((Message.sender == me) & (Message.recipient == other)) |
                ((Message.sender == other) & (Message.recipient == me)))
        for m in q.all():
            for a in m.attachments:
                storage.delete_file(a.path)
            db.delete(m)
        db.commit()
        flash(request, "已清除這個對話的訊息。", "ok")
        return RedirectResponse("/inbox", 303)




@router.post("/note")
def save_note(request: Request, note: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        user.note = note.strip()[:2000] or None
        db.commit()
        return RedirectResponse("/inbox", 303)


@router.post("/compose")
def compose_submit(request: Request, recipient: str = Form(...),
                   body: str = Form(""), attachment: list[UploadFile] = File(None)):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        body = body.strip()
        recipient = recipient.strip()
        target = db.query(User).filter(User.username == recipient, User.is_active == True).first()
        if not target:
            flash(request, "收件人不存在或已停用。", "err")
            return RedirectResponse("/inbox", 303)
        if target.username != user.username and not fs.are_friends(db, user.username, target.username):
            flash(request, "只能傳給好友或自己，請先到「好友」頁互加好友。", "err")
            return RedirectResponse("/inbox", 303)

        thread_url = "/inbox/" + target.username  # 出錯時退回這個對話，維持聊天流程

        import app.config as config
        is_admin = bool(user.is_admin)
        tier = user.level or 1
        images_only = (not is_admin) and config.TIER_IMAGES_ONLY.get(tier, True)
        up_max_mb = None if is_admin else config.TIER_FILE_MB.get(tier, 5)
        quota_mb = None if is_admin else config.TIER_QUOTA_MB.get(tier)
        pending = [up for up in (attachment or []) if up and up.filename]
        # 銀級：只能傳圖片
        if images_only:
            for up in pending:
                if not storage.is_image(up.filename):
                    flash(request, f"你的等級（{config.TIER_NAME.get(tier)}）只能傳文字與圖片。如需傳其他格式，請洽管理者提升等級。", "err")
                    return RedirectResponse(thread_url, 303)

        # 多檔附件：逐一存檔
        saved = []  # (path, name, size)
        for up in pending:
            stored, orig, sz = storage.save_upload(up, max_mb=up_max_mb)
            if stored == "__too_big__":
                for p, _, _ in saved:
                    storage.delete_file(p)
                if not is_admin:
                    flash(request, f"你的等級（{config.TIER_NAME.get(tier)}）單檔上限為 {up_max_mb} MB。如需傳更大的檔案，請洽管理者提升等級。", "err")
                else:
                    flash(request, f"有附件超過設定的單檔上限（{security_max_mb()} MB）。", "err")
                return RedirectResponse(thread_url, 303)
            if stored:
                saved.append((stored, orig, sz))

        # 每月上傳額度（依等級；管理者不限）
        att_total_chk = sum(s for _, _, s in saved)
        if quota_mb is not None and att_total_chk > 0:
            used = usage.month_bytes(db, user.username)
            if used + att_total_chk > quota_mb * 1024 * 1024:
                for p, _, _ in saved:
                    storage.delete_file(p)
                flash(request, f"本月上傳額度已達上限（已用 {storage.human_size(used)} / {quota_mb} MB，{config.TIER_NAME.get(tier)}）。下月初重置，或請管理者調整等級。", "err")
                return RedirectResponse(thread_url, 303)

        if not body and not saved:
            flash(request, "請輸入內容或附加檔案。", "err")
            return RedirectResponse(thread_url, 303)

        att_total = sum(s for _, _, s in saved)
        size = len(body.encode("utf-8")) + att_total
        cap = security.capacity_info(db)
        if cap["used_mb"] * 1024 * 1024 + size > cap["limit_mb"] * 1024 * 1024:
            for p, _, _ in saved:
                storage.delete_file(p)
            flash(request, "剩餘容量不足，請先清除部分舊訊息，或調高容量上限。", "err")
            return RedirectResponse(thread_url, 303)

        m = Message(sender=user.username, recipient=target.username, body=body, size_bytes=size)
        db.add(m)
        db.flush()  # 取得 m.id
        for p, orig, sz in saved:
            db.add(Attachment(message_id=m.id, name=orig, path=p, size=sz))
        db.add(SendLog(sender=user.username, recipient=target.username))
        db.commit()
        usage.add_upload(db, user.username, att_total)  # 記入本月上傳量
        return RedirectResponse(thread_url, 303)


def security_max_mb():
    import app.config as config
    return config.MAX_FILE_MB


@router.get("/attachment/{aid}")
def download_attachment(request: Request, aid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        a = db.query(Attachment).filter(Attachment.id == aid).first()
        m = a.message if a else None
        # 只有寄件人或收件人能取用
        if not a or not m or user.username not in (m.recipient, m.sender):
            flash(request, "找不到附件或沒有權限。", "err")
            return RedirectResponse("/inbox", 303)
        path = storage.file_path(a.path)
        if not os.path.exists(path):
            flash(request, "附件檔案不存在（伺服器可能未設定持久儲存 Volume）。", "err")
            return RedirectResponse("/inbox", 303)
        # 附件內容不會變 → 設快取，省重複下載的 egress 流量
        # 檔名可能含中文等非 ASCII；HTTP 標頭只能放 latin-1，需用 RFC 5987 編碼，
        # 否則中文檔名會讓回應在編碼標頭時 500（圖片就顯示「已遺失」）。
        from urllib.parse import quote
        ascii_name = a.name.encode("ascii", "ignore").decode("ascii").strip() or "file"
        headers = {
            "Content-Disposition": (
                f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(a.name)}"
            ),
            "Cache-Control": "private, max-age=86400",
        }
        return FileResponse(path, media_type=storage.guess_type(a.name), headers=headers)


@router.post("/message/{mid}/title")
def set_title(request: Request, mid: int, title: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        m = db.query(Message).filter(Message.id == mid).first()
        # 只有收件者能為「收到的訊息」加標題
        if m and m.recipient == user.username:
            m.title = title.strip()[:200] or None
            db.commit()
        back = "/inbox/" + _counterpart(user.username, m) if m else "/inbox"
        return RedirectResponse(back, 303)


@router.post("/message/{mid}/tags")
def set_tags(request: Request, mid: int, tags: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        m = db.query(Message).filter(Message.id == mid).first()
        if m and user.username in (m.sender, m.recipient):
            cleaned = ",".join(t.strip() for t in tags.replace("，", ",").split(",") if t.strip())
            m.tags = cleaned[:255] or None
            db.commit()
        back = "/inbox/" + _counterpart(user.username, m) if m else "/inbox"
        return RedirectResponse(back, 303)


@router.post("/message/{mid}/favorite")
def toggle_favorite(request: Request, mid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        m = db.query(Message).filter(Message.id == mid).first()
        if not m or user.username not in (m.sender, m.recipient):
            return RedirectResponse("/inbox", 303)
        fav = db.query(Favorite).filter_by(username=user.username, message_id=mid).first()
        if fav:
            db.delete(fav)
        else:
            db.add(Favorite(username=user.username, message_id=mid,
                            sender=m.sender, other=_counterpart(user.username, m),
                            title=m.title, body=m.body, msg_created_at=m.created_at))
        db.commit()
        nxt = request.query_params.get("next")
        return RedirectResponse(nxt or ("/inbox/" + _counterpart(user.username, m)), 303)


@router.post("/favorite/{fid}/remove")
def remove_favorite(request: Request, fid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        db.query(Favorite).filter_by(id=fid, username=user.username).delete(synchronize_session=False)
        db.commit()
        return RedirectResponse("/favorites", 303)


@router.post("/favorite/{fid}/title")
def set_favorite_title(request: Request, fid: int, title: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        fav = db.query(Favorite).filter_by(id=fid, username=user.username).first()
        if fav:
            fav.title = title.strip()[:200] or None
            db.commit()
        return RedirectResponse("/favorites", 303)


@router.get("/favorites", response_class=HTMLResponse)
def favorites_page(request: Request):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        me = user.username
        favs = db.query(Favorite).filter_by(username=me).order_by(Favorite.created_at.desc()).all()
        items = []
        senders = []
        for f in favs:
            msg = db.query(Message).filter(Message.id == f.message_id).first() if f.message_id else None
            items.append({
                "fid": f.id,
                "title": f.title,
                "body": f.body,
                "from": "你傳的" if f.sender == me else (f.sender or "（未知）"),
                "sender": f.sender or "",
                "other": f.other or (f.sender or me),
                "at": f.msg_created_at or f.created_at,
                "attachments": msg.attachments if msg else [],
            })
            senders.append(f.sender or "")
        ctx = base_ctx(request, db, user)
        ctx["items"] = items
        ctx["avset"] = avatar_set(db, senders + [me])
        return render("favorites.html", ctx)


@router.post("/sticker")
def send_sticker(request: Request, recipient: str = Form(""), sticker: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        recipient = (recipient or "").strip()
        sticker = (sticker or "").strip()
        target = db.query(User).filter(User.username == recipient, User.is_active == True).first()
        if not target or (target.username != user.username and not fs.are_friends(db, user.username, target.username)):
            flash(request, "只能傳給好友或自己。", "err")
            return RedirectResponse("/inbox", 303)
        if not stickers.is_valid(sticker):
            flash(request, "找不到這個貼圖。", "err")
            return RedirectResponse("/inbox/" + target.username, 303)
        m = Message(sender=user.username, recipient=target.username, body="", sticker=sticker, size_bytes=0)
        db.add(m)
        db.commit()
        return RedirectResponse("/inbox/" + target.username, 303)
