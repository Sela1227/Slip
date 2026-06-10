"""貼圖：掃描 static/stickers/ 下的子資料夾＝貼圖組，組內圖片依檔名排序。
不需改碼即可增刪貼圖組（放資料夾→重新部署）。素材由使用者自備並負責授權。"""
import os
import re

BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "stickers")
EXTS = (".png", ".webp", ".gif", ".apng")


def _display(name):
    """組名若以「數字_」開頭，用數字排序、顯示時去掉前綴。"""
    m = re.match(r"^(\d+)_(.+)$", name)
    return (int(m.group(1)), m.group(2)) if m else (10 ** 9, name)


def packs():
    out = []
    if not os.path.isdir(BASE):
        return out
    for d in sorted(os.listdir(BASE)):
        full = os.path.join(BASE, d)
        if d.startswith(".") or not os.path.isdir(full):
            continue
        items = [f for f in sorted(os.listdir(full))
                 if not f.startswith(".") and f.lower().endswith(EXTS)]
        if not items:
            continue
        order, disp = _display(d)
        out.append({"dir": d, "name": disp, "order": order,
                    "files": [f"{d}/{f}" for f in items]})
    out.sort(key=lambda p: (p["order"], p["name"]))
    return out


def is_valid(rel: str) -> bool:
    """驗證 'pack/file.ext' 安全且存在（擋路徑穿越）。"""
    if not rel or ".." in rel or rel.startswith("/") or "\\" in rel:
        return False
    parts = rel.split("/")
    if len(parts) != 2:
        return False
    pack, fn = parts
    if not fn.lower().endswith(EXTS):
        return False
    return os.path.isfile(os.path.join(BASE, pack, fn))
