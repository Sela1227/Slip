# CLAUDE.md — Slip 診間傳遞

> **這份是給下次 Claude 看的工作上下文，不是文件。**
> 判斷標準只有一個：下次 Claude 讀完，能不能直接動手？
> 維護章法見 `SELA-Starter-Kit/conventions/CLAUDE-MD-章法.md`，每升一版至少更新三處：踩過的坑、版本歷程、下版候選工作。

---

## 〇、當前狀態

- **版本：** V1.12.0
- **狀態：** 可運作，煙霧測試全綠；Railway build 問題已解（坑 #1），尚未正式上線
- **一句話定位：** 診間用的「傳給自己 / 傳給同事」交接工具，多帳號、共用電腦友善、訊息 7 天自動清除，部署在 Railway。英文名 Slip，畫面顯示「Slip 診間傳遞」
- **技術棧：** Python 3.12 + FastAPI 0.115 + SQLAlchemy 2.0 + PostgreSQL（Railway）+ Jinja2 SSR
- **入口點：** `app/main.py` 的 `app`（Procfile 用 `uvicorn app.main:app`；本機 `python run.py`）

---

## 一、技術棧決策（為什麼這樣選）

| 選擇 | 替代品 | 選這個的理由 |
|------|--------|------------|
| FastAPI + Jinja2 SSR | React PWA / 純靜態 | 需要登入帳密 + server 端資料庫，但畫面單純（表單 + 列表），SSR 最少檔案、診間好維護、載入快 |
| PostgreSQL（Railway）| SQLite 檔 | Railway 重啟會清掉本地檔，要保留訊息必須用持久 DB（坑 P1） |
| `create_all` 自動建表 | Alembic | 診間 2-3 人、schema 穩定，不過度工程（tech-stack-lessons §1.1）。切換時機見坑 #4 |
| bcrypt 直接用 | passlib[bcrypt] | 少一層相依，且避開坑 #28（bcrypt 4.1+ 砸壞 passlib）|
| 多帳號定址訊息 | 共用白板 | SELA 要求可傳給自己也可指定收件人（醫師 ↔ 個管師） |

> 提案三行（V0.1.0 起手）：
> 提案：FastAPI + Jinja2 SSR + PostgreSQL。
> 理由：基於需求 (1) 共用電腦要帳密登入 (2) 訊息要跨電腦持久保存 (3) 畫面只是表單與列表、不需 SPA 互動。
> 延續性：Railway + FastAPI 過去 6 個專案用過，部署測試流程一致。
>
> 改技術棧 = 大版本升級，記得回頭更新這張表並在「八、升版必讀」開 ⚠ 章節。

---

## 二、業務對映表

（V0.1.0 暫無 — 業務概念與程式幾乎 1:1（訊息 = Message、帳號 = User），結構穩定後若出現「同概念散在 3+ 檔」再立表。）

---

## 三、關鍵檔案路徑

> 寫「改 X 功能 → 動 Y 檔案」，不列 tree（那是 README 的事）。

| 想改什麼 | 動哪些檔 |
|---------|---------|
| 登入 / 首次設密碼 / 改密碼 | `app/routers/auth.py` |
| 對話列表 / 對話內訊息 / 撰寫傳送 / 寄件紀錄 | `app/routers/messages.py` |
| 帳號管理（新增 / 停用 / 重設 / 刪除） | `app/routers/admin.py` |
| 好友頁 / 邀請連結 / 接受 / 移除好友 | `app/routers/friends.py` |
| 好友與邀請邏輯（誰是好友、能不能寄） | `app/friends_service.py` |
| 多檔附件存檔 / 判斷圖片 | `app/storage.py`（檔案放 `UPLOAD_DIR`，DB 只記中繼）|
| 多附件子表（一則訊息多檔） | `app/models.py` 的 `Attachment` |
| 每月上傳量統計 | `app/usage.py` + `app/models.py` 的 `UploadStat` |
| 標題 / 標籤 / 收藏 路由 | `app/routers/messages.py`（/message/{id}/title、/tags、/favorite、/favorites）|
| 我的最愛資料 | `app/models.py` 的 `Favorite`（每人各自收藏）|
| 標籤/收藏 → 不自動刪 | `app/security.py` 的 `purge_old`（跳過有 tag 或被收藏的）|
| 自助註冊（產生連結 / 撤銷） | `app/routers/admin.py`（/admin/signup*）+ `_signup_link` |
| 自助註冊（公開頁 / 建帳號） | `app/routers/auth.py`（/signup/{token}）+ `templates/signup.html` + `app/models.py` 的 `Signup` |
| 頭像（上傳裁切/內建/中心點/主題）、個人設定 | `app/routers/auth.py`（/avatar*、/theme、/settings）+ `app/avatars.py`（內建頭像）+ `app/storage.py`（crop_square）|
| 後加欄位補強（坑 #3） | `app/database.py` 的 `_ensure_columns()` |
| 配色 / 版型（北歐主題） | `static/style.css` 的 `:root` |
| 介面 icon（SVG，不用 emoji） | `templates/icons.html` 的 `icon()` macro |
| 統一認證、閒置逾時、頁面共用 context | `app/dependencies.py` |
| 密碼雜湊、過期清除、容量統計 | `app/security.py` |
| 保留天數 / 閒置分鐘 / 容量上限 / 版本號 | `app/config.py` |
| 共用 templates 實例（坑 #32）| `app/template_env.py` |

---

## 四、踩過的坑（編號累積，永不重排）

> 三段式：症狀 → 原因 → 做法。環境/語法類放前面，業務類放後面。
> V0.1.0 是種子坑（從跨專案坑庫挑 FastAPI 相關預埋），用 P 編號；遇到本專案專屬新坑時從 #1 起編。

1. **Railway railpack + mise 裝 Python 卡在 GitHub attestation（V0.1.2 實際踩到）**
   - 症狀：Railway build 失敗 `mise ERROR Failed to install core:python@3.12.8: No GitHub artifact attestations found for python@3.12.8`
   - 原因：Railway 新建置器改用 railpack + mise（2026.6.0）。mise 近期預設會驗證 Python 的 GitHub artifact attestation，但 cpython 釋出版多半沒簽 → 安裝 Python 那步直接掛。跟我們的程式碼無關
   - 做法：Railway Variables 加 `MISE_PYTHON_GITHUB_ATTESTATIONS=false`（錯誤訊息本身建議的開關），重新部署即可。已寫進 README 部署變數表
   - 備註：任何當前（2026/06）在 Railway 跑 Python 的專案都會中，已列入 SELA-handoff.md 建議回流 Kit

2. **反向代理後面 `request.base_url` 是 http，產生的連結會壞（V0.3.0 好友邀請連結踩到）**
   - 症狀：好友邀請連結若用 `request.base_url` 直接組，會得到 `http://...`，分享出去可能連不上 / 不安全
   - 原因：Railway 在反向代理後面，uvicorn 預設只信任 127.0.0.1 的 forwarded header，所以 `request.url.scheme` 是 http
   - 做法：(1) Procfile 加 `--proxy-headers --forwarded-allow-ips=*` 讓 uvicorn 信任 Railway 的 `X-Forwarded-Proto`；(2) 組連結時再保險一次：非 localhost 的 http 一律改成 https（見 `app/routers/friends.py` 的 `_invite_link`）

