# 基礎設施架構盤點與改善方案

> 審查日期：2026-07-12｜審查角度：架構師視角「在正確的規模用正確的工具」
> 審查方法：五個子系統平行盤點 → 逐元件必要性判定 → 跨系統一致性檢查 → 對抗性雙視角驗證
> 驗證強度：40 條判定，其中 34 條經對抗性驗證保留（15 條通過完整雙視角驗證）

---

## 0. 一句話結論

**在「幾個朋友、每人每日 50 張名片」的實際規模下，這套系統的基礎設施明顯過度設計。**
Redis / RQ / honcho 雙進程 / Flask-SocketIO / APScheduler 這五樣，**沒有一樣是此規模的必需品**——它們解的問題，用專案裡**已經存在且已證明可用的 SQLite** 機制就能解，而且更簡單、更可靠、跨進程天然一致。

更關鍵的是：這些「分散式」基礎設施不只是多餘，它們**在現行的多進程部署下本身就是壞的**——SocketIO 收不到推播、APScheduler 重啟即失效、Redis 掛掉時每日限額靜默翻倍。也就是說，你付了分散式的複雜度成本，卻沒得到分散式的正確性。

**核心答案：不需要 Redis。** 能用 SQLite 的原子 `UPDATE`／`UPSERT` 取代（專案的 `consume_scan` 已經示範過正確做法）。若未來真的成長到需要多 replica，正確的一步是遷 Postgres 統一狀態，而不是留著現在這套 SQLite + Redis 雙持久層。

---

## 1. 規模 vs 基礎設施對照

| 面向       | 實際數字                                             | 現有基礎設施假設                       |
| ---------- | ---------------------------------------------------- | -------------------------------------- |
| 使用者     | 幾個朋友（租戶數個位數）                             | 分散式多租戶                           |
| 每日流量   | 每人上限 50 張，總計每日數百 webhook                 | 需要佇列削峰、水平擴展                 |
| 尖峰       | 批次模式一次最多 10 張                               | RQ 佇列 + 獨立 worker                  |
| 部署       | Zeabur Hobby，1 CPU / 1Gi RAM                        | `zeabur.json` 宣告 max:3 replicas      |
| 持久層     | SQLite 掛單一 volume                                 | 同時用 SQLite + Redis 兩套             |
| 跨進程需求 | gunicorn 2 workers（實際被 SQLite 釘死在單 replica） | Redis 分散式鎖、SocketIO message queue |

**瓶頸從來不是 SQLite 的能力，而是部署宣告的虛胖。** 每日幾百個請求，SQLite 單機閒到發慌；Redis 承接的所有狀態，量級小到用一張 SQLite 表就綽綽有餘。

---

## 2. 必須先修的真 Bug（P0，與「要不要簡化」無關）

這幾條是**現況就有 bug**，不論你選哪個目標架構，動工前都該先修。

### 2.1 配額系統在唯一的「拒絕」路徑上崩潰 —— fail-open

- **位置**：`event_handler.py:174` 呼叫 `tenant_service.get_tenant(self.tenant_id)`
- **問題**：`TenantService` 上根本沒有 `get_tenant()`，只有 `get_tenant_by_id()`（`tenant_service.py:245`）。配額耗盡時 `check_scan_quota` 正確回報 `has_quota=False`，進入回覆分支後**立刻拋 `AttributeError`**，被 `227` 行 `except` 吞掉後「fall back to default limit」；而 `232` 行的向後相容檢查 `if not self.tenant_id and daily_usage >= 50` 又因為 `tenant_id` 存在而跳過。
- **後果**：**配額用完的租戶完全不受限**，`consume_scan` 還繼續累加。整套訂閱方案（plan_versions、grandfathering、交易流水）在唯一該擋人的地方形同虛設，最後防線只剩 Gemini API 自己的 quota。
- **修法**：`event_handler.py:174` 改成 `get_tenant_by_id(self.tenant_id)`（一行），並補一個測試：mock `check_scan_quota` 回 `has_quota=False`，斷言使用者收到配額訊息且圖片未進處理流程。現有 e2e 測試沒蓋到這條路徑，否則早就抓到。

### 2.2 SocketIO 在多 worker 下收不到推播

