# Notion Client 修改對比

## 修改文件

`src/namecard/infrastructure/storage/notion_client.py`

## 修改方法

`_prepare_card_properties(self, card: BusinessCard) -> Dict[str, Any]`

---

## 1. Email 字段（第 278-281 行）

### 修復前

```python
if card.email and "@" in card.email and self._field_exists(NotionFields.EMAIL):
    try:
        properties[NotionFields.EMAIL] = {"email": card.email}
        logger.info("Email field added to properties", email=card.email[:20])
    except Exception as e:
        logger.warning("Failed to add email field", error=str(e))
```

### 修復後

```python
if card.email and "@" in card.email:
    properties[NotionFields.EMAIL] = {"email": card.email}
    logger.info("Email field added to properties", email=card.email[:20])
```

**改變**：

- 移除 `self._field_exists(NotionFields.EMAIL)` 檢查
- 移除 try-except 包裝（由外層統一處理錯誤）

---

## 2. 公司名稱字段（第 299-305 行）

### 修復前

```python
if card.company and self._field_exists(NotionFields.COMPANY):
    company_parts = card.company.split()
    main_company = company_parts[0] if company_parts else card.company

    properties[NotionFields.COMPANY] = {"rich_text": [{"text": {"content": main_company}}]}
```

### 修復後

```python
if card.company:
    company_parts = card.company.split()
    main_company = company_parts[0] if company_parts else card.company

    properties[NotionFields.COMPANY] = {"rich_text": [{"text": {"content": main_company}}]}
    logger.info("Company field added to properties", company=main_company)
```

**改變**：

- 移除 `self._field_exists(NotionFields.COMPANY)` 檢查
- 增加日誌記錄

---

## 3. 地址字段（第 308-310 行）

### 修復前

```python
if card.address and self._field_exists(NotionFields.ADDRESS):
    properties[NotionFields.ADDRESS] = {"rich_text": [{"text": {"content": card.address}}]}
```

### 修復後

```python
if card.address:
    properties[NotionFields.ADDRESS] = {"rich_text": [{"text": {"content": card.address}}]}
    logger.info("Address field added to properties", address=card.address[:30])
```

**改變**：

- 移除 `self._field_exists(NotionFields.ADDRESS)` 檢查
- 增加日誌記錄

---

## 4. 職稱字段（第 321-330 行）

### 修復前

```python
if card.title and self._field_exists(NotionFields.TITLE):
    cleaned_title = self._clean_title_or_department(card.title)
    if cleaned_title:
        properties[NotionFields.TITLE] = {"select": {"name": cleaned_title}}
        logger.info(
            "Title saved to Notion",
            card_name=card.name,
            original_title=card.title,
            cleaned_title=cleaned_title,
        )
```

### 修復後

```python
if card.title:
    cleaned_title = self._clean_title_or_department(card.title)
    if cleaned_title:
        properties[NotionFields.TITLE] = {"select": {"name": cleaned_title}}
        logger.info(
            "Title field added to properties",
            card_name=card.name,
            original_title=card.title,
            cleaned_title=cleaned_title,
        )
```

**改變**：

- 移除 `self._field_exists(NotionFields.TITLE)` 檢查
- 更新日誌訊息（更準確描述操作）

---

## 5. 部門字段（第 333-344 行）

### 修復前

```python
if card.department and self._field_exists(NotionFields.DEPARTMENT):
    cleaned_department = self._clean_title_or_department(card.department)
    if cleaned_department:
        properties[NotionFields.DEPARTMENT] = {
            "rich_text": [{"text": {"content": cleaned_department}}]
        }
        logger.info(
            "Department saved to Notion",
            card_name=card.name,
            original_department=card.department,
            cleaned_department=cleaned_department,
        )
```

### 修復後

```python
if card.department:
    cleaned_department = self._clean_title_or_department(card.department)
    if cleaned_department:
        properties[NotionFields.DEPARTMENT] = {
            "rich_text": [{"text": {"content": cleaned_department}}]
        }
        logger.info(
            "Department field added to properties",
            card_name=card.name,
            original_department=card.department,
            cleaned_department=cleaned_department,
        )
```

**改變**：

- 移除 `self._field_exists(NotionFields.DEPARTMENT)` 檢查
- 更新日誌訊息（更準確描述操作）

---

## 6. 電話字段（第 347-349 行）

### 修復前

```python
if card.phone and self._field_exists(NotionFields.PHONE):
    properties[NotionFields.PHONE] = {"phone_number": card.phone}
```

### 修復後

```python
if card.phone:
    properties[NotionFields.PHONE] = {"phone_number": card.phone}
    logger.info("Phone field added to properties", phone=card.phone)
```

**改變**：

- 移除 `self._field_exists(NotionFields.PHONE)` 檢查
- 增加日誌記錄

---

## 7. 備註字段（第 352-357 行）

### 修復前

```python
if additional_info and self._field_exists(NotionFields.NOTES):
    properties[NotionFields.NOTES] = {
        "rich_text": [{"text": {"content": " | ".join(additional_info)}}]
    }
```

### 修復後

```python
if additional_info:
    notes_content = " | ".join(additional_info)
    properties[NotionFields.NOTES] = {
        "rich_text": [{"text": {"content": notes_content}}]
    }
    logger.info("Notes field added to properties", notes_preview=notes_content[:50])
```

**改變**：

- 移除 `self._field_exists(NotionFields.NOTES)` 檢查
- 提取 notes_content 變量（避免重複計算）
- 增加日誌記錄

---

## 總結

### 統一的改變模式

所有 7 個字段的修改都遵循相同的模式：

1. **移除 `_field_exists()` 檢查**
   - 不再依賴 `_db_schema` 來決定是否保存字段
   - 避免因 schema 為空導致字段丟失

2. **增強日誌記錄**
   - 為所有字段添加或改進日誌訊息
   - 方便調試和監控

3. **保持數據驗證**
   - Email 仍然檢查 `"@"` 符號
   - 職稱和部門仍然進行清理處理
   - 所有業務邏輯保持不變

### 影響

- **Before**: 當 `_db_schema` 為空時，只保存 Name 字段
- **After**: 無論 `_db_schema` 狀態如何，都嘗試保存所有字段
- **Result**: 字段保存從 1 個增加到 7 個（100% → 700% 改進）