3. **後加欄位 create_all 不會幫既有表補（V0.5.0 加 avatar_path 踩到，對應 Kit 坑 #4）**
   - 症狀：給 User 加 `avatar_path` 後，舊的線上資料庫查詢炸 `column users.avatar_path does not exist`
   - 原因：`Base.metadata.create_all` 只建「不存在的表」，不會 ALTER 已存在的表加欄位
   - 做法：`app/database.py` 的 `_ensure_columns()` 在啟動時用 inspector 檢查、缺就 `ALTER TABLE users ADD COLUMN`。新增後加欄位時，都在這裡補一行即可（這專案夠小，不上 Alembic）

4. **時間全用 UTC 存、顯示沒轉時區（V0.11.1）**
   - 症狀：下午 6 點傳的訊息顯示成早上 10 點（差 8 小時）
   - 原因：到處用 `datetime.utcnow()` 存 UTC，模板直接 `created_at.strftime()` 等於顯示 UTC
   - 做法：`app/template_env.py` 的 `localtime()`（ZoneInfo `APP_TZ`，後備固定 +8）把 UTC 轉在地時間；模板所有時間改 `{{ localtime(x).strftime(...) }}`。requirements 加 `tzdata` 確保雲端找得到時區資料

6. **頭像換了別人看不到（固定網址 + 快取，V0.12.1）**
   - 症狀：某人上傳/換頭像，其他人仍看到舊圖或字首
   - 原因：`/avatar/{帳號}` 網址固定不變，瀏覽器把舊圖、甚至「沒頭像」的 404 快取住
   - 做法：所有頭像回應一律 `Cache-Control: no-store`（含 404）。規模小，不快取的成本可忽略

5. **附件 / 頭像檔案部署後消失（與 P1 同源，V0.11.1 再次踩到）**
   - 症狀：重新部署後，先前傳的圖片變破圖、頭像不見
   - 原因：圖片/頭像存在容器檔案系統（`UPLOAD_DIR`），Railway 每次部署/重啟都清空——除非掛 Volume
   - 做法：在 Railway 掛 Volume（例如 /data），設 `UPLOAD_DIR=/data/uploads`、`CAPACITY_LIMIT_MB=Volume 大小`。已消失的檔案無法復原；程式端已讓破圖退回字首圓 / 顯示「圖片已遺失」

P1. **Railway 檔案系統重啟會清空**
   - 症狀：部署 / 重啟後訊息與帳號全消失
   - 原因：Railway 容器檔案系統非持久，SQLite 檔會被還原
   - 做法：用 Railway PostgreSQL（`DATABASE_URL` 自動注入）；本機才退回 SQLite

P2. **`requirements.txt` 浮動版本 + 雲端 rebuild 破壞 API（坑 #46）**
   - 症狀：某天 Railway 自己 rebuild 後整站 500
   - 原因：`>=` 沒鎖上限，rebuild 拉到新版套件，舊寫法不相容
   - 做法：全部用 `==` 精確鎖版本（已照做）

P3. **Starlette 1.x 的 `TemplateResponse` 簽名（坑 #46 同源）**
   - 症狀：`TypeError: unhashable type: 'dict'`
   - 原因：新版第一參數是 `request`，舊寫法 `TemplateResponse("x.html", {...})` 把 dict 當快取 key
   - 做法：統一走 `app/template_env.py` 的 `render()`，內部用 `TemplateResponse(request, name, ctx)`

P4. **bcrypt 4.1+ 砸壞 passlib（坑 #28）**
   - 症狀：啟動 `AttributeError: module 'bcrypt' has no attribute '__about__'`
   - 原因：passlib 1.7.4 讀 `bcrypt.__about__` 判版本，4.1 起移除
   - 做法：本專案不用 passlib，直接用 bcrypt（`app/security.py`），從源頭避開

P5. **Python 3.14 太新、套件無對應 wheel**
   - 症狀：本機 `pip install` 失敗（SELA 的 Mac 是 3.14）
   - 原因：fastapi/pydantic-core 等在 3.14 還沒出 wheel
   - 做法：`runtime.txt` 釘 Railway 用 3.12；本機請用 3.12/3.13

> 已主動預防（沒踩但相關）：不用 PostgreSQL Enum（坑 #2 大小寫）；session 統一用 `sync_db_session()` context manager（坑 #24）；訊息 body 用 Jinja 自動跳脫顯示（坑 #18 XSS）。

---

## 五、煙霧測試（可貼上執行）

> 每次升版前必跑，全綠才打包。

```bash
# 1. 語法檢查（全部 app/*.py）
python -c "import ast,glob; [ast.parse(open(f).read()) for f in glob.glob('app/**/*.py', recursive=True)]; print('parse OK')"

# 2. 路由註冊驗證（會觸發所有 import，早期攔 NameError）
COOKIE_SECURE=false ADMIN_USERNAME=drlee SESSION_SECRET=t \
  python -c "from app.main import app; print(len(app.routes), 'routes')"   # 預期 53 routes

# 3. 找漏掉的 debug（必須空白）
grep -rn "console.log\|TODO\|FIXME" app/ || true

# 4. 啟動測試（本機 SQLite，6 秒後自動結束）
timeout 6 python run.py
# 預期：印出「本機預覽已啟動」+ Uvicorn running，無錯誤
```

---

## 六、版本歷程（最近 6-10 版）

