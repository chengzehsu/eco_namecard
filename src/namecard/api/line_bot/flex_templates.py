"""
Flex Message Templates for LINE Bot Namecard System (SDK v3)

設計原則 (based on UI/UX Pro Max):
- Minimal & Direct: 簡潔直接，留白適當
- High Contrast: 文字對比度 4.5:1 以上
- LINE Green #06C755 為主色
- 中文介面
- 視覺層次分明：姓名為焦點
"""

from linebot.v3.messaging import (
    FlexMessage,
    FlexBubble,
    FlexBox,
    FlexText,
    FlexSeparator,
    FlexButton,
    FlexFiller,
    URIAction,
    MessageAction,
)
from typing import Optional, List
from src.namecard.core.models.card import BusinessCard, BatchProcessResult


class FlexColors:
    """Flex Message 顏色常數"""
    # 主色 - LINE Green
    PRIMARY = "#06C755"

    # 文字色 - 高對比度
    TEXT_PRIMARY = "#1D1D1F"      # 主要文字 (Apple style)
    TEXT_SECONDARY = "#48484A"    # 次要文字
    TEXT_MUTED = "#8E8E93"        # 輔助文字

    # 背景色
    WHITE = "#FFFFFF"
    BACKGROUND = "#F5F5F7"        # 淺灰背景

    # 狀態色
    SUCCESS = "#06C755"           # 成功 (同 LINE Green)
    WARNING = "#FF9500"           # 警告/錯誤 (橘色)
    ERROR = "#FF3B30"             # 嚴重錯誤 (紅色)

    # 進度條
    PROGRESS_BG = "#E5E5EA"       # 進度條背景


def _create_info_row_with_icon(icon: str, value: str) -> FlexBox:
    """建立資訊列（emoji icon + 值）"""
    return FlexBox(
        layout="horizontal",
        margin="md",
        spacing="md",
        contents=[
            FlexText(
                text=icon,
                size="sm",
                flex=0
            ),
            FlexText(
                text=value or "-",
                size="sm",
                color=FlexColors.TEXT_PRIMARY,
                flex=1,
                wrap=True
            )
        ]
    )


def build_card_result_bubble(
    card: BusinessCard,
    notion_url: Optional[str] = None
) -> FlexBubble:
    """
    建立單張名片識別結果卡片

    設計：
    - 姓名置中放大，成為視覺焦點
    - 職稱和公司分行顯示
    - 使用 emoji icon 標記聯絡資訊
    - 底部添加按鈕
    """
    # Header - LINE Green 背景
    header = FlexBox(
        layout="vertical",
        background_color=FlexColors.PRIMARY,
        padding_all="16px",
        contents=[
            FlexText(
                text="✓ 識別成功",
                color=FlexColors.WHITE,
                size="md",
                weight="bold"
            )
        ]
    )

    # Body - 名片資訊
    body_contents = []

    # 姓名（大字體置中突出）
    body_contents.append(
        FlexText(
            text=card.name or "未識別",
            size="xxl",
            weight="bold",
            color=FlexColors.TEXT_PRIMARY,
            align="center"
        )
    )

    # 職稱（獨立一行）
    if card.title:
        body_contents.append(
            FlexText(
                text=card.title,
                size="md",
                color=FlexColors.TEXT_SECONDARY,
                align="center",
                margin="sm"
            )
        )

    # 公司（獨立一行，較小字體）
    if card.company:
        body_contents.append(
            FlexText(
                text=card.company,
                size="sm",
                color=FlexColors.TEXT_MUTED,
                align="center",
                margin="xs",
                wrap=True
            )
        )

    # 分隔線
    body_contents.append(FlexSeparator(margin="lg"))

    # 聯絡資訊區塊（使用 emoji icon）
    info_box_contents = []

    if card.phone:
        info_box_contents.append(_create_info_row_with_icon("📞", card.phone))

    if card.email:
        info_box_contents.append(_create_info_row_with_icon("✉️", card.email))

    if card.address:
        info_box_contents.append(_create_info_row_with_icon("📍", card.address))

    if card.website:
        info_box_contents.append(_create_info_row_with_icon("🌐", card.website))

    if info_box_contents:
        body_contents.append(
            FlexBox(
                layout="vertical",
                margin="lg",
                spacing="none",
                contents=info_box_contents
            )
        )

    body = FlexBox(
        layout="vertical",
        padding_all="20px",
        contents=body_contents
    )

    # Footer - 按鈕區
    footer_contents = []

    # 如果有 Notion URL，添加「查看詳情」按鈕
    if notion_url:
        footer_contents.append(
            FlexButton(
                action=URIAction(label="查看 Notion", uri=notion_url),
                style="primary",
                color=FlexColors.PRIMARY,
                height="sm"
            )
        )

    # 添加「開始批次」按鈕
    footer_contents.append(
        FlexButton(
            action=MessageAction(label="開始批次", text="批次"),
            style="secondary",
            height="sm"
        )
    )

    footer = FlexBox(
        layout="horizontal",
        padding_all="12px",
        spacing="md",
        contents=footer_contents
    )

    return FlexBubble(
        size="mega",
        header=header,
        body=body,
        footer=footer
    )


