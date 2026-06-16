// k6 Test: RAG Query Performance
// S4-3 NFR: RAG query P95 < 2s, 100 concurrent users, 0 5xx errors
//
// Run: k6 run tests/k6/rag-test.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, API_PREFIX, defaultOptions, login, authPost } from './config.js';

const ragThresholds = {
  ...defaultOptions.thresholds,
  'http_req_duration{endpoint:rag_query}': ['p(50)<800', 'p(95)<2000'],
  'http_req_failed': ['rate==0'],
};

const QUERIES = [
  'how to deploy the platform',
  'ontology definition',
  'show me recent action executions',
  'cost summary last 30 days',
  'list interfaces with low compliance',
];

export const options = {
  ...defaultOptions,
  thresholds: ragThresholds,
  scenarios: {
    rag_load: {
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

export function setup() {
  const token = login(http);
  return { token };
}

export default function (data) {
  const token = data.token;
  const query = QUERIES[__VU % QUERIES.length];

  const tags = { endpoint: 'rag_query' };
  const res = authPost(
    http,
    token,
    '/aip/rag/query',
    { query, top_k: 5 },
    { tags }
  );
  check(res, {
    'rag_query status not 5xx': (r) => r.status < 500,
    'rag_query latency ok': (r) => r.timings.duration < 2000,
  });

  sleep(0.3);
}
