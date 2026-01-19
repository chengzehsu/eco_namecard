#!/usr/bin/env python3
"""
電話號碼正規化功能測試腳本

測試 phone_utils.py 的正規化功能是否正確運作。
"""

import sys
import os

# 添加專案根目錄到 Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.namecard.core.utils.phone_utils import (
    normalize_phone,
    parse_phone_info,
    is_valid_phone,
    PHONENUMBERS_AVAILABLE,
)


def test_taiwan_mobile():
    """測試台灣手機號碼"""
    print("\n=== 台灣手機號碼測試 ===")
    
    test_cases = [
        ("0912345678", "+886912345678"),
        ("0912-345-678", "+886912345678"),
        ("0912 345 678", "+886912345678"),
        ("+886912345678", "+886912345678"),
        ("886-912-345-678", "+886912345678"),
        ("+886-912-345-678", "+886912345678"),
        ("0912345678", "+886912345678"),
    ]
    
    passed = 0
    failed = 0
    
    for input_phone, expected in test_cases:
        result = normalize_phone(input_phone, format_type="e164")
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"  {status} '{input_phone}' -> '{result}' (expected: '{expected}')")
    
    return passed, failed


def test_taiwan_landline():
    """測試台灣市話"""
    print("\n=== 台灣市話測試 ===")
    
    test_cases = [
        ("02-12345678", "+886212345678"),
        ("(02) 1234-5678", "+886212345678"),
        ("02 1234 5678", "+886212345678"),
        ("03-1234567", "+88631234567"),
        ("04-12345678", "+886412345678"),
    ]
    
    passed = 0
    failed = 0
    
    for input_phone, expected in test_cases:
        result = normalize_phone(input_phone, format_type="e164")
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"  {status} '{input_phone}' -> '{result}' (expected: '{expected}')")
    
    return passed, failed


def test_international():
    """測試國際電話"""
    print("\n=== 國際電話測試 ===")
    
    test_cases = [
        ("+1-123-456-7890", "+11234567890"),      # 美國
        ("+86-138-1234-5678", "+8613812345678"),  # 中國
        ("+81-3-1234-5678", "+81312345678"),      # 日本
        ("+852-1234-5678", "+85212345678"),       # 香港
        ("+65-1234-5678", "+6512345678"),         # 新加坡
    ]
    
    passed = 0
    failed = 0
    
    for input_phone, expected in test_cases:
        result = normalize_phone(input_phone, format_type="e164")
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"  {status} '{input_phone}' -> '{result}' (expected: '{expected}')")
    
    return passed, failed


def test_edge_cases():
    """測試邊界情況"""
    print("\n=== 邊界情況測試 ===")
    
    test_cases = [
        ("", None),           # 空字串
        (None, None),         # None
        ("123", None),        # 太短
        ("abcdefgh", None),   # 非數字
    ]
    
    passed = 0
    failed = 0
    
    for input_phone, expected in test_cases:
        try:
            result = normalize_phone(input_phone, format_type="e164") if input_phone else None
        except:
            result = None
        
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"  {status} '{input_phone}' -> '{result}' (expected: '{expected}')")
    
    return passed, failed


def test_parse_info():
    """測試詳細解析功能"""
    print("\n=== 電話資訊解析測試 ===")
    
    if not PHONENUMBERS_AVAILABLE:
        print("  ⚠️ phonenumbers 套件未安裝，跳過詳細解析測試")
        return 0, 0
    
    test_phone = "0912345678"
    info = parse_phone_info(test_phone)
    
    print(f"  輸入: {test_phone}")
    print(f"  有效: {info['valid']}")
    print(f"  E.164: {info['e164']}")
    print(f"  國際格式: {info['international']}")
    print(f"  本地格式: {info['national']}")
    print(f"  國碼: {info['country_code']}")
    print(f"  地區: {info['region']}")
    print(f"  電信業者: {info['carrier']}")
    print(f"  位置: {info['location']}")
    
    return 1 if info['valid'] else 0, 0 if info['valid'] else 1


def main():
    print("=" * 50)
    print("電話號碼正規化功能測試")
    print("=" * 50)
    print(f"\nphonumbers 套件可用: {PHONENUMBERS_AVAILABLE}")
    
    total_passed = 0
    total_failed = 0
    
    # 執行所有測試
    p, f = test_taiwan_mobile()
    total_passed += p
    total_failed += f
    
    p, f = test_taiwan_landline()
    total_passed += p
    total_failed += f
    
    p, f = test_international()
    total_passed += p
    total_failed += f
    
    p, f = test_edge_cases()
    total_passed += p
    total_failed += f
    
    p, f = test_parse_info()
    total_passed += p
    total_failed += f
    
    # 總結
    print("\n" + "=" * 50)
    print(f"測試結果: {total_passed} 通過, {total_failed} 失敗")
    print("=" * 50)
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