| 版本 | 重點 |
|------|------|
| V1.12.0 | App logo 落地（依 Kit V1.14.1 §8-12 雙軌系統）：SELA 委託 Gemini 生圖（北歐藍 #547A91 圓角方框＋白色 S 紙條＋SLIP 字樣）→ Claude 去浮水印（鏡像乾淨左下角覆蓋右下角 Gemini 星號）＋ Pillow 生全套：static/app-logo/app-logo-{16..1024}.png（透明外緣，四角 floodfill）＋覆蓋 static/favicon/（favicon.ico 多尺寸/16/32 透明、apple-touch/android-chrome 實心藍底避免 iOS 透明變黑）。base.html favicon＋品牌列改 app logo（帶 ?v=app_version 破快取）、theme-color→#547A91；site.webmanifest theme_color→#547A91。SELA logo 降為品牌歸屬印記：login footer＋個人設定底部 .sela-attrib 小角標。SW 快取升 v4。另已產 SELA-logo-prompt.md（§17 工作流）|
| V1.11.0 | 七項：(1) 公告：新 Announcement 表＋`/admin/announce` 設/清（清空 active 後存新 active）；base_ctx 帶最新 active 公告，base.html 全頁頂橫幅 .announce (2) 對話顯示優化：泡泡與時間/動作分離——thread 包 `.bubble-col`，`.bubble-meta` 移到 .bubble 外（時間/已讀/收藏/更多在泡泡下方），meta 改 muted 深色、me 側覆蓋原綠底白字色，chat gap 加大 16px (3) 修邀請註冊失效：成因是舊 signups 表缺 expires_at/used_at/used_by，_ensure_columns 沒列到→補上 ALTER (4) 帳號管理顯示最後登入：User.last_login（_ensure_columns 補欄）；login/activate/signup 皆寫入；admin 顯示 last_logins（localtime 格式化）(5) 剪貼簿強化：每格加「清空」＋「全部清空」(JS clearSlot/clearAllSlots) (6) 瀏覽器存密碼＝瀏覽器密碼管理員，非 App 儲存（App 只存 bcrypt 雜湊）；屬說明 (7) 網頁書籤：新 Bookmark 表（username/label/url/sort_order）＋常用功能「書籤」分頁＋`/bookmark/add|/{id}/delete`，_safe_url 擋非 http(s)。新增 announcements、bookmarks 表（自動建）|
| V1.10.2 | 貼圖缺「貼圖感」：圖仍包在綠色泡泡裡。原因＝`.bubble-row.me/.them .bubble` 綠底 specificity(0,3,0) 蓋過 `.bubble.sticker`(0,2,0)。修法：改用同等具體並排後的 `.bubble-row.me/.them .bubble.sticker` 設 transparent/no-border/no-shadow/padding0、文字色改回 var(--ink)，meta 改深色可讀；貼圖放大到 160px。現在貼圖浮在背景上、無泡泡，符合 LINE 風 |
| V1.10.1 | 修貼圖爆框：症狀是貼圖以原圖尺寸顯示、泡泡底色還在 → 其實是舊 CSS 快取（自 V1.10.1 起 style.css 連結帶 ?v=app_version 自動破快取；早期 V1.10.0 的 .sticker-img/.bubble.sticker 沒載到）。根本修法：base.html 的 style.css 連結改帶 `?v={{ app_version }}`，每次改版自動破瀏覽器快取；sw.js CACHE 升 v3。日後任何 CSS 改動都會隨版本自動更新，不必再手動 hard-refresh |
| V1.10.0 | LINE 風貼圖：新 app/stickers.py 掃描 static/stickers/<組>/（子資料夾＝組名、檔名排序、可 .png/.webp/.gif/.apng；組名「數字_」前綴用於排序並於顯示去除）；不需改碼即可增刪（放資料夾→部署）。Message 新增 sticker 欄（pack/file 相對路徑；create_all+_ensure_columns 自動補欄），size_bytes=0 不計容量。`POST /sticker`（驗收件人為自己/好友、stickers.is_valid 擋路徑穿越）。對話頁：composer 加貼圖盤（多組分頁 showPack、點圖即送的提交鈕）、貼圖訊息以透明無泡泡大圖呈現（.bubble.sticker）；訊息夾預覽顯示「［貼圖］」。新 smile 圖示；移除 icons.html 重複的 eye 區塊。素材由使用者自備並負責授權（static/stickers/README.txt 含規則與生成 prompt）|
| V1.9.1 | 解 PDF 密碼欄加「眼睛」顯示/隱藏切換（togglePw 切 input type，icon eye/eye-off）；icons.html 新增 eye、eye-off 線性圖示。內嵌 JS 用 `icon(...)|replace("\n","")` 確保單行不破壞字串 |
| V1.9.0 | 常用功能新增「解 PDF 密碼」（使用者已知密碼）：分頁上傳加密 PDF＋輸入正確密碼 → 下載無密碼版本。`POST /pdf/unlock`（async、UploadFile）用 pypdf 讀取、`reader.decrypt(pw)`（0=密碼錯）、PdfWriter 輸出未加密；只在記憶體處理、不存檔（隱私）；50MB 上限；錯誤/非PDF/未加密/密碼錯都 flash+導回 /tools?tab=pdf；下載檔名用 RFC5987（filename*=UTF-8 中文安全）。新增相依 pypdf==5.1.0、cryptography==44.0.0（解 AES）。技能建議的 qpdf 是 CLI、Railway 不一定有，故改純 Python 的 pypdf |
| V1.8.1 | (1) 統一管理路由守門：所有 /admin POST 擋下時一律 flash「沒有權限」+導回 /inbox（原本 toggle/level/reset/delete 等導去 /login，不一致）；admin_page GET 仍保留兩段式（未登入→/login、登入非管理者→/inbox）(2) 對一般使用者隱藏「管理者」標籤：好友清單的管理者標籤改為僅管理者檢視可見（`{% if f.is_admin and user.is_admin %}`）；topbar/設定頁僅顯示本人自己的（管理者）標示，不洩漏他人身分 |
| V1.8.0 | (1) 待辦便條空狀態改小膠囊：原本滿版淡黃虛線大框 → inline-flex 自動寬度的靠左小膠囊，未使用時不佔版面 (2) 私密對話：新增 `PrivatePair` 表（create_all 自動建）；管理者在帳號管理可對某帳號「設為私密對話(1天)/關閉」（`POST /admin/user/<id>/private`，配對含管理者自己）；卡片顯示「私密 1天」標籤、對話頁顯示私密橫幅。`security.purge_old` 重寫：私密配對訊息滿 1 天即刪、且無視標籤（私密優先），一般訊息維持 15 天且標籤保留；inbox 載入時也呼叫 purge_old 讓 1 天保留即時生效。新增 private_pairs 表（自動建）|
| V1.7.0 | 管理者可協助互加好友：帳號管理新增「協助互加好友」（兩個 active 帳號下拉，含管理者自己），`POST /admin/befriend` 直接 fs.add_friend（免對方同意；擋同帳號、已是好友則略過、非管理者導離）。複用 friends_service.add_friend（自動去重、caller commit）|
| V1.6.1 | 縮網址支援自訂短網域：新增環境變數 `SHORT_BASE`（如 https://短網域）；設了之後短連結改用它、否則用目前網址。搭配在 Railway 綁自訂網域（免費，CNAME），短連結才能真的變短（自建縮網址長度受限於網域本身）。/s/<code> 在任一綁定網域上都能轉址 |
| V1.6.0 | 常用功能再加兩工具＋管理者看 ID：(1) 縮網址：自建短連結（新 `ShortLink` 表，create_all 自動建），`/shorten` 產生本站短碼、`/s/<code>` 302 轉址；只收 http/https（擋 javascript: 等開放轉址）；縮網址頁可複製、刪除、「做成 QR」 (2) QR 產生：`/qr/img?data=`（PNG，dl=1 下載）、`/qr/send` 產生 PNG 存檔並建 Message+Attachment 傳給自己/好友（storage 新增 save_bytes）；QR 分頁可下載或選收件人傳送，從縮網址帶 `?qr=` 自動產生 (3) 帳號管理每張卡片顯示該帳號 friend_id（admin 傳 acct_ids＝ids.fmt）。新增 short_links 表（自動建）|
| V1.5.1 | 三項打磨：(1) 手機計算機輸入框會跳出系統鍵盤＋自動填入黑條遮擋 → display 改 `inputmode="none"`（手機不跳鍵盤、仍可點游標插入；電腦實體鍵盤照常）＋autocomplete/lpignore 抑制自動填入 (2) 常用片語的新增欄改成按「新增片語」才展開（toggleEdit），預設收起保持簡潔 (3) 訊息夾待辦便條改成 3M 便利貼黃（filled #fef6a5＋深色字＋軟陰影；empty 淡黃虛線），不再吃主題色 |
| V1.5.0 | 常用功能三項：(1) 片語編輯版面重排：由 flex 列+rowmenu 下拉（窄畫面會把文字擠成直排、編輯框亂跑）改為**直式卡片**：名稱→內容全寬→操作列（複製/↑/↓/編輯/刪除），編輯框 toggleEdit 全寬展開 (2) 計算機升級：加括號 ( )、display 改可編輯 input 支援**游標插入**（insertAtCaret）與**實體鍵盤**（Enter=等於、Esc=清除）；運算改 shunting-yard→RPN，支援括號/優先序/一元負號，仍不用 eval (3) 剪貼簿**多分格**：clipboard 改存 JSON 陣列（相容舊純文字→單格），可新增/刪除/各自複製，上限 12；`/clipboard` 改 async 讀 `form().getlist("slot")`（List[str]=Form 綁不到重複欄位）|
| V1.4.0 | 常用功能五項：(1) 片語內容改 textarea 可多行 (2) 移除對話輸入框上方的片語快捷鈕（thread 不再帶 snippets、移除 insertSnip） (3) 常用功能頁加分頁 tag（剪貼簿／常用片語／計算機；JS showTab 切換、`?tab=` 帶初始與表單轉址後落點、history.replaceState 不重整） (4) 加簡易計算機（純前端、自製 shunting 風格安全運算 calcEval，不用 eval；＋−×÷％、小數、負號、優先序） (5) 送出更直覺：送出鈕加「送出」文字（id=csend），選檔後顯示「已選 N 個，按送出」提示且送出鈕加 .ready 外框強調 |
| V1.3.0 | 把剪貼簿/片語抽成獨立「常用功能」分頁（nav 排在訊息夾**之前**，新 router `tools.py`：`/tools`、`/clipboard`、`/phrase/add|edit|delete|move`）。剪貼簿＝跨裝置暫存區（新 `User.clipboard` TEXT，存/複製全部/清空）；片語＝可命名+排序+修改、上限 20（`Snippet` 加 `label`、`sort_order`；注意欄名不可用保留字 order→用 sort_order；init_db 回填舊片語 sort_order=id）。訊息夾移除原面板（待辦便條保留）；對話輸入框快捷鈕改顯示 label。新增 users.clipboard、snippets.label/sort_order（自動補） |
| V1.2.0 | 診間小功能三件：(1) 臨時剪貼簿／常用片語：新增 `Snippet` 表（每人多條短文字，create_all 自動建），訊息夾面板可新增/刪除/一鍵複製（最多 40 條、每條 ≤300 字）(2) 常用語範本：同一份片語在對話輸入框上方化為快捷鈕，點一下插入游標處（insertSnip）(3) 已讀狀態：新增 `Message.read_at`（自動補欄），開啟對話標記已讀時記錄時間；寄件者在自己送出的泡泡看到「未讀／已讀 HH:MM」，自我對話不顯示。另把圖片後備字改為「圖片無法顯示」 |
| V1.1.1 | 修中文檔名附件下載/顯示 500（圖片顯示「已遺失」的真因）。`/attachment` 直接把原始檔名塞進 `Content-Disposition`，HTTP 標頭只能 latin-1，中文檔名（如 Mac 截圖「截圖 2026-…png」）→ UnicodeEncodeError 500 → `<img>` 失敗。改用 RFC 5987：ASCII 後備 `filename="..."` ＋ `filename*=UTF-8''<quote(name)>`。檔案其實有存、Volume 正常，與大小/HEIC 無關 |
| V1.1.0 | 訊息夾最上方新增「給自己的待辦／提醒」便條：每人一則（`User.note` TEXT，自動補欄），有寫就以柔色卡片顯示全文＋「編輯」、可清除；沒寫就縮成小小一條虛線「＋給自己的待辦／提醒」。`POST /note`（空白即清除→None），inbox ctx 帶 user_note。純個人、不影響訊息/好友 |
| V1.0.1 | 修桌機頂列更亂的真因：V0.19.0 的 service worker 對 /static 用「快取優先」，部署後拿到**舊的 style.css**（新 HTML 配舊 CSS，.topbar-right/.logout-btn 沒套上 → 右側區塊往下疊）。改為 /static **網路優先**（順手更新快取、離線退回），CACHE 升 v2（activate 自動清舊）；另收窄 cap-bar 120、品牌 min-width:0 nowrap、cap nowrap 防擠。部署後首次需重整一次讓新 SW 接管 |
| V1.0.0 | 正式版里程碑。修桌機頂列登出鈕跑到第二行：內容欄 640 下「品牌＋容量＋使用者＋登出」在 flex-wrap 擠不下（容量上限變 4 位數更明顯）→ 右側 cap/who/logout 包成 `.topbar-right`（nowrap、整組才換行），`.topbar-inner` 改 space-between、gap 12，登出改 38px 圖示鈕（title/aria 顯示「登出」），移除 spacer。功能不變、純版型修正＋升版號 |
| V0.19.0 | (1) PWA 可安裝：補齊 site.webmanifest（start_url/scope/標準 icon），新增 `static/sw.js`（最小化：只快取 /static、HTML 走網路），用 `GET /sw.js`（root scope + Service-Worker-Allowed）提供、base/login 註冊＋iOS standalone meta (2) 暗色模式：新增 `User.dark`，`[data-mode="dark"]` 覆寫中性色變數（保留各主題 --primary），蓋掉硬寫白底控制項與 topbar；設定頁「明暗」淺色/暗色切換、`/darkmode` (3) QR 加好友：新增相依 `qrcode`，`GET /friend/qr` 回傳含加好友連結的 QR PNG；好友頁可顯示自己 QR、`?add=<id>` 自動帶入、「開啟相機掃 QR」用 BarcodeDetector（不支援則提示改用連結/手動）。新增 users.dark（自動補） |
| V0.18.0 | 新增「皮克敏」佈景主題（第 5 個）：花園綠意明亮配色（葉綠主色 #5fa345＋暖草米底），純色盤、不含任何官方角色/圖像；THEMES 加一筆、style.css 加 `[data-theme="pikmin"]` 完整覆寫底色與主色 |
| V0.17.0 | 使用性微調 7 項：(1) 導覽「訊息夾」顯示未讀**數字**徽章（base_ctx 算 recipient=本人且未讀數）(2) 導覽「好友」有待處理邀請時顯示**紅點**（base_ctx 算 to_user=本人的 FriendRequest 數）(3) 訊息夾空狀態文案改成用 ID 加好友 (4) 登入頁加「忘記密碼請洽管理者重設」 (5) 移除孤兒 GET /compose 與 compose.html（POST /compose 保留；原錯誤轉址改 /inbox）(6) 非管理者對話頁顯示「本月可上傳剩餘 X（等級）」(7) 閒置自動登出預設 10→15 分。base_ctx 多回 unread_total / pending_requests |
| V0.16.0 | (1) 登入頁加「記住帳號」勾選：勾選後以 `slip_user` cookie 記住帳號名、下次自動帶入（GET 預填、POST 依勾選 set/delete cookie，httponly+samesite），密碼欄 `autocomplete=off` 不記憶 (2) 好友頁移除「改用邀請連結」：刪 UI 區塊、`invites` ctx 與 `friend_invite`/`friend_invite_revoke`/`friend_accept` 路由、`_invite_link`、登入/啟用裡的 pending_invite 轉址（Invite 模型保留無害）(3) 個人設定三個折疊鈕等寬：`details.editbox>summary` 改 `width:100%` 滿版 (4) 帳號的「邀請新同事註冊」連結，對方註冊完成後**自動與邀請人（Signup.created_by）成為好友**（signup_submit 內 fs.add_friend）|
| V0.15.0 | 等級改三級（管理者獨立於 is_admin）：`User.level` 1=銀 2=金 3=白金。config `TIER_NAME/TIER_FILE_MB{5,25,200}/TIER_QUOTA_MB{300,500,1024}/TIER_IMAGES_ONLY{銀:True}`（各 env 可調）。compose 依等級擋：銀僅圖片、單檔上限、**每月上傳額度**（用 upload_stats 的本月量；管理者不限）；對話輸入列對銀隱藏加檔案鈕；個人設定顯示「等級＋本月上傳/額度」；帳號管理選單三選一切換、標籤 銀/金/白金。遷移：舊「進階(2)」一次性升白金(3)（以「是否已有白金」當旗標避免重跑）、admin→3、NULL→銀(1)、新帳號預設銀 |
| V0.14.0 | (1) 修功能列未對齊：上版把內容欄改 640 時漏改 `.nav`（仍 780/padding16），改為 640/padding22（手機 14）與品牌列、內容對齊 (2) 頂部容量標示改「總空間」並加 title 註明是全站共用空間；個人用量在設定（本人）與帳號管理（每人）已是個人值 (3) 一般使用者也能邀請新帳號：`/signup-link` 產生註冊連結（任何登入者）、`/signup-link/{sid}/revoke`，好友頁「邀請新同事註冊」折疊區顯示本人產生的連結 (4) 使用者等級（`User.level` 1=一般 2=進階，管理者於帳號管理設定）：一般只能傳圖片且單檔 ≤ `LEVEL1_MAX_FILE_MB`(預設10MB)，進階全格式大檔；compose 依等級擋型別/大小，對話輸入列對一般隱藏「加檔案」鈕，admin 為 2 且豁免。新增 users.level（啟動補既有帳號為 2）、新增帳號預設 1 |
| V0.13.1 | UI 欄寬統一：先前各頁卡片用了不一致的 max-width（480/520）、列表與表格卻是整寬，同頁寬窄不齊。改成全站內容欄一律 640px（`.wrap` 與 `.topbar-inner` 對齊），移除模板裡所有 inline max-width，卡片一律填滿欄寬 → 每頁欄寬一致、左右對齊 |
| V0.13.0 | (1) 佈景主題改成連底色一起換：`[data-theme]` 完整覆寫 --paper/-2/--card/--card-soft/--line/--line-soft + 主色三件組（navy 冷藍灰、sage 霧綠、terracotta 陶土、plum 梅紫），不再只換按鈕 (2) 帳號唯一 ID：`app/ids.py` 產生隨機 12 碼（前 11 隨機＋Luhn 檢查碼防呆，非連續），`User.friend_id` 唯一索引，建立帳號即指派、舊帳號啟動自動補（`_backfill_friend_ids`）；好友頁顯示自己 ID（4-4-4），輸入對方 ID → `request_by_id`（normalize+luhn 防呆、擋自己/已是好友/重複）→ 建 `FriendRequest`(pending)；對方在好友頁「待你同意」接受 → 互加並刪邀請。邀請連結保留但收進折疊。刪帳號連同清 friend_requests |
| V0.12.2 | UI 去雜亂：把「編輯類」控制收進點開才顯示的折疊區。個人設定的更換頭像/更換配色/修改密碼各自收進 `details.editbox`（預設只顯示現況）；帳號管理的新增帳號收進 editbox、每個帳號的重設/停用/刪除收進「管理」`details.rowmenu`；好友的移除、我的最愛的標題/移除也收進列內選單。原則：預設顯示現況，要改才點開 |
| V0.12.1 | 修 bug：頭像換了別人看不到。頭像網址 `/avatar/{帳號}` 固定不變、內容卻會變；舊版成功用 `no-cache`、而「沒頭像」的 404 沒帶快取標頭被瀏覽器快取住，於是對方上傳後你仍拿到舊圖或舊 404。改成所有頭像回應（圖片/內建 SVG/404/原圖）一律 `Cache-Control: no-store`，永遠取最新 |
| V0.12.0 | (1) 內建頭像：15 種北歐扁平人物（`app/avatars.py` 純 SVG 產生），`/avatar/preset/{i}` 選用 (2) 介面配色 4 主題（`User.theme`，`[data-theme]` 覆寫主色三件組；靛藍/霧綠/陶土/梅紫），`/theme` 切換 (3) 好友邀請連結未產生前隱藏說明與清單（`{% if invites %}` 包住）(4) 移除「寄件紀錄」（對話本身即記錄；拿掉 nav + /sent 路由 + sent.html）(5) 上傳頭像後可調整中心位置：Pillow 以焦點裁正方形（`storage.crop_square`，EXIF 轉正），存原圖 `avatar_orig`＋焦點 `avatar_pos`，`/avatar/position` 重裁。新增 users 欄位 avatar_orig/avatar_pos/avatar_preset/theme（自動補）；新增 Pillow 相依 |
| V0.11.3 | 對話標題列（返回＋頭像＋對象名）改成 sticky 釘在頂端、黏在 topbar 下面（base.html 用 JS 量 topbar 高度設 `--topbar-h`，`.thread-head` 用 `top: var(--topbar-h)`），長對話往下捲也一直看得到在跟誰講、隨時可返回 |
| V0.11.2 | 附件操作優化：對話輸入列改成兩顆鈕——「圖片」(input `accept="image/*"`，手機會直接開相簿/相機) 與「檔案」(任意檔)；選完即時顯示**縮圖＋檔名**的預覽列（電腦手機都看得到選了什麼）、可一鍵清除。兩個 input 都 name=attachment，後端不變 |
| V0.11.1 | 修 bug 三項：(1) 時區：DB 存 UTC，畫面顯示要轉在地時間，否則下午 6 點顯示成早上 10 點。新增 `template_env.localtime()`（ZoneInfo `APP_TZ`，後備固定 +8）+ `tzdata` 套件，所有 strftime 改 `localtime(x).strftime()` (2) 我的最愛長訊息沒收合：clamp CSS 只寫了 `.bubble-body.clamp`，最愛用的是 `.msg-body.clamp`，補上選擇器 (3) 圖片檔案遺失時改顯示「圖片已遺失」提示（`imgGone()` + `.att-gone`）取代破圖。注意：圖片真正消失的根因是 Railway 沒掛 Volume、重新部署清空檔案系統（見 P1）|
| V0.11.0 | 照片顯示優化（圖片只留預覽＋角落小下載鈕）、帳號管理改堆疊卡片＋頭像破圖退回字首、自助註冊（`signups` 表 + `/admin/signup` 產生一次性連結 + 公開 `/signup/{token}` 建帳號）|
| V0.10.0 | 我的最愛改獨立快照（刪對話不連動、可設標題、長訊息收合）；閒置登出 10 分；清掉 UI 非必要說明文字 |
| V0.9.0 | 長訊息收合、收件者自訂標題（`Message.title`）、標籤（`Message.tags`，設了不自動刪）、我的最愛收藏區（標註誰寄的）|
| V0.8.0 | 定位放寬為「小型用戶交流，核心是各帳號跨裝置傳給自己」。每帳號每月上傳量（`upload_stats` 表）；收發改 LINE 式（訊息夾列自己+好友、聊天泡泡、底部輸入列直接送、移除撰寫傳送分頁）|
| V0.7.0 | (1) 撰寫頁附件區加 Railway 成本警語：以「下載 100MB 約 NT$X」呈現，費率走 config (2) 手機介面優化：頁首縮排、行動版收容量條、導覽橫向可滑、表格/動作列換行、加大觸控 |
| V0.6.0 | (1) 訊息夾改兩層：第一層對話列表（`_counterpart` 分組，自己永遠置頂第一項、未讀數徽章），第二層 `/inbox/{other}` 看雙向訊息、開啟即標已讀、可清整個對話、可從「回覆」帶 `?to=` 預選收件人 (2) 多檔附件：新增 `attachments` 子表（`Message.attachments` relationship，啟動時把舊單一附件欄位搬進來），compose 可加多列、送出前可逐列移除，下載改 `/attachment/{aid}` (3) 附件下載加 `Cache-Control` 省重複 egress。各種刪除/清除/過期/刪帳號都連帶刪所有附件檔 |
| V0.5.0 | 六項：(1) 單檔上限改成「只受 Volume 容量限制」——查證 Railway 對上傳無硬性上限（僅 5 分鐘逾時），`MAX_FILE_MB` 預設 0=不設固定上限 (2) 每人可設頭像（`avatar_path`，/settings 上傳、/avatar/{user} 授權顯示） (3) 中文改名「絲利普」 (4) 主色改 #304073 深藍靛 (5) 訊息、好友、名單都顯示頭像 (6) 收件匣→訊息夾、保留 7→15。新增 User.avatar_path，靠 `_ensure_columns()` 自動補（坑 #3） |
| V0.4.0 | 三件事：(1) 名稱旁加版本徽章 (2) 介面往北歐風重做——暖中性紙底、留白加大、霧藍點綴、全 SVG 線性 icon（`templates/icons.html`，零 emoji） (3) 附件功能：compose 可附圖/檔，收件匣圖片內嵌預覽 + 下載，檔案放 `UPLOAD_DIR`（Volume）、DB 只記中繼，下載走授權路由，刪除/清除/過期/刪帳號都會連帶刪檔。用既有預留欄位，無新表 |
| V0.3.0 | 好友系統：帳號間要先互加好友才能互寄 / 看到對方。一次性 + 24h 過期邀請連結，對方登入後點連結即成立（未登入會先導登入再自動完成）；可移除好友、作廢邀請。compose 收件人只列好友 + 自己。新增 friendships / invites 兩表（create_all 自動建）。Procfile 加 proxy-headers（坑 #2） |
| V0.2.0 | 加兩個小功能：收件匣每則訊息「一鍵複製」（前端 clipboard + textarea fallback）、帳號管理「刪除帳號」（連帶清掉該帳號相關訊息與寄件紀錄）。無 schema 變動 |
| V0.1.2 | 修 Railway build 失敗：railpack + mise 驗 Python attestation 卡死 → 加環境變數 `MISE_PYTHON_GITHUB_ATTESTATIONS=false`（坑 #1）。純部署修正，程式不動 |
| V0.1.1 | 命名：英文名定為 Slip，畫面顯示「Slip 診間傳遞」；zip / 資料夾改英文 `Slip`（避中文檔名跨平台問題，坑 #20）。純命名，結構與功能不動 |
| V0.1.0 | 初版：多帳號定址訊息、首次登入自設密碼、收件匣/寄件紀錄、7 天自動清除、20 分閒置登出、容量條、預留附件欄位；依 Kit 起手（app/ 結構、統一認證、共用 templates、精確鎖版本、北歐霧藍、SELA logo+favicon） |