def build_multi_card_summary_bubble(
    total: int,
    success_count: int = 0,
    failed_count: int = 0
) -> FlexBubble:
    """
    建立多張名片處理摘要卡片

    設計：簡潔統計，顯示成功/失敗數量
    """
    header = FlexBox(
        layout="vertical",
        background_color=FlexColors.PRIMARY,
        padding_all="16px",
        contents=[
            FlexText(
                text="✓ 識別完成",
                color=FlexColors.WHITE,
                size="md",
                weight="bold",
                align="center"
            )
        ]
    )

    body_contents = [
        FlexText(
            text=str(total),
            size="4xl",
            weight="bold",
            align="center",
            color=FlexColors.TEXT_PRIMARY
        ),
        FlexText(
            text="張名片已處理",
            size="sm",
            align="center",
            color=FlexColors.TEXT_SECONDARY,
            margin="sm"
        )
    ]

    # 如果有失敗的，顯示成功/失敗統計
    if failed_count > 0:
        body_contents.append(FlexSeparator(margin="lg"))
        body_contents.append(
            FlexBox(
                layout="horizontal",
                margin="md",
                contents=[
                    FlexText(
                        text=f"✓ 成功 {success_count} 張",
                        size="sm",
                        color=FlexColors.SUCCESS,
                        flex=1,
                        align="center"
                    ),
                    FlexText(
                        text=f"✗ 失敗 {failed_count} 張",
                        size="sm",
                        color=FlexColors.ERROR,
                        flex=1,
                        align="center"
                    )
                ]
            )
        )

    body = FlexBox(
        layout="vertical",
        padding_all="24px",
        contents=body_contents
    )

    # Footer - 按鈕
    footer = FlexBox(
        layout="horizontal",
        padding_all="12px",
        spacing="md",
        contents=[
            FlexButton(
                action=MessageAction(label="開始批次", text="批次"),
                style="secondary",
                height="sm"
            )
        ]
    )

    return FlexBubble(
        size="kilo",
        header=header,
        body=body,
        footer=footer
    )


