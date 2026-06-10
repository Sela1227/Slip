#!/usr/bin/env python3
"""
診間傳遞 - 資料庫連線與初始化
功能：engine / session context manager / 建表 + 確保管理者帳號存在
適用：SQLAlchemy 2.0 + PostgreSQL（Railway）/ SQLite（本機）

用 create_all 自動建表，不用 Alembic：診間 2-3 人、schema 穩定，符合不過度工程原則
（tech-stack-lessons §1.1）。日後若加第二項資料結構或頻繁改 schema 再切 Alembic。
"""
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

import app.config as config
from app.models import Base, User, Message, Attachment

# SQLite 需要這個參數才能多執行緒使用；PostgreSQL 不需要。
connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def sync_db_session():
    """統一管理 session 開關，避免 connection pool 漸耗盡（坑 #24）。

    用法：with sync_db_session() as db: ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_columns():
    """create_all 不會幫『既有表』加新欄位（坑 #4）。後加的欄位在這裡用 ALTER 補上。
    用 inspector 先檢查，避開各資料庫 IF NOT EXISTS 語法差異。"""
    insp = inspect(engine)
    tables = insp.get_table_names()
    wants = {
        "users": [("avatar_path", "VARCHAR(255)"), ("avatar_orig", "VARCHAR(255)"),
                  ("avatar_pos", "VARCHAR(16)"), ("avatar_preset", "INTEGER"), ("theme", "VARCHAR(20)"),
                  ("friend_id", "VARCHAR(12)"), ("level", "INTEGER"), ("dark", "INTEGER"), ("note", "TEXT"), ("clipboard", "TEXT"), ("last_login", "TIMESTAMP")],
        "snippets": [("label", "VARCHAR(80)"), ("sort_order", "INTEGER")],
        "messages": [("title", "VARCHAR(200)"), ("tags", "VARCHAR(255)"), ("read_at", "TIMESTAMP"), ("sticker", "VARCHAR(255)")],
        "signups": [("expires_at", "TIMESTAMP"), ("used_at", "TIMESTAMP"), ("used_by", "VARCHAR(64)")],
    }
    for table, cols in wants.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        for name, ddl in cols:
            if name not in existing:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _migrate_legacy_attachments():
    """V0.6.0：把舊版單一附件欄位搬進 attachments 子表，搬完清掉舊欄位避免重複顯示。"""
    with sync_db_session() as db:
        legacy = db.query(Message).filter(Message.attachment_path.isnot(None)).all()
        for m in legacy:
            has = db.query(Attachment).filter(Attachment.message_id == m.id).first()
            if not has:
                db.add(Attachment(message_id=m.id, name=m.attachment_name or "附件",
                                  path=m.attachment_path, size=m.attachment_size or 0))
            m.attachment_path = None
            m.attachment_name = None
        db.commit()


def _counterpart_name(me, sender, recipient):
    if sender == me and recipient == me:
        return me
    return recipient if sender == me else sender


def _as_dt(v):
    """SQLite 讀出的時間是字串、Postgres 是 datetime；統一轉成 datetime。"""
    if v is None or isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("T", " ").split(".")[0])
    except ValueError:
        return None


def _read_old_favorites_then_drop():
    """V0.10.0：舊 favorites 表（含 FK、無快照欄位）→ 讀出、建快照、DROP，等 create_all 重建新表。
    回傳要回填的快照 list 或 None。"""
    insp = inspect(engine)
    if "favorites" not in insp.get_table_names():
        return None
    cols = {c["name"] for c in insp.get_columns("favorites")}
    if "body" in cols:   # 已是新 schema
        return None
    snaps = []
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT username, message_id, created_at FROM favorites")).fetchall()
        for username, mid, created_at in rows:
            mrow = conn.execute(text(
                "SELECT sender, recipient, title, body, created_at FROM messages WHERE id=:i"
            ), {"i": mid}).fetchone()
            if not mrow:
                continue
            sender, recipient, title, body, mcreated = mrow
            snaps.append({"username": username, "message_id": mid, "sender": sender,
                          "other": _counterpart_name(username, sender, recipient),
                          "title": title, "body": body,
                          "msg_created_at": _as_dt(mcreated),
                          "created_at": _as_dt(created_at) or datetime.utcnow()})
        conn.execute(text("DROP TABLE favorites"))
    return snaps


def _backfill_friend_ids():
    """給還沒有 friend_id 的帳號補上唯一 12 碼 ID；既有帳號預設等級 2（維持原有能力）。"""
    import app.ids as ids
    from app.models import User
    with sync_db_session() as db:
        existing = {r[0] for r in db.query(User.friend_id).filter(User.friend_id.isnot(None)).all()}
        for u in db.query(User).filter(User.friend_id.is_(None)).all():
            fid = ids.gen_id()
            while fid in existing:
                fid = ids.gen_id()
            existing.add(fid)
            u.friend_id = fid
        # 等級（1 銀 / 2 金 / 3 白金）。舊版「進階(2)」一次性升白金(3)；用「是否已有白金」當旗標避免重跑
        has_platinum = db.query(User.id).filter(User.level == 3).first() is not None
        if not has_platinum:
            db.query(User).filter(User.level == 2).update({User.level: 3}, synchronize_session=False)
        db.query(User).filter(User.is_admin == True).update({User.level: 3}, synchronize_session=False)
        db.query(User).filter(User.level.is_(None)).update({User.level: 1}, synchronize_session=False)
        db.commit()


def init_db():
    """建立資料表，補既有表缺的欄位，搬移舊附件 / 舊收藏，並確保管理者帳號存在。"""
    old_favs = _read_old_favorites_then_drop()
    Base.metadata.create_all(engine)
    _ensure_columns()
    _migrate_legacy_attachments()
    _backfill_friend_ids()
    # 既有片語補 sort_order（用 id 當預設順序）
    with engine.begin() as conn:
        try:
            conn.execute(text("UPDATE snippets SET sort_order = id WHERE sort_order IS NULL"))
        except Exception:
            pass
    if old_favs:
        from app.models import Favorite
        with sync_db_session() as db:
            for s in old_favs:
                db.add(Favorite(**s))
            db.commit()
    with sync_db_session() as db:
        admin = db.query(User).filter(User.username == config.ADMIN_USERNAME).first()
        if not admin:
            import app.ids as ids
            taken = {r[0] for r in db.query(User.friend_id).filter(User.friend_id.isnot(None)).all()}
            fid = ids.gen_id()
            while fid in taken:
                fid = ids.gen_id()
            db.add(User(username=config.ADMIN_USERNAME, password_hash=None,
                        is_active=True, is_admin=True, friend_id=fid, level=3))
            db.commit()
        elif not admin.is_admin:
            admin.is_admin = True
            db.commit()
