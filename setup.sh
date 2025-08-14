#!/bin/bash

# LINE Bot 名片管理系統 - 快速設置腳本

set -e

echo "🚀 LINE Bot 名片管理系統 - 快速設置"
echo "======================================"

# 檢查 Python 版本
echo "📋 檢查 Python 版本..."
python3 --version

# 檢查是否有 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件，正在從範例創建..."
    cp .env.example .env
    echo "✅ 已創建 .env 文件，請編輯並填入你的 API Keys"
    echo ""
    echo "必要的環境變數："
    echo "- LINE_CHANNEL_ACCESS_TOKEN"
    echo "- LINE_CHANNEL_SECRET" 
    echo "- GOOGLE_API_KEY"
    echo "- NOTION_API_KEY"
    echo "- NOTION_DATABASE_ID"
    echo "- SECRET_KEY"
    echo ""
    read -p "按 Enter 繼續設置，或 Ctrl+C 退出編輯 .env 文件..."
fi

# 檢查虛擬環境
if [ ! -d "venv" ]; then
    echo "🐍 創建 Python 虛擬環境..."
    python3 -m venv venv
fi

echo "🔧 啟用虛擬環境..."
source venv/bin/activate

echo "📦 安裝依賴包..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🧪 運行測試..."
pytest --tb=short || echo "⚠️ 測試有些問題，但可以繼續"

echo "🔍 運行代碼品質檢查..."
black --check src/ || echo "建議運行: black src/"
flake8 src/ || echo "建議檢查代碼品質"

echo ""
echo "🎉 設置完成！"
echo ""
echo "📚 下一步："
echo "1. 編輯 .env 文件並填入你的 API Keys"
echo "2. 在 LINE Developer Console 設置 Webhook URL"
echo "3. 在 Notion 中創建資料庫並設置權限"
echo "4. 運行: python app.py"
echo ""
echo "🔗 有用的指令："
echo "- 啟動應用: python app.py"
echo "- 運行測試: pytest"
echo "- 檢查健康: curl http://localhost:5002/health"
echo "- 代碼格式: black src/"
echo ""
echo "📖 詳細說明請查看 README.md"
echo "🤖 Claude Code 協作記錄請查看 CLAUDE.md"