// k6 Stress Test: Find the breaking point
// S6-1: Push beyond 100 concurrent to find limits
//
// Run: k6 run tests/k6/stress-test.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, API_PREFIX, defaultOptions, login, authGet } from './config.js';

export const options = {
  ...defaultOptions,
  stages: [
    { duration: '20s', target: 100 },
    { duration: '20s', target: 200 },
    { duration: '20s', target: 300 },
    { duration: '20s', target: 400 },
    { duration: '20s', target: 0 },  // recovery
  ],
  // Allow higher latency under stress
  thresholds: {
    ...defaultOptions.thresholds,
    'http_req_duration': ['p(50)<200', 'p(95)<1000', 'p(99)<2000'],
    'http_req_failed': ['rate<0.01'],
  },
};

export function setup() {
  const token = login(http);
  return { token };
}

export default function (data) {
  const token = data.token;

  // Hot path: object types listing
  const res = authGet(http, token, '/ontology/object-types?page=1&page_size=50');
  check(res, {
    'status 200': (r) => r.status === 200,
    'no 5xx': (r) => r.status < 500,
  });

  // Stats
  const stats = authGet(http, token, '/ontology/stats');
  check(stats, {
    'stats 200': (r) => r.status === 200,
  });

  sleep(0.2);
}
