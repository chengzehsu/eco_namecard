"""
Flex Message Templates 測試
"""

import pytest
from datetime import datetime, timedelta
from linebot.models import FlexSendMessage, BubbleContainer

from src.namecard.core.models.card import BusinessCard, BatchProcessResult
from src.namecard.api.line_bot.flex_templates import (
    build_card_result_bubble,
    build_multi_card_summary_bubble,
    build_batch_complete_bubble,
    create_card_result_message,
    create_batch_complete_message,
)


@pytest.fixture
def sample_card():
    """範例名片"""
    return BusinessCard(
        name="王大明",
        company="ABC 科技股份有限公司",
        title="技術總監",
        phone="0912-345-678",
        email="wang@abc.com",
        address="台北市信義區信義路五段7號",
        line_user_id="test_user"
    )


@pytest.fixture
def sample_card_minimal():
    """最小資料的名片"""
    return BusinessCard(
        name="李小華",
        line_user_id="test_user"
    )


@pytest.fixture
def sample_batch_result():
    """範例批次結果"""
    return BatchProcessResult(
        user_id="test_user",
        total_cards=10,
        successful_cards=10,
        failed_cards=0,
        started_at=datetime.now() - timedelta(minutes=2, seconds=30),
        completed_at=datetime.now()
    )


class TestBuildCardResultBubble:
    """測試單張名片卡片建立"""

    def test_returns_bubble_container(self, sample_card):
        """應回傳 BubbleContainer"""
        result = build_card_result_bubble(sample_card)
        assert isinstance(result, BubbleContainer)

    def test_includes_header(self, sample_card):
        """應包含 header"""
        result = build_card_result_bubble(sample_card)
        assert result.header is not None

    def test_includes_body(self, sample_card):
        """應包含 body"""
        result = build_card_result_bubble(sample_card)
        assert result.body is not None

    def test_includes_footer(self, sample_card):
        """應包含 footer"""
        result = build_card_result_bubble(sample_card)
        assert result.footer is not None

    def test_handles_minimal_card(self, sample_card_minimal):
        """應能處理只有姓名的名片"""
        result = build_card_result_bubble(sample_card_minimal)
        assert isinstance(result, BubbleContainer)


class TestBuildMultiCardSummaryBubble:
    """測試多張名片摘要卡片建立"""

    def test_returns_bubble_container(self):
        """應回傳 BubbleContainer"""
        result = build_multi_card_summary_bubble(total=5)
        assert isinstance(result, BubbleContainer)

    def test_size_is_kilo(self):
        """應使用 kilo 尺寸"""
        result = build_multi_card_summary_bubble(total=5)
        assert result.size == "kilo"


class TestBuildBatchCompleteBubble:
    """測試批次完成卡片建立"""

    def test_returns_bubble_container(self, sample_batch_result):
        """應回傳 BubbleContainer"""
        result = build_batch_complete_bubble(sample_batch_result)
        assert isinstance(result, BubbleContainer)

    def test_size_is_kilo(self, sample_batch_result):
        """應使用 kilo 尺寸"""
        result = build_batch_complete_bubble(sample_batch_result)
        assert result.size == "kilo"


class TestCreateCardResultMessage:
    """測試名片結果訊息建立"""

    def test_single_card_returns_flex_message(self, sample_card):
        """單張名片應回傳 FlexSendMessage"""
        result = create_card_result_message(cards=[sample_card])
        assert isinstance(result, FlexSendMessage)

    def test_single_card_alt_text_includes_name(self, sample_card):
        """單張名片的 alt_text 應包含姓名"""
        result = create_card_result_message(cards=[sample_card])
        assert "王大明" in result.alt_text

    def test_multiple_cards_returns_flex_message(self, sample_card):
        """多張名片應回傳 FlexSendMessage"""
        result = create_card_result_message(cards=[sample_card, sample_card])
        assert isinstance(result, FlexSendMessage)

    def test_multiple_cards_alt_text_shows_count(self, sample_card):
        """多張名片的 alt_text 應顯示數量"""
        result = create_card_result_message(cards=[sample_card, sample_card, sample_card])
        assert "3" in result.alt_text


class TestCreateBatchCompleteMessage:
    """測試批次完成訊息建立"""

    def test_returns_flex_message(self, sample_batch_result):
        """應回傳 FlexSendMessage"""
        result = create_batch_complete_message(sample_batch_result)
        assert isinstance(result, FlexSendMessage)

    def test_alt_text_includes_total(self, sample_batch_result):
        """alt_text 應包含總數"""
        result = create_batch_complete_message(sample_batch_result)
        assert "10" in result.alt_text
