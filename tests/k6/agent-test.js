// k6 Test: Agent API Performance
// S4-3 NFR: Agent API P95 < 2s, 100 concurrent users, 0 5xx errors
//
// Run: k6 run tests/k6/agent-test.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, API_PREFIX, defaultOptions, login, authGet, authPost } from './config.js';

// Agent API has higher latency budget than ontology endpoints
const agentThresholds = {
  ...defaultOptions.thresholds,
  'http_req_duration{endpoint:agent_run}': ['p(50)<500', 'p(95)<2000'],
  'http_req_duration{endpoint:agent_status}': ['p(95)<300'],
  'http_req_failed': ['rate==0'], // 0 5xx for agent flows
};

export const options = {
  ...defaultOptions,
  thresholds: agentThresholds,
  scenarios: {
    agent_load: {
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
  // Pick any agent id present in the registry
  const list = authGet(http, token, '/aip/agents');
  let agentId = null;
  if (list.status === 200) {
    try {
      const body = list.json();
      const items = body.agents || body.items || body;
      if (Array.isArray(items) && items.length > 0) {
        agentId = items[0].id;
      }
    } catch (_) {
      // ignore parse error
    }
  }
  if (!agentId) {
    // Fall back to a known dev agent id; the request will 404 in environments
    // without the agent, but k6 still measures the path the API exposes.
    agentId = '00000000-0000-0000-0000-000000000001';
  }
  return { token, agentId };
}

export default function (data) {
  const token = data.token;
  const agentId = data.agentId;

  const tags = { endpoint: 'agent_run' };
  const run = authPost(
    http,
    token,
    `/aip/agents/${agentId}/run`,
    { input: 'ping', sessionId: `k6-agent-${__VU}` },
    { tags }
  );
  check(run, {
    'agent_run status not 5xx': (r) => r.status < 500,
    'agent_run latency ok': (r) => r.timings.duration < 2000,
  });

  if (run.status === 200) {
    try {
      const body = run.json();
      const statusTags = { endpoint: 'agent_status' };
      const status = authGet(
        http,
        token,
        `/aip/agents/${agentId}/status`,
        { tags: statusTags }
      );
      check(status, {
        'agent_status not 5xx': (r) => r.status < 500,
        'agent_status latency ok': (r) => r.timings.duration < 300,
      });
    } catch (_) {
      // body parse failure is non-fatal for the test
    }
  }

  sleep(0.5);
}