- **位置**：`socketio_events.py:19-22`，`SocketIO(app, cors_allowed_origins="*", async_mode="threading")`——**沒有 `message_queue` 參數**。
- **問題**：Procfile 跑 2 個 gunicorn worker。Flask-SocketIO 官方明言多 worker 必須配 `message_queue` + sticky sessions，兩者皆無。Drive 同步在 worker A 的背景 thread `emit`，管理後台若連在 worker B 就**永遠收不到**。這不用等 scale 到 3，現行單容器內就已壞。
- **好消息**：`routes.py:1133` 已經有一個跨進程天然正確的 SQLite 輪詢端點 `/api/drive/sync-status/<tenant_id>`，回傳進度百分比與狀態。即時推播層是與正確方案並存的壞件。
- **修法**：整個砍掉 SocketIO（刪 `socketio_events.py`、`app.py` 初始化、所有 `emit_sync_*`、`requirements` 的 flask-socketio），管理後台前端改每 2 秒輪詢既有端點。附帶修掉不必要全開的 `cors_allowed_origins="*"`。

### 2.3 APScheduler 重啟後排程全部沉睡 + 多 worker 重複執行

- **位置**：`app.py` 從不呼叫 `init_scheduler`，唯一初始化點在 `routes.py:1248`（管理員 POST 排程時才 lazy init）。
- **問題**：
  1. **每次部署後 `scheduler_jobs.db` 內的 job 全部沉睡**，直到有人進後台重存排程——「定時同步」實質是重啟即靜默失效的功能。
  2. lazy init 是 per-process 的，兩次管理請求路由到不同 gunicorn worker 就有 2 個 `BackgroundScheduler` 掛同一個 jobstore，同一 cron 到點**各跑一次**（`max_instances=1` 只限單一 scheduler 實例內）——同批 Drive 圖片辨識兩次、Notion 建兩份。
  3. `scheduler.py:163-175` 把 notion / google API key **明文序列化**進 `scheduler_jobs.db`，違反 `tenants.db` 的 Fernet 加密政策。
- **修法**：刪掉 APScheduler + SQLAlchemyJobStore + `scheduler_jobs.db`。排程改成單一背景 thread 每 60 秒醒來、用 croniter 判斷各租戶 cron 欄位是否到點（憑證執行時才解密，不寫入磁碟）。或更簡單：用 Zeabur scheduled job / 外部 cron-job.org 定時打一個帶 token 的內部端點。

### 2.4 生產程式碼硬編碼開發機絕對路徑（名片寫入熱路徑上的固定成本）

- **位置**：`notion_client.py:269,415,459` 每次存卡都 `open("/Users/user/Ecofirst_namecard/.cursor/debug.log", "a")`；`rq_worker.py:37` 同路徑且 `RQ_WORKER_DEBUG_LOG` 未設時**預設啟用**；另有 6 處寫 `/tmp/namecard_debug.log`。
- **問題**：生產容器內這些路徑不存在，每筆寫入都拋 `FileNotFoundError` 再被吞掉——每一筆名片寫入都在付這個死成本；且 `DEBUG_*` 事件以 **warning 級別**打出，污染告警訊號。
- **修法**：全部刪除檔案側寫，需保留的診斷點改 `logger.debug`（structlog 已在用），`DEBUG_*` 從 warning 降到 debug。生產想看細節就調 log level。

---

## 3. Redis 過度設計清單 —— 為什麼可以整個拔掉

Redis 在這套系統裡承接三類狀態，**每一類都有更簡單的 SQLite 替代，且替代方案順帶修掉現有 bug**。

| Redis 用途                         | 位置                                     | 問題                                                                                                                         | SQLite 替代                                                                                                        |
| ---------------------------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 使用者每日限額 + 批次狀態          | `user_service.py:48-83`                  | JSON blob `GET`→改→`SETEX` 整包寫回，**並發 lost update**；Redis 掛掉時靜默落回記憶體，2 worker 各算各的→**限額實際變 50×2** | `user_status` 表，`UPDATE ... SET daily_usage = daily_usage + 1`（單句原子）；日期換了自然歸零，連重設邏輯都不用寫 |
| 滑動窗口 rate limit（ZSET）        | `security.py:113-194`                    | **純死碼**，生產零呼叫端；ZSET 四指令還非原子                                                                                | 直接刪。未來要防灌爆，`user_status` 加 `last_request_at` 做最小間隔                                                |
| 封鎖名單（SETEX）                  | `security.py` + `event_handler.py:148`   | `block_user` 無呼叫端，**名單恆空**，卻每張圖查一次 Redis                                                                    | 直接刪。要手動封鎖時，SQLite `blocked_users` 表 + 後台按鈕，語意還更貼近需求                                       |
| 失敗上傳記錄                       | `image_upload_worker.py:591+`            | 存整張 base64 圖進 Redis（膨脹）；`retry-all` 用 `keys()` 全鍵掃描                                                           | `failed_uploads` 表，圖用 BLOB 存免 base64 膨脹                                                                    |
| RQ 佇列後端                        | `image_upload_worker.py`, `rq_worker.py` | 見 §4                                                                                                                        | 隨 RQ 一併移除                                                                                                     |
| 分散式鎖 `embedded_rq_worker_lock` | `main.py:910`                            | **寫入端已從 codebase 移除**，只剩一個孤兒 `delete`                                                                          | 隨 RQ 移除                                                                                                         |

