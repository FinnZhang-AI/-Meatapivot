// k6 Smoke Test: Basic functionality check
// S6-1: Verifies endpoints work with minimal load
//
// Run: k6 run tests/k6/smoke-test.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, API_PREFIX, defaultOptions, login, authGet, authPost } from './config.js';

export const options = {
  ...defaultOptions,
  vus: 1,
  duration: '10s',
  thresholds: {
    'http_req_failed': ['rate==0'],  // Must have 0% errors in smoke
  },
};

export function setup() {
  const token = login(http);
  return { token };
}

export default function (data) {
  const token = data.token;

  // Health check
  const health = http.get(`${BASE_URL}/health`);
  check(health, {
    'health 200': (r) => r.status === 200,
  });

  // Authenticated read
  const ot = authGet(http, token, '/ontology/object-types?page=1&page_size=5');
  check(ot, {
    'object-types 200': (r) => r.status === 200,
  });

  // Validate endpoint
  const validate = authPost(http, token, '/ontology/compile/validate', {});
  check(validate, {
    'validate 200': (r) => r.status === 200,
  });

  sleep(1);
}