def build_progress_bubble(
    current: int,
    total: int,
    success_count: int,
    failed_count: int
) -> FlexBubble:
    """
    建立批次進度卡片（含視覺化進度條）

    設計：
    - 視覺化進度條
    - 成功/失敗計數
    - 快捷操作按鈕
    """
    # 計算進度百分比
    progress_percent = (current / total * 100) if total > 0 else 0
    # 進度條寬度（使用 flex 值，最大 10）
    filled_flex = max(1, int(progress_percent / 10))
    empty_flex = 10 - filled_flex

    header = FlexBox(
        layout="vertical",
        background_color=FlexColors.PRIMARY,
        padding_all="16px",
        contents=[
            FlexText(
                text="📦 批次處理中",
                color=FlexColors.WHITE,
                size="md",
                weight="bold"
            )
        ]
    )

    # 進度條
    progress_bar_contents = [
        FlexBox(
            layout="vertical",
            background_color=FlexColors.PRIMARY,
            height="8px",
            corner_radius="4px",
            flex=filled_flex,
            contents=[]
        )
    ]
    if empty_flex > 0:
        progress_bar_contents.append(
            FlexBox(
                layout="vertical",
                background_color=FlexColors.PROGRESS_BG,
                height="8px",
                corner_radius="4px",
                flex=empty_flex,
                contents=[]
            )
        )

    progress_bar = FlexBox(
        layout="horizontal",
        spacing="none",
        contents=progress_bar_contents
    )

    body = FlexBox(
        layout="vertical",
        padding_all="20px",
        spacing="lg",
        contents=[
            # 進度條區
            FlexBox(
                layout="vertical",
                spacing="sm",
                contents=[
                    progress_bar,
                    FlexText(
                        text=f"{current}/{total}",
                        size="sm",
                        color=FlexColors.TEXT_SECONDARY,
                        align="end"
                    )
                ]
            ),
            # 統計區
            FlexBox(
                layout="vertical",
                spacing="sm",
                contents=[
                    FlexBox(
                        layout="horizontal",
                        contents=[
                            FlexText(
                                text="✓ 成功",
                                size="sm",
                                color=FlexColors.TEXT_SECONDARY,
                                flex=1
                            ),
                            FlexText(
                                text=f"{success_count} 張",
                                size="sm",
                                weight="bold",
                                color=FlexColors.SUCCESS,
                                flex=0,
                                align="end"
                            )
                        ]
                    ),
                    FlexBox(
                        layout="horizontal",
                        contents=[
                            FlexText(
                                text="✗ 失敗",
                                size="sm",
                                color=FlexColors.TEXT_SECONDARY,
                                flex=1
                            ),
                            FlexText(
                                text=f"{failed_count} 張",
                                size="sm",
                                weight="bold",
                                color=FlexColors.ERROR if failed_count > 0 else FlexColors.TEXT_MUTED,
                                flex=0,
                                align="end"
                            )
                        ]
                    )
                ]
            )
        ]
    )

    # Footer - 按鈕
    footer = FlexBox(
        layout="horizontal",
        padding_all="12px",
        spacing="md",
        contents=[
            FlexButton(
                action=MessageAction(label="結束批次", text="結束批次"),
                style="primary",
                color=FlexColors.PRIMARY,
                height="sm"
            ),
            FlexButton(
                action=MessageAction(label="查看狀態", text="狀態"),
                style="secondary",
                height="sm"
            )
        ]
    )

    return FlexBubble(
        size="kilo",
        header=header,
        body=body,
        footer=footer
    )


def build_batch_complete_bubble(batch_result: BatchProcessResult) -> FlexBubble:
    """
    建立批次完成統計卡片

    設計：
    - 大數字顯示總數
    - 成功/失敗統計和百分比
    - 處理時間
    """
    # 計算處理時間
    if batch_result.completed_at and batch_result.started_at:
        duration = batch_result.completed_at - batch_result.started_at
        minutes = duration.seconds // 60
        seconds = duration.seconds % 60
        duration_str = f"{minutes}:{seconds:02d}"
    else:
        duration_str = "-"

    # 計算成功率
    total = batch_result.total_cards
    success = batch_result.successful_cards
    failed = batch_result.failed_cards
    success_rate = (success / total * 100) if total > 0 else 0

    header = FlexBox(
        layout="vertical",
        background_color=FlexColors.PRIMARY,
        padding_all="20px",
        contents=[
            FlexText(
                text="🎉 批次完成！",
                color=FlexColors.WHITE,
                size="lg",
                weight="bold",
                align="center"
            )
        ]
    )

    body = FlexBox(
        layout="vertical",
        padding_all="24px",
        spacing="lg",
        contents=[
            # 總數統計
            FlexBox(
                layout="vertical",
                contents=[
                    FlexText(
                        text=str(total),
                        size="5xl",
                        weight="bold",
                        align="center",
                        color=FlexColors.TEXT_PRIMARY
                    ),
                    FlexText(
                        text="張名片已儲存",
                        size="md",
                        align="center",
                        color=FlexColors.TEXT_SECONDARY,
                        margin="sm"
                    )
                ]
            ),
            # 分隔線
            FlexSeparator(),
            # 詳細統計
            FlexBox(
                layout="vertical",
                spacing="sm",
                contents=[
                    FlexBox(
                        layout="horizontal",
                        contents=[
                            FlexText(
                                text="✓ 成功",
                                size="sm",
                                color=FlexColors.TEXT_SECONDARY,
                                flex=1
                            ),
                            FlexText(
                                text=f"{success} 張",
                                size="sm",
                                weight="bold",
                                color=FlexColors.SUCCESS,
                                flex=0
                            ),
                            FlexText(
                                text=f"({success_rate:.0f}%)",
                                size="xs",
                                color=FlexColors.TEXT_MUTED,
                                flex=0,
                                margin="sm"
                            )
                        ]
                    ),
                    FlexBox(
                        layout="horizontal",
                        contents=[
                            FlexText(
                                text="✗ 失敗",
                                size="sm",
                                color=FlexColors.TEXT_SECONDARY,
                                flex=1
                            ),
                            FlexText(
                                text=f"{failed} 張",
                                size="sm",
                                weight="bold",
                                color=FlexColors.ERROR if failed > 0 else FlexColors.TEXT_MUTED,
                                flex=0
                            ),
                            FlexText(
                                text=f"({100-success_rate:.0f}%)",
                                size="xs",
                                color=FlexColors.TEXT_MUTED,
                                flex=0,
                                margin="sm"
                            )
                        ]
                    ),
                    FlexBox(
                        layout="horizontal",
                        contents=[
                            FlexText(
                                text="⏱ 耗時",
                                size="sm",
                                color=FlexColors.TEXT_SECONDARY,
                                flex=1
                            ),
                            FlexText(
                                text=duration_str,
                                size="sm",
                                weight="bold",
                                color=FlexColors.TEXT_PRIMARY,
                                flex=0,
                                align="end"
                            )
                        ]
                    )
                ]
            )
        ]
    )

    return FlexBubble(
        size="kilo",
        header=header,
        body=body
    )