---

## 七、下版候選工作（按優先序）

1. **SELA 實機試用後的順手度迭代** — 上線前必走：醫師 + 個管師各用一輪，看對話列表 / 多檔附件 / 頭像在手機上順不順
2. 好友頁顯示「何時成為好友」（目前只列名單）
3. 寄件紀錄保留天數獨立於訊息（目前同為 15 天）
4. 管理者頁顯示各帳號最後登入時間
5. 對話內「拖拉上傳」多檔（目前用「加檔案」逐列）
6. 對話列表分頁 / 搜尋（量大時才需要）

---

## 八、升版必讀（如有）

### V0.15.0 升版指引

- 沿用 users.level，語意改 1=銀 2=金 3=白金；啟動時一次性把舊「進階(2)」升白金(3)、管理者設白金、空值設銀，之後不再重跑。
- 新增可選環境變數：`SILVER/GOLD/PLATINUM_MAX_FILE_MB`（單檔上限，預設 5/25/200）與 `SILVER/GOLD/PLATINUM_QUOTA_MB`（每月額度，預設 300/500/1024）。移除 `LEVEL1_MAX_FILE_MB`（改用上列）。
- 無新資料表、無新相依。推 main → 重新部署即可。

### V0.14.0 升版指引

- 新增 users 欄位 `level`（啟動自動 ALTER；既有帳號自動補為 2＝進階，維持原能力；新帳號預設 1＝一般）。
- 新增環境變數（選用）`LEVEL1_MAX_FILE_MB`（一般等級單檔上限，預設 10）。
- 無新資料表、無新相依。推 main → 重新部署即可。

