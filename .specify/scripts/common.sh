#!/bin/bash
# spec-kit 腳本的通用工具

# 輸出顏色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 無顏色

# 印出彩色訊息
print_error() {
    echo -e "${RED}❌ 錯誤：$1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  警告：$1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# 檢查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 檢查是否在 git 版本庫中
is_git_repo() {
    git rev-parse --git-dir > /dev/null 2>&1
}

# 取得專案根目錄
get_project_root() {
    if is_git_repo; then
        git rev-parse --show-toplevel
    else
        pwd
    fi
}

# 檢查 .specify 目錄是否存在
check_specify_dir() {
    local project_root=$(get_project_root)
    if [ ! -d "$project_root/.specify" ]; then
        print_error "不是 spec-kit 專案。請先執行 'specify init'。"
        return 1
    fi
    return 0
}

# 驗證功能名稱
validate_feature_name() {
    local name="$1"
    if [[ ! "$name" =~ ^[a-z0-9-]+$ ]]; then
        print_error "功能名稱只能包含小寫字母、數字和連字號"
        return 1
    fi
    return 0
}