def build_error_bubble(
    error_type: str,
    reasons: List[str],
    suggestions: List[str]
) -> FlexBubble:
    """
    建立結構化錯誤訊息卡片

    Args:
        error_type: 錯誤類型（如「識別失敗」「配額用盡」）
        reasons: 可能原因列表
        suggestions: 建議操作列表
    """
    header = FlexBox(
        layout="vertical",
        background_color=FlexColors.WARNING,
        padding_all="16px",
        contents=[
            FlexText(
                text=f"⚠️ {error_type}",
                color=FlexColors.WHITE,
                size="md",
                weight="bold"
            )
        ]
    )

    body_contents = []

    # 可能原因
    if reasons:
        body_contents.append(
            FlexText(
                text="可能原因：",
                size="sm",
                weight="bold",
                color=FlexColors.TEXT_PRIMARY
            )
        )
        for reason in reasons:
            body_contents.append(
                FlexText(
                    text=f"• {reason}",
                    size="sm",
                    color=FlexColors.TEXT_SECONDARY,
                    margin="sm",
                    wrap=True
                )
            )

    # 分隔線
    if reasons and suggestions:
        body_contents.append(FlexSeparator(margin="lg"))

    # 建議操作
    if suggestions:
        body_contents.append(
            FlexText(
                text="建議操作：",
                size="sm",
                weight="bold",
                color=FlexColors.TEXT_PRIMARY,
                margin="lg" if not reasons else "none"
            )
        )
        for i, suggestion in enumerate(suggestions, 1):
            body_contents.append(
                FlexText(
                    text=f"{i}. {suggestion}",
                    size="sm",
                    color=FlexColors.TEXT_SECONDARY,
                    margin="sm",
                    wrap=True
                )
            )

    body = FlexBox(
        layout="vertical",
        padding_all="20px",
        contents=body_contents
    )

    # Footer - 按鈕
    footer = FlexBox(
        layout="horizontal",
        padding_all="12px",
        spacing="md",
        contents=[
            FlexButton(
                action=MessageAction(label="使用說明", text="幫助"),
                style="secondary",
                height="sm"
            )
        ]
    )

    return FlexBubble(
        size="kilo",
        header=header,
        body=body,
        footer=footer
    )


# ============================================
# 錯誤類型預設配置
# ============================================