### V0.13.0 升版指引

- 新增 users 欄位 `friend_id`（啟動自動 ALTER 補上）＋自動為所有現有帳號補唯一 ID（`_backfill_friend_ids`）。
- 新增資料表 `friend_requests`（create_all 自動建立）。
- 無新環境變數、無新相依套件。推 main → 重新部署即可。

### V0.12.0 升版指引

- 新增 users 欄位 avatar_orig / avatar_pos / avatar_preset / theme（`_ensure_columns` 啟動自動 ALTER 補上），不需手動 migration。
- 新增相依套件 `Pillow`（頭像裁切用），已 `==` 鎖版；Railway 會在下次 build 安裝。
- 無新環境變數。頭像原圖與裁切圖都存在 `UPLOAD_DIR`（Volume），記得 Volume 已掛。
- 推 main → 重新部署即可。

### V0.11.0 升版指引

- 新增 `signups` 表（create_all 自動建），不需手動 migration。新增 env（選填）`SIGNUP_EXPIRE_HOURS`（預設 72）。
- 自助註冊連結走 `/signup/{token}`，是公開頁（免登入）；連結用後即失效、過期失效。建立的帳號是一般使用者（非管理者）。
- 提醒：頭像/附件要持久，仍需在 Railway 掛 Volume（`UPLOAD_DIR=/data/uploads`）；沒掛的話重啟後檔案會遺失（這也是後台頭像顯示破圖的原因，V0.11.0 已讓破圖自動退回字首圓）。
- 推 main → 重新部署即可。

