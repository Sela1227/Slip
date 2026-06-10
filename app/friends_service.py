#!/usr/bin/env python3
"""
診間傳遞 - 好友與邀請邏輯
功能：好友查詢 / 加 / 移除；邀請連結產生 / 列出 / 作廢 / 接受
適用：被 routers/friends.py 與 routers/messages.py 共用

好友是雙向關係，用排序後的一對 username 存一列（user_low < user_high）。
邀請連結一次性 + 會過期：used_at 有值 = 用過；超過 expires_at = 過期。
"""
import secrets
from datetime import datetime, timedelta

import app.config as config
import app.ids as ids
from app.models import User, Friendship, Invite, FriendRequest


def unique_friend_id(db) -> str:
    """產生一組在資料庫中唯一的 12 碼 ID。"""
    fid = ids.gen_id()
    while db.query(User.id).filter(User.friend_id == fid).first():
        fid = ids.gen_id()
    return fid


def _pair(a: str, b: str):
    return (a, b) if a < b else (b, a)


def are_friends(db, a: str, b: str) -> bool:
    lo, hi = _pair(a, b)
    return db.query(Friendship).filter(
        Friendship.user_low == lo, Friendship.user_high == hi
    ).first() is not None


def friends_of(db, username: str) -> list:
    rows = db.query(Friendship).filter(
        (Friendship.user_low == username) | (Friendship.user_high == username)
    ).all()
    return sorted({(r.user_high if r.user_low == username else r.user_low) for r in rows})


def add_friend(db, a: str, b: str) -> None:
    if a == b or are_friends(db, a, b):
        return
    lo, hi = _pair(a, b)
    db.add(Friendship(user_low=lo, user_high=hi))


def remove_friend(db, a: str, b: str) -> None:
    lo, hi = _pair(a, b)
    db.query(Friendship).filter(
        Friendship.user_low == lo, Friendship.user_high == hi
    ).delete(synchronize_session=False)
    db.commit()


# === 邀請連結 ===
def create_invite(db, inviter: str) -> Invite:
    inv = Invite(
        token=secrets.token_urlsafe(24),
        inviter=inviter,
        expires_at=datetime.utcnow() + timedelta(hours=config.INVITE_EXPIRE_HOURS),
    )
    db.add(inv)
    db.commit()
    return inv


def active_invites(db, inviter: str) -> list:
    """未使用、未過期的邀請連結（最新在上）。"""
    now = datetime.utcnow()
    return (db.query(Invite)
            .filter(Invite.inviter == inviter, Invite.used_at.is_(None), Invite.expires_at > now)
            .order_by(Invite.created_at.desc()).all())


def revoke_invite(db, inviter: str, iid: int) -> None:
    db.query(Invite).filter(Invite.id == iid, Invite.inviter == inviter)\
        .delete(synchronize_session=False)
    db.commit()


def consume_invite(db, token: str, accepter: str):
    """接受邀請。回傳 (成功, 訊息)。"""
    inv = db.query(Invite).filter(Invite.token == token).first()
    if not inv:
        return False, "邀請連結無效。"
    if inv.used_at:
        return False, "這個邀請連結已被使用過。"
    if inv.expires_at < datetime.utcnow():
        return False, "邀請連結已過期，請對方重新產生一個。"
    if inv.inviter == accepter:
        return False, "這是你自己的邀請連結，無法加自己為好友。"
    inviter = db.query(User).filter(User.username == inv.inviter, User.is_active == True).first()
    if not inviter:
        return False, "邀請人的帳號已不存在或已停用。"
    if are_friends(db, inv.inviter, accepter):
        inv.used_at = datetime.utcnow()
        inv.used_by = accepter
        db.commit()
        return True, f"你和 {inv.inviter} 已經是好友了。"
    add_friend(db, inv.inviter, accepter)
    inv.used_at = datetime.utcnow()
    inv.used_by = accepter
    db.commit()
    return True, f"已和 {inv.inviter} 成為好友。"


# === 用 ID 加好友：邀請（pending 即一列）===
def request_by_id(db, me: str, raw_id: str):
    """以對方的 12 碼 ID 送出好友邀請。回傳 (成功, 訊息)。"""
    fid = ids.normalize(raw_id)
    if not ids.luhn_valid(fid):
        return False, "ID 格式不正確，請確認是否打錯（12 碼數字）。"
    target = db.query(User).filter(User.friend_id == fid, User.is_active == True).first()
    if not target:
        return False, "找不到這個 ID 的帳號。"
    if target.username == me:
        return False, "這是你自己的 ID。"
    if are_friends(db, me, target.username):
        return False, f"你和 {target.username} 已經是好友了。"
    # 對方已先邀請我 → 直接成為好友
    incoming = db.query(FriendRequest).filter(
        FriendRequest.from_user == target.username, FriendRequest.to_user == me).first()
    if incoming:
        add_friend(db, me, target.username)
        db.delete(incoming)
        db.commit()
        return True, f"已和 {target.username} 成為好友。"
    if db.query(FriendRequest).filter(
            FriendRequest.from_user == me, FriendRequest.to_user == target.username).first():
        return False, f"你已送出邀請給 {target.username}，等待對方同意。"
    db.add(FriendRequest(from_user=me, to_user=target.username))
    db.commit()
    return True, f"已送出好友邀請給 {target.username}，待對方同意。"


def incoming_requests(db, me: str) -> list:
    return (db.query(FriendRequest).filter(FriendRequest.to_user == me)
            .order_by(FriendRequest.created_at.desc()).all())


def outgoing_requests(db, me: str) -> list:
    return (db.query(FriendRequest).filter(FriendRequest.from_user == me)
            .order_by(FriendRequest.created_at.desc()).all())


def accept_request(db, me: str, rid: int):
    req = db.query(FriendRequest).filter(FriendRequest.id == rid, FriendRequest.to_user == me).first()
    if not req:
        return False, "找不到這個邀請。"
    add_friend(db, req.from_user, me)
    db.delete(req)
    db.commit()
    return True, f"已和 {req.from_user} 成為好友。"


def decline_request(db, me: str, rid: int):
    """拒絕（我是被邀請方）或取消（我是邀請方）。"""
    db.query(FriendRequest).filter(
        FriendRequest.id == rid,
        (FriendRequest.to_user == me) | (FriendRequest.from_user == me)
    ).delete(synchronize_session=False)
    db.commit()


def cleanup_user(db, username: str) -> None:
    """刪除帳號時，清掉與此人相關的好友關係、邀請與好友邀請。"""
    db.query(Friendship).filter(
        (Friendship.user_low == username) | (Friendship.user_high == username)
    ).delete(synchronize_session=False)
    db.query(Invite).filter(
        (Invite.inviter == username) | (Invite.used_by == username)
    ).delete(synchronize_session=False)
    db.query(FriendRequest).filter(
        (FriendRequest.from_user == username) | (FriendRequest.to_user == username)
    ).delete(synchronize_session=False)
