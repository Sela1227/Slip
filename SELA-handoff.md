# SELA-handoff.md ｜ Slip 診間傳遞

> 給 Kit Claude 升 Kit 用。本份的觸發點是「發現一條會影響所有 Railway Python 專案的跨專案坑」（鐵律 #0 觸發條件：發現該回流 Kit 的坑），不是版本里程碑。

---

## 〇、專案速覽

- **專案名稱：** Slip 診間傳遞
- **專案類型：** FastAPI 後端（Jinja2 SSR）+ PostgreSQL，部署 Railway
- **技術棧：** Python 3.12 / FastAPI 0.115 / SQLAlchemy 2.0 / PostgreSQL / bcrypt
- **規模：** app/ 套件約 16 檔、~700 行
- **使用 Kit 版本：** V1.11.1
- **完成版本：** V0.1.2
- **完成日期：** 2026-06-06

---

## 一、用 Kit 的整體感受

### 預期外的順利
- FastAPI 起手必做（統一認證 dependencies、共用 templates 模組、`with sync_db_session()`、`==` 精確鎖版本）照抄就到位，沒踩到坑庫已記的 #5 / #32 / #46。
- 「踩過的坑」種子預埋機制有用：P3 預埋了 Starlette `TemplateResponse` 簽名，實作時果然遇到，當場就知道怎麼處理。

### 預期外的卡住
- **Railway 的建置器悄悄從 nixpacks 換成 railpack + mise**，帶出一條 Kit 沒覆蓋的新坑（見第二節）。這跟程式碼無關，純粹是部署平台行為變動。

### 整體評價
- ✓ FastAPI §1.1 起手清單品質高，新專案幾乎零摩擦。
- ✗ 部署層的「雲端平台建置器換代」Kit 沒有任何著墨，這次踩到。

---

## 一.5、新 stack 首遇報告

### B. 既有 stack 的新 API / 工具（方向 2：踩到坑才記）
- **Railway railpack（取代 nixpacks）+ mise 2026.6.0** — Railway 既有部署平台，但建置器換代是新行為，且踩到實質坑（attestation）。標 `[既有 stack 新工具: railpack/mise]`。第二節詳述。

---

## 二、發現的「跨專案通用坑」（建議進 Kit）

### 強烈建議加坑

#### 1. Railway railpack + mise 裝 Python 卡在 GitHub attestation

- **症狀**：Railway build 失敗 `mise ERROR Failed to install core:python@3.12.8: No GitHub artifact attestations found for python@3.12.8`，build daemon exit code 1。
- **原因**：Railway 新建置器（railpack-v0.26.1）改用 mise（2026.6.0）安裝 Python。mise 近期預設 `MISE_PYTHON_GITHUB_ATTESTATIONS=true`，會驗證 cpython 釋出版的 GitHub artifact attestation，但多數 cpython standalone build 沒簽 → 安裝 Python 步驟直接失敗。跟專案程式碼、requirements.txt 完全無關。
- **做法**：Railway Variables 加 `MISE_PYTHON_GITHUB_ATTESTATIONS=false`（錯誤訊息本身建議的開關），重新部署即過。寫進該專案 README 部署變數表。
- **影響範圍**：**當前（2026/06）所有用 Railway 部署、且走 railpack 自動裝 Python 的專案**（FastAPI / Flask / Django / CLI 皆中）。未來 Railway / mise 可能改回預設或修正，但現在是普遍地雷。
- **證據**：本專案 CLAUDE.md 坑 #1 + V0.1.2 版本歷程；上傳的 Railway build log（railpack-v0.26.1 / mise 2026.6.0）。
- **檢查 1 結果**：`grep -rn -i "attestation\|railpack\|mise" Kit/conventions Kit/deployment` → 無重複（命中的是 "Promise" 誤判）。Kit 坑庫目前無此條。

---

## 三、發現的「跨專案設計模式」

### 1. 雲端平台「建置器換代」要當成部署風險看

- **本案發生情境**：Railway 從 nixpacks 默默切到 railpack，安裝 Python 的底層（改用 mise）跟著換，引入了原本沒有的 attestation 驗證步驟，讓「上一次能 build、這次不能」。
- **可推廣的原則**：部署在受管平台（Railway / Render / Vercel 等）時，build 失敗的第一個排查方向是「平台建置器 / 底層工具是否換版」，不要先懷疑自己的程式碼。對應已有坑 #46（依賴浮動版本）的精神，但這次的變數在**平台工具鏈**，不在 requirements。
- **代價 / 取捨**：關掉 attestation 驗證等於放棄該層的供應鏈簽章檢查；對個人 / 小團隊工具可接受，企業級需評估。
- **建議寫入**：cross-project-pitfalls.md（B. 環境與部署 或 G. 工具鏈與依賴版本）。

---

## 四、Kit 該瘦身或調整的地方

#### 1. tech-stack-lessons.md §1.1 FastAPI「部署架構」段
- **現狀**：只寫「本地開發 + Railway 部署」「egress 白名單」「Sleep 省成本」。
- **建議改成**：加一條「Railway 已改用 railpack + mise 裝 Python；若 build 卡在 attestation，設 `MISE_PYTHON_GITHUB_ATTESTATIONS=false`」。
- **理由**：本案實證，且影響所有 Railway Python 專案。

#### 2. start-project-decisions.md 第 9 項部署平台表「Railway 注意」
- **建議**：「注意」欄補一句指向上述坑，讓新專案第一天就把這個環境變數列進部署清單。

---

## 五、留在這個專案、**不要回流 Kit** 的東西

- 診間交接的業務設計（多帳號定址訊息、傳自己 / 傳同事、寄件 log 不存內容）— 業務邏輯。
- 7 天自動清除用「開頁面順手清」取代排程服務 — 本案取捨（小團隊夠用），非通用準則。
- 共用電腦安全三件套（閒置 20 分登出、不記密碼、bcrypt）— 一般做法，Kit 已隱含。
- 北歐霧藍選色、SELA logo+favicon 整合 — 已照 Kit 既有規範，無新東西。
- 病人個資上雲的取捨討論 — 屬該專案與 SELA 的決策，哲學 1 已涵蓋。

---

## 六、Kit Claude 的建議行動清單

### 建議升 Kit 版本
**V1.12.0（b+1，新內容）** — 新增一條跨專案坑 + 補強既有部署規範。理由：是結構性新增（新坑），非純補字。

### 必做
- [ ] cross-project-pitfalls.md 新增坑：「Railway railpack + mise 裝 Python 卡 GitHub attestation → 設 `MISE_PYTHON_GITHUB_ATTESTATIONS=false`」（編號接續，附本案證據）。
- [ ] tech-stack-lessons.md §1.1 FastAPI 部署架構段補上該環境變數。
- [ ] start-project-decisions.md 第 9 項 Railway「注意」欄補指引。
- [ ] 速查索引「FastAPI / Railway 部署」對應新坑編號。

### 暫緩
- [ ] 不為「平台建置器換代」單獨開設計原則章節 — N=1，先以坑的形式記，等第二個平台換代案例再升級為原則。

### 不做
- [ ] 不收任何 Slip 業務邏輯（見第五節）。

---

## 七、給 Kit Claude 的最後備註

這條坑時效性強：Railway / mise 之後可能改預設或修掉，屆時這條可降級或標「2026/06 期間適用」。但在它還是普遍地雷的期間，任何 SELA 的 Railway Python 專案都會省下一次卡關，值得進 Kit。
