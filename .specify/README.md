# Spec-Kit 規格驅動開發

本專案已配置 Spec-Kit（規格驅動開發工具），用於系統化管理功能規格、技術計畫和實作任務。

## 目錄結構

```
.specify/
├── memory/
│   └── constitution.md          # 專案憲章（核心原則和開發標準）
├── scripts/
│   ├── check-prerequisites.sh   # 檢查前置條件
│   ├── common.sh                # 通用工具函式
│   └── create-new-feature.sh    # 建立新功能規格
├── specs/
│   └── current-system/          # 當前系統完整規格
│       ├── spec.md              # 功能規格說明
│       └── plan.md              # 技術實作計畫
└── templates/
    ├── spec-template.md         # 規格範本
    ├── plan-template.md         # 計畫範本
    └── tasks-template.md        # 任務範本
```

## 快速開始

### 1. 檢查前置條件

```bash
./.specify/scripts/check-prerequisites.sh
```

### 2. 查看專案憲章

專案憲章定義了開發的核心原則和標準：

```bash
cat .specify/memory/constitution.md
```

### 3. 查看當前系統規格

```bash
# 功能規格
cat .specify/specs/current-system/spec.md

# 技術計畫
cat .specify/specs/current-system/plan.md
```

## 建立新功能

### 使用腳本建立

```bash
# 語法：./.specify/scripts/create-new-feature.sh <功能名稱>
./.specify/scripts/create-new-feature.sh export-to-excel
```

這會建立以下結構：
```
.specify/specs/export-to-excel/
├── spec.md           # 從範本建立
├── research.md       # 研究筆記
├── data-model.md     # 資料模型
├── quickstart.md     # 快速入門
└── contracts/        # API 規格
```

### 手動建立

1. 在 `.specify/specs/` 下建立功能目錄
2. 複製範本檔案並填寫內容
3. 遵循 SDD 流程

## Spec-Driven Development 流程

### 階段 1：規格說明 (Specify)
定義「要什麼」和「為什麼」，不涉及技術實作細節。

**編輯檔案**：`.specify/specs/<功能名稱>/spec.md`

**包含內容**：
- 使用者故事
- 功能需求
- 驗收標準
- 成功指標
- 不在範圍內的項目

### 階段 2：技術計畫 (Plan)
決定「如何做」，制定技術實作策略。

**建立檔案**：`.specify/specs/<功能名稱>/plan.md`

**包含內容**：
- 架構設計
- 元件設計
- 資料模型
- API 設計
- 測試策略
- 部署計畫
- 風險評估

### 階段 3：任務清單 (Tasks)
將計畫分解為可執行的任務。

**建立檔案**：`.specify/specs/<功能名稱>/tasks.md`

**包含內容**：
- 分階段任務清單
- 依賴關係
- 驗收標準
- 測試要求

### 階段 4：實作 (Implement)
按照任務清單執行實作。

**最佳實踐**：
- 一次只執行一個任務
- 每個任務完成後執行測試
- 定期提交程式碼
- 更新任務狀態

## 使用範例

### 範例 1：新增匯出功能

```bash
# 1. 建立功能規格
./.specify/scripts/create-new-feature.sh export-to-excel

# 2. 編輯規格說明
vim .specify/specs/export-to-excel/spec.md
# 填寫：使用者故事、功能需求、驗收標準

# 3. 建立技術計畫
vim .specify/specs/export-to-excel/plan.md
# 填寫：架構設計、元件設計、API 設計

# 4. 建立任務清單
cp .specify/templates/tasks-template.md .specify/specs/export-to-excel/tasks.md
# 填寫：分階段任務清單

# 5. 開始實作
# 按照 tasks.md 逐項完成
```

### 範例 2：查看現有規格

```bash
# 列出所有功能規格
ls -la .specify/specs/

# 查看特定功能規格
cat .specify/specs/current-system/spec.md

# 搜尋特定關鍵字
grep -r "批次處理" .specify/specs/
```

## 最佳實踐

### 撰寫規格
1. **專注於「什麼」和「為什麼」**，不要過早討論「如何」
2. **使用使用者故事**：「身為 [角色]，我想要 [功能]，以便 [好處]」
3. **明確的驗收標準**：可測試、可量化
4. **考慮邊界情況**：錯誤處理、極端情況

### 制定計畫
1. **架構先行**：先設計整體架構，再深入細節
2. **模組化設計**：每個元件職責單一且明確
3. **考慮可測試性**：設計時就考慮如何測試
4. **評估風險**：識別潛在問題並制定應對策略

### 執行任務
1. **小步快跑**：將大任務分解為小任務
2. **測試先行**：先寫測試，再寫實作
3. **持續整合**：頻繁提交和整合程式碼
4. **文件同步**：實作時更新相關文件

## 工具整合

### 與 Claude Code 整合

在 Claude Code 中，可以參考這些規格文件：

```
# 查看專案原則
請參考 .specify/memory/constitution.md 中的專案原則

# 查看功能規格
請根據 .specify/specs/current-system/spec.md 進行開發

# 查看技術計畫
請依照 .specify/specs/current-system/plan.md 的架構設計
```

### 與 Git 整合

```bash
# 提交規格變更
git add .specify/
git commit -m "docs: update feature specification for export functionality"

# 建立功能分支
git checkout -b feature/export-to-excel

# 提交時引用規格
git commit -m "feat: implement export to excel

Ref: .specify/specs/export-to-excel/spec.md
Closes: Task 2.1 in tasks.md"
```

## 維護

### 定期檢查
- 每個 Sprint 開始前檢查規格是否符合當前需求
- 功能完成後更新規格文件
- 定期審查憲章是否需要更新

### 更新規格
當需求變更時：
1. 更新對應的 spec.md
2. 評估是否需要更新 plan.md
3. 調整 tasks.md 中的待辦任務
4. 提交變更並記錄原因

## 常見問題

### Q: 規格太詳細會不會失去敏捷性？
A: 規格驅動開發不是瀑布式開發。規格可以迭代更新，重點是先思考「要什麼」再實作。

### Q: 每個小功能都需要完整規格嗎？
A: 不一定。簡單的 bug 修復或小調整可以跳過。但對於新功能、架構變更、API 設計等，建議撰寫規格。

### Q: 規格和程式碼不一致怎麼辦？
A: 程式碼是真相來源。發現不一致時，應該更新規格文件以反映實際狀況。

### Q: 如何確保團隊遵循規格？
A: 在 PR review 時檢查是否符合規格，將規格審查納入 DoD (Definition of Done)。

## 參考資源

- [GitHub Spec-Kit](https://github.com/github/spec-kit)
- [專案憲章](./.specify/memory/constitution.md)
- [當前系統規格](./.specify/specs/current-system/spec.md)
- [CLAUDE.md](../../CLAUDE.md) - Claude Code 專案說明