**關鍵洞察**：專案裡 `quota_service.consume_scan` 的 CAS `UPDATE` + rowcount、`tenant_db` 的 `user_stats` UPSERT 累加，**已經是跨進程原子計數的正確示範**。也就是說——正確與錯誤的實作在同一顆 codebase 裡並存，Redis 版反而是錯的那個。拔掉 Redis 不是冒險，是把錯的那半邊對齊到已經對的那半邊。

---

## 4. 圖片上傳管線：一個需求養了四套實作，實際只走一套

「webhook 回覆不等圖片上傳完成」這**一個需求**，現在疊了四套機制：

1. **RQ + 獨立 worker 進程**（`rq_worker.py` 653 行，其中約 470 行在對抗 RQ 自己的 worker 註冊問題——git `8b46aa7`、`801f206` 兩個 commit 都在修它）
2. **`ImageUploadWorker` in-memory queue**（**純死碼**：`src/` 與 `app.py` 零引用，只有測試用；但 `get_queue_info` 在 RQ 不可用時仍回報它的 `queue_size`——**監控吐假資料**）
3. **`_sync_upload_image` 同步路徑**（`image_upload_worker.py:497-547`，程式註解自承這條路徑最可靠，**是實際可靠、也是常走的那條**）
4. **`image_storage.upload_async` daemon thread**（主流程未使用，worker 回收時上傳無聲消失）

**而且**：LINE 回覆其實在提交上傳**之前**就送出了（`event_handler` 先 `_send_processing_result` 才 `submit_image_upload`）——非同步性對使用者本來就不可見，整套佇列在解一個已經不存在的問題。

**改法**：四選一，保留 `_sync_upload_image` 用 `threading.Thread`（或 `ThreadPoolExecutor(max_workers=1)`）包一層讓請求執行緒不被佔住；其餘三套（RQ + `rq_worker.py`、`ImageUploadWorker`、`upload_async`）連同 Procfile worker 行與 honcho 一併刪除。失敗補償統一走 SQLite `failed_uploads` 表 + 現有「重試」指令。

**附帶修掉的重試風暴**：現在同一次上傳最壞對掛掉的 ImgBB 打 **12 次 HTTP**（客戶端 3 次 × RQ Retry 4 次），且手動 `/admin/worker/process-pending` 可與 worker 重複跑同一 job 造成 Notion 重複附圖。收斂成單層重試即可。

---

## 5. 部署宣告 vs 程式假設：11 個矛盾（濃縮）

系統的部署宣告（多 replica、分散式）與程式碼的實際假設（單進程、本機狀態）**系統性地互相矛盾**：

| #   | 矛盾                                                                                                                                                                     | 嚴重度    |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- |
| 1   | `zeabur.json` scaling max:3 **vs** SQLite 掛單一 volume——volume 無法多 replica 掛載，實際被釘死在 1 replica                                                              | 🔴 high   |
| 2   | Procfile 每 replica 一個 RQ worker **vs** `rq_worker.py` 的 stale 清理假設自己是唯一 worker——多 replica 啟動時互刪註冊                                                   | 🔴 high   |
| 3   | gunicorn 2 workers **vs** SocketIO 無 message_queue（§2.2）                                                                                                              | 🔴 high   |
| 4   | 多進程部署 **vs** 模組層可變狀態（`_last_destination`、Redis fallback 記憶體、quota 旗標、schema 快取全是單進程假設）                                                    | 🔴 high   |
| 5   | APScheduler per-process lazy init **vs** 多 worker + 「定時同步」宣告（§2.3）                                                                                            | 🔴 high   |
| 8   | 訂閱配額宣告強制執行 **vs** 拒絕路徑 fail-open（§2.1）                                                                                                                   | 🔴 high   |
| 6   | gunicorn `--timeout 120` **vs** ImgBB 同步路徑最壞 ~180s（60s × 3）→ worker 被 SIGKILL                                                                                   | 🟡 medium |
| 7   | 宣告 Gemini `timeout_seconds=30` **從未生效**（只拿去組錯誤訊息，`generate_content` 沒傳 timeout）→ 一次網路黑洞佔死 worker 到 120s，2 個並發掛住整站含 `/health` 無回應 | 🟡 medium |
| 9   | `CLAUDE.md` 文件描述兩代前架構（內嵌 worker、分散式鎖）**vs** 現行程式；`requirements` 的 `redis>=5.0.0` 無上限違反同份文件的 Hard Rule #1                               | 🟡 medium |
| 11  | `--preload` **vs** 模組載入期建的 Redis 連線池（fork 後未重建，違反 redis-py 官方建議）                                                                                  | 🟡 medium |
| 10  | 生產硬編碼開發機路徑（§2.4）                                                                                                                                             | 🟢 low    |

