# BMAD × Claude Code 開發指南

> 適用：BMAD Method v6、Claude Code｜版本：2026-10-28
> 目的：說明全組如何用 BMAD 與 Claude Code，從本確認稿一路做到 11/18 期中檢核與 12/16 期末 demo。

## 0. 先理解：為什麼不從頭跑 BMAD 的需求與架構流程

BMAD 一般流程是：產品簡介 → PRD → UX → 架構 → Epic 與 Story → 實作。我們已經有經過討論與驗證的 `docs/PRD.md`、`docs/SCHEMA.md`、`docs/ARCHITECTURE.md`，如果再跑一次 `/bmad-create-prd` 和 `/bmad-create-architecture`，AI 會重新設計，反而推翻已確認的決定。

因此做法是：**把這三份文件當成 BMAD 的規劃產出，直接從「拆 Epic 與 Story」開始。** 這也是 (g) 可以說明的重點：先由人與 AI 討論定案規格，再讓 BMAD 的 agent 依規格執行，而不是讓 AI 自由發揮。

> 每個 BMAD 版本的 skill 名稱可能略有不同。開始前先在 Claude Code 輸入 `/bmad-help`，以它列出的名稱為準；下面的 prompt 內容不用改。

## 1. 角色分工：一人生成、三人驗證

本組採用「**主開發一人以 BMAD＋Claude Code 生成全部程式，其他三人負責驗證**」的模式。好處是程式風格與架構一致、不會有 migration 衝突；驗證者都有明確的產出，貢獻可以在 GitHub 上看到。

| 角色 | 負責人 | 主要工作 | 負責文件 |
|---|---|---|---|
| 主開發與整合 | 【組長】 | 建立 repo 與環境；用 BMAD 拆 Story、生成程式；每個 Story 開一個 PR；修正驗證者開的 Issue | (g) 中「程式」的紀錄 |
| 測試負責人 | 成員 A | 每個 PR 依驗收條件實際操作；用 BMAD TEA 產生並維護端對端與併發測試；記錄缺陷 | (e) 測試計畫、(f) 測試個案與報告 |
| 程式審查與安全 | 成員 B | 審查每個 PR（以 `/bmad-code-review` 輔助，自行判斷採用）；對照 CLAUDE.md 檢查權限、安全、交易 | (c) 架構設計、(d) 物件設計（依實際程式碼撰寫） |
| 專案管理與文件 | 成員 C | 審查 Epic 與 Story 切分；追蹤 Sprint 進度；手機與桌機介面檢查；彙整 AI 使用紀錄；統籌報告 | (a) 專案管理規劃、(b) 需求分析、(g) 彙整、報告投影片 |

**讓驗證真的發揮作用的規則**

1. **PR 必須經過核准才能合併**：在 GitHub 設定 `main` 分支保護，至少 1 位組員核准；核心流程（預約、付款、取消、改期）需要測試負責人與審查者都核准。
2. **問題一律開 Issue**：驗證者發現問題就開 GitHub Issue（格式見 7.4 節），由主開發修正後在 PR 中引用。這是每個人貢獻的紀錄，也是 (g)「人工審查發現 AI 錯誤」的證據。
3. **每天固定審查**：當天下午 6 點前開的 PR，驗證者在晚上 10 點前完成審查，避免卡住主開發。
4. **每個人都記錄自己的 AI 使用**：測試、審查、文件都會用到 AI，各自寫進 `docs/ai-usage-log.md`。
5. **整合週做一次程式導讀**（11/15～11/17）：主開發花一小時帶大家看核心流程程式碼，讓每個人在期中報告都答得出問題。
6. **選擇性**：分配 1～2 個簡單的 P1 Story（例如收藏、評論管理）給驗證者自己用 dev-story 完成，讓每個人都實際走過一次生成流程。

## 2. 主開發：準備環境與 repo

**一次性安裝（每位組員都要，驗證者需要在本機跑系統）**

| 工具 | 確認指令 |
|---|---|
| Git | `git --version` |
| Docker Desktop（Windows 需先啟用 WSL2） | `docker compose version` |
| Node.js 20 以上 | `node -v` |
| Claude Code（主開發；驗證者用來跑審查與測試 workflow） | `claude --version` |

**建立 repo（主開發）**

