// k6 Test: Workshop App Performance
// S4-3 NFR: Workshop app load < 1s P95, 100 concurrent users, 0 5xx errors
//
// Run: k6 run tests/k6/workshop-test.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, API_PREFIX, defaultOptions, login, authGet, authPost, authPut, authDelete } from './config.js';

const wsThresholds = {
  ...defaultOptions.thresholds,
  'http_req_duration{endpoint:workshop_list}': ['p(95)<1000'],
  'http_req_duration{endpoint:workshop_get}': ['p(95)<500'],
  'http_req_duration{endpoint:workshop_create}': ['p(95)<1000'],
  'http_req_failed': ['rate==0'],
};

export const options = {
  ...defaultOptions,
  thresholds: wsThresholds,
  scenarios: {
    workshop_load: {
      executor: 'ramping-vus',
      stages: [
        { duration: '20s', target: 25 },
        { duration: '40s', target: 100 },
        { duration: '30s', target: 100 },
        { duration: '20s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
};

const GRAPH = JSON.stringify({
  nodes: [
    { id: 't1', type: 'table', position: { x: 0, y: 0 }, data: { label: 'T1' } },
    { id: 'c1', type: 'chart', position: { x: 200, y: 0 }, data: { label: 'C1' } },
  ],
  edges: [{ id: 'e1', source: 't1', target: 'c1' }],
  viewport: { x: 0, y: 0, zoom: 1 },
});

export function setup() {
  const token = login(http);
  return { token };
}

export default function (data) {
  const token = data.token;

  // List — most common read path
  const list = authGet(http, token, '/workshop/apps?page=1&page_size=20', { tags: { endpoint: 'workshop_list' } });
  check(list, {
    'workshop_list not 5xx': (r) => r.status < 500,
    'workshop_list latency ok': (r) => r.timings.duration < 1000,
  });

  // Get first app id if any
  let appId = null;
  if (list.status === 200) {
    try {
      const body = list.json();
      if (body.items && body.items.length > 0) {
        appId = body.items[0].id;
      }
    } catch (_) {}
  }

  if (appId) {
    const detail = authGet(http, token, `/workshop/apps/${appId}`, { tags: { endpoint: 'workshop_get' } });
    check(detail, {
      'workshop_get not 5xx': (r) => r.status < 500,
      'workshop_get latency ok': (r) => r.timings.duration < 500,
    });
  } else {
    // Exercise the create path so we still measure it
    const create = authPost(
      http,
      token,
      '/workshop/apps',
      { name: `k6-ws-${__VU}-${__ITER}`, graph: JSON.parse(GRAPH) },
      { tags: { endpoint: 'workshop_create' } }
    );
    check(create, {
      'workshop_create not 5xx': (r) => r.status < 500,
      'workshop_create latency ok': (r) => r.timings.duration < 1000,
    });
  }

  sleep(0.3);
}