**槓桿點**：矛盾 #1、#4、#5、#11 有一個共同的一行解——把 `zeabur.json` scaling 改 `max:1`、gunicorn 改 `--workers 1 --threads 4`。**單 worker 讓所有 module-level 單例、in-memory 狀態、背景 thread 全部一次變正確**。這是「把部署宣告改成與程式假設一致」，而不是反過來去餵養一個用不到的分散式假設。

---

## 6. 目標架構建議：採用方案 A

盤點產出三個目標架構，逐一評估後**建議方案 A**。

### ✅ 方案 A（建議）：全砍 Redis，單 replica + 單 gunicorn worker + SQLite 統一狀態

把部署宣告改成與程式假設一致：

- `zeabur.json` scaling → `min:1 max:1`
- Procfile 退回單行：`web: gunicorn --workers 1 --worker-class gthread --threads 4 --timeout 120 app:application`（刪 `--preload`、刪 worker 行）
- `requirements` 刪 `redis`、`rq`、`honcho`、`flask-socketio`
- 狀態全部收斂到既有 `tenants.db`（開 WAL + `busy_timeout=15s`）：新增 `user_status` 表（每日計數、批次旗標）與 `failed_uploads` 表（BLOB 存圖）
- 圖片上傳走現成 `_sync_upload_image` + `threading.Thread`
- 排程改單一背景 thread + croniter

**得**：刪掉約 1,000+ 行「基礎設施對抗程式碼」與 4 個依賴、消除本報告大多數矛盾與重複、運維面歸零（一個 process、一顆 DB 檔）、Redis 費用與連線管理消失。
**失**：水平擴容能力（此流量用不到）、process 重啟瞬間 in-flight 上傳遺失（名片主資料已在 Notion，失敗表 + 重傳可補）、吞吐上限約 4 併發（每日幾百 webhook 無感）。
**前提**：接受單 replica 為長期形態（`tenants.db` 本來就鎖定這件事，無新增約束）；ImgBB timeout 降到 15-20s 讓同步路徑安全落在 gunicorn timeout 內。

### ⚠️ 方案 B：保留 Redis 只做佇列（不建議）

只在「半年內有明確流量成長/商業化」且「願意持續維護 RQ worker 註冊問題」時才合理。否則是「付 A 的遷移成本、留 RQ 的維護稅」的劣勢組合——狀態遷 SQLite 兩案都要做，B 只降三成複雜度。

### 🔮 方案 C：遷 Postgres 統一所有狀態（未來選項）

唯一真正支援多 replica 的方案：佇列用 `SELECT ... FOR UPDATE SKIP LOCKED`、互斥用 advisory lock、進度用 LISTEN/NOTIFY。**觸發條件明確才啟動**：租戶數成長到數十個、訂閱制真的收費且 SLA 要求消除單 replica 重啟窗口。在那之前，C 是把「Redis 過度設計」換成「Postgres 過度設計」。

---

## 7. 「不要動」清單 —— 避免過度簡化反而弄壞

簡化的方向是對的，但以下幾樣是**合理設計，不要順手砍掉**：

