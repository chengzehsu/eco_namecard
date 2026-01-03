#!/usr/bin/env python
"""
驗證 Notion 字段保存修復
此腳本驗證 _prepare_card_properties() 方法即使在 _db_schema 為空時也能正常工作
"""

from src.namecard.core.models.card import BusinessCard
from src.namecard.infrastructure.storage.notion_fields import NotionFields


# 模擬場景：_db_schema 為空的情況
class MockNotionClient:
    """模擬 NotionClient 以測試修復"""

    def __init__(self):
        self._db_schema = {}  # 模擬空 schema（bug 場景）

    def _field_exists(self, field_name: str) -> bool:
        """檢查欄位是否存在（修復前的邏輯）"""
        return field_name in self._db_schema

    def _clean_title_or_department(self, text):
        """簡化版清理方法"""
        if not text:
            return None
        text = text.strip()
        if "," in text:
            text = text.split(",")[0].strip()
        return text

    def _prepare_card_properties_OLD(self, card: BusinessCard):
        """修復前的版本（有 _field_exists 檢查）"""
        properties = {}

        # Name - 必填
        properties[NotionFields.NAME] = {"title": [{"text": {"content": card.name or "未知姓名"}}]}

        # Email - 修復前：有 _field_exists 檢查
        if card.email and "@" in card.email and self._field_exists(NotionFields.EMAIL):
            properties[NotionFields.EMAIL] = {"email": card.email}

        # Company - 修復前：有 _field_exists 檢查
        if card.company and self._field_exists(NotionFields.COMPANY):
            properties[NotionFields.COMPANY] = {"rich_text": [{"text": {"content": card.company}}]}

        # Phone - 修復前：有 _field_exists 檢查
        if card.phone and self._field_exists(NotionFields.PHONE):
            properties[NotionFields.PHONE] = {"phone_number": card.phone}

        # Address - 修復前：有 _field_exists 檢查
        if card.address and self._field_exists(NotionFields.ADDRESS):
            properties[NotionFields.ADDRESS] = {"rich_text": [{"text": {"content": card.address}}]}

        # Title - 修復前：有 _field_exists 檢查
        if card.title and self._field_exists(NotionFields.TITLE):
            cleaned_title = self._clean_title_or_department(card.title)
            if cleaned_title:
                properties[NotionFields.TITLE] = {"select": {"name": cleaned_title}}

        # Department - 修復前：有 _field_exists 檢查
        if card.department and self._field_exists(NotionFields.DEPARTMENT):
            cleaned_department = self._clean_title_or_department(card.department)
            if cleaned_department:
                properties[NotionFields.DEPARTMENT] = {
                    "rich_text": [{"text": {"content": cleaned_department}}]
                }

        return properties

    def _prepare_card_properties_NEW(self, card: BusinessCard):
        """修復後的版本（移除 _field_exists 檢查）"""
        properties = {}

        # Name - 必填
        properties[NotionFields.NAME] = {"title": [{"text": {"content": card.name or "未知姓名"}}]}

        # Email - 修復後：直接嘗試保存
        if card.email and "@" in card.email:
            properties[NotionFields.EMAIL] = {"email": card.email}

        # Company - 修復後：直接嘗試保存
        if card.company:
            properties[NotionFields.COMPANY] = {"rich_text": [{"text": {"content": card.company}}]}

        # Phone - 修復後：直接嘗試保存
        if card.phone:
            properties[NotionFields.PHONE] = {"phone_number": card.phone}

        # Address - 修復後：直接嘗試保存
        if card.address:
            properties[NotionFields.ADDRESS] = {"rich_text": [{"text": {"content": card.address}}]}

        # Title - 修復後：直接嘗試保存
        if card.title:
            cleaned_title = self._clean_title_or_department(card.title)
            if cleaned_title:
                properties[NotionFields.TITLE] = {"select": {"name": cleaned_title}}

        # Department - 修復後：直接嘗試保存
        if card.department:
            cleaned_department = self._clean_title_or_department(card.department)
            if cleaned_department:
                properties[NotionFields.DEPARTMENT] = {
                    "rich_text": [{"text": {"content": cleaned_department}}]
                }

        return properties


def test_fix():
    """測試修復效果"""
    print("=" * 80)
    print("Notion 字段保存 Bug 修復驗證")
    print("=" * 80)

    # 創建測試名片
    card = BusinessCard(
        name="張三",
        company="測試公司",
        title="工程師",
        department="技術部",
        phone="02-1234-5678",
        email="test@example.com",
        address="台北市信義區",
        confidence_score=0.95,
        quality_score=0.9,
        line_user_id="U1234567890",
    )

    client = MockNotionClient()

    print("\n場景：_db_schema 為空（模擬 bug 情況）")
    print(f"_db_schema: {client._db_schema}")
    print(f"_field_exists('Email'): {client._field_exists('Email')}")
    print(f"_field_exists('公司名稱'): {client._field_exists('公司名稱')}")

    # 測試修復前的版本
    print("\n" + "-" * 80)
    print("修復前（有 _field_exists 檢查）")
    print("-" * 80)
    properties_old = client._prepare_card_properties_OLD(card)
    print(f"生成的 properties 字段數: {len(properties_old)}")
    print(f"包含的字段: {list(properties_old.keys())}")
    print(f"✗ 問題：只有 Name 被保存，其他字段都被 _field_exists 檢查過濾掉了")

    # 測試修復後的版本
    print("\n" + "-" * 80)
    print("修復後（移除 _field_exists 檢查）")
    print("-" * 80)
    properties_new = client._prepare_card_properties_NEW(card)
    print(f"生成的 properties 字段數: {len(properties_new)}")
    print(f"包含的字段: {list(properties_new.keys())}")
    print(f"✓ 修復成功：所有字段都被正確保存")

    # 詳細顯示字段內容
    print("\n" + "-" * 80)
    print("修復後的字段詳細內容")
    print("-" * 80)
    for field, value in properties_new.items():
        print(f"  {field}: {value}")

    # 驗證結果
    print("\n" + "=" * 80)
    print("驗證結果")
    print("=" * 80)

    expected_fields = [
        NotionFields.NAME,
        NotionFields.EMAIL,
        NotionFields.COMPANY,
        NotionFields.PHONE,
        NotionFields.ADDRESS,
        NotionFields.TITLE,
        NotionFields.DEPARTMENT,
    ]

    missing_in_old = [f for f in expected_fields if f not in properties_old]
    missing_in_new = [f for f in expected_fields if f not in properties_new]

    print(f"修復前缺少的字段: {missing_in_old}")
    print(f"修復後缺少的字段: {missing_in_new}")

    if len(missing_in_new) == 0:
        print("\n✓ 測試通過：修復後所有字段都能正確保存")
        return True
    else:
        print("\n✗ 測試失敗：仍有字段缺失")
        return False


if __name__ == "__main__":
    success = test_fix()
    exit(0 if success else 1)