1. 在 GitHub 建立 private repo，邀請 3 位組員，設定 `main` 分支保護（Settings → Branches → Require a pull request before merging，至少 1 個 approval）。
2. 把確認稿解壓縮到專案資料夾根目錄（`CLAUDE.md`、`實作前確認稿.md`、`docs/`）。
3. 在專案資料夾執行 `npx bmad-method install`，選 Claude Code、BMM 模組與 Test Architect（TEA）模組。若資料夾已裝過 BMAD，重跑一次確認模組齊全即可。
4. 建立 `.gitignore`：`.env`、`node_modules/`、`venv/`、`__pycache__/`、`.pytest_cache/`、`frontend/dist/`、`uploads/`、`test-results/`、`playwright-report/`。
5. 第一次 commit 並 push：`git init`、`git add .`、`git commit -m "docs: 實作前確認稿"`、`git remote add origin <repo 網址>`、`git push -u origin main`。
6. 在 Claude Code 輸入 `/bmad-help`，確認 skill 名稱與本指南一致。

**分支規則**：每個 Story 一個分支 `story/<編號>-<簡述>`，完成後開 PR；修正 Issue 時在 commit 訊息寫 `fix #<Issue 編號>`。

## 3. 拆 Epic 與 Story（主開發執行，成員 C 主審）

在 Claude Code 開新對話，輸入 `/bmad-create-epics-and-stories`，agent 開始後貼上：

```text
本專案的規劃文件已經定案，請以它們為唯一依據拆分 Epic 與 Story，不要重新設計需求、資料表或 API：
- 需求與業務規則：docs/PRD.md（FR-xx、BR-xx）
- 資料結構：docs/SCHEMA.md
- 架構與 API：docs/ARCHITECTURE.md
- 類別、方法與互動：docs/設計圖_邏輯設計與細部設計.md（D3 Service 類別圖、D5～D9 循序圖）
- 專案規範：CLAUDE.md

開發模式：由一位主開發依序實作全部 Story，其他三位組員負責測試、審查與文件，因此 Story 要能依序逐一完成、逐一以 PR 交付審查。

請依下列 Epic 結構拆分（可調整 Story 切法，但不要改變 Epic 範圍）：
- E1 專案骨架：Docker Compose 五個服務、Flask app factory 與 extensions、依 SCHEMA.md 建立全部 16 張表的 model 與 migration（含 btree_gist 與排除約束）、統一錯誤格式、CSRF 與 session 設定、種子資料與測試帳號、React 專案骨架（路由、Mantine 主題、API 用戶端、受保護路由）、pytest 與 Vitest 可執行。
- E2 帳號：FR-01～08。
- E3 場館、空間、照片、設備管理：FR-40～43。
- E4 搜尋、空間詳細頁、可預約時段、收藏：FR-10～15。
- E5 預約、付款、房間密碼、確認信：FR-20～23，含 ARCHITECTURE.md 6.1、6.2 的交易與併發測試。
- E6 我的訂單：列表、詳細、取消、改期、評論：FR-30～34，含 6.3、6.4。
- E7 管理員訂單、會員、評論、通知：FR-44～48。
- E8 排程：FR-50～55。

拆分原則：
1. 每個 Story 是垂直切片：包含後端、前端與測試，完成後可在畫面上實際操作；以 AI 協助開發約半天到 1 天可完成，PR 大小適合他人在 1 小時內審查完。
2. Story 格式：「身為…我想要…以便…」；驗收條件使用 Given／When／Then，並逐條引用 PRD 的 FR 與 BR 編號；必須包含失敗情境。驗收條件要寫到測試負責人能照著手動操作驗證。
3. 每個 Story 標示優先級：P0（11/18 前必須完成）或 P1（期末前完成），與 PRD 中的優先級一致。
4. 給出建議的實作順序：E1 → E2 → E3 → E4 → E5 → E6 → E7 → E8，P0 全部在 P1 之前；標示 Story 之間的相依關係。
5. 最後附上「FR 覆蓋表」，確認每個 FR 至少對應一個 Story；若有 FR 無法對應，列在「待確認事項」，不要自行新增需求。

時程：E1 在 11/01–11/03 完成；11/14 前完成所有 P0 Story；11/15–11/17 只做整合與修正。
輸出使用繁體中文。
```

**成員 C 審查重點**：Story 是否太大、驗收條件是否能照著操作、P0 範圍是否與 PRD 一致、FR 覆蓋表有無遺漏。發現的問題開 Issue，由主開發請 agent 修正。

## 4. 一致性檢查（主開發執行，成員 B 主審）

