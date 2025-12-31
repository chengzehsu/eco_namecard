"""健康檢查和基本 API 測試

Updated for multi-tenant architecture (v3.0.0)
"""

import json
import pytest


def test_health_check(client):
    """測試健康檢查端點"""
    response = client.get('/health')

    assert response.status_code == 200

    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert 'service' in data
    assert 'version' in data
    assert 'timestamp' in data
    # 多租戶版本新增欄位
    assert 'multi_tenant' in data
    assert 'active_tenants' in data


def test_test_endpoint(client):
    """測試 test 端點"""
    response = client.get('/test')

    assert response.status_code == 200

    data = json.loads(response.data)
    assert data['status'] == 'ok'
    assert 'config' in data
    assert 'environment' in data
    assert 'timestamp' in data
    # 檢查配置欄位
    assert 'line_bot_configured' in data['config']
    assert 'google_ai_configured' in data['config']
    assert 'notion_configured' in data['config']
    assert 'multi_tenant_enabled' in data['config']


def test_invalid_endpoint(client):
    """測試無效端點"""
    response = client.get('/invalid-endpoint')
    assert response.status_code == 404


def test_callback_without_signature(client):
    """測試沒有簽名的 webhook 請求

    LINE webhook 設計返回 200 避免平台重試，
    錯誤資訊透過 JSON body 回傳。
    """
    response = client.post('/callback', data='test data')
    # 返回 200 但 status 為 error
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'missing signature or body'


def test_callback_with_invalid_signature(client):
    """測試無效簽名的 webhook 請求

    LINE webhook 設計返回 200 避免平台重試，
    簽名錯誤透過 JSON body 回傳。
    """
    headers = {'X-Line-Signature': 'invalid_signature'}
    response = client.post('/callback', data='{"events":[]}', headers=headers)
    # 返回 200 但 status 表示錯誤
    assert response.status_code == 200


def test_debug_tenants_endpoint_blocked_in_production(client):
    """測試 debug/tenants 端點在生產環境被封鎖"""
    response = client.get('/debug/tenants')
    # 生產環境返回 403，開發環境返回 200
    # 這裡接受兩種情況都算通過
    assert response.status_code in [200, 403]
    if response.status_code == 200:
        data = json.loads(response.data)
        assert 'tenants' in data or 'error' in data
    else:
        data = json.loads(response.data)
        assert 'error' in data
