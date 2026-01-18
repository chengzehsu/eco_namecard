"""
電話號碼正規化工具

支援國際電話號碼的解析、驗證和正規化。
使用 Google 的 libphonenumber 庫（Python 版本：phonenumbers）。

支援的格式：
- 台灣手機：0912345678, 0912-345-678, +886912345678
- 台灣市話：02-12345678, (02)1234-5678, +886212345678
- 國際電話：+1-123-456-7890, +86-123-4567-8901, +81-3-1234-5678
- 各種分隔符號：空格、破折號、點、括號
"""

import re
import structlog
from typing import Optional, Tuple, Dict, Any

logger = structlog.get_logger()

# 嘗試導入 phonenumbers，如果沒有安裝則使用基本的正規化
try:
    import phonenumbers
    from phonenumbers import NumberParseException, PhoneNumberFormat, geocoder, carrier
    PHONENUMBERS_AVAILABLE = True
except ImportError:
    PHONENUMBERS_AVAILABLE = False
    logger.warning("phonenumbers package not installed, using basic phone normalization")


# 預設區域（用於解析不含國碼的電話號碼）
DEFAULT_REGION = "TW"

# 常見的國碼對應
COUNTRY_CODE_MAP = {
    "886": "TW",  # 台灣
    "86": "CN",   # 中國
    "852": "HK",  # 香港
    "853": "MO",  # 澳門
    "81": "JP",   # 日本
    "82": "KR",   # 韓國
    "65": "SG",   # 新加坡
    "60": "MY",   # 馬來西亞
    "66": "TH",   # 泰國
    "63": "PH",   # 菲律賓
    "84": "VN",   # 越南
    "62": "ID",   # 印尼
    "1": "US",    # 美國/加拿大
    "44": "GB",   # 英國
    "49": "DE",   # 德國
    "33": "FR",   # 法國
    "61": "AU",   # 澳洲
    "64": "NZ",   # 紐西蘭
}


def normalize_phone(
    phone: str,
    default_region: str = DEFAULT_REGION,
    format_type: str = "international"
) -> Optional[str]:
    """
    正規化電話號碼
    
    Args:
        phone: 原始電話號碼字串
        default_region: 預設國家/地區代碼（ISO 3166-1 alpha-2）
        format_type: 輸出格式
            - "e164": +886912345678（純數字，適合儲存）
            - "international": +886 912 345 678（國際格式，可讀性好）
            - "national": 0912 345 678（本地格式）
            - "rfc3966": tel:+886-912-345-678（URI 格式）
    
    Returns:
        正規化後的電話號碼，無效則返回 None
    """
    if not phone:
        return None
    
    # 基本清理
    phone = phone.strip()
    
    if PHONENUMBERS_AVAILABLE:
        return _normalize_with_phonenumbers(phone, default_region, format_type)
    else:
        return _normalize_basic(phone, default_region)


def _normalize_with_phonenumbers(
    phone: str,
    default_region: str,
    format_type: str
) -> Optional[str]:
    """使用 phonenumbers 套件進行正規化"""
    try:
        # 預處理：處理一些常見的格式問題
        phone = _preprocess_phone(phone)
        
        # 嘗試解析電話號碼
        parsed = phonenumbers.parse(phone, default_region)
        
        # 驗證電話號碼是否有效
        if not phonenumbers.is_valid_number(parsed):
            # 嘗試使用其他可能的區域
            for region in ["TW", "CN", "HK", "JP", "US"]:
                if region != default_region:
                    try:
                        parsed = phonenumbers.parse(phone, region)
                        if phonenumbers.is_valid_number(parsed):
                            break
                    except NumberParseException:
                        continue
            else:
                # 如果還是無效，嘗試寬鬆模式
                if not phonenumbers.is_possible_number(parsed):
                    logger.debug("Invalid phone number", phone=phone)
                    return _normalize_basic(phone, default_region)
        
        # 根據格式類型輸出
        format_map = {
            "e164": PhoneNumberFormat.E164,
            "international": PhoneNumberFormat.INTERNATIONAL,
            "national": PhoneNumberFormat.NATIONAL,
            "rfc3966": PhoneNumberFormat.RFC3966,
        }
        
        fmt = format_map.get(format_type, PhoneNumberFormat.INTERNATIONAL)
        result = phonenumbers.format_number(parsed, fmt)
        
        logger.debug("Phone normalized", original=phone, normalized=result)
        return result
        
    except NumberParseException as e:
        logger.debug("Failed to parse phone number", phone=phone, error=str(e))
        return _normalize_basic(phone, default_region)
    except Exception as e:
        logger.warning("Phone normalization error", phone=phone, error=str(e))
        return _normalize_basic(phone, default_region)


