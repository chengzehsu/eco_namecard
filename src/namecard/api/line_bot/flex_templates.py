"""
Flex Message Templates for LINE Bot Namecard System

設計原則 (based on UI/UX Pro Max):
- Minimal & Direct: 簡潔直接，留白適當
- High Contrast: 文字對比度 4.5:1 以上
- LINE Green #06C755 為主色
- 中文介面
"""

from linebot.models import (
    FlexSendMessage,
    BubbleContainer,
    BoxComponent,
    TextComponent,
    SeparatorComponent,
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


def _create_info_row(label: str, value: str) -> BoxComponent:
    """建立資訊列（標籤 + 值）"""
    return BoxComponent(
        layout="horizontal",
        margin="sm",
        contents=[
            TextComponent(
                text=label,
                size="sm",
                color=FlexColors.TEXT_MUTED,
                flex=2
            ),
            TextComponent(
                text=value or "-",
                size="sm",
                color=FlexColors.TEXT_PRIMARY,
                flex=5,
                wrap=True
            )
        ]
    )


def build_card_result_bubble(card: BusinessCard) -> BubbleContainer:
    """
    建立單張名片識別結果卡片

    設計：簡潔現代風格，突出姓名和公司
    """
    # Header - LINE Green 背景
    header = BoxComponent(
        layout="vertical",
        backgroundColor=FlexColors.PRIMARY,
        paddingAll="16px",
        contents=[
            TextComponent(
                text="名片識別成功",
                color=FlexColors.WHITE,
                size="md",
                weight="bold"
            )
        ]
    )

    # Body - 名片資訊
    body_contents = []

    # 姓名（大字體突出）
    body_contents.append(
        TextComponent(
            text=card.name or "未識別",
            size="xl",
            weight="bold",
            color=FlexColors.TEXT_PRIMARY
        )
    )

    # 職稱 + 公司（次要資訊）
    subtitle_parts = []
    if card.title:
        subtitle_parts.append(card.title)
    if card.company:
        subtitle_parts.append(card.company)

    if subtitle_parts:
        body_contents.append(
            TextComponent(
                text=" · ".join(subtitle_parts),
                size="sm",
                color=FlexColors.TEXT_SECONDARY,
                wrap=True,
                margin="sm"
            )
        )

    # 分隔線
    body_contents.append(SeparatorComponent(margin="lg"))

    # 聯絡資訊區塊
    info_box_contents = []

    if card.phone:
        info_box_contents.append(_create_info_row("電話", card.phone))

    if card.email:
        info_box_contents.append(_create_info_row("Email", card.email))

    if card.address:
        info_box_contents.append(_create_info_row("地址", card.address))

    if card.website:
        info_box_contents.append(_create_info_row("網站", card.website))

    if info_box_contents:
        body_contents.append(
            BoxComponent(
                layout="vertical",
                margin="lg",
                spacing="sm",
                contents=info_box_contents
            )
        )

    body = BoxComponent(
        layout="vertical",
        paddingAll="16px",
        contents=body_contents
    )

    # Footer - 儲存狀態
    footer = BoxComponent(
        layout="vertical",
        paddingAll="12px",
        contents=[
            TextComponent(
                text="已儲存至 Notion",
                size="xs",
                color=FlexColors.SUCCESS,
                align="center",
                weight="bold"
            )
        ]
    )

    return BubbleContainer(
        size="mega",
        header=header,
        body=body,
        footer=footer
    )


def build_multi_card_summary_bubble(total: int) -> BubbleContainer:
    """
    建立多張名片處理摘要卡片

    設計：簡潔統計，只顯示總數
    """
    header = BoxComponent(
        layout="vertical",
        backgroundColor=FlexColors.PRIMARY,
        paddingAll="16px",
        contents=[
            TextComponent(
                text="名片識別完成",
                color=FlexColors.WHITE,
                size="md",
                weight="bold",
                align="center"
            )
        ]
    )

    body = BoxComponent(
        layout="vertical",
        paddingAll="20px",
        contents=[
            TextComponent(
                text=str(total),
                size="3xl",
                weight="bold",
                align="center",
                color=FlexColors.TEXT_PRIMARY
            ),
            TextComponent(
                text="張名片已處理",
                size="sm",
                align="center",
                color=FlexColors.TEXT_SECONDARY,
                margin="sm"
            )
        ]
    )

    return BubbleContainer(
        size="kilo",
        header=header,
        body=body
    )


def build_batch_complete_bubble(batch_result: BatchProcessResult) -> BubbleContainer:
    """
    建立批次完成統計卡片

    設計：簡潔，只顯示總數和處理時間
    """
    # 計算處理時間
    if batch_result.completed_at and batch_result.started_at:
        duration = batch_result.completed_at - batch_result.started_at
        minutes = duration.seconds // 60
        seconds = duration.seconds % 60
        duration_str = f"{minutes}:{seconds:02d}"
    else:
        duration_str = "-"

    header = BoxComponent(
        layout="vertical",
        backgroundColor=FlexColors.PRIMARY,
        paddingAll="16px",
        contents=[
            TextComponent(
                text="批次處理完成",
                color=FlexColors.WHITE,
                size="lg",
                weight="bold",
                align="center"
            )
        ]
    )

    body = BoxComponent(
        layout="vertical",
        paddingAll="24px",
        spacing="lg",
        contents=[
            # 總數統計
            BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text=str(batch_result.total_cards),
                        size="3xl",
                        weight="bold",
                        align="center",
                        color=FlexColors.TEXT_PRIMARY
                    ),
                    TextComponent(
                        text="張名片已處理",
                        size="sm",
                        align="center",
                        color=FlexColors.TEXT_SECONDARY,
                        margin="sm"
                    )
                ]
            ),
            # 分隔線
            SeparatorComponent(),
            # 處理時間
            BoxComponent(
                layout="horizontal",
                contents=[
                    TextComponent(
                        text="處理時間",
                        size="sm",
                        color=FlexColors.TEXT_SECONDARY,
                        flex=1
                    ),
                    TextComponent(
                        text=duration_str,
                        size="sm",
                        weight="bold",
                        color=FlexColors.TEXT_PRIMARY,
                        flex=1,
                        align="end"
                    )
                ]
            )
        ]
    )

    return BubbleContainer(
        size="kilo",
        header=header,
        body=body
    )


