/**
 * Cloudflare Worker for LINE Bot Security Enhancement
 * 為 LINE Bot 名片管理系統提供額外的安全層
 */

// 設定常數
const CONFIG = {
  // Rate limiting 設定
  RATE_LIMITS: {
    WEBHOOK: {
      windowMs: 60000,  // 1 分鐘
      maxRequests: 100   // 最多 100 次請求
    },
    API: {
      windowMs: 60000,  // 1 分鐘  
      maxRequests: 60    // 最多 60 次請求
    },
    GLOBAL: {
      windowMs: 3600000, // 1 小時
      maxRequests: 1000  // 最多 1000 次請求
    }
  },
  
  // 安全設定
  SECURITY: {
    MAX_BODY_SIZE: 1048576, // 1MB
    ALLOWED_METHODS: ['GET', 'POST'],
    SENSITIVE_ENDPOINTS: ['/callback', '/debug/webhook'],
    PUBLIC_ENDPOINTS: ['/health', '/test']
  },
  
  // 地理限制 (可選)
  GEO_RESTRICTIONS: {
    ENABLED: false, // 設為 true 啟用地理限制
    ALLOWED_COUNTRIES: ['TW', 'US', 'JP'], // 允許的國家代碼
    WEBHOOK_STRICT: true // webhook 端點是否啟用嚴格地理限制
  }
};

/**
 * 主要請求處理函數
 */
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

/**
 * 處理傳入請求
 */
async function handleRequest(request) {
  const url = new URL(request.url);
  const method = request.method;
  const pathname = url.pathname;
  const clientIP = request.headers.get('CF-Connecting-IP');
  const country = request.cf?.country || 'UNKNOWN';
  
  try {
    // 1. 基本安全檢查
    const securityCheck = await performSecurityChecks(request, pathname, method, country);
    if (securityCheck.blocked) {
      return securityCheck.response;
    }
    
    // 2. Rate limiting 檢查
    const rateLimitCheck = await checkRateLimit(clientIP, pathname);
    if (rateLimitCheck.blocked) {
      return rateLimitCheck.response;
    }
    
    // 3. 請求大小檢查
    if (method === 'POST') {
      const bodySize = parseInt(request.headers.get('content-length') || '0');
      if (bodySize > CONFIG.SECURITY.MAX_BODY_SIZE) {
        return createErrorResponse(413, 'Request too large', {
          maxSize: CONFIG.SECURITY.MAX_BODY_SIZE,
          requestSize: bodySize
        });
      }
    }
    
    // 4. LINE webhook 特殊處理
    if (pathname === '/callback' && method === 'POST') {
      const webhookCheck = await validateLineWebhook(request);
      if (webhookCheck.blocked) {
        return webhookCheck.response;
      }
    }
    
    // 5. 轉發請求到原始伺服器
    const response = await fetch(request);
    
    // 6. 添加安全標頭
    return addSecurityHeaders(response);
    
  } catch (error) {
    console.error('Worker error:', error);
    return createErrorResponse(500, 'Internal server error');
  }
}

/**
 * 執行基本安全檢查
 */
async function performSecurityChecks(request, pathname, method, country) {
  // 1. HTTP 方法檢查
  if (!CONFIG.SECURITY.ALLOWED_METHODS.includes(method)) {
    return {
      blocked: true,
      response: createErrorResponse(405, 'Method not allowed')
    };
  }
  
  // 2. 地理限制檢查
  if (CONFIG.GEO_RESTRICTIONS.ENABLED) {
    // 對 webhook 端點進行嚴格檢查
    if (CONFIG.GEO_RESTRICTIONS.WEBHOOK_STRICT && pathname === '/callback') {
      if (!CONFIG.GEO_RESTRICTIONS.ALLOWED_COUNTRIES.includes(country)) {
        return {
          blocked: true,
          response: createErrorResponse(403, 'Geographic restriction', {
            country: country,
            allowedCountries: CONFIG.GEO_RESTRICTIONS.ALLOWED_COUNTRIES
          })
        };
      }
    }
  }
  
  // 3. User-Agent 檢查 (檢測明顯的惡意 bot)
  const userAgent = request.headers.get('user-agent') || '';
  const suspiciousAgents = [
    'curl', 'wget', 'python-requests', 'bot', 'crawler', 'scanner'
  ];
  
  // 對非公開端點進行 User-Agent 檢查
  if (!CONFIG.SECURITY.PUBLIC_ENDPOINTS.includes(pathname)) {
    const isSuspicious = suspiciousAgents.some(agent => 
      userAgent.toLowerCase().includes(agent)
    );
    
    if (isSuspicious) {
      // 不直接阻擋，而是要求 CAPTCHA 驗證
      return {
        blocked: true,
        response: createErrorResponse(429, 'Automated request detected', {
          hint: 'Please access through a web browser'
        })
      };
    }
  }
  
  return { blocked: false };
}