新對話，輸入 `/bmad-check-implementation-readiness`，貼上：

```text
請交叉檢查 docs/PRD.md、docs/SCHEMA.md、docs/ARCHITECTURE.md、CLAUDE.md 與剛完成的 Epic、Story 之間的一致性：
1. 是否有 FR 或 BR 沒有對應的 Story、API 或測試。
2. Story 中提到的資料表、欄位、API 路徑、錯誤碼，是否和三份文件完全一致。
3. 業務規則在不同文件中是否有矛盾。
4. 由一位主開發以 AI 協助依序實作，P0 Story 能否在 11/01～11/14 完成；若有風險，建議哪些 Story 可延到 11/18 之後（只能從 PRD 標示為 P1 的項目中選）。
以表格列出問題：編號、嚴重程度、涉及文件、問題描述、建議修正。先不要修改任何檔案。
```

檢查結果要保存（AI 找到的、組內採納的、人工另外發現的），這是 (g) 最有說服力的素材。

## 5. Sprint 規劃（主開發執行，成員 C 追蹤）

新對話，輸入 `/bmad-sprint-planning`，貼上：

```text
請依 Epic 與 Story 建立 Sprint 狀態追蹤。開發者只有一位主開發，依序實作；每個 Story 完成後開 PR，經測試負責人與審查者核准才算完成。
- Sprint 1（11/01–11/07）：E1 全部，以及 E2、E3、E4 的 P0 Story。
- Sprint 2（11/08–11/14）：E5、E6、E7、E8 的 P0 Story。
- 整合週（11/15–11/17）：不排新 Story，只修正 Issue 與整合。
- Sprint 3（11/19–12/09）：所有 P1 Story、補齊測試、錯誤狀態與無障礙。
狀態欄位請包含：待開發、開發中、待審查、需修正、已完成。
```

## 6. 主開發：每個 Story 的循環

**一次只做一個 Story，每一步都開新對話（`/clear`）。**

### 6.1 建立 Story 檔

`/bmad-create-story`，貼上：

```text
請建立 Story【編號】的 Story 檔。除了一般內容，額外寫明：
1. 會新增或修改的檔案（後端、前端、測試分開列），路徑須符合 ARCHITECTURE.md 第 4 節。
2. 會用到的資料表與欄位，名稱必須和 docs/SCHEMA.md 完全相同。
3. 會實作的 API（方法、路徑、請求與回應範例、錯誤碼），必須和 ARCHITECTURE.md 第 5 節一致。
4. 會實作的 Service 類別與方法，名稱與參數必須和設計圖 D3 一致；流程依對應的 D5～D9 循序圖。訂單相關寫入只能經過 BookingService，狀態只能用 Booking.transition() 改變。
5. 必須通過的測試清單：每條驗收條件至少一個測試，含失敗情境，標註 FR／BR 編號。
6. 給測試負責人的手動驗證步驟：使用哪個測試帳號、在哪個頁面、操作什麼、預期看到什麼。
7. 不在本 Story 範圍、不應修改的部分。
```

### 6.2 實作

先建立分支：`git checkout -b story/【編號】-【簡述】`。然後 `/bmad-dev-story`，貼上：

```text
請實作 Story【編號】，嚴格遵守 CLAUDE.md：
1. 先寫測試，再寫程式，最後執行該 Story 的測試與全部既有測試。
2. 商業規則只寫在 service 層；跨表寫入用單一交易。
3. 不得修改資料表結構；若發現 Story 需要的欄位不存在，停下來告訴我。
4. 不修改與本 Story 無關的檔案。
5. 完成後回報：修改的檔案、新增的測試、實際執行的測試指令與結果、以及 Story 沒寫清楚而你自行判斷的地方。
```

第 5 點「自行判斷的地方」要逐條確認，這通常是 AI 猜錯的地方；也要寫進 PR 說明讓審查者知道。

### 6.3 自我檢查後開 PR

先用一次 `/bmad-code-review` 自我檢查（prompt 同 7.2 節），修掉明顯的問題，再推上 GitHub 開 PR。PR 說明使用以下格式：

```markdown
## Story【編號】：【標題】
對應：FR-xx、BR-xx

### 做了什麼
-

### 手動驗證步驟（給測試負責人）
1.

### 測試執行結果
（貼上 pytest／npm test 的輸出摘要）

### AI 自行判斷、需要審查者特別確認的地方
-
```

### 6.4 處理 Issue