| 元件                                    | 為什麼保留                                                                                                                                                                |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`tenant_service` 的 Fernet 憑證加密** | 朋友們的 LINE / Notion token 存在 volume，加密是對的。**只修配置**：`SECRET_KEY` 未設時 fail-fast、解密失敗拋例外（帶 tenant_id）而非靜默回空字串。不要為了簡化拿掉加密。 |
| **`consume_scan` 的 SQLite 原子計數**   | 這是全專案跨進程狀態的**正確示範**，是遷移的範本，不是要清理的目標。                                                                                                      |
| **`/api/drive/sync-status` 輪詢端點**   | 跨進程天然正確的進度來源，SocketIO 砍掉後它就是唯一且足夠的方案。                                                                                                         |
| **Drive 同步的 `threading.Thread`**     | 不要改成同步 HTTP（會超時）。**補三件事**：`processing` 列加 stale 逾時（>30 分鐘自動放行）、同步做成冪等（改名前查 Notion 是否已有）、心跳更新 `updated_at`。            |
| **Gemini 主/備 API key fallback**       | quota 超限自動切換的設計合理。只修：讓 `timeout_seconds=30` 真正生效（建 client 時傳 `http_options={'timeout': 30_000}`）、旗標存設立日期跨日自動清除。                   |

---

## 8. 分階段行動計畫（每階段可獨立上線、可回退）

### Phase 0：止血（純 bug，不改架構，先上）

- [ ] `event_handler.py:174` `get_tenant` → `get_tenant_by_id`，補配額拒絕測試（§2.1）
- [ ] 刪除硬編碼 `/Users/user/...` 與 `/tmp/*.log` 檔案側寫，`DEBUG_*` 降 debug 級（§2.4）
- [ ] `tenant_db` 的 `get_connection()` 加 `PRAGMA journal_mode=WAL` + `timeout=15`（三行）
- [ ] Gemini 建 client 傳 `http_options={'timeout': 30_000}`；ImgBB timeout 降 15-20s、重試降 1 次（§5 #6#7）
- [ ] `SECRET_KEY` fail-fast、Fernet 解密失敗拋例外（§7）

### Phase 1：對齊部署宣告與程式假設（一行槓桿）

- [ ] `zeabur.json` scaling → `min:1 max:1`
- [ ] gunicorn → `--workers 1 --threads 4`，拿掉 `--preload`
- [ ] 驗證：所有 module-level 單例、in-memory 狀態即刻變正確

### Phase 2：狀態遷 SQLite，拔掉 Redis 的狀態用途

- [ ] 新增 `user_status` 表，`user_service` / `security_service` backend 從 Redis 換 SQLite（介面不變）
- [ ] 每日限額統一：租戶讀 plan `daily_card_limit`、非租戶讀 `settings.rate_limit_per_user`；統一 Asia/Taipei 定義「一天」
- [ ] 刪死碼：`check_rate_limit`、`block_user`/`is_user_blocked`、`SecurityService` 的 Fernet 四件套

### Phase 3：拔掉 RQ / honcho / SocketIO

- [ ] 圖片上傳改 `_sync_upload_image` + `threading.Thread`；失敗記 SQLite `failed_uploads` 表
- [ ] 刪 `rq_worker.py`、Procfile worker 行、honcho；`/admin/worker/*` 端點收斂並移進 admin 認證
- [ ] 砍 SocketIO，前端改輪詢 `/api/drive/sync-status`
- [ ] 排程改 croniter 背景 thread

### Phase 4：收尾

- [ ] `requirements` 刪 `redis`/`rq`/`honcho`/`flask-socketio`；所有版本約束補上限（Hard Rule #1）
- [ ] `CLAUDE.md` 同步更新為實際架構（刪內嵌 worker / 分散式鎖章節）
- [ ] 訂閱系統：若無商業化計畫，砍到剩 `monthly_scan_quota` 欄位 + `consume_scan`；若保留，先修 fail-open 並補強制執行測試

---

## 附錄：重複機制速查（7 組）

同一個問題被多套機制解，收斂方向：

1. **上傳失敗重試** — 4 層（客戶端 + RQ Retry + Redis 失敗記錄 + 手動端點）→ 收斂單層 SQLite
2. **非同步上傳** — 4 套實作只走 1 套 → 保留同步函式 + Thread
3. **用量限額** — 4 套平行系統（連「一天」定義都不同：04:00 vs naive UTC）→ 單一檢查點
4. **跨進程共享狀態** — Redis（錯，lost update）+ SQLite（對，CAS）並存 → 統一 SQLite
5. **加密** — 2 套 Fernet，一套死碼卻每次啟動付 100k 次 PBKDF2 → 收斂 tenant_service
6. **互斥/鎖** — 4 種鎖無一在宣告部署下正確 → 單 replica 後大部分消失，Drive 同步改 DB 列 + 逾時
7. **診斷/觀測** — 3 條 debug 通道 2 條生產無效 → 統一 structlog