/**
 * Rate limiting 檢查
 */
async function checkRateLimit(clientIP, pathname) {
  const now = Date.now();
  
  // 選擇適當的限制設定
  let limit;
  if (pathname === '/callback') {
    limit = CONFIG.RATE_LIMITS.WEBHOOK;
  } else if (pathname.startsWith('/debug/') || pathname === '/test') {
    limit = CONFIG.RATE_LIMITS.API;
  } else {
    limit = CONFIG.RATE_LIMITS.GLOBAL;
  }
  
  // 生成 rate limit key
  const key = `rate_limit:${clientIP}:${pathname}`;
  
  // 檢查當前計數 (使用 Cloudflare KV 或簡單的內存存儲)
  // 注意：這裡使用簡化的檢查，實際環境中應該使用 KV 存儲
  const stored = await RATE_LIMIT_KV?.get(key);
  const data = stored ? JSON.parse(stored) : { count: 0, resetTime: now + limit.windowMs };
  
  // 重置計數器如果時間窗口已過
  if (now > data.resetTime) {
    data.count = 0;
    data.resetTime = now + limit.windowMs;
  }
  
  // 檢查是否超過限制
  if (data.count >= limit.maxRequests) {
    return {
      blocked: true,
      response: createErrorResponse(429, 'Rate limit exceeded', {
        limit: limit.maxRequests,
        windowMs: limit.windowMs,
        resetTime: data.resetTime
      })
    };
  }
  
  // 增加計數
  data.count++;
  await RATE_LIMIT_KV?.put(key, JSON.stringify(data), { expirationTtl: Math.ceil(limit.windowMs / 1000) });
  
  return { blocked: false };
}

/**
 * 驗證 LINE webhook 請求
 */
async function validateLineWebhook(request) {
  const signature = request.headers.get('x-line-signature');
  
  // 基本簽章檢查
  if (!signature) {
    return {
      blocked: true,
      response: createErrorResponse(400, 'Missing LINE signature')
    };
  }
  
  // 檢查簽章格式
  if (!signature.startsWith('sha256=') || signature.length < 64) {
    return {
      blocked: true,
      response: createErrorResponse(400, 'Invalid LINE signature format')
    };
  }
  
  // 檢查 Content-Type
  const contentType = request.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    return {
      blocked: true,
      response: createErrorResponse(400, 'Invalid content type for webhook')
    };
  }
  
  return { blocked: false };
}

/**
 * 添加安全標頭
 */
function addSecurityHeaders(response) {
  const newResponse = new Response(response.body, response);
  
  // 添加安全標頭
  newResponse.headers.set('X-Content-Type-Options', 'nosniff');
  newResponse.headers.set('X-Frame-Options', 'DENY');
  newResponse.headers.set('X-XSS-Protection', '1; mode=block');
  newResponse.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  newResponse.headers.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  
  // API 特定標頭
  if (response.headers.get('content-type')?.includes('application/json')) {
    newResponse.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate');
    newResponse.headers.set('Pragma', 'no-cache');
  }
  
  // 添加自定義標頭標識 Cloudflare Worker
  newResponse.headers.set('X-Protected-By', 'Cloudflare-Worker');
  
  return newResponse;
}

/**
 * 創建錯誤回應
 */
function createErrorResponse(status, message, details = {}) {
  const errorResponse = {
    error: true,
    status: status,
    message: message,
    timestamp: new Date().toISOString(),
    details: details
  };
  
  return new Response(JSON.stringify(errorResponse), {
    status: status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
      'X-Error-Source': 'Cloudflare-Worker'
    }
  });
}

/**
 * 健康檢查處理 (快取友好)
 */
async function handleHealthCheck() {
  const response = {
    status: 'healthy',
    service: 'LINE Bot 名片識別系統',
    worker: 'active',
    timestamp: new Date().toISOString(),
    protection: {
      rateLimiting: true,
      geoRestriction: CONFIG.GEO_RESTRICTIONS.ENABLED,
      securityHeaders: true
    }
  };
  
  return new Response(JSON.stringify(response), {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300', // 5 分鐘快取
      'X-Worker-Health': 'OK'
    }
  });
}