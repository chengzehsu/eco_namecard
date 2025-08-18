#!/usr/bin/env python3
"""
名片處理診斷工具
專門用來分析為什麼某些名片的電話號碼無法被正確識別
"""

import sys
import os
import json
from datetime import datetime

# 添加專案根目錄到路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.namecard.infrastructure.ai.card_processor import CardProcessor, ProcessingConfig
from src.namecard.core.models.card import BusinessCard


def analyze_card_processing_issue(card_name: str = "熊恩皓"):
    """分析特定名片的處理問題"""
    print(f"🔍 分析 {card_name} 名片處理問題")
    print("=" * 60)
    
    # 創建處理器
    processor = CardProcessor()
    
    print("📋 當前處理配置：")
    print(f"   • 最小信心度閾值: {processor.config.min_confidence_threshold}")
    print(f"   • 最小品質閾值: {processor.config.min_quality_threshold}")
    print(f"   • 最大重試次數: {processor.config.max_retries}")
    print()
    
    print("🤖 當前 AI Prompt 關鍵部分：")
    prompt_lines = processor.card_prompt.split('\n')
    phone_related = [line for line in prompt_lines if '電話' in line or 'phone' in line.lower()]
    for line in phone_related:
        print(f"   {line.strip()}")
    print()
    
    print("💡 可能的電話識別失敗原因：")
    print()
    
    print("1️⃣ **AI 識別階段問題**")
    print("   • Gemini AI 可能將電話識別為其他欄位（如傳真）")
    print("   • 圖片品質問題導致 OCR 失敗")
    print("   • 電話號碼格式特殊，AI 無法正確分類")
    print("   • Prompt 指令不夠明確")
    print()
    
    print("2️⃣ **資料解析階段問題**")
    print("   • JSON 解析錯誤")
    print("   • 欄位名稱對應錯誤")
    print("   • 資料類型轉換問題")
    print()
    
    print("3️⃣ **品質驗證階段問題**")
    print("   • 信心度太低被過濾掉")
    print("   • 品質分數太低被過濾掉")
    print("   • 聯絡方式驗證失敗")
    print()
    
    print("4️⃣ **Notion 儲存階段問題**")
    print("   • 電話號碼格式不符合 Notion 要求")
    print("   • 資料長度超過限制")
    print("   • 特殊字符處理問題")
    print()
    
    return generate_debugging_recommendations(card_name)


def generate_debugging_recommendations(card_name: str):
    """生成除錯建議"""
    print("🛠️ 除錯建議和解決方案：")
    print()
    
    recommendations = []
    
    print("**立即檢查步驟：**")
    steps = [
        "1. 檢查 Sentry Dashboard 中是否有相關錯誤記錄",
        "2. 查看 /monitoring/dashboard 了解最近的處理統計",
        "3. 檢查該用戶的處理日誌",
        "4. 確認圖片品質和清晰度",
        "5. 驗證電話號碼在圖片中的實際格式"
    ]
    
    for step in steps:
        print(f"   {step}")
        recommendations.append(step)
    print()
    
    print("**測試方法：**")
    test_methods = [
        "重新上傳同一張名片圖片",
        "嘗試裁剪圖片只保留電話號碼區域",
        "使用其他相似格式的名片測試",
        "檢查是否為特定用戶的問題"
    ]
    
    for method in test_methods:
        print(f"   • {method}")
        recommendations.append(method)
    print()
    
    print("**程式碼修正建議：**")
    code_fixes = [
        "降低電話號碼驗證的嚴格度",
        "增加更多電話號碼格式的支援",
        "改善 AI prompt 的電話識別指令",
        "添加更詳細的除錯日誌"
    ]
    
    for fix in code_fixes:
        print(f"   • {fix}")
        recommendations.append(fix)
    print()
    
    return recommendations


def create_enhanced_prompt():
    """建立增強版的 AI prompt"""
    enhanced_prompt = """
你是一個專業的名片 OCR 識別系統。請特別注意電話號碼的正確識別。

電話號碼識別重點：
1. 優先尋找以下格式的電話號碼：
   - (02) XXXX-XXXX
   - 02-XXXX-XXXX  
   - 0912-XXX-XXX
   - +886-2-XXXX-XXXX
   - 任何數字組合，包含分隔符號或括號

2. 電話號碼可能出現的位置：
   - 名片正面任何位置
   - 可能有 "Tel:", "電話:", "Phone:" 標籤
   - 也可能沒有任何標籤，直接是數字

3. 傳真號碼識別：
   - 明確標示 "Fax", "傳真", "F:" 的才是傳真
   - 沒有標示的數字優先當作電話

4. 如果有多個號碼：
   - 優先選擇較長的完整號碼
   - 手機號碼格式：09XX-XXX-XXX
   - 市話格式：(0X) XXXX-XXXX

特別注意：
- 即使號碼格式特殊也要嘗試識別
- 寧可多識別也不要漏掉
- 電話號碼是重要資訊，請仔細尋找
"""
    
    return enhanced_prompt


def suggest_immediate_fixes():
    """建議立即修正方案"""
    print("🚀 建議的立即修正方案：")
    print()
    
    fixes = [
        {
            "priority": "高",
            "title": "降低品質閾值",
            "description": "暫時降低 min_confidence_threshold 從 0.3 到 0.1",
            "code": "config.min_confidence_threshold = 0.1"
        },
        {
            "priority": "高", 
            "title": "增強 AI prompt",
            "description": "在 prompt 中特別強調電話號碼識別",
            "code": "在 prompt 中加入專門的電話識別指令"
        },
        {
            "priority": "中",
            "title": "添加除錯日誌",
            "description": "記錄 AI 回應的原始 JSON 以便分析",
            "code": "logger.debug('Raw AI response', response=response_text)"
        },
        {
            "priority": "中",
            "title": "寬鬆聯絡方式驗證",
            "description": "即使沒有電話也允許有姓名和公司的名片通過",
            "code": "修改 _validate_card_quality 方法"
        }
    ]
    
    for fix in fixes:
        print(f"**[{fix['priority']}] {fix['title']}**")
        print(f"   說明: {fix['description']}")
        print(f"   實作: {fix['code']}")
        print()
    
    return fixes


def main():
    """主函數"""
    print("🎯 名片電話識別問題診斷工具")
    print(f"⏰ 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 分析問題
    recommendations = analyze_card_processing_issue("熊恩皓")
    
    # 顯示增強 prompt
    print("📝 建議的增強版 AI Prompt：")
    enhanced_prompt = create_enhanced_prompt()
    print(enhanced_prompt)
    print()
    
    # 建議修正方案
    fixes = suggest_immediate_fixes()
    
    print("📊 診斷總結：")
    print("   • 電話識別失敗可能原因已分析")
    print("   • 提供了具體的除錯步驟")
    print("   • 建議了立即可行的修正方案")
    print()
    
    print("💡 下一步建議：")
    print("   1. 先檢查 Sentry 和監控日誌")
    print("   2. 嘗試降低品質閾值的快速修正")
    print("   3. 改善 AI prompt 增強電話識別")
    print("   4. 測試修正效果")
    
    print("\n" + "=" * 60)
    print("🎉 診斷完成！請根據建議進行修正和測試。")


if __name__ == "__main__":
    main()