驗證者開的 Issue，在同一個分支修正，commit 訊息寫 `fix #<Issue 編號>`。修正時可貼給 Claude Code：

```text
請修正 GitHub Issue #【編號】：【貼上 Issue 內容】
先說明根本原因，再修正；補一個能重現此問題的測試，修正後執行全部測試並回報結果。
```

## 7. 驗證者的工作流程

驗證者 clone repo 後，`git checkout <PR 分支>`，再依 ARCHITECTURE.md 第 11 節啟動系統。

### 7.1 測試負責人（成員 A）

**每個 PR**：

- [ ] 依 PR 的「手動驗證步驟」實際操作，包含失敗情境（例如時段已被預約、帳號被凍結）
- [ ] 手機寬度（瀏覽器開發者工具 360 px）與桌機各操作一次
- [ ] 執行 `docker compose exec api pytest`，確認結果與 PR 說明一致
- [ ] 有問題開 Issue；沒問題在 PR 按 Approve，留言寫「已依驗證步驟測試通過」與測試環境

**每完成一個 Epic**，用 Claude Code 補端對端測試：輸入 `/bmad-testarch-atdd`（或 `/bmad-help` 列出的對應名稱），貼上：

```text
請依 docs/PRD.md 的驗收條件與 Epic【編號】的 Story，為已完成的功能撰寫 Playwright 端對端測試，放在 e2e/。
1. 每條驗收條件至少一個測試，測試名稱標註 FR／BR 編號，包含失敗情境。
2. 使用種子資料的測試帳號（ARCHITECTURE.md 第 11 節）；需要寄信驗證的流程，從 Mailpit API（http://localhost:8025/api/v1/messages）取得信件連結。
3. 不得修改應用程式碼；若發現程式與驗收條件不符，列出來，我會開 Issue。
4. 執行測試並回報實際結果。
```

**E5 完成後**，確認併發測試存在並實際執行過：

```text
請檢查 backend/tests/concurrency/ 是否涵蓋 ARCHITECTURE.md 第 10 節列出的四種併發情境（同時段 20 筆預約只成立 1 筆、同一訂單併發付款只成功 1 次、付款與逾時排程競爭、同一人併發突破待付款上限）。缺少的請補上，使用實際 PostgreSQL。執行後回報每個測試的實際結果。
```

### 7.2 程式審查與安全（成員 B）

**每個 PR**，在 PR 分支上用 Claude Code 輸入 `/bmad-code-review`，貼上：

```text
請審查目前分支相對於 main 的程式變更（Story【編號】），依下列項目逐一檢查，以表格回報（項目、結果、檔案與行數、建議）：
1. 每條驗收條件是否都已實作並有測試。
2. 權限：未登入、非本人、非管理員是否都被擋下；不屬於本人的資源是否回 404。
3. 安全：CSRF、SQL 拼接、XSS、機密外洩、密碼與權杖是否只存雜湊。
4. 業務規則：對照 PRD 的 BR 編號逐條確認；金額是否由後端計算。
5. 交易與併發：跨表寫入是否在單一交易；寄信是否在提交後；是否違反 ARCHITECTURE.md 第 6 節。
6. 耦合與內聚：是否違反 CLAUDE.md 架構規則 2、7～12 與時間規範（直接設定 booking.status、BookingService 以外的地方寫訂單或退款、PaymentService 呼叫其他 Service、金額不經 policies 計算、布林旗標參數、直接讀系統時間、Service 回傳 ORM 物件）；類別與方法名稱是否與設計圖 D3 一致。
7. 時間：是否都使用含時區時間，畫面是否以 Asia/Taipei 顯示。
8. 程式品質：重複程式碼、過長函式、命名與 SCHEMA.md、ARCHITECTURE.md 不一致。
只回報問題，不要修改程式。
```

**審查者要自己判斷**：AI 的審查建議不一定正確。逐條決定「採納並開 Issue」「不採納」並寫下理由。把 AI 建議有誤或漏掉、由你自己發現的問題記入 AI 使用紀錄，這是 (g) 最好的素材。

除了 AI 審查，每個 PR 至少親自讀過 service 層的變更與 PR 說明中「AI 自行判斷」的項目。

### 7.3 專案管理與文件（成員 C）

