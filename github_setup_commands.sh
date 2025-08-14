#!/bin/bash

# GitHub Repository 設置指令
# 請將 YOUR_USERNAME 替換為您的 GitHub 用戶名

echo "🐙 GitHub Repository 設置指令"
echo "================================="
echo ""
echo "1. 在 GitHub 上創建好 repository 後，執行以下指令："
echo ""
echo "# 添加 GitHub remote origin"
echo "git remote add origin https://github.com/chengzehsu/Ecofirst_namecard.git"
echo ""
echo "# 推送代碼到 GitHub"
echo "git branch -M main"
echo "git push -u origin main"
echo ""
echo "3. 推送完成後，設置 GitHub Actions Secrets："
echo "   Repository → Settings → Secrets and variables → Actions"
echo "   添加以下 Secrets:"
echo "   - ZEABUR_SERVICE_ID"
echo "   - ZEABUR_API_TOKEN"
echo ""
echo "4. 推送到 main 分支會自動觸發 GitHub Actions 部署到 Zeabur"