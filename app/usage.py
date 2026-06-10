#!/usr/bin/env python3
"""
診間傳遞 - 每月上傳量統計
功能：記錄每帳號每月上傳的附件位元組數，供個人設定與帳號管理顯示。
獨立於訊息表，所以即使訊息 15 天被清掉，月上傳量仍正確。
"""
from datetime import datetime

from app.models import UploadStat


def current_ym() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def add_upload(db, username: str, nbytes: int) -> None:
    if not nbytes or nbytes <= 0:
        return
    ym = current_ym()
    row = db.query(UploadStat).filter_by(username=username, ym=ym).first()
    if not row:
        row = UploadStat(username=username, ym=ym, bytes=0)
        db.add(row)
    row.bytes += nbytes
    db.commit()


def month_bytes(db, username: str, ym: str = None) -> int:
    ym = ym or current_ym()
    row = db.query(UploadStat).filter_by(username=username, ym=ym).first()
    return row.bytes if row else 0


def month_all(db, ym: str = None) -> dict:
    """{username: bytes} 該月所有帳號的上傳量。"""
    ym = ym or current_ym()
    return {r.username: r.bytes for r in db.query(UploadStat).filter_by(ym=ym).all()}
