#!/usr/bin/env python3
"""
Cloudflare 監控和測試腳本
用於監控 LINE Bot 名片管理系統的 Cloudflare 配置和效能
"""

import requests
import json
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse
import sys

class CloudflareMonitor:
    """Cloudflare 監控類"""
    
    def __init__(self, domain: str, endpoints: List[str] = None):
        self.domain = domain.replace('https://', '').replace('http://', '')
        self.base_url = f"https://{self.domain}"
        self.endpoints = endpoints or ['/health', '/test', '/callback']
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CloudflareMonitor/1.0'
        })
    
    def test_endpoint(self, endpoint: str, method: str = 'GET', 
                     data: Dict = None, timeout: int = 10) -> Dict:
        """測試單一端點"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, timeout=timeout)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # 檢查 Cloudflare 標頭
            cf_ray = response.headers.get('cf-ray', 'Not found')
            cf_cache_status = response.headers.get('cf-cache-status', 'Not found')
            cf_country = response.headers.get('cf-ipcountry', 'Not found')
            
            result = {
                'endpoint': endpoint,
                'method': method,
                'status_code': response.status_code,
                'response_time': round(response_time, 3),
                'content_length': len(response.content),
                'cloudflare': {
                    'ray_id': cf_ray,
                    'cache_status': cf_cache_status,
                    'country': cf_country,
                    'server': response.headers.get('server', 'Unknown')
                },
                'headers': dict(response.headers),
                'timestamp': datetime.now().isoformat()
            }
            
            # 如果是 JSON 回應，嘗試解析
            if 'application/json' in response.headers.get('content-type', ''):
                try:
                    result['json_response'] = response.json()
                except:
                    result['json_response'] = None
            
            return result
            
        except requests.exceptions.Timeout:
            return {
                'endpoint': endpoint,
                'method': method,
                'error': 'Timeout',
                'response_time': timeout,
                'timestamp': datetime.now().isoformat()
            }
        except requests.exceptions.RequestException as e:
            return {
                'endpoint': endpoint,
                'method': method,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def performance_test(self, endpoint: str, iterations: int = 10, 
                        delay: float = 0.5) -> Dict:
        """效能測試"""
        print(f"🚀 對 {endpoint} 進行效能測試 ({iterations} 次)...")
        
        results = []
        for i in range(iterations):
            print(f"  請求 {i+1}/{iterations}", end='\r')
            result = self.test_endpoint(endpoint)
            results.append(result)
            
            if delay > 0 and i < iterations - 1:
                time.sleep(delay)
        
        print()  # 換行
        
        # 計算統計資料
        response_times = [r.get('response_time', 0) for r in results if 'response_time' in r]
        status_codes = [r.get('status_code', 0) for r in results if 'status_code' in r]
        cache_statuses = [r.get('cloudflare', {}).get('cache_status', 'Unknown') for r in results]
        
        success_count = len([s for s in status_codes if 200 <= s < 300])
        
        stats = {
            'endpoint': endpoint,
            'total_requests': iterations,
            'successful_requests': success_count,
            'success_rate': round(success_count / iterations * 100, 2),
            'response_times': {
                'min': round(min(response_times), 3) if response_times else 0,
                'max': round(max(response_times), 3) if response_times else 0,
                'avg': round(statistics.mean(response_times), 3) if response_times else 0,
                'median': round(statistics.median(response_times), 3) if response_times else 0
            },
            'cache_analysis': {
                'cache_statuses': list(set(cache_statuses)),
                'cache_hit_rate': round(cache_statuses.count('HIT') / len(cache_statuses) * 100, 2) if cache_statuses else 0
            },
            'status_codes': list(set(status_codes)),
            'raw_results': results
        }
        
        return stats
    
    def security_test(self) -> Dict:
        """安全性測試"""
        print("🔒 進行安全性測試...")
        
        tests = []
        
        # 測試 1: 無簽章的 webhook 請求
        print("  測試 webhook 安全性...")
        webhook_test = self.test_endpoint('/callback', 'POST', {'test': 'data'})
        tests.append({
            'name': 'Webhook without signature',
            'expected': 'Should be blocked (400 or 403)',
            'actual': webhook_test.get('status_code', 'Error'),
            'passed': webhook_test.get('status_code') in [400, 403],
            'details': webhook_test
        })
        
        # 測試 2: 不支援的 HTTP 方法
        print("  測試 HTTP 方法限制...")
        method_test = self.test_endpoint('/health', 'DELETE')
        tests.append({
            'name': 'Unsupported HTTP method',
            'expected': 'Should be blocked (405)',
            'actual': method_test.get('status_code', 'Error'),
            'passed': method_test.get('status_code') == 405,
            'details': method_test
        })
        
        # 測試 3: 檢查安全標頭
        print("  檢查安全標頭...")
        headers_test = self.test_endpoint('/health')
        security_headers = {
            'x-content-type-options': 'nosniff',
            'x-frame-options': 'DENY',
            'strict-transport-security': True  # 只檢查是否存在
        }
        
        headers_passed = True
        missing_headers = []
        for header, expected in security_headers.items():
            actual = headers_test.get('headers', {}).get(header)
            if expected is True:
                if not actual:
                    headers_passed = False
                    missing_headers.append(header)
            else:
                if actual != expected:
                    headers_passed = False
                    missing_headers.append(f"{header} (expected: {expected}, got: {actual})")
        
        tests.append({
            'name': 'Security headers',
            'expected': 'All required headers present',
            'actual': f"Missing: {missing_headers}" if missing_headers else "All headers present",
            'passed': headers_passed,
            'details': headers_test.get('headers', {})
        })
        
        # 測試 4: SSL/TLS 檢查
        print("  檢查 SSL/TLS...")
        ssl_test = self.test_endpoint('/health')
        ssl_passed = ssl_test.get('status_code') == 200
        tests.append({
            'name': 'SSL/TLS connectivity',
            'expected': 'HTTPS connection successful',
            'actual': f"Status: {ssl_test.get('status_code', 'Error')}",
            'passed': ssl_passed,
            'details': ssl_test
        })
        
        passed_tests = len([t for t in tests if t['passed']])
        
        return {
            'total_tests': len(tests),
            'passed_tests': passed_tests,
            'success_rate': round(passed_tests / len(tests) * 100, 2),
            'tests': tests
        }
    
    def cache_test(self) -> Dict:
        """快取測試"""
        print("💾 進行快取測試...")
        
        cacheable_endpoints = ['/health', '/test']
        results = {}
        
        for endpoint in cacheable_endpoints:
            print(f"  測試 {endpoint} 快取...")
            
            # 第一次請求 (應該是 MISS)
            first_request = self.test_endpoint(endpoint)
            time.sleep(1)
            
            # 第二次請求 (應該是 HIT)
            second_request = self.test_endpoint(endpoint)
            
            first_cache = first_request.get('cloudflare', {}).get('cache_status', 'Unknown')
            second_cache = second_request.get('cloudflare', {}).get('cache_status', 'Unknown')
            
            cache_working = second_cache in ['HIT', 'EXPIRED'] or \
                           (first_cache == 'MISS' and second_cache == 'HIT')
            
            results[endpoint] = {
                'first_request': first_cache,
                'second_request': second_cache,
                'cache_working': cache_working,
                'response_time_improvement': first_request.get('response_time', 0) - second_request.get('response_time', 0)
            }
        
        return results
    
    def rate_limit_test(self, endpoint: str = '/health', 
                       requests_count: int = 20, rate: float = 2.0) -> Dict:
        """Rate limiting 測試"""
        print(f"⚡ 測試 rate limiting ({requests_count} 請求, {rate} req/sec)...")
        
        results = []
        blocked_requests = 0
        
        for i in range(requests_count):
            print(f"  請求 {i+1}/{requests_count}", end='\r')
            result = self.test_endpoint(endpoint)
            results.append(result)
            
            # 檢查是否被 rate limit
            if result.get('status_code') == 429:
                blocked_requests += 1
            
            if i < requests_count - 1:
                time.sleep(1.0 / rate)
        
        print()  # 換行
        
        return {
            'total_requests': requests_count,
            'blocked_requests': blocked_requests,
            'rate_limiting_triggered': blocked_requests > 0,
            'results': results
        }
    
    def comprehensive_test(self) -> Dict:
        """完整測試套件"""
        print("🔍 執行完整的 Cloudflare 測試套件...\n")
        
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'domain': self.domain,
            'tests': {}
        }
        
        # 1. 基本連通性測試
        print("1️⃣ 基本連通性測試")
        connectivity_results = {}
        for endpoint in self.endpoints:
            result = self.test_endpoint(endpoint)
            connectivity_results[endpoint] = result
        test_results['tests']['connectivity'] = connectivity_results
        
        # 2. 效能測試
        print("\n2️⃣ 效能測試")
        performance_results = {}
        for endpoint in ['/health', '/test']:  # 只測試非 webhook 端點
            perf_result = self.performance_test(endpoint, iterations=5, delay=0.2)
            performance_results[endpoint] = perf_result
        test_results['tests']['performance'] = performance_results
        
        # 3. 安全性測試
        print("\n3️⃣ 安全性測試")
        security_result = self.security_test()
        test_results['tests']['security'] = security_result
        
        # 4. 快取測試
        print("\n4️⃣ 快取測試")
        cache_result = self.cache_test()
        test_results['tests']['cache'] = cache_result
        
        # 5. Rate limiting 測試 (輕量)
        print("\n5️⃣ Rate limiting 測試")
        rate_limit_result = self.rate_limit_test('/health', requests_count=10, rate=5.0)
        test_results['tests']['rate_limiting'] = rate_limit_result
        
        return test_results
    
    def generate_report(self, test_results: Dict) -> str:
        """生成測試報告"""
        report = []
        report.append("# Cloudflare 測試報告")
        report.append(f"**域名**: {test_results['domain']}")
        report.append(f"**測試時間**: {test_results['timestamp']}")
        report.append("")
        
        # 連通性測試結果
        report.append("## 📡 連通性測試")
        connectivity = test_results['tests']['connectivity']
        for endpoint, result in connectivity.items():
            status = result.get('status_code', 'Error')
            time_taken = result.get('response_time', 0)
            cache_status = result.get('cloudflare', {}).get('cache_status', 'Unknown')
            
            if 200 <= status < 300:
                report.append(f"✅ `{endpoint}`: {status} ({time_taken}s, Cache: {cache_status})")
            else:
                report.append(f"❌ `{endpoint}`: {status} ({time_taken}s)")
        report.append("")
        
        # 效能測試結果
        report.append("## ⚡ 效能測試")
        performance = test_results['tests']['performance']
        for endpoint, result in performance.items():
            success_rate = result['success_rate']
            avg_time = result['response_times']['avg']
            cache_hit_rate = result['cache_analysis']['cache_hit_rate']
            
            report.append(f"### {endpoint}")
            report.append(f"- 成功率: {success_rate}%")
            report.append(f"- 平均回應時間: {avg_time}s")
            report.append(f"- 快取命中率: {cache_hit_rate}%")
        report.append("")
        
        # 安全性測試結果
        report.append("## 🔒 安全性測試")
        security = test_results['tests']['security']
        report.append(f"**總體通過率**: {security['success_rate']}%")
        for test in security['tests']:
            status = "✅" if test['passed'] else "❌"
            report.append(f"{status} {test['name']}: {test['actual']}")
        report.append("")
        
        # 快取測試結果
        report.append("## 💾 快取測試")
        cache = test_results['tests']['cache']
        for endpoint, result in cache.items():
            status = "✅" if result['cache_working'] else "❌"
            improvement = result['response_time_improvement']
            report.append(f"{status} `{endpoint}`: {result['first_request']} → {result['second_request']} (提升: {improvement:.3f}s)")
        report.append("")
        
        # Rate limiting 測試結果
        report.append("## ⚡ Rate Limiting 測試")
        rate_limit = test_results['tests']['rate_limiting']
        if rate_limit['rate_limiting_triggered']:
            report.append(f"✅ Rate limiting 正常運作 ({rate_limit['blocked_requests']}/{rate_limit['total_requests']} 被阻擋)")
        else:
            report.append("⚠️ Rate limiting 未觸發 (可能需要更高的請求頻率)")
        
        return "\n".join(report)

def main():
    parser = argparse.ArgumentParser(description='Cloudflare 監控和測試工具')
    parser.add_argument('domain', help='要測試的域名 (例如: example.com)')
    parser.add_argument('--test', choices=['all', 'performance', 'security', 'cache'], 
                       default='all', help='測試類型')
    parser.add_argument('--output', help='輸出檔案路徑')
    parser.add_argument('--json', action='store_true', help='以 JSON 格式輸出')
    
    args = parser.parse_args()
    
    monitor = CloudflareMonitor(args.domain)
    
    if args.test == 'all':
        results = monitor.comprehensive_test()
    elif args.test == 'performance':
        results = {}
        for endpoint in ['/health', '/test']:
            results[endpoint] = monitor.performance_test(endpoint)
    elif args.test == 'security':
        results = monitor.security_test()
    elif args.test == 'cache':
        results = monitor.cache_test()
    
    if args.json:
        output = json.dumps(results, indent=2, ensure_ascii=False)
    else:
        if args.test == 'all':
            output = monitor.generate_report(results)
        else:
            output = json.dumps(results, indent=2, ensure_ascii=False)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"結果已儲存到 {args.output}")
    else:
        print(output)

if __name__ == "__main__":
    main()