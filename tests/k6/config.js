// k6 Performance Test Configuration
// S6-1: P50 < 100ms, P95 < 500ms, 100 concurrent users, 0 5xx errors

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
export const API_PREFIX = '/api/v1';
export const TEST_USER = __ENV.TEST_USER || 'perftest@example.com';
export const TEST_PASSWORD = __ENV.TEST_PASSWORD || 'perftest123';

// Performance thresholds
export const thresholds = {
  'http_req_duration': ['p(50)<100', 'p(95)<500', 'p(99)<1000'],
  'http_req_failed': ['rate<0.001'],  // < 0.1% errors (no 5xx)
  'http_reqs': ['rate>100'],          // > 100 req/s
  'iteration_duration': ['p(95)<2000'],
};

// Default VU and duration
export const defaultOptions = {
  thresholds,
  noConnectionReuse: false,
  userAgent: 'k6-perf-test/1.0',
};

// Auth helper
export function login(http) {
  const url = `${BASE_URL}${API_PREFIX}/auth/login`;
  const payload = JSON.stringify({
    email: TEST_USER,
    password: TEST_PASSWORD,
  });
  const params = {
    headers: { 'Content-Type': 'application/json' },
  };
  const res = http.post(url, payload, params);
  if (res.status !== 200) {
    throw new Error(`Login failed: ${res.status} ${res.body}`);
  }
  return res.json('access_token');
}

// Authenticated GET request. Optional `options` lets callers attach k6 tags
// (e.g. for per-endpoint thresholds).
export function authGet(http, token, path, options = {}) {
  return http.get(`${BASE_URL}${API_PREFIX}${path}`, {
    headers: { 'Authorization': `Bearer ${token}` },
    ...options,
  });
}

// Authenticated POST request. Pass `options` for k6 tags / extra headers.
export function authPost(http, token, path, body, options = {}) {
  return http.post(`${BASE_URL}${API_PREFIX}${path}`, JSON.stringify(body), {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    ...options,
  });
}

// Authenticated PUT request. Pass `options` for k6 tags / extra headers.
export function authPut(http, token, path, body, options = {}) {
  return http.put(`${BASE_URL}${API_PREFIX}${path}`, JSON.stringify(body), {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    ...options,
  });
}

// Authenticated DELETE request. Pass `options` for k6 tags / extra headers.
export function authDelete(http, token, path, options = {}) {
  return http.del(`${BASE_URL}${API_PREFIX}${path}`, null, {
    headers: { 'Authorization': `Bearer ${token}` },
    ...options,
  });
}
