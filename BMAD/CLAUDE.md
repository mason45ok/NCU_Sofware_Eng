# CLAUDE.md

本檔由 Claude Code 在每次對話自動讀取。內容是本專案已確認的技術棧、開發規範與指令；修改前須經全組同意。

## 專案

「聚點」空間租借系統：會員搜尋並預約活動空間、模擬付款、取得房間密碼自助入場；管理員維護場館、空間、訂單與會員。軟體工程課程期末專案，4 人小組。

**開發模式**：由主開發一人以 BMAD＋Claude Code 生成全部程式，其他三人負責測試、審查與文件。每個 Story 一個分支與 PR，經驗證者核准才合併；驗證者回報的問題以 GitHub Issue 追蹤。

- 期中檢核 **2026-11-18**：所有 P0 功能可從頭到尾操作，並完成文件 (a)–(d) 與部分 (g)。
- 期末 demo **2026-12-16**。

## 文件分工（唯一依據，不要重複抄寫）

| 檔案 | 內容 |
|---|---|
| `docs/PRD.md` | 範圍、角色權限、業務規則 BR-xx、功能需求 FR-xx 與驗收條件、頁面、UI 方向 |
| `docs/SCHEMA.md` | 正式資料結構、ER 圖、約束；`docs/sql/schema.sql` 為已驗證的參考 DDL |
| `docs/ARCHITECTURE.md` | 技術棧與理由、架構、目錄、API 清單、交易與併發、安全、測試策略、指令 |
| `docs/設計圖_邏輯設計與細部設計.md` | 模組相依、類別圖（類別與方法名稱的依據）、循序圖、狀態圖、活動圖；`docs/圖檔/` 為 PNG |
| `docs/設計審查_耦合與內聚.md` | 耦合與內聚審查結果與設計取捨（C1～C13） |
| `docs/ai-usage-log.md` | AI 使用紀錄（課程文件 (g) 的來源） |

需求、資料表或 API 與這些文件不一致時，**先停下來說明差異並詢問**，不要自行選一邊。

## 技術棧（不可自行更換）

- 後端：Python 3.12、Flask 3、SQLAlchemy 2、Flask-Migrate、Pydantic 2、Flask-Login、Flask-WTF（CSRF）、Authlib、Flask-Limiter、APScheduler、Gunicorn
- 資料庫：PostgreSQL 16（需 `btree_gist`）
- 前端：React 18、Vite、TypeScript、React Router 6、TanStack Query 5、React Hook Form、Zod、Mantine 7、dayjs
- 測試：pytest、pytest-cov、Vitest、Testing Library、Playwright、Locust
- 環境：Docker Compose（web、api、scheduler、db、mailpit）

新增套件前先說明用途與理由，並更新 ARCHITECTURE.md 第 1 節。

## 架構規則

1. MVC：Model＝`backend/app/models`；Controller＝`backend/app/blueprints`；View＝`frontend`。商業邏輯只能放在 `backend/app/services` 與 `backend/app/policies`。
2. Blueprint 只做：解析請求、Pydantic 驗證、呼叫 service、轉換回應。Service 回傳 DTO（`schemas/` 的 Pydantic 模型），ORM 物件不離開 Service 層。
3. 跨多張表的寫入必須在 service 中以單一交易完成；寄信在交易提交後執行。
4. 權限與資料所有權在後端檢查；不屬於本人的資源回 404。前端隱藏按鈕不算權限控制。
5. 金額、可預約時段、退款比例一律由後端計算，前端只顯示。
6. 防止重複預約依賴資料庫排除約束 `ex_bookings_no_overlap`，不可改成「先查再新增」。
7. 訂單狀態只能透過 `Booking.transition()` 改變（它檢查轉換是否合法並寫入 `booking_status_logs`）；改期與部分退款不改狀態，用 `Booking.record()` 寫紀錄。不得在其他地方直接設定 `booking.status`。
8. 訂單相關的寫入（訂單、狀態紀錄、退款）只能經過 `BookingService`；`PaymentService` 只負責模擬金流與寫 payments，不呼叫其他 Service。
9. 金額、價差與退款比例只能由 `policies/pricing.py`、`policies/refund.py` 的純函式計算；試算 API 與正式流程呼叫同一個函式。
10. 公開方法不用布林旗標切換行為（例如不要 `cancel(by_admin=True)`），改成兩個方法（`cancel_by_member`、`cancel_by_admin`）共用私有核心。
11. Service 拋出的例外只帶錯誤碼；HTTP 狀態碼對照放在 `errors.py`。
12. 類別與方法名稱依設計圖 D3；需要新增或改名時先提出。
13. 不得自行新增、刪除或改名資料表與欄位；需要時先提出並等待確認，確認後同步更新 SCHEMA.md 與 migration。

## 程式規範

- Python：型別標註；ruff 格式化與檢查；函式與變數英文命名，註解與 docstring 用繁體中文。
- TypeScript：`strict` 模式；ESLint＋Prettier；元件 PascalCase，hook 以 `use` 開頭。
- API：前綴 `/api/v1`；錯誤格式 `{"error": {"code", "message", "details"}}`；錯誤碼使用 ARCHITECTURE.md 5.1 節定義的代碼。
- 時間：資料庫與 API 使用含時區的 ISO 8601；畫面一律以 Asia/Taipei 顯示。Service 不直接讀系統時間，一律透過注入的 `Clock`（`utils/clock.py`），測試時用固定時間；時區轉換用 `utils/time.py`。
- 安全：不使用 `dangerouslySetInnerHTML`；不拼接 SQL 字串；機密只從環境變數讀取，不寫進程式或提交到版控。
- 介面文字使用繁體中文；錯誤訊息要告訴使用者下一步怎麼做。

## 測試規則

- 每個 Story 完成時，其驗收條件都要有自動化測試，含失敗情境。
- 每條業務規則 BR-xx 至少一個成功與一個失敗測試；測試名稱或 docstring 標註 BR／FR 編號。
- 併發測試必須使用實際 PostgreSQL，不可用 SQLite 或 mock 代替。
- 回報時只能說明實際執行過的測試結果；未執行的標示「未執行」。

## 常用指令

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec api flask db upgrade
docker compose exec api flask seed
docker compose exec api pytest
docker compose exec api pytest tests/concurrency -v
docker compose exec api flask db migrate -m "說明"
cd frontend && npm test
cd e2e && npx playwright test
```

網址：前台與後台 `http://localhost:8080`；測試信箱 `http://localhost:8025`。測試帳號見 ARCHITECTURE.md 第 11 節。

## 工作方式

- 一次只做一個 Story，在 `story/<編號>-<簡述>` 分支上進行；完成後回報：修改的檔案、新增的測試、測試執行結果、以及 Story 沒寫清楚而自行判斷的地方（這些要寫進 PR 說明給審查者確認）。
- 修正 GitHub Issue 時，commit 訊息寫 `fix #<編號>`。
- 修正錯誤時先說明根本原因，並補一個能重現該錯誤的測試。
- 不修改與目前工作無關的檔案。
- 每次重要的 AI 協助（產出、被人工修正之處、修正理由）由組員記錄到 `docs/ai-usage-log.md`。