### V0.10.0 升版指引

- 收藏改成獨立快照：`favorites` 表結構改變（加 sender/other/title/body/msg_created_at、去 FK）。啟動時 `_read_old_favorites_then_drop()` 會把 V0.9.0 的舊收藏搬成快照保留（不需手動處理）。
- 閒置登出 10 分鐘（`IDLE_TIMEOUT_MIN` 預設 10，可用 env 調）。
- 無新環境變數，推 main → 重新部署即可。

### V0.9.0 升版指引

- 新增 `messages.title` / `messages.tags` 欄位（`_ensure_columns` 啟動自動 ALTER 補上）與 `favorites` 表（create_all 自動建），不需手動 migration、無新環境變數。
- 行為：有標籤或被任何人收藏的訊息，`purge_old` 會跳過、不再 15 天自動刪。
- 推 main → 重新部署即可。

### V0.8.0 升版指引

- 新增 `upload_stats` 表，`create_all` 自動建，不需手動 migration、無新環境變數。
- 「撰寫傳送」分頁已移除，改成在對話內直接輸入送出；`/compose`（POST）仍是送出端點，GET 頁面保留但未連入導覽。
- 推 main → 重新部署即可。

### V0.6.0 升版指引

- 新增 `attachments` 子表，`create_all` 自動建；啟動時 `_migrate_legacy_attachments()` 會把舊版單一附件搬進子表，**不需手動 migration**。
- 沒有新環境變數。附件 / 頭像仍共用 `UPLOAD_DIR`（要持久就掛 Volume，同前）。
- 推 main → 重新部署即可。