- 每天更新 Sprint 狀態檔（或 GitHub Projects 看板），在群組回報進度與卡住的 PR。
- 每完成一個 Epic，用手機實機走一次該 Epic 的畫面，檢查文字、排版、載入中與錯誤訊息，問題開 Issue。
- 每週彙整 `docs/ai-usage-log.md`，提醒大家補紀錄。
- 11/18 前負責 (a)、(b) 文件與報告投影片（prompt 見第 8、9 節）。

### 7.4 Issue 格式

```markdown
**類型**：缺陷／安全／與規格不符／介面
**對應**：Story【編號】、FR-xx、BR-xx
**重現步驟**：
1.
**預期結果**：
**實際結果**：
**嚴重程度**：阻擋／高／中／低
**發現方式**：手動測試／AI 審查（已人工確認）／自動化測試
```

## 8. 11/18 文件：從確認稿延伸

四份文件的內容大多已在確認稿中，只需整理成課程要求的格式。每份文件開新對話，在一般模式（不需 BMAD skill）貼上對應 prompt。

| 文件 | 負責人 | 截止 |
|---|---|---|
| (a) 專案管理規劃 | 成員 C | 11/16 初稿 |
| (b) 需求分析 | 成員 C | 11/16 初稿 |
| (c) 架構設計 | 成員 B | 11/16 初稿（依實際程式碼核對） |
| (d) 物件設計 | 成員 B | 11/16 初稿（依實際程式碼核對） |
| (g) AI 使用紀錄（部分） | 成員 C 彙整，全員提供 | 11/17 |
| (e)(f) 測試計畫、測試個案與報告 | 成員 A | 12/14 |

11/17 全組互相校閱一次：文件與程式是否一致。

### (a) 軟體專案管理規劃

```text
請依 CLAUDE.md、docs/PRD.md、BMAD 產出的 Epic／Story 與 Sprint 狀態檔，撰寫 docs/course/a-專案管理規劃.md：
1. 專案目標、範圍與交付物（含 11/18 期中檢核與 12/16 期末 demo）。
2. 組織與分工：一人生成、三人驗證的角色分工（主開發、測試負責人、程式審查、專案管理與文件），各角色的工作、負責文件與 AI 使用；PR 核准與 Issue 流程。
3. 工作分解結構（WBS）：以 Epic → Story 呈現，標示 P0／P1。
4. 時程：甘特圖（Mermaid gantt），含 Sprint 1、Sprint 2、整合週、Sprint 3 與兩個里程碑。
5. 開發流程：BMAD 各 agent 與 workflow 在本專案的用途、分支與 PR 規則、完成定義（Definition of Done：測試通過、測試負責人與審查者核准、AI 使用已記錄）。
6. 風險管理：至少 6 項風險（例如時程壓力、併發錯誤、AI 產出與規格不符、成員環境問題），各附機率、影響、因應措施。
7. 品質與組態管理：測試策略摘要、版本控制、文件一致性維護方式。
只使用文件中已有的資訊；需要組員補充的資訊以【待填】標示，不要虛構。
```

### (b) 軟體需求分析

```text
請依 docs/PRD.md 撰寫 docs/course/b-需求分析.md：
1. 系統簡介與範圍、角色定義。
2. Use Case 圖（Mermaid flowchart 模擬，訪客、會員、管理員、排程系統四個角色）。
3. Use Case 清單（對應 FR 編號），以及核心 Use Case 的完整描述：註冊、Google 登入、搜尋空間、建立預約並付款、取消訂單、改期、管理員停用空間並處理受影響訂單。每個描述包含：參與者、前置條件、主要流程、替代流程、例外流程、後置條件、相關 BR。
4. 業務規則表（BR-01～26）。
5. 非功能需求。
6. 術語表（Glossary）：空間、場館、訂單、房間密碼、冪等鍵、軟刪除、排除約束等。
7. 需求追溯表：US → FR → Use Case。
內容必須與 PRD 一致，不得新增需求。
```

### (c) 軟體設計（架構設計）

```text
請依 docs/ARCHITECTURE.md、docs/SCHEMA.md、docs/設計圖_邏輯設計與細部設計.md（L1～L5）與 docs/設計審查_耦合與內聚.md 撰寫 docs/course/c-架構設計.md：
1. 設計目標與限制（課程要求、技術限制）。
2. 系統架構圖、部署圖（Docker Compose 服務）。
3. MVC 與分層說明，各層職責與相依方向。
4. 技術選型與理由。
5. 資料設計：ER 圖、資料表總覽（表數與平均欄位數）、關鍵約束（特別說明排除約束如何防止重複預約）。
6. API 設計：端點總表與錯誤處理。
7. 關鍵設計決策：交易與併發、安全、時間處理、外部服務替代方案；每項說明考慮過的方案與取捨。
8. 設計品質評估：耦合與內聚。引用設計審查的評估基準、優點、C1～C13 問題與修正、修正前後的相依圖與指標表，以及 SCHEMA.md 記錄的 C11 已知取捨。
請以目前 repo 的實際程式碼核對，若文件與程式不一致，列出差異讓我們決定以哪個為準。
```

