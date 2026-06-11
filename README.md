<div align="center">
  <img src="static/app-logo/app-logo-256.png" width="120" alt="Slip"/>
  <h1>Slip 絲利普</h1>
  <p>小型用戶間的訊息工具——核心是讓每個帳號方便在不同裝置間傳訊息給自己，也能和好友互傳</p>
  <p><strong>V1.12.0</strong></p>
</div>

---

## 簡介

在一台裝置貼上內容，到另一台裝置登入就能取用、複製——核心是讓每個帳號方便在不同裝置間傳訊息給自己，也能和加為好友的帳號互傳。聊天式介面，支援多帳號、附件、頭像。為共用電腦設計：閒置自動登出、不記密碼、訊息預設 15 天自動清除（設標籤或收藏的會保留）。整包部署在 Railway。

## 功能

- 多帳號，管理者新增；使用者**首次登入自設密碼**，可自行修改，管理者可重設（管理者看不到任何人的密碼）
- 聊天式介面（像 LINE）：訊息夾是對象列表（自己永遠置頂、含所有好友），點進去就是對話泡泡＋底部輸入列，直接打字或附檔送出
- **好友制：帳號間要先成為好友才能互相寄件 / 看到對方**。加好友靠一次性、24 小時過期的邀請連結（對方登入後點連結即成立），可移除好友
- 可傳給自己，也可和**好友**互傳；對話內可一次附加多個檔案 / 圖片（圖片內嵌預覽、可下載）
- 頭像：可上傳照片（上傳後可調整中心位置）或從 15 種北歐風內建人物頭像挑選
- 介面配色可切換（靛藍 / 霧綠 / 陶土 / 梅紫 / 皮克敏）＋暗色模式，連底色一起換
- 可「安裝為 App」（PWA，加到主畫面、全螢幕開啟）
- 好友頁可顯示自己的 QR、或開相機掃對方 QR 加好友
- 每個帳號有唯一 12 碼 ID，可在好友頁輸入對方 ID 送出邀請、對方同意後互加好友
- 一般使用者也能產生「註冊連結」邀請新同事建立帳號
- 使用者分等級（管理者設定）：銀（文字＋圖片 / 單檔 5MB / 每月 300MB）、金（全格式 / 25MB / 500MB）、白金（全格式 / 200MB / 1GB）；管理者不限。超過單檔上限或每月額度會被擋下
- 長訊息（超過 5 行）自動收合，可展開
- 收到的訊息可加自訂標題（不改原內容）、可設標籤（設了就不會被自動清除）
- 可把訊息加入「我的最愛」收藏區（標註誰寄的、可另設標題、長訊息可收合）；收藏是獨立的，刪掉原對話也不會消失，要自己移除
- 個人設定可看「本月上傳量」，管理者頁可看各帳號本月上傳量
- 管理者可產生一次性註冊連結，讓人自己開帳號（不必管理者先建好）
- 每人可設定頭像，顯示在訊息、好友與名單上
- 寄件紀錄（只記給誰、何時，不存內容）
- 管理者新增 / 停用 / 重設密碼 / 刪除帳號（刪除會一併清掉該帳號相關訊息與好友關係）
- 訊息超過 15 天自動清除（每次有人開頁面時順手清，不需排程服務）
- 容量用量條（已用 / 上限）
- 資料結構已預留附件欄位，日後加圖片 / 檔案不用改結構
- 共用電腦安全：閒置 10 分鐘自動登出、登入頁不記密碼、密碼以 bcrypt 雜湊儲存

## 安裝

```bash
pip install -r requirements.txt
```

（本機預覽不需要 PostgreSQL；沒設 `DATABASE_URL` 時會自動用 SQLite 檔。）

## 啟動

本機預覽（用本機友善設定）：

```bash
python run.py
```

開瀏覽器到 http://127.0.0.1:8000 ，帳號 `admin`，第一次登入時自設密碼。

> 請用 Python 3.12 或 3.13；3.14 太新，部分套件還沒對應版本。Railway 上已用 `runtime.txt` 釘住 3.12。

## 部署到 Railway

1. 用 Git Pusher 把這個 zip 推上 GitHub。
2. Railway 建專案 → Deploy from GitHub repo，選此 repo。
3. New → Database → Add PostgreSQL（會自動注入 `DATABASE_URL`）。
4. Web 服務的 Variables 加：

   | 變數 | 說明 | 範例 |
   |---|---|---|
   | `ADMIN_USERNAME` | 管理者帳號名稱 | `drlee` |
   | `SESSION_SECRET` | 長亂碼，簽署登入 cookie | `python -c "import secrets;print(secrets.token_hex(32))"` |
   | `COOKIE_SECURE` | HTTPS cookie（Railway 有 HTTPS） | `true` |
   | `MISE_PYTHON_GITHUB_ATTESTATIONS` | **必加**，否則 build 失敗（見下） | `false` |
   | `UPLOAD_DIR` | 附件存放路徑，**需指向 Volume**（見下） | `/data/uploads` |
   | `MAX_FILE_MB` | 單一附件硬上限，0=不設（只受容量限制）。Railway 本身無上傳上限 | `0` |
   | `CAPACITY_LIMIT_MB` | 容量上限，可省略 | `500` |

   > **附件要持久就要掛 Volume：** Railway 該服務 → Volumes → 新增一個 Volume，掛載路徑設 `/data`，並把 `UPLOAD_DIR` 設成 `/data/uploads`。沒掛 Volume 的話檔案會在每次重啟後消失（同 SQLite 的道理）。純文字訊息存在 PostgreSQL，不受影響。

   > **為什麼要加 `MISE_PYTHON_GITHUB_ATTESTATIONS=false`：** Railway 的新建置器（railpack + mise）裝 Python 時會驗證 GitHub attestation，但 cpython 釋出版多半沒簽，會讓 build 卡在 `No GitHub artifact attestations found for python`。設為 `false` 關掉驗證即可正常 build（坑 #1）。

5. Settings → Networking → Generate Domain 產生網址。
6. 用 `ADMIN_USERNAME` 登入 → 設密碼 → 到「帳號管理」開同事帳號。

## 目錄結構

```
診間傳遞/
├── app/
│   ├── main.py            FastAPI 入口（uvicorn app.main:app）
│   ├── config.py          設定與環境變數（VERSION 在這）
│   ├── models.py          資料表
│   ├── database.py        連線、session、建表
│   ├── security.py        密碼雜湊、閒置、清除、容量
│   ├── dependencies.py    統一認證
│   ├── template_env.py    共用 templates 實例
│   └── routers/           auth / messages / admin 三組路由
├── templates/             畫面（Jinja2）
├── static/                style.css + favicon 套組
├── assets/sela.svg        SELA 品牌標識
├── run.py                 本機預覽啟動器
├── requirements.txt       相依套件（精確鎖版本）
├── runtime.txt            Python 3.12
├── Procfile               Railway 啟動指令
├── README.md              本檔
├── CLAUDE.md              給下次 Claude 的工作上下文
└── .gitignore
```

## 關於病人資料

資料會經由 Railway（雲端，機房通常在境外）傳遞與暫存。傳輸走 HTTPS。建議只傳必要欄位，避免姓名、病歷號、診斷一次全包；15 天自動清除可降低舊資料長期留存的風險。

## 版本

V1.12.0

---

> Made by **SELA** · V1.12.0

---

<div align="center">
  <img src="static/favicon/sela.svg" width="20" alt="SELA"/>
  <sub>App logo：Slip 自有視覺（北歐藍紙條 S）　·　品牌歸屬 Made by SELA</sub>
</div>
