"""常用功能：剪貼簿（多分格暫存）＋ 常用片語 ＋ 縮網址 ＋ QR 產生。"""
import io
import json
import secrets
from urllib.parse import quote

import qrcode
from pypdf import PdfReader, PdfWriter
from fastapi import APIRouter, Request, Form, File, UploadFile
from fastapi.responses import RedirectResponse, HTMLResponse, Response

import app.config as config
import app.storage as storage
import app.usage as usage
import app.friends_service as fs
from app.database import sync_db_session
from app.dependencies import flash, get_current_user, base_ctx
from app.models import Snippet, ShortLink, User, Message, Attachment, Bookmark
from app.template_env import render

router = APIRouter()

PHRASE_LIMIT = 20
CLIP_MAX = 12        # 剪貼簿分格上限
QR_MAX_LEN = 1500    # QR 內容長度上限


def _safe_url(u):
    u = (u or "").strip()
    return u if u[:7].lower() == "http://" or u[:8].lower() == "https://" else None


def _base(request):
    base = str(request.base_url).rstrip("/")
    if base.startswith("http://") and "127.0.0.1" not in base and "localhost" not in base:
        base = "https://" + base[len("http://"):]
    return base


def _load_clips(raw):
    """把 clipboard 欄解析成分格清單；相容舊的純文字（變成單一分格）。"""
    raw = raw or ""
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data if isinstance(x, str)]
    except Exception:
        pass
    return [raw] if raw.strip() else []


def _phrases(db, username):
    return (db.query(Snippet).filter(Snippet.username == username)
            .order_by(Snippet.sort_order.asc(), Snippet.id.asc()).all())


@router.get("/tools", response_class=HTMLResponse)
def tools_page(request: Request):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        ctx = base_ctx(request, db, user)
        clips = _load_clips(user.clipboard)
        ctx["clips"] = clips if clips else [""]   # 至少一個空分格
        ctx["phrases"] = _phrases(db, user.username)
        ctx["phrase_limit"] = PHRASE_LIMIT
        # 縮網址：本人最近的短網址
        links = (db.query(ShortLink).filter(ShortLink.created_by == user.username)
                 .order_by(ShortLink.id.desc()).limit(20).all())
        sbase = config.SHORT_BASE or _base(request)   # 綁了短網域就用它
        ctx["links"] = [{"short": f"{sbase}/s/{l.code}", "url": l.url, "id": l.id} for l in links]
        # QR：可傳送的對象（自己＋好友）
        friends = fs.friends_of(db, user.username)
        ctx["qr_recipients"] = [user.username] + sorted(friends)
        ctx["qr_data"] = request.query_params.get("qr", "")
        ctx["bookmarks"] = (db.query(Bookmark).filter(Bookmark.username == user.username)
                            .order_by(Bookmark.sort_order.asc(), Bookmark.id.asc()).all())
        tab = request.query_params.get("tab", "clip")
        ctx["tab"] = tab if tab in ("clip", "phrases", "calc", "url", "qr", "pdf", "bookmark") else "clip"
        return render("tools.html", ctx)


@router.post("/clipboard")
async def save_clipboard(request: Request):
    form = await request.form()
    slots = [(s or "").strip()[:20000] for s in form.getlist("slot")]
    slots = [s for s in slots if s][:CLIP_MAX]   # 丟掉空分格
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        user.clipboard = json.dumps(slots, ensure_ascii=False) if slots else None
        db.commit()
    flash(request, "剪貼簿已儲存。", "ok")
    return RedirectResponse("/tools?tab=clip", 303)


