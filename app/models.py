#!/usr/bin/env python3
"""
診間傳遞 - 資料表定義
功能：users（帳號）/ messages（訊息，含預留附件欄位）/ send_logs（寄件紀錄）
適用：SQLAlchemy 2.0

刻意不用 PostgreSQL Enum（坑 #2 大小寫陷阱），狀態一律用 Boolean / String。
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    # 為空 = 尚未啟用：本人第一次登入時自設密碼。
    password_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)   # 停用帳號用
    is_admin = Column(Boolean, default=False, nullable=False)
    avatar_path = Column(String(255), nullable=True)           # 顯示用頭像（上傳裁切後 / 隨機檔名）
    avatar_orig = Column(String(255), nullable=True)           # 上傳的原圖（用來重新裁切中心點）
    avatar_pos = Column(String(16), nullable=True)             # 中心點 "x,y"（百分比），預設置中
    avatar_preset = Column(Integer, nullable=True)             # 選用的內建人物頭像編號（0 起）
    theme = Column(String(20), nullable=True)                  # 介面配色主題 key
    friend_id = Column(String(12), unique=True, nullable=True, index=True)  # 唯一 12 碼 ID（加好友用）
    dark = Column(Integer, nullable=True)                      # 1=暗色模式
    note = Column(Text, nullable=True)                         # 給自己的待辦/提醒（顯示在訊息夾上方）
    clipboard = Column(Text, nullable=True)
    last_login = Column(DateTime, nullable=True)            # 最後一次登入時間                    # 常用功能：剪貼簿暫存區
    level = Column(Integer, nullable=True)                     # 等級 1=銀(文字+圖片) 2=金 3=白金（管理者另由 is_admin 控管）
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String(64), nullable=False)                 # 寄件人 username
    recipient = Column(String(64), nullable=False, index=True)  # 收件人 username
    body = Column(Text, nullable=False, default="")
    title = Column(String(200), nullable=True)                  # 收件者自訂標題（不改原內容）
    tags = Column(String(255), nullable=True)                   # 逗號分隔；有 tag 就不自動刪除
    size_bytes = Column(Integer, default=0, nullable=False)     # 容量統計（內容 + 附件）
    sticker = Column(String(255), nullable=True)                # 貼圖相對路徑 pack/file（有值＝貼圖訊息）
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)              # 收件人讀取時間（已讀回條）
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # ── 舊版單一附件欄位（V0.6.0 起改用 attachments 子表，啟動時自動搬移）──
    attachment_name = Column(String(255), nullable=True)
    attachment_path = Column(String(512), nullable=True)
    attachment_size = Column(Integer, default=0, nullable=False)

    # 多附件：一則訊息可掛多個檔。刪訊息時連帶刪附件列（檔案本體另外刪）。
    attachments = relationship("Attachment", cascade="all, delete-orphan",
                               backref="message", order_by="Attachment.id")
    # 註：我的最愛刻意「不」用 relationship cascade —— 收藏是獨立快照，刪訊息不連動刪最愛。


class Attachment(Base):
    __tablename__ = "attachments"
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    name = Column(String(255), nullable=False)   # 原始檔名
    path = Column(String(512), nullable=False)   # 存在 UPLOAD_DIR 的隨機檔名
    size = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SendLog(Base):
    __tablename__ = "send_logs"
    id = Column(Integer, primary_key=True)
    sender = Column(String(64), nullable=False, index=True)
    recipient = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class Friendship(Base):
    """雙向好友關係，用排序後的一對 username 存一列（user_low < user_high）。"""
    __tablename__ = "friendships"
    id = Column(Integer, primary_key=True)
    user_low = Column(String(64), nullable=False, index=True)
    user_high = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Invite(Base):
    """加好友邀請連結：一次性、會過期。used_at 有值 = 已用過。"""
    __tablename__ = "invites"
    id = Column(Integer, primary_key=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    inviter = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    used_by = Column(String(64), nullable=True)


class UploadStat(Base):
    """每帳號每月的上傳檔案量（位元組）。獨立記錄，不隨訊息 15 天清除而消失。"""
    __tablename__ = "upload_stats"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)
    ym = Column(String(7), nullable=False, index=True)   # 'YYYY-MM'
    bytes = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("username", "ym", name="uq_upload_user_ym"),)


class Favorite(Base):
    """我的最愛：收藏時把訊息內容複製一份（快照），所以原對話刪了，最愛仍保留，要自己手動刪。
    message_id 只是軟參照（無 FK 連動），用來顯示附件與『前往對話』。"""
    __tablename__ = "favorites"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)
    message_id = Column(Integer, nullable=True, index=True)
    sender = Column(String(64), nullable=True)          # 原寄件人
    other = Column(String(64), nullable=True)           # 對話對象（前往對話用）
    title = Column(String(200), nullable=True)          # 最愛自己的標題（可在最愛區設）
    body = Column(Text, nullable=True)                  # 內容快照
    msg_created_at = Column(DateTime, nullable=True)    # 原訊息時間
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # 收藏時間
    __table_args__ = (UniqueConstraint("username", "message_id", name="uq_fav_user_msg"),)


class Signup(Base):
    """自助註冊連結：管理者產生一次性 token，對方開連結自己設定帳號與密碼。"""
    __tablename__ = "signups"
    id = Column(Integer, primary_key=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    created_by = Column(String(64), nullable=False)      # 哪位管理者產生的
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    used_by = Column(String(64), nullable=True)          # 用這個連結建立的帳號名


class FriendRequest(Base):
    """好友邀請（站內用 ID 送出，對方同意才互加）。存在即代表 pending。"""
    __tablename__ = "friend_requests"
    id = Column(Integer, primary_key=True)
    from_user = Column(String(64), nullable=False, index=True)
    to_user = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("from_user", "to_user", name="uq_freq_from_to"),)


class Snippet(Base):
    """個人常用片語／臨時剪貼簿：每人多條短文字，可一鍵複製，也可在輸入框一鍵插入。"""
    __tablename__ = "snippets"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)
    label = Column(String(80), nullable=True)                  # 片語名稱（顯示在快捷鈕上）
    text = Column(Text, nullable=False)                        # 片語內容（插入/複製的文字）
    sort_order = Column(Integer, nullable=False, default=0)     # 排序
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ShortLink(Base):
    """縮網址：把長網址對應到短碼，/s/<code> 轉址。"""
    __tablename__ = "short_links"
    id = Column(Integer, primary_key=True)
    code = Column(String(16), unique=True, nullable=False, index=True)
    url = Column(Text, nullable=False)
    created_by = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PrivatePair(Base):
    """私密對話：此配對的訊息僅保留 1 天（雙方皆是），由管理者設定。"""
    __tablename__ = "private_pairs"
    id = Column(Integer, primary_key=True)
    user_low = Column(String(64), nullable=False, index=True)
    user_high = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("user_low", "user_high", name="uq_private_pair"),)


class Announcement(Base):
    """公告：管理者張貼，所有使用者看得到（顯示最新一則 active）。"""
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Bookmark(Base):
    """網頁書籤：每位使用者自己的常用網址。"""
    __tablename__ = "bookmarks"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False, index=True)
    label = Column(String(120), nullable=True)
    url = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
