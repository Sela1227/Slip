#!/usr/bin/env python3
"""
診間傳遞 - 內建人物頭像（北歐扁平風，無 emoji，純 SVG）
15 種：柔和北歐配色 + 不同髮型 / 膚色 / 衣色組合，臉部留白（簡潔剪影）。
preset_svg(i) 回傳一張 100x100 的圓形頭像 SVG 字串。
畫法：肩 → 頭髮 → 臉（臉蓋住頭髮下半，頭髮就成了上方的髮型）。
"""

PRESET_COUNT = 15

# (背景, 膚色, 髮色, 衣色, 髮型 0-4)
# 髮型：0 短髮 / 1 側分 / 2 長髮 / 3 包頭 / 4 平頭
_P = [
    ("#cdd9e3", "#e9c9a6", "#3a3330", "#5a7a8b", 0),
    ("#d6e0d2", "#d8a87b", "#6b4a2b", "#7a8a6b", 2),
    ("#e6d7cf", "#b07d56", "#2b2b2b", "#a96b4f", 1),
    ("#d9cdd6", "#f0d9c0", "#b0894d", "#6f5a82", 3),
    ("#cfd8d6", "#8a5a3b", "#231f1d", "#4f6b6b", 0),
    ("#e3d5c8", "#e9c9a6", "#8a8f96", "#9a7b6b", 2),
    ("#cdd9e3", "#d8a87b", "#5a3a2a", "#5a7a8b", 4),
    ("#d6e0d2", "#b07d56", "#3a3330", "#7a8a6b", 3),
    ("#e6d7cf", "#f0d9c0", "#c97b4a", "#a96b4f", 1),
    ("#d9cdd6", "#8a5a3b", "#2b2b2b", "#6f5a82", 2),
    ("#cfd8d6", "#e9c9a6", "#6b4a2b", "#4f6b6b", 0),
    ("#e3d5c8", "#d8a87b", "#b0894d", "#9a7b6b", 1),
    ("#cdd9e3", "#b07d56", "#8a8f96", "#5a7a8b", 4),
    ("#d6e0d2", "#f0d9c0", "#5a3a2a", "#7a8a6b", 3),
    ("#e6d7cf", "#8a5a3b", "#3a3330", "#a96b4f", 2),
]


def _hair(style, hair):
    if style == 0:   # 短髮
        return f'<circle cx="50" cy="42" r="21" fill="{hair}"/>'
    if style == 1:   # 側分（偏一邊 + 一側鬢角）
        return (f'<circle cx="50" cy="41" r="21" fill="{hair}"/>'
                f'<rect x="29" y="40" width="9" height="22" rx="4" fill="{hair}"/>')
    if style == 2:   # 長髮（後方一片垂到肩）
        return f'<rect x="28" y="34" width="44" height="50" rx="21" fill="{hair}"/>'
    if style == 3:   # 包頭（短帽 + 頂上小髻）
        return (f'<circle cx="50" cy="42" r="21" fill="{hair}"/>'
                f'<circle cx="50" cy="21" r="7.5" fill="{hair}"/>')
    # 4 平頭（薄薄一層）
    return f'<path d="M29 46 A21 21 0 0 1 71 46 Z" fill="{hair}"/>'


def preset_svg(i: int) -> str:
    bg, skin, hair, cloth, style = _P[i % PRESET_COUNT]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">'
        '<defs><clipPath id="c"><circle cx="50" cy="50" r="50"/></clipPath></defs>'
        f'<circle cx="50" cy="50" r="50" fill="{bg}"/>'
        '<g clip-path="url(#c)">'
        f'<ellipse cx="50" cy="99" rx="31" ry="25" fill="{cloth}"/>'
        f'{_hair(style, hair)}'
        f'<circle cx="50" cy="50" r="17" fill="{skin}"/>'
        '</g></svg>'
    )
