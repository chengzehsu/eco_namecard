#!/bin/bash

# 一鍵部署到 GitHub 腳本
# 用戶: chengzehsu
# Repository: Ecofirst_namecard

set -e

echo "🚀 LINE Bot 名片管理系統 - GitHub 部署腳本"
echo "================================================"
echo ""
echo "👤 用戶: chengzehsu"
echo "📁 Repository: eco_namecard"
echo "🌐 URL: https://github.com/chengzehsu/eco_namecard"
echo ""

# 檢查是否已經設置 remote
if git remote get-url origin > /dev/null 2>&1; then
    echo "⚠️  Remote origin 已存在，正在檢查..."
    current_remote=$(git remote get-url origin)
    expected_remote="https://github.com/chengzehsu/eco_namecard.git"
    
    if [ "$current_remote" = "$expected_remote" ]; then
        echo "✅ Remote origin 正確"
    else
        echo "🔧 更新 remote origin..."
        git remote set-url origin $expected_remote
    fi
else
    echo "🔗 添加 GitHub remote origin..."
    git remote add origin https://github.com/chengzehsu/eco_namecard.git
fi

echo ""
echo "📋 檢查 Git 狀態..."
git status --short

if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  有未提交的變更，正在提交..."
    git add .
    git commit -m "chore: 自動提交部署前的變更"
fi

echo ""
echo "🚀 推送到 GitHub..."
echo "分支: main"
echo "目標: https://github.com/chengzehsu/eco_namecard.git"
echo ""

read -p "確認推送到 GitHub? (y/N): " confirm
if [[ $confirm =~ ^[Yy]$ ]]; then
    git branch -M main
    git push -u origin main
    
    echo ""
    echo "🎉 成功推送到 GitHub!"
    echo ""
    echo "📋 下一步:"
    echo "1. 前往設置 GitHub Actions Secrets:"
    echo "   https://github.com/chengzehsu/eco_namecard/settings/secrets/actions"
    echo ""
    echo "2. 添加以下 Secrets:"
    echo "   - ZEABUR_SERVICE_ID (從 Zeabur Dashboard 獲取)"
    echo "   - ZEABUR_API_TOKEN (從 Zeabur Account Settings 獲取)"
    echo ""
    echo "3. 查看 GitHub Actions 執行狀態:"
    echo "   https://github.com/chengzehsu/eco_namecard/actions"
    echo ""
    echo "4. 部署完成後檢查:"
    echo "   https://eco-namecard.zeabur.app/health"
    echo ""
    echo "📚 詳細說明請查看:"
    echo "   - QUICK_SETUP.md (5分鐘快速指南)"
    echo "   - GITHUB_SETUP.md (詳細設置說明)" 
    echo "   - DEPLOYMENT.md (完整部署指南)"
    
else
    echo "❌ 取消推送"
    echo ""
    echo "💡 當您準備好時，可以手動執行:"
    echo "git push -u origin main"
fi

echo ""
echo "🔗 有用的連結:"
echo "- GitHub Repository: https://github.com/chengzehsu/eco_namecard"
echo "- Zeabur Dashboard: https://zeabur.com/dashboard"
echo "- 應用 URL: https://eco-namecard.zeabur.app"