# ============================================
# 高階訊息建立函數
# ============================================

def create_card_result_message(
    cards: List[BusinessCard],
    is_batch_mode: bool = False,
    batch_progress: Optional[int] = None
) -> FlexSendMessage:
    """
    建立名片處理結果的 Flex Message

    Args:
        cards: 處理完成的名片列表
        is_batch_mode: 是否為批次模式
        batch_progress: 批次模式下的累計數量

    Returns:
        FlexSendMessage 準備發送
    """
    total = len(cards)

    if total == 1:
        # 單張名片 - 顯示詳細卡片
        bubble = build_card_result_bubble(cards[0])
        alt_text = f"名片識別成功：{cards[0].name or '未識別'}"
    else:
        # 多張名片 - 顯示摘要
        bubble = build_multi_card_summary_bubble(total)
        alt_text = f"已處理 {total} 張名片"

    return FlexSendMessage(
        alt_text=alt_text,
        contents=bubble
    )


def create_batch_complete_message(batch_result: BatchProcessResult) -> FlexSendMessage:
    """
    建立批次完成的 Flex Message

    Args:
        batch_result: 批次處理結果

    Returns:
        FlexSendMessage 準備發送
    """
    bubble = build_batch_complete_bubble(batch_result)

    return FlexSendMessage(
        alt_text=f"批次完成：共 {batch_result.total_cards} 張名片",
        contents=bubble
    )
