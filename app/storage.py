#!/usr/bin/env python3
"""
診間傳遞 - 附件儲存
功能：存上傳檔到 UPLOAD_DIR（隨機檔名）、組路徑、刪檔、判斷是否圖片
適用：搭配 Railway Volume（DB 只記中繼資料，檔案本體放 Volume）

資料表 messages 已預留 attachment_name（原始檔名）/ attachment_path（存的隨機檔名）
/ attachment_size（位元組）。這支只管檔案本體，中繼資料由 router 寫進 DB。
"""
import os
import uuid
import mimetypes

import app.config as config

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def ensure_dir():
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)


def file_path(stored_name: str) -> str:
    return os.path.join(config.UPLOAD_DIR, stored_name)


def save_upload(upload, max_mb=None):
    """存檔。回傳 (stored_name, original_name, size) 或 (None, None, 0) 表示沒有檔案。
    max_mb=None 時用 config.MAX_FILE_MB；超過上限回傳 ("__too_big__", None, size)。"""
    if not upload or not upload.filename:
        return None, None, 0
    data = upload.file.read()
    size = len(data)
    if size == 0:
        return None, None, 0
    limit = config.MAX_FILE_MB if max_mb is None else max_mb
    if limit and limit > 0 and size > limit * 1024 * 1024:
        return "__too_big__", None, size
    ext = os.path.splitext(upload.filename)[1].lower()[:10]
    stored = uuid.uuid4().hex + ext
    ensure_dir()
    with open(file_path(stored), "wb") as f:
        f.write(data)
    return stored, os.path.basename(upload.filename), size


def save_bytes(data: bytes, ext: str = ".png") -> str:
    """把原始位元組存成檔案（如伺服器產生的 QR PNG），回傳儲存檔名。"""
    import uuid
    ensure_dir()
    stored = uuid.uuid4().hex + (ext or "")
    with open(file_path(stored), "wb") as f:
        f.write(data)
    return stored


def save_avatar_original(upload):
    """存上傳的頭像原圖（限圖片）。回傳 stored_name 或 None（沒檔／非圖片）。"""
    if not upload or not upload.filename or not is_image(upload.filename):
        return None
    data = upload.file.read()
    if not data:
        return None
    ext = os.path.splitext(upload.filename)[1].lower()[:10]
    stored = "avo_" + uuid.uuid4().hex + ext
    ensure_dir()
    with open(file_path(stored), "wb") as f:
        f.write(data)
    return stored


def crop_square(orig_name: str, fx: int = 50, fy: int = 50, size: int = 256):
    """把原圖以焦點 (fx, fy)%為中心裁成正方形、縮到 size，存成新檔。回傳新檔名或 None。"""
    from PIL import Image, ImageOps
    src = file_path(orig_name)
    if not os.path.exists(src):
        return None
    try:
        im = Image.open(src)
        im = ImageOps.exif_transpose(im)   # 尊重手機照片方向
        im = im.convert("RGBA")
    except Exception:
        return None
    w, h = im.size
    side = min(w, h)
    cx, cy = w * fx / 100.0, h * fy / 100.0
    left = max(0, min(cx - side / 2.0, w - side))
    top = max(0, min(cy - side / 2.0, h - side))
    im = im.crop((int(left), int(top), int(left + side), int(top + side)))
    if side != size:
        im = im.resize((size, size), Image.LANCZOS)
    stored = "av_" + uuid.uuid4().hex + ".png"
    ensure_dir()
    im.save(file_path(stored), "PNG")
    return stored


def delete_file(stored_name: str):
    if not stored_name:
        return
    try:
        os.remove(file_path(stored_name))
    except OSError:
        pass


def is_image(name: str) -> bool:
    return os.path.splitext(name or "")[1].lower() in IMAGE_EXTS


def guess_type(name: str) -> str:
    return mimetypes.guess_type(name or "")[0] or "application/octet-stream"


def human_size(n: int) -> str:
    n = n or 0
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{round(n / 1024)} KB"
    return f"{round(n / 1024 / 1024, 1)} MB"
