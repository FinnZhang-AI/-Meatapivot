// k6 Load Test: Read-Heavy Endpoints
// S6-1: Validates P50 < 100ms, P95 < 500ms at 100 concurrent users
//
// Run: k6 run --vus 100 --duration 30s tests/k6/load-test-read.js
//   or: k6 run tests/k6/load-test-read.js (uses defaults)

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, API_PREFIX, defaultOptions, login, authGet } from './config.js';

export const options = {
  ...defaultOptions,
  stages: [
    { duration: '10s', target: 50 },   // ramp up to 50 users
    { duration: '10s', target: 100 },  // ramp up to 100 users
    { duration: '30s', target: 100 },  // hold at 100 users
    { duration: '10s', target: 0 },    // ramp down
  ],
};

export function setup() {
  const token = login(http);
  return { token };
}

export default function (data) {
  const token = data.token;

  // 1. List object types (most common)
  const res1 = authGet(http, token, '/ontology/object-types?page=1&page_size=20');
  check(res1, {
    'object-types status 200': (r) => r.status === 200,
    'object-types p95 < 500ms': (r) => r.timings.duration < 500,
  }) || console.error(`object-types failed: ${res1.status}`);

  sleep(0.1);

  // 2. Get dashboard stats
  const res2 = authGet(http, token, '/ontology/stats');
  check(res2, {
    'stats status 200': (r) => r.status === 200,
    'stats has counts': (r) => r.body && r.body.includes('object_type_count'),
  });

  sleep(0.1);

  // 3. List link types
  const res3 = authGet(http, token, '/ontology/link-types?page=1&page_size=20');
  check(res3, {
    'link-types status 200': (r) => r.status === 200,
  });

  sleep(0.1);

  // 4. List interfaces
  const res4 = authGet(http, token, '/ontology/interfaces?page=1&page_size=20');
  check(res4, {
    'interfaces status 200': (r) => r.status === 200,
  });

  sleep(0.1);

  // 5. List action types
  const res5 = authGet(http, token, '/ontology/action-types?page=1&page_size=20');
  check(res5, {
    'action-types status 200': (r) => r.status === 200,
  });

  sleep(0.1);

  // 6. List functions
  const res6 = authGet(http, token, '/ontology/functions?page=1&page_size=20');
  check(res6, {
    'functions status 200': (r) => r.status === 200,
  });

  sleep(0.1);

  // 7. Get compile logs
  const res7 = authGet(http, token, '/ontology/compile/logs?limit=10');
  check(res7, {
    'compile-logs status 200': (r) => r.status === 200,
  });

  sleep(0.5);
}