@router.post("/phrase/add")
def phrase_add(request: Request, label: str = Form(""), text: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        text = (text or "").strip()[:300]
        label = (label or "").strip()[:80]
        if not text:
            return RedirectResponse("/tools?tab=phrases", 303)
        if db.query(Snippet).filter(Snippet.username == user.username).count() >= PHRASE_LIMIT:
            flash(request, f"片語最多 {PHRASE_LIMIT} 個，請先刪除一些。", "err")
            return RedirectResponse("/tools?tab=phrases", 303)
        nxt = (max((p.sort_order for p in _phrases(db, user.username)), default=0)) + 1
        db.add(Snippet(username=user.username, label=label or None, text=text, sort_order=nxt))
        db.commit()
        return RedirectResponse("/tools?tab=phrases", 303)


@router.post("/phrase/{pid}/edit")
def phrase_edit(request: Request, pid: int, label: str = Form(""), text: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        p = db.query(Snippet).filter(Snippet.id == pid, Snippet.username == user.username).first()
        if p:
            text = (text or "").strip()[:300]
            if text:
                p.text = text
                p.label = (label or "").strip()[:80] or None
                db.commit()
        return RedirectResponse("/tools?tab=phrases", 303)


@router.post("/phrase/{pid}/delete")
def phrase_delete(request: Request, pid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        p = db.query(Snippet).filter(Snippet.id == pid, Snippet.username == user.username).first()
        if p:
            db.delete(p)
            db.commit()
        return RedirectResponse("/tools?tab=phrases", 303)


@router.post("/phrase/{pid}/move")
def phrase_move(request: Request, pid: int, dir: str = Form("up")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        items = _phrases(db, user.username)
        idx = next((i for i, p in enumerate(items) if p.id == pid), None)
        if idx is not None:
            swap = idx - 1 if dir == "up" else idx + 1
            if 0 <= swap < len(items):
                a, b = items[idx], items[swap]
                a.sort_order, b.sort_order = b.sort_order, a.sort_order
                db.commit()
        return RedirectResponse("/tools?tab=phrases", 303)


# ===== 縮網址 =====
@router.post("/shorten")
def shorten(request: Request, url: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        safe = _safe_url(url)
        if not safe:
            flash(request, "請輸入有效網址（需以 http:// 或 https:// 開頭）。", "err")
            return RedirectResponse("/tools?tab=url", 303)
        # 產生唯一短碼
        for _ in range(10):
            code = secrets.token_urlsafe(4)[:6].replace("-", "a").replace("_", "b")
            if not db.query(ShortLink).filter(ShortLink.code == code).first():
                break
        db.add(ShortLink(code=code, url=safe[:2000], created_by=user.username))
        db.commit()
        flash(request, "短網址已建立。", "ok")
        return RedirectResponse("/tools?tab=url", 303)


@router.post("/shorten/{lid}/delete")
def shorten_delete(request: Request, lid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        l = db.query(ShortLink).filter(ShortLink.id == lid, ShortLink.created_by == user.username).first()
        if l:
            db.delete(l)
            db.commit()
        return RedirectResponse("/tools?tab=url", 303)


@router.get("/s/{code}")
def short_redirect(code: str):
    with sync_db_session() as db:
        l = db.query(ShortLink).filter(ShortLink.code == code).first()
        if not l:
            return Response("短網址不存在或已刪除。", status_code=404)
        return RedirectResponse(l.url, 302)


# ===== QR 產生 =====
def _qr_png(data: str) -> bytes:
    img = qrcode.make(data, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@router.get("/qr/img")
def qr_img(request: Request, data: str = "", dl: int = 0):
    with sync_db_session() as db:
        if not get_current_user(request, db):
            return Response(status_code=403)
    data = (data or "")[:QR_MAX_LEN]
    if not data:
        return Response(status_code=404)
    headers = {"Cache-Control": "no-store"}
    if dl:
        headers["Content-Disposition"] = 'attachment; filename="qr.png"'
    return Response(content=_qr_png(data), media_type="image/png", headers=headers)


@router.post("/qr/send")
def qr_send(request: Request, data: str = Form(""), recipient: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        data = (data or "").strip()[:QR_MAX_LEN]
        recipient = (recipient or "").strip()
        if not data:
            flash(request, "請先輸入要轉成 QR 的內容。", "err")
            return RedirectResponse("/tools?tab=qr", 303)
        target = db.query(User).filter(User.username == recipient, User.is_active == True).first()
        if not target or (target.username != user.username and not fs.are_friends(db, user.username, target.username)):
            flash(request, "只能傳給自己或好友。", "err")
            return RedirectResponse("/tools?tab=qr", 303)
        png = _qr_png(data)
        stored = storage.save_bytes(png, ".png")
        size = len(png)
        m = Message(sender=user.username, recipient=target.username, body="［QR Code］" + data[:60], size_bytes=size)
        db.add(m)
        db.flush()
        db.add(Attachment(message_id=m.id, name="qr.png", path=stored, size=size))
        db.commit()
        usage.add_upload(db, user.username, size)
        flash(request, f"QR 已傳送給 {target.username}。", "ok")
        return RedirectResponse(f"/inbox/{target.username}", 303)


# ===== 解 PDF 密碼（使用者已知密碼）=====
PDF_MAX_MB = 50


@router.post("/pdf/unlock")
async def pdf_unlock(request: Request, pdf: UploadFile = File(None), password: str = Form("")):
    with sync_db_session() as db:
        if not get_current_user(request, db):
            return RedirectResponse("/login", 303)
    if not pdf or not pdf.filename:
        flash(request, "請先選擇 PDF 檔。", "err")
        return RedirectResponse("/tools?tab=pdf", 303)
    data = await pdf.read()
    if len(data) > PDF_MAX_MB * 1024 * 1024:
        flash(request, f"檔案太大（上限 {PDF_MAX_MB} MB）。", "err")
        return RedirectResponse("/tools?tab=pdf", 303)
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        flash(request, "無法讀取，請確認這是有效的 PDF 檔。", "err")
        return RedirectResponse("/tools?tab=pdf", 303)
    if not reader.is_encrypted:
        flash(request, "這個 PDF 沒有設密碼，不需解鎖。", "ok")
        return RedirectResponse("/tools?tab=pdf", 303)
    try:
        ok = reader.decrypt(password or "")
    except Exception:
        ok = 0
    if not ok:
        flash(request, "密碼錯誤，請重試。", "err")
        return RedirectResponse("/tools?tab=pdf", 303)
    try:
        writer = PdfWriter()
        for p in reader.pages:
            writer.add_page(p)
        out = io.BytesIO()
        writer.write(out)
    except Exception:
        flash(request, "解鎖時發生問題，這個 PDF 可能無法處理。", "err")
        return RedirectResponse("/tools?tab=pdf", 303)
    base = pdf.filename
    if base.lower().endswith(".pdf"):
        base = base[:-4]
    fname = (base or "document") + "-unlocked.pdf"
    cd = "attachment; filename=\"unlocked.pdf\"; filename*=UTF-8''%s" % quote(fname)
    return Response(content=out.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": cd, "Cache-Control": "no-store"})


# ===== 網頁書籤 =====
BOOKMARK_LIMIT = 100


@router.post("/bookmark/add")
def bookmark_add(request: Request, label: str = Form(""), url: str = Form("")):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        safe = _safe_url(url)
        if not safe:
            flash(request, "請輸入有效網址（需以 http:// 或 https:// 開頭）。", "err")
            return RedirectResponse("/tools?tab=bookmark", 303)
        n = db.query(Bookmark).filter(Bookmark.username == user.username).count()
        if n >= BOOKMARK_LIMIT:
            flash(request, f"書籤已達上限 {BOOKMARK_LIMIT} 個。", "err")
            return RedirectResponse("/tools?tab=bookmark", 303)
        db.add(Bookmark(username=user.username, label=(label or "").strip()[:120] or None,
                        url=safe[:2000], sort_order=n))
        db.commit()
        flash(request, "書籤已新增。", "ok")
        return RedirectResponse("/tools?tab=bookmark", 303)


@router.post("/bookmark/{bid}/delete")
def bookmark_delete(request: Request, bid: int):
    with sync_db_session() as db:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        db.query(Bookmark).filter(Bookmark.id == bid, Bookmark.username == user.username).delete(
            synchronize_session=False)
        db.commit()
        return RedirectResponse("/tools?tab=bookmark", 303)