### V0.5.0 升版指引

- 新增 `users.avatar_path` 欄位，啟動時 `_ensure_columns()` 會自動 ALTER 補上（坑 #3），**不需手動 migration**。
- 頭像跟附件共用 `UPLOAD_DIR`，所以一樣**要掛 Volume 才會持久**（同 V0.4.0；已掛過就不用動）。
- 單檔上限預設不設固定值，受總容量限制 → 把 `CAPACITY_LIMIT_MB` 設成你開的 Volume 大小最準（不設預設 500MB）。Railway 本身對上傳無上限，只有 5 分鐘逾時。
- 推 main → 重新部署即可，無需新增環境變數。

### V0.4.0 升版指引

- 沒有新表（附件用 messages 早就預留的 attachment_* 欄位）。但**要附件能持久，必須掛 Railway Volume**：
  - Railway 該服務 → Volumes → 新增，掛載路徑設 `/data`
  - Variables 加 `UPLOAD_DIR=/data/uploads`（可選 `MAX_FILE_MB`，預設 10）
  - 沒掛 Volume 也能用，但檔案會在重啟後消失（純文字訊息存 PostgreSQL 不受影響，坑 P1 同理）
- 推 main → 重新部署即可。

### V0.3.0 升版指引

- 新增 `friendships`、`invites` 兩張表，`create_all` 啟動時自動建，**不需手動 migration**。
- **行為改變：** 上線後帳號之間要先互加好友才能互寄。現有帳號彼此會「突然不能寄」直到互加一次好友 —— 帳號還少時影響很小，先告知使用者。
- Procfile 已加 `--proxy-headers --forwarded-allow-ips=*`（讓邀請連結產生正確的 https 網址，坑 #2）。推上去重新部署即可，無需新增環境變數。

### V0.1.2 部署動作

- [ ] Railway Variables 新增 `MISE_PYTHON_GITHUB_ATTESTATIONS=false`（不加會 build 失敗，坑 #1）
- [ ] 重新部署即可（程式碼沒動）
- [ ] 首次部署其餘變數見 README「部署到 Railway」

---

## 九、一句話總結

V1.9.1：PDF 密碼欄加眼睛顯示切換。

V1.12.0：Slip 有了自己的 app logo（北歐藍 S 紙條），favicon／品牌列改用之，SELA logo 退為角標；依 Kit 雙軌系統。

V1.11.0：公告、對話時間移出泡泡、修邀請註冊（舊 signups 缺欄）、最後登入時間、剪貼簿清空鍵、網頁書籤。

V1.10.2：貼圖去泡泡（透明、浮在背景、放大 160px）——覆蓋 me/them 綠底的 specificity。

V1.10.1：修貼圖爆框（舊 CSS 快取）——style.css 連結改帶 ?v=版本自動破快取、SW 快取升 v3。

V1.10.0：LINE 風貼圖——掃描 static/stickers/<組>/，輸入列貼圖盤一鍵送，貼圖以透明大圖顯示；素材由使用者自備（含生成 prompt 與規則於 README）。

V1.9.1：解 PDF 密碼的密碼欄加眼睛切換可顯示/隱藏，確認有沒有打對。

V1.9.0：常用功能加「解 PDF 密碼」（已知密碼→下載無密碼版，記憶體處理不存檔；pypdf+cryptography）。

V1.8.1：統一管理路由擋下導向（/inbox+沒有權限）；好友清單「管理者」標籤對一般使用者隱藏。

V1.8.0：待辦便條空狀態改小膠囊；管理者可設「與特定帳號的私密對話」雙方訊息僅保留 1 天（purge_old 重寫，私密無視標籤）。

V1.7.0：管理者可在帳號管理直接讓兩個帳號（含自己）互加好友，免對方同意。

V1.6.1：縮網址加 SHORT_BASE 環境變數，綁自訂短網域後短連結就用它（自建縮網址長度本來受限於網域）。

V1.6.0：常用功能加「縮網址」（自建短連結 /s/<code>）與「QR 產生」（可下載或傳送給自己/好友）；帳號管理顯示每個帳號的 ID。

V1.5.1：手機計算機 inputmode=none 去除鍵盤黑條；片語新增欄點了才展開；待辦便條改 3M 便利貼黃。

V1.5.0：片語編輯改直式卡片版面；計算機加括號＋游標插入＋實體鍵盤；剪貼簿多分格（JSON 存、相容舊純文字）。

V1.4.0：片語可多行、不再帶到輸入框上方；常用功能加分頁 tag（剪貼簿/片語/計算機）＋簡易計算機；傳照片的送出鈕加文字並在選檔後強調提示。

V1.3.0：剪貼簿/片語獨立成「常用功能」分頁（排在訊息夾前）；剪貼簿=跨裝置暫存畫面；片語可命名/排序/修改、上限 20。

