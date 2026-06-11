# SELA-logo-prompt.md — Slip 絲利普

> 由 Claude 依 SELA-Starter-Kit V1.14.1 §17 自動工作流產出。
> 給其他 AI（Midjourney / DALL-E / Adobe Firefly 等）生 logo 用。

## 〇、產出資訊（讓 SELA 驗證）

- **專案名稱：** Slip 絲利普（診間傳遞）
- **產出日期：** 2026-06-10
- **使用 Kit 版本：** V1.14.1
- **使用範本：** B — 醫療專業型
- **資訊來源：** 從專案 CLAUDE.md 自動萃取

## 一、萃取的設計 context

- **這 app 做什麼：** 多帳號跨裝置的自我傳訊與診間交班工具——每個帳號可把訊息／檔案傳給「自己」在不同裝置間同步，也可好友互傳，主打診間之間的交班與暫存。
- **給誰用：** 台灣的醫療人員（醫師、護理師等小團隊），臨床工作情境。
- **解決什麼痛點：** 不想用私人 LINE 處理工作訊息；需要在診間／手機／電腦之間快速帶走文字與檔案、做交班。
- **情緒基調：** 親和但專業、可靠、安靜——簡潔不炫技（無 emoji、北歐配色、SVG 線性圖示），給人「隨時在那、值得信任」的工具感。
- **使用情境：** 上班時在診間之間、手機與電腦之間快速傳一則訊息／一張單子／一個檔案，或暫存待會要用的資料。

## 二、自動決策

### 範本類型
- **選定：** B — 醫療專業型
- **理由：** Slip 是臨床交班／訊息工具，使用者是醫療人員；Kit §14.3 也直接把 Slip 列為此型範例（溝通類工具用「對折信件／紙條」為主體）。

### 壁虎/蜥蜴繼承
- **決定：** NO（不繼承）
- **理由：** 依 Kit §13.2 判斷流程與範例對照——「訊息傳遞」精神跟壁虎「家中守護」涵義不直接相關，應改用紙條／信封／訊息相關元素，避免稀釋 SELA 主品牌的壁虎獨特性。

### 背景色提案
- **候選 1：** Nordic 霧藍變體 `#5B8FB9`（臨床面、稍亮、帶一點親和與信任感）
- **候選 2：** 北歐霧藍 `#5A7A8B`（工具預設、更沉穩內斂）
- **理由：** 醫療專業型避開愛馬仕橘（橘屬溫暖／工具主品牌色，醫療需冷靜可信）；選北歐藍系既符合臨床氣質，也與作為品牌歸屬印記的 SELA 橘明顯區隔，避免 dock／分頁撞色。

## 三、完整 Prompt（複製貼上給其他 AI）

```
A flat 2D vector logo design in a 1:1 square aspect ratio.

CORE STYLE (inherited from SELA brand DNA):
- Square frame, corner radius about 15% of edge (rounded square)
- Single solid background color (no gradients)
- Pure white silhouette for the main subject
- Bold sans-serif app name at bottom, all caps
- Subject occupies top 60-70% of frame
- App name occupies bottom 30-40% of frame
- Padding: 8-15% margin between subject and frame edge
- No shadows, no gradients, no 3D effect, no glow, no texture, no embossing
- Sharp clean edges, suitable for favicon at 16x16 pixels
- Quiet, reliable, tool-like feeling — not flashy, not aggressive

REFERENCE STYLE: Sibling to SELA brand logo (orange #F36825 background, white gecko + "SELA" text, rounded square frame).
This new logo should feel like a family member — same design language, different subject and color.

ADDITIONAL FOR MEDICAL/CLINICAL TYPE:
- Subject should evoke clinical professionalism without being cold
- Avoid red crosses, syringes, or overly clinical symbols (too generic)
- Prefer abstract gestures of "navigation / guidance / care / connection"
- Tone: trustworthy, calm, professional, soft enough for patients

SUBJECT: a single folded paper note / message slip, clean white silhouette, shown mid-motion as if being passed from hand to hand. The folded paper has a gentle curl that subtly echoes the letter "S" (for Slip), suggesting a small clinical handoff note travelling between rooms. Simple, minimal, instantly readable even at tiny sizes. No text on the paper, no clip, no envelope clutter.

APP NAME: SLIP   (bold, all-caps, sans-serif, white, centered at the bottom)

BACKGROUND COLOR: Nordic blue #5B8FB9   (alternative: Nordic misty blue #5A7A8B)

GECKO INHERITANCE: NO — medical/communication tool; uses a paper-slip motif instead of the SELA gecko.
```

## 四、給 SELA 的備註

- 拿到原圖後 → 走 Kit §10.2 工作流 B（我幫你優化轉檔、去背、規整 1:1、用 Pillow 縮出 16/32/48/64/128/256/512/1024 多解析度 + `favicon.ico` + `apple-touch-icon` 180×180 + 客製 `site.webmanifest`，再套進 `static/` 與 `<head>`、README 頂部主視覺，SELA logo 退為 footer/About 的品牌歸屬印記）。
- 如果 prompt 不滿意 → 跟我說，我重生（不必改 CLAUDE.md，回頭看它就能重跑）。
- 想改範本類型 / 顏色 / 壁虎繼承決定 → 告訴我「改 X 為 Y」，我重產這份檔。
- 想試「會動的 S 紙條」動態 favicon、或紙條換成「對話泡泡＋紙條」複合主體，也可以提，我調整 SUBJECT 段重生。
