#!/bin/bash
# 檢查 spec-kit 的所有前置條件是否已安裝

source "$(dirname "$0")/common.sh"

echo "檢查 spec-kit 前置條件..."
echo ""

# 檢查 Python
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "已安裝 Python 3：$PYTHON_VERSION"
else
    print_error "未安裝 Python 3"
    exit 1
fi

# 檢查 Git
if command_exists git; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    print_success "已安裝 Git：$GIT_VERSION"
else
    print_error "未安裝 Git"
    exit 1
fi

# 檢查是否在 git 版本庫中
if is_git_repo; then
    print_success "當前目錄是 Git 版本庫"
else
    print_warning "當前目錄不是 Git 版本庫"
fi

# 檢查 Claude Code
if command_exists claude; then
    print_success "Claude Code 可用"
else
    print_warning "未找到 Claude Code CLI（在 IDE 中仍可能可用）"
fi

# 檢查 .specify 目錄是否存在
if check_specify_dir; then
    print_success "Spec-kit 已初始化（找到 .specify 目錄）"
else
    print_warning "此目錄尚未初始化 Spec-kit"
fi

echo ""
echo "前置條件檢查完成！"
