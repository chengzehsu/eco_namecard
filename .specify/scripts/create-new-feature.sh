#!/bin/bash
# 建立新功能規格結構

set -e

# 取得此腳本所在的目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SPECIFY_DIR="$PROJECT_ROOT/.specify"

# 檢查是否提供功能名稱
if [ -z "$1" ]; then
    echo "使用方式: $0 <功能名稱>"
    echo "範例: $0 export-to-excel"
    exit 1
fi

FEATURE_NAME="$1"
FEATURE_DIR="$SPECIFY_DIR/specs/$FEATURE_NAME"

# 檢查功能是否已存在
if [ -d "$FEATURE_DIR" ]; then
    echo "錯誤：功能 '$FEATURE_NAME' 已存在於 $FEATURE_DIR"
    exit 1
fi

# 建立功能目錄結構
echo "為功能建立目錄結構：$FEATURE_NAME"
mkdir -p "$FEATURE_DIR/contracts"

# 複製範本
echo "從範本建立 spec.md..."
cp "$SPECIFY_DIR/templates/spec-template.md" "$FEATURE_DIR/spec.md"
sed -i.bak "s/\[功能名稱\]/$FEATURE_NAME/g" "$FEATURE_DIR/spec.md"
rm "$FEATURE_DIR/spec.md.bak"

# 建立佔位檔案
echo "建立佔位檔案..."
cat > "$FEATURE_DIR/research.md" << 'EOF'
# 研究筆記

## 背景研究
- 在此記錄研究發現
- 相關文件連結
- 競品分析

## 技術調查
- 概念驗證
- 函式庫/框架評估
- 效能考量

## 決策日誌
| 決策 | 理由 | 日期 |
|------|------|------|
|      |      |      |
EOF

cat > "$FEATURE_DIR/data-model.md" << 'EOF'
# 資料模型

## 實體

### 實體名稱
```python
class EntityName(BaseModel):
    field1: str
    field2: int
```

## 關係
- 描述實體之間的關係

## 驗證規則
- 列出驗證規則和限制
EOF

cat > "$FEATURE_DIR/quickstart.md" << 'EOF'
# 快速入門指南

## 前置條件
- 列出任何前置條件

## 設定
1. 步驟 1
2. 步驟 2

## 使用範例
```python
# 範例程式碼
```
EOF

echo ""
echo "✅ 功能結構建立成功！"
echo ""
echo "📁 功能目錄：$FEATURE_DIR"
echo ""
echo "下一步："
echo "1. 編輯 spec.md 定義需求"
echo "2. 執行：claude /speckit.specify（精煉規格）"
echo "3. 執行：claude /speckit.plan（建立技術計畫）"
echo "4. 執行：claude /speckit.tasks（產生實作任務）"
echo ""
echo "已建立檔案："
echo "  - spec.md（從範本）"
echo "  - research.md（佔位）"
echo "  - data-model.md（佔位）"
echo "  - quickstart.md（佔位）"
echo "  - contracts/（目錄）"
