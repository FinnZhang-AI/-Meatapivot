// k6 Load Test: Write-Heavy Endpoints
// S6-1: Validates write performance at 100 concurrent users
//
// Run: k6 run tests/k6/load-test-write.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, API_PREFIX, defaultOptions, login, authPost, authGet } from './config.js';

export const options = {
  ...defaultOptions,
  stages: [
    { duration: '10s', target: 50 },
    { duration: '10s', target: 100 },
    { duration: '30s', target: 100 },
    { duration: '10s', target: 0 },
  ],
};

export function setup() {
  const token = login(http);
  return { token };
}

export default function (data) {
  const token = data.token;
  const ts = Date.now();

  // 1. Create object type
  const createPayload = {
    name: `perf_test_ot_${__VU}_${ts}`,
    display_name: `Perf Test OT ${__VU}-${ts}`,
    description: 'k6 performance test object type',
    properties: [
      { name: 'title', type: 'string', required: true },
      { name: 'count', type: 'integer', required: false },
    ],
    neo4j_label: `PerfTestOT${__VU}`,
  };

  const res1 = authPost(http, token, '/ontology/object-types', createPayload);
  check(res1, {
    'create-object-type status 201': (r) => r.status === 201,
    'create-object-type has id': (r) => r.body && r.body.includes('"id"'),
  }) || console.error(`create-ot failed: ${res1.status} ${res1.body}`);

  sleep(0.5);

  // 2. Create interface
  const interfacePayload = {
    name: `perf_test_iface_${__VU}_${ts}`,
    display_name: `Perf Test Interface ${__VU}-${ts}`,
    description: 'k6 performance test interface',
    properties: [
      { name: 'name', type: 'string', required: true },
    ],
  };

  const res2 = authPost(http, token, '/ontology/interfaces', interfacePayload);
  check(res2, {
    'create-interface status 201': (r) => r.status === 201,
  });

  sleep(0.5);

  // 3. Create function
  const functionPayload = {
    name: `perf_test_fn_${__VU}_${ts}`,
    display_name: `Perf Test Function ${__VU}-${ts}`,
    description: 'k6 performance test function',
    language: 'python',
    code: 'def main():\n    return {"status": "ok"}',
    timeout_seconds: 5,
    memory_mb: 128,
  };

  const res3 = authPost(http, token, '/ontology/functions', functionPayload);
  check(res3, {
    'create-function status 201': (r) => r.status === 201,
  });

  sleep(0.5);
}
