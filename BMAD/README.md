# 聚點 空間租借系統

會員搜尋並預約活動空間、模擬付款、取得房間密碼自助入場；管理員維護場館、空間、訂單與會員。軟體工程課程期末專案。

- 後端：Python 3.12、Flask 3、SQLAlchemy 2、PostgreSQL 16
- 前端：React 18、Vite、TypeScript、Mantine 7
- 環境：Docker Compose（web、api、scheduler、db、mailpit）

> 狀態說明：需要資料庫的測試（Service、API、併發）已撰寫但**尚未在實際 PostgreSQL 上執行**，第一次啟動後請先跑一次 `pytest` 並回報結果。

## 1. 事前準備

| 工具 | 用途 | 確認指令 |
|---|---|---|
| Git | 取得程式 | `git --version` |
| Docker Desktop（Windows 需啟用 WSL2） | 一鍵啟動全部服務 | `docker compose version` |
| Node.js 20 以上（選用） | 只有要在本機跑前端開發伺服器或前端測試才需要 | `node -v` |

## 2. 五分鐘啟動

在專案根目錄依序執行：

```bash
cp .env.example .env                       # Windows PowerShell：Copy-Item .env.example .env
docker compose up --build -d               # 第一次需要幾分鐘建置
docker compose exec api flask db upgrade   # 建立資料表（含防重複預約的排除約束）
docker compose exec api flask seed         # 建立測試帳號、場館與空間
```

完成後開啟：

| 網址 | 內容 |
|---|---|
| http://localhost:8080 | 前台與後台（後台入口：用管理員登入後，右上角帳號選單 →「管理後台」，或直接開 `/admin`） |
| http://localhost:8025 | Mailpit 測試信箱（驗證信、確認信、房間密碼都在這裡看） |

停止：`docker compose down`。連資料一起清除：`docker compose down -v`。

## 3. 測試帳號

密碼皆為 `Passw0rd!`。

| 帳號 | 角色與狀態 | 用途 |
|---|---|---|
| admin@judian.local | 管理員 | 管理後台 |
| user1@judian.local、user2@judian.local | 會員，已驗證 | 一般預約流程 |
| unverified@judian.local | 會員，未驗證 | 測試 email 驗證 |
| frozen@judian.local | 會員，凍結 | 無法預約、付款、改期，但可取消 |
| blacklisted@judian.local | 會員，黑名單 | 同上 |
| g1@gmail.com（Google mock，sub `google-001`） | 只用 Google 登入 | Google 登入、設定本地密碼 |

## 4. 五分鐘試玩

1. 用 `user1@judian.local` 登入 → 「找空間」→ 進入任一空間。
2. 選日期，點時段格選開始與結束（中間自動連續選取），畫面會顯示後端試算的金額。
3. 按「預約」→ 填人數 → 送出，進入付款頁（15 分鐘倒數）。
4. 卡號輸入 `4000 0000 0000 0002`：**一律遭拒**，可測試失敗與重付；改用 `4242 4242 4242 4242` 付款成功。
5. 「我的訂單」→ 訂單詳細：房間密碼在開始前 10 分鐘才會顯示；可試取消（先顯示預計退款）、改期（顯示價差）。
6. 到 Mailpit 查看確認信。
7. 用 `admin@judian.local` 登入 `/admin`：查訂單、取消、代為改期、部分退款，或把空間改為維修中，看受影響訂單清單。

Google 登入在開發模式使用模擬頁面（`GOOGLE_MOCK=true`），可選三種情境：已綁定、全新帳號、email 已存在需輸入密碼綁定。

## 5. 常用指令

```bash
# 後端測試（容器內，使用 compose 的 PostgreSQL，測試庫 judian_test）
docker compose exec api pytest
docker compose exec api pytest tests/concurrency -v     # 併發測試：20 筆同時段預約只成立 1 筆
docker compose exec api ruff check .                    # 程式風格檢查

# 資料庫結構變更
docker compose exec api flask db migrate -m "說明"
docker compose exec api flask db upgrade

# 重設資料：清空後重建
docker compose down -v && docker compose up --build -d
docker compose exec api flask db upgrade && docker compose exec api flask seed

# 看日誌（排程在 scheduler 容器）
docker compose logs -f api scheduler

# 前端（本機需要 Node.js）
cd frontend && npm install
npm run dev        # 開發伺服器 http://localhost:5173，/api 代理到 localhost:8080（需先 compose up）
npm test           # Vitest
npm run lint && npm run build

# 端對端測試（系統需先啟動並 seed）
cd e2e && npm install && npx playwright install && npx playwright test

# 壓力測試
docker compose exec api locust -f tests/load/locustfile.py --host http://web --headless -u 100 -r 20 -t 1m
```

修改後端程式後執行 `docker compose up --build -d api scheduler` 重新建置。

## 6. 不用 Docker 的本機後端開發（選用）

需要自行準備 PostgreSQL 16（含 `btree_gist` 擴充），建立資料庫 `judian` 與 `judian_test`。

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows：.venv\Scripts\activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/judian
export TEST_DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/judian_test
export FLASK_APP=app
flask db upgrade && flask seed
flask run --port 8000
pytest
```

不需要資料庫的測試可直接執行：`pytest tests/unit/test_policies.py tests/unit/test_booking_model.py tests/unit/test_slot_validation.py tests/unit/test_passwords.py`。

## 7. 專案結構

```text
backend/app/
  models/        資料表對應（16 張表）；Booking.transition() 是唯一能改訂單狀態的地方
  services/      商業邏輯與交易；BookingService 是訂單流程唯一入口
  policies/      金額與退款比例的純函式
  blueprints/    API 路由，只解析請求、呼叫 Service、轉換回應
  schemas/       Pydantic 請求與回應（DTO）
  jobs/          排程工作
backend/tests/   unit、api、concurrency、load
frontend/src/    pages（頁面）、components、api（API 用戶端與查詢）
e2e/             Playwright
docs/            規格與設計文件
```

## 8. 文件導覽

| 想知道 | 看哪裡 |
|---|---|
| 需求、業務規則 BR-xx、功能需求 FR-xx | `docs/PRD.md` |
| 資料表與約束 | `docs/SCHEMA.md`、`docs/sql/schema.sql` |
| 架構、API 清單、錯誤碼、交易與併發 | `docs/ARCHITECTURE.md` |
| 類別圖、循序圖、狀態圖 | `docs/設計圖_邏輯設計與細部設計.md` |
| Use Case 圖、需求到程式與測試的對照 | `docs/用例圖與程式追溯.md` |
| 開發規範與 AI 協作規則 | `CLAUDE.md` |

## 9. 常見問題

- **`flask db upgrade` 連不上資料庫**：db 容器還在啟動，等幾秒重試；用 `docker compose ps` 確認 db 為 healthy。
- **8080、5432 或 8025 連接埠被占用**：關閉占用的程式，或修改 `docker-compose.yml` 的連接埠對應。
- **看不到信**：確認 `.env` 的 `SMTP_HOST=mailpit`，信件在 http://localhost:8025。
- **上傳的照片看不到**：照片存在 `uploads` volume，由 web 容器提供；若用 `docker compose down -v` 清除過資料，請重新 `flask seed`。
- **pytest 出現 `btree_gist` 或連線錯誤**：測試庫 `judian_test` 只在 db 容器**第一次建立**時自動建立；若 db volume 是舊的，執行 `docker compose down -v` 後重新啟動。
- **前端改了沒反應**：用 Docker 時要重新建置 web（`docker compose up --build -d web`）；開發時改用 `npm run dev`。