ERROR_CONFIGS = {
    "low_quality": {
        "type": "圖片品質不足",
        "reasons": ["圖片模糊或解析度過低", "光線不足導致細節不清"],
        "suggestions": ["確保光線充足", "保持手機穩定", "使用更高解析度拍攝"]
    },
    "not_business_card": {
        "type": "無法識別名片",
        "reasons": ["圖片可能不是名片", "名片內容不完整或遮擋"],
        "suggestions": ["確認上傳的是名片照片", "確保名片完整入鏡", "避免手指遮擋"]
    },
    "quota_exceeded": {
        "type": "配額已用盡",
        "reasons": ["今日掃描額度已達上限"],
        "suggestions": ["明天再試", "聯絡管理員提升額度"]
    },
    "system_error": {
        "type": "系統錯誤",
        "reasons": ["伺服器暫時無法處理請求"],
        "suggestions": ["稍後重試", "如持續發生請聯絡客服"]
    },
    "storage_error": {
        "type": "儲存失敗",
        "reasons": ["無法連接 Notion 資料庫", "資料庫權限問題"],
        "suggestions": ["稍後重試", "確認 Notion 整合設定"]
    }
}


# ============================================
# 高階訊息建立函數
# ============================================

def create_card_result_message(
    cards: List[BusinessCard],
    is_batch_mode: bool = False,
    batch_progress: Optional[int] = None,
    notion_url: Optional[str] = None,
    success_count: int = 0,
    failed_count: int = 0
) -> FlexMessage:
    """
    建立名片處理結果的 Flex Message

    Args:
        cards: 處理完成的名片列表
        is_batch_mode: 是否為批次模式
        batch_progress: 批次模式下的累計數量
        notion_url: Notion 頁面連結（單張名片時使用）
        success_count: 成功數量
        failed_count: 失敗數量

    Returns:
        FlexMessage 準備發送
    """
    total = len(cards)

    if total == 1:
        # 單張名片 - 顯示詳細卡片
        bubble = build_card_result_bubble(cards[0], notion_url)
        alt_text = f"名片識別成功：{cards[0].name or '未識別'}"
    else:
        # 多張名片 - 顯示摘要
        bubble = build_multi_card_summary_bubble(
            total,
            success_count=success_count or total,
            failed_count=failed_count
        )
        alt_text = f"已處理 {total} 張名片"

    return FlexMessage(
        alt_text=alt_text,
        contents=bubble
    )


def create_batch_complete_message(batch_result: BatchProcessResult) -> FlexMessage:
    """
    建立批次完成的 Flex Message

    Args:
        batch_result: 批次處理結果

    Returns:
        FlexMessage 準備發送
    """
    bubble = build_batch_complete_bubble(batch_result)

    return FlexMessage(
        alt_text=f"批次完成：共 {batch_result.total_cards} 張名片",
        contents=bubble
    )


def create_progress_message(
    current: int,
    total: int,
    success_count: int,
    failed_count: int
) -> FlexMessage:
    """
    建立批次進度的 Flex Message

    Args:
        current: 當前處理數量
        total: 預計總數（或當前批次限制）
        success_count: 成功數量
        failed_count: 失敗數量

    Returns:
        FlexMessage 準備發送
    """
    bubble = build_progress_bubble(current, total, success_count, failed_count)

    return FlexMessage(
        alt_text=f"批次進度：{current}/{total}",
        contents=bubble
    )


def create_error_message(
    error_key: str = "system_error",
    custom_type: Optional[str] = None,
    custom_reasons: Optional[List[str]] = None,
    custom_suggestions: Optional[List[str]] = None
) -> FlexMessage:
    """
    建立錯誤訊息的 Flex Message

    Args:
        error_key: 錯誤類型 key（使用預設配置）
        custom_type: 自定義錯誤類型標題
        custom_reasons: 自定義原因列表
        custom_suggestions: 自定義建議列表

    Returns:
        FlexMessage 準備發送
    """
    config = ERROR_CONFIGS.get(error_key, ERROR_CONFIGS["system_error"])

    bubble = build_error_bubble(
        error_type=custom_type or config["type"],
        reasons=custom_reasons or config["reasons"],
        suggestions=custom_suggestions or config["suggestions"]
    )

    return FlexMessage(
        alt_text=f"⚠️ {custom_type or config['type']}",
        contents=bubble
    )