### (d) 物件設計

```text
請依 docs/ARCHITECTURE.md、docs/設計圖_邏輯設計與細部設計.md（D1～D13，v2）與 repo 中的實際程式碼，撰寫 docs/course/d-物件設計.md：
1. 類別圖（Mermaid classDiagram）：分別畫 Model 層、Service 層，以及 Controller（Blueprint）與 Service 的相依；標示屬性、方法、關聯與多重性。
2. 核心 Service 說明：BookingService、PaymentService、PricingPolicy、RefundPolicy、AccessCodeService、AvailabilityService、AuthService、PasswordService、GoogleAuthService。並說明 Booking.transition() 狀態機；每個 Service 標註其內聚等級與它和其他類別的耦合方式。每個公開方法寫明輸入、輸出、前置條件、後置條件、可能拋出的例外與對應錯誤碼。
3. 循序圖（Mermaid sequenceDiagram）：Google 登入（三種情況）、建立訂單（含併發衝突）、付款（含冪等與逾時競爭）、取消並退款、改期補付差額。
4. 狀態圖：Booking、User。
5. 使用的設計原則與模式（例如分層、依賴注入、純函式 Policy、DTO、Outbox 式通知、冪等設計），各說明在本系統的位置與理由。
類別與方法名稱必須和實際程式碼一致；程式尚未實作的部分標示【規劃中】。
```

### (g) AI 使用紀錄（部分）

```text
請閱讀 docs/ai-usage-log.md，依軟工活動（需求、設計、程式、測試、專案管理）分類整理，撰寫 docs/course/g-AI使用紀錄.md：
1. 使用的工具與 BMAD agent，以及我們採用的工作模式（先由人定案規格，再由 agent 依規格執行）。
2. 每個活動：用 AI 做了什麼、prompt 怎麼下、AI 的錯誤或不足、人工如何發現與修正、如何驗證。
3. 成熟度反思：哪些工作可放心交給 AI、哪些必須人工把關，以及原因。
只使用紀錄中確實發生的事件，不得虛構。
```

## 9. 期中報告投影片

```text
請依 docs/course 下的 (a)～(d)、(g) 與實際系統，規劃 8 分鐘期中報告：
1 分鐘系統定位與範圍；3 分鐘 demo（搜尋 → 選時段 → 付款 → 房間密碼 → 取消退款 → 管理後台查看）；3 分鐘挑選架構圖、ER 圖、一張預約與付款循序圖、甘特圖；1 分鐘 AI 使用實例（從 ai-usage-log 中挑 2 個「AI 出錯 → 人工發現 → 修正」）。
請給每張投影片的標題、要放的圖、講者要講的重點（每張不超過 3 點），以及 demo 操作腳本與備案。
```

## 10. Copilot 的分工

BMAD workflow 一律在 Claude Code 執行，讓文件與程式保持一致。Copilot 用在：寫程式時的自動補完、小範圍修改、產生單一函式的測試。使用 Copilot Chat 時，先用 `#file:CLAUDE.md` 帶入專案規範。

## 11. 常見問題

| 狀況 | 處理方式 |
|---|---|
| agent 想修改資料表或更換套件 | 拒絕；若確實需要，全組討論後先改 SCHEMA.md／ARCHITECTURE.md，再改程式 |
| agent 回報「測試通過」但沒附指令輸出 | 要求貼出實際執行的指令與輸出 |
| 驗證者想直接改程式 | 開 Issue 由主開發修正，保持程式由同一流程產生；文件與測試程式則由驗證者自己提交 |
| Story 太大，一次做不完 | 請 agent 把 Story 拆成兩個，更新 Sprint 狀態檔 |
| PR 累積太多審查不完 | 主開發暫停開新 Story，先處理 Issue；審查順序以核心流程優先 |
| 對話太長，AI 開始忘記規則 | 開新對話；CLAUDE.md 會自動重新載入 |