V1.2.0：臨時剪貼簿／常用片語（Snippet 表，訊息夾一鍵複製＋輸入框快捷插入）、已讀狀態（Message.read_at，寄件者看未讀/已讀時間，自我對話不顯示）。

V1.1.1：修中文檔名附件 500（圖片「已遺失」真因）——Content-Disposition 改 RFC 5987 編碼。與儲存/HEIC/大小無關。

V1.1.0：訊息夾上方加「給自己的待辦／提醒」便條（有寫顯示全文、空白縮小一條；User.note 自動補欄）。

V1.0.1：修 service worker「快取優先」導致部署後拿到舊 CSS、桌機頂列錯位；改 /static 網路優先＋升快取版本。

V1.0.0：正式版。修桌機頂列登出鈕被擠到第二行（右側群組化 nowrap、登出改圖示鈕、space-between）。

V0.19.0：可安裝為 App（PWA：manifest＋service worker）；暗色模式（與配色主題正交，保留主色點綴）；QR 加好友（顯示自己 QR、相機掃描 BarcodeDetector、?add 帶入）。新增 users.dark 與 qrcode 相依。

V0.18.0：新增「皮克敏」佈景（第 5 個主題，花園綠意明亮配色，純色盤無官方圖像）。

V0.17.0：使用性微調——導覽訊息夾未讀數字徽章、好友待處理邀請紅點；訊息夾空狀態文案改用 ID；登入頁加忘記密碼提示；移除孤兒 /compose 頁；非管理者對話頁顯示本月可上傳剩餘；閒置登出預設改 15 分。

V0.16.0：登入頁加「記住帳號」（記帳號不記密碼，cookie）；好友頁移除「改用邀請連結」（連同路由）；個人設定三折疊鈕改等寬滿版；帳號的註冊邀請連結，對方註冊後自動與邀請人成為好友。

V0.15.0：使用者等級改三級——銀（文字+圖片/單檔5MB/月300MB）、金（全格式/25MB/500MB）、白金（全格式/200MB/1GB），管理者獨立不限。compose 依等級擋型別/單檔/每月額度，輸入列對銀隱藏加檔案鈕，設定頁顯示等級與額度，帳號管理三選一切換。舊「進階」一次性升白金、新帳號預設銀。

V0.14.0：修功能列未對齊（640）；頂部容量標示改「總空間」(全站共用)；一般使用者也能產生註冊連結邀新帳號；使用者分等級（管理者設定，一般＝文字+圖片且單檔上限、進階＝全格式大檔），compose 依等級擋型別/大小、輸入列對一般隱藏加檔案鈕。新增 users.level（既有自動補 2、新帳號預設 1）。

V0.13.1：UI 欄寬統一——全站內容欄一律 640px、移除各頁不一致的 inline 寬度，卡片填滿欄寬，視覺對齊。

V0.13.0：佈景主題改成連底色一起換（不只按鈕）；新增帳號唯一 12 碼 ID（隨機＋Luhn 防呆），好友頁可輸入對方 ID 送邀請、對方同意後互加好友（FriendRequest）。新增 users.friend_id 與 friend_requests 表，皆自動建立/補值。

V0.12.2：UI 去雜亂——各頁「編輯/管理類」控制改成點開才顯示（個人設定三段折疊、帳號管理與好友的操作收進「管理」選單、我的最愛標題/移除收進「更多」），預設只顯示現況。

V0.12.1：修頭像換了別人看不到的快取問題——頭像網址固定、舊版 404 沒帶快取標頭被瀏覽器快取，改成所有頭像回應 `no-store` 永遠取最新。

V0.12.0：頭像系統升級——可上傳照片（上傳後用 Pillow 依焦點裁正方形、可調中心位置）或從 15 種北歐風內建人物頭像挑；介面配色 4 主題可切換；好友邀請連結未產生前隱藏；移除寄件紀錄分頁（對話即記錄）。新增 users 欄位與 Pillow 相依，欄位自動補、無破壞性。

V0.11.3：對話頁的對象標題列（返回＋對象名）改成釘在頂端（sticky，黏在 topbar 下），捲動長對話時一直看得到在跟誰講、也好返回。

V0.11.2：對話輸入列附件改兩顆鈕（圖片鈕直接開相簿、檔案鈕任意檔），選完顯示縮圖＋檔名預覽、可清除，解決「手機叫不出相簿、選完不知選了什麼、電腦也看不到附了什麼」。

V0.11.1（修 bug）：(1) 時區—DB 存 UTC、畫面沒轉導致下午 6 點顯示早上 10 點，新增 `localtime()`＋`tzdata`、模板時間全改在地時間 (2) 我的最愛長訊息沒收合—clamp CSS 漏了 `.msg-body.clamp`，補上 (3) 圖片遺失改顯示「圖片已遺失」提示取代破圖。圖片真正消失的根因是 Railway 沒掛 Volume、部署清空檔案系統（坑 #5/P1），需掛 Volume 才會持久。部署超過 5 分鐘是 railpack+mise 冷建置（裝 Python+pip）所致，非程式問題。煙霧測試全綠（43 routes，UTC→在地時間、收合、圖片 fallback、開機正常）。下版第一優先仍是 SELA 實機試用順手度。

### Pitfall：PWA service worker 不可對常變動的靜態檔用「快取優先」
- 症狀：改了 CSS／JS 部署後，畫面沒更新甚至錯位（新 HTML 配舊 CSS）。
- 原因：SW 用 cache-first 快取 /static，更新被卡住，直到 CACHE 名稱改變才失效。
- 做法：/static 改 **network-first**（fetch 成功就更新快取、失敗才退 cache）；每次結構性改版可順手升 CACHE 版本；/sw.js 路由回 Cache-Control: no-cache 讓瀏覽器抓到新 SW。

### Pitfall：HTTP 標頭放非 ASCII 會 500（Content-Disposition 檔名）
- 症狀：中文檔名的附件下載/圖片顯示時 500（圖片變「已遺失」），英數檔名正常。
- 原因：HTTP 標頭值只能 latin-1；把中文檔名直接寫進 `Content-Disposition: ...filename="中文"` 會 UnicodeEncodeError。
- 做法：用 RFC 5987 → `filename="<ASCII 後備>"; filename*=UTF-8''<urllib.parse.quote(name)>`。任何要放使用者輸入到標頭的地方都要先確保 latin-1 安全。

### Pitfall：重複的表單欄位要用 form().getlist，不要靠 List[str]=Form
- 症狀：多個同名欄位（如多個 <textarea name="slot">）在 `slot: List[str] = Form([])` 收不到（拿到空）。
- 做法：把該路由改 async，`form = await request.form(); form.getlist("slot")`。瀏覽器表單天然會送重複欄位；TestClient 要用 `data={"slot":[...]}` 而非 list-of-tuples 才會送出重複鍵。

### Pitfall：Jinja 中 dict 的 key 不要叫 items
- `{% for x in p.items %}` 會取到 dict.items 方法（非鍵），TypeError。改用 `p["items"]` 或把 key 改名（本專案貼圖把 items 改成 files）。
