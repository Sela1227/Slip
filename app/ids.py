#!/usr/bin/env python3
"""
診間傳遞 - 帳號唯一 ID（12 碼數字，隨機、非連續、含 Luhn 檢查碼防呆）
- 前 11 碼隨機，第 12 碼為 Luhn 檢查碼 → 打錯一碼或相鄰兩碼互換多半會被擋下。
- 以字串保存（保留前導 0）。顯示時用 4-4-4 分組好讀。
"""
import random


def _luhn_residue(number: str) -> int:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10


def luhn_valid(number: str) -> bool:
    return number.isdigit() and len(number) == 12 and _luhn_residue(number) == 0


def gen_id() -> str:
    """產生一組隨機、通過 Luhn 的 12 碼數字 ID。"""
    base = "".join(random.choice("0123456789") for _ in range(11))
    for c in "0123456789":
        if _luhn_residue(base + c) == 0:
            return base + c
    return base + "0"  # 理論上不會走到


def normalize(s: str) -> str:
    """把使用者輸入裡的非數字（空白 / 連字號等）去掉。"""
    return "".join(ch for ch in (s or "") if ch.isdigit())


def fmt(number: str) -> str:
    """顯示用 4-4-4 分組，例如 1234-5678-9012。"""
    n = number or ""
    if len(n) == 12:
        return f"{n[0:4]}-{n[4:8]}-{n[8:12]}"
    return n