def _preprocess_phone(phone: str) -> str:
    """預處理電話號碼字串"""
    # 移除常見的非電話字元
    phone = phone.replace("　", " ")  # 全形空格轉半形
    phone = phone.replace("－", "-")  # 全形破折號轉半形
    phone = phone.replace("（", "(").replace("）", ")")
    phone = phone.replace("．", ".")
    
    # 處理台灣手機號碼的常見寫法
    # 例如: 0912-345-678 -> 保持不變（phonenumbers 可以處理）
    
    # 處理國碼的常見寫法
    # +886(0)912345678 -> +886912345678
    phone = re.sub(r'\+886\s*\(0\)', '+886', phone)
    # 886-0912 -> +886912
    if re.match(r'^886[\s\-]?0', phone):
        phone = '+' + re.sub(r'^886[\s\-]?0', '886', phone)
    
    # 處理 00 開頭的國際電話
    # 00886912345678 -> +886912345678
    if phone.startswith('00'):
        phone = '+' + phone[2:]
    
    # 處理台灣市話（0X 開頭，但非手機 09）
    # 02-12345678 -> +886-2-12345678
    # (02) 1234-5678 -> +886-2-1234-5678
    # 關鍵：把台灣市話轉成國際格式讓 phonenumbers 正確解析
    cleaned_for_check = re.sub(r'[^\d]', '', phone)
    if not phone.startswith('+') and cleaned_for_check.startswith('0'):
        # 台灣市話區碼：02, 03, 04, 05, 06, 07, 08
        # 02 台北 (8位)，03-08 其他縣市 (7-8位)
        tw_landline_match = re.match(r'^0([2-8])[\s\-\.\(\)]*(\d{7,8})$', cleaned_for_check)
        if tw_landline_match:
            area_code = tw_landline_match.group(1)
            number = tw_landline_match.group(2)
            phone = f"+886{area_code}{number}"
    
    return phone


def _normalize_basic(phone: str, default_region: str = "TW") -> Optional[str]:
    """基本的電話號碼正規化（不使用 phonenumbers）"""
    if not phone:
        return None
    
    # 移除所有非數字和 + 號
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    if not cleaned:
        return None
    
    # 處理台灣電話號碼
    if default_region == "TW":
        # 如果是 09 開頭（台灣手機）
        if cleaned.startswith('09') and len(cleaned) == 10:
            return f"+886{cleaned[1:]}"  # 0912345678 -> +886912345678
        
        # 如果是 886 開頭
        if cleaned.startswith('886') and len(cleaned) >= 11:
            return f"+{cleaned}"
        
        # 如果是 +886 開頭
        if cleaned.startswith('+886'):
            return cleaned
        
        # 如果是 02-08 開頭（市話）
        if re.match(r'^0[2-8]', cleaned) and 9 <= len(cleaned) <= 10:
            return f"+886{cleaned[1:]}"
    
    # 如果已經是 + 開頭，保持不變
    if cleaned.startswith('+'):
        return cleaned
    
    # 長度檢查
    if len(cleaned) < 8 or len(cleaned) > 15:
        return None
    
    return cleaned


def parse_phone_info(phone: str, default_region: str = DEFAULT_REGION) -> Dict[str, Any]:
    """
    解析電話號碼並返回詳細資訊
    
    Returns:
        Dict 包含:
        - valid: 是否有效
        - e164: E.164 格式
        - international: 國際格式
        - national: 本地格式
        - country_code: 國碼
        - region: 國家/地區代碼
        - carrier: 電信業者（如果可用）
        - location: 地理位置（如果可用）
    """
    result = {
        "valid": False,
        "original": phone,
        "e164": None,
        "international": None,
        "national": None,
        "country_code": None,
        "region": None,
        "carrier": None,
        "location": None,
    }
    
    if not phone or not PHONENUMBERS_AVAILABLE:
        return result
    
    try:
        phone = _preprocess_phone(phone)
        parsed = phonenumbers.parse(phone, default_region)
        
        if phonenumbers.is_valid_number(parsed):
            result["valid"] = True
            result["e164"] = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
            result["international"] = phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
            result["national"] = phonenumbers.format_number(parsed, PhoneNumberFormat.NATIONAL)
            result["country_code"] = parsed.country_code
            result["region"] = phonenumbers.region_code_for_number(parsed)
            
            # 嘗試獲取電信業者
            try:
                result["carrier"] = carrier.name_for_number(parsed, "zh-TW") or carrier.name_for_number(parsed, "en")
            except:
                pass
            
            # 嘗試獲取地理位置
            try:
                result["location"] = geocoder.description_for_number(parsed, "zh-TW") or geocoder.description_for_number(parsed, "en")
            except:
                pass
    
    except Exception as e:
        logger.debug("Failed to parse phone info", phone=phone, error=str(e))
    
    return result


def is_valid_phone(phone: str, default_region: str = DEFAULT_REGION) -> bool:
    """
    檢查電話號碼是否有效
    """
    if not phone:
        return False
    
    if PHONENUMBERS_AVAILABLE:
        try:
            phone = _preprocess_phone(phone)
            parsed = phonenumbers.parse(phone, default_region)
            return phonenumbers.is_valid_number(parsed)
        except:
            pass
    
    # 基本驗證
    cleaned = re.sub(r'[^\d]', '', phone)
    return 8 <= len(cleaned) <= 15


def format_phone_display(phone: str, default_region: str = DEFAULT_REGION) -> str:
    """
    格式化電話號碼用於顯示
    
    返回人類可讀的格式，如果無法解析則返回原始值
    """
    normalized = normalize_phone(phone, default_region, "international")
    return normalized if normalized else phone


# 導出便捷函數
__all__ = [
    "normalize_phone",
    "parse_phone_info", 
    "is_valid_phone",
    "format_phone_display",
    "PHONENUMBERS_AVAILABLE",
]
