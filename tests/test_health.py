"""健康檢查和基本 API 測試"""

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


def test_test_endpoint(client):
    """測試 test 端點"""
    response = client.get('/test')
    
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'message' in data
    assert 'config' in data
    assert 'rate_limit' in data['config']
    assert 'batch_limit' in data['config']
    assert 'max_image_size' in data['config']


def test_invalid_endpoint(client):
    """測試無效端點"""
    response = client.get('/invalid-endpoint')
    assert response.status_code == 404


def test_callback_without_signature(client):
    """測試沒有簽名的 webhook 請求"""
    response = client.post('/callback', data='test data')
    assert response.status_code == 400


def test_callback_with_invalid_signature(client):
    """測試無效簽名的 webhook 請求"""
    headers = {'X-Line-Signature': 'invalid_signature'}
    response = client.post('/callback', data='test data', headers=headers)
    assert response.status_code == 400