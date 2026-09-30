// k6 load test for the read path, through the gateway.
//
//   docker run --rm --network radar_default -v "${PWD}/scripts/load:/scripts" \
//     -e BASE=http://web grafana/k6 run /scripts/read.js
//
// It exercises what a reader does most: browse articles, search them, open
// the digest list, one digest and the personal feed. Writes and digest
// builds are left out on purpose: their cost is the language model, not this
// service. Every virtual user signs in to the demo account once.

import http from 'k6/http'
import { check } from 'k6'
import { Trend } from 'k6/metrics'

const BASE = __ENV.BASE || 'http://web'
const VUS = Number(__ENV.VUS || 50)
const DURATION = __ENV.DURATION || '30s'

export const options = {
  scenarios: {
    readers: { executor: 'constant-vus', vus: VUS, duration: DURATION },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
  },
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
}

const byEndpoint = {
  articles: new Trend('t_articles', true),
  search: new Trend('t_search', true),
  digests: new Trend('t_digests', true),
  digest: new Trend('t_digest', true),
  feed: new Trend('t_feed', true),
}

const QUERIES = ['уязвимость', 'SCADA', 'ФСТЭК', 'ransomware', 'импортозамещение', 'Kubernetes']

export function setup() {
  // The cookie jar of setup() is not shared with the virtual users, so the
  // session is passed on explicitly.
  const login = http.post(`${BASE}/api/v1/auth/demo`)
  const session = login.cookies.radar_session[0].value
  const list = http
    .get(`${BASE}/api/v1/digests?limit=5`, { cookies: { radar_session: session } })
    .json()
  const done = list.find((digest) => digest.status === 'done')
  return { digestId: done ? done.id : null, session }
}

function hit(name, url, session) {
  const response = http.get(url, {
    tags: { endpoint: name },
    cookies: { radar_session: session },
  })
  byEndpoint[name].add(response.timings.duration)
  check(response, { 'status is 200': (r) => r.status === 200 })
}

export default function (data) {
  const offset = Math.floor(Math.random() * 10) * 30
  hit('articles', `${BASE}/api/v1/articles?limit=30&offset=${offset}`, data.session)
  const query = QUERIES[Math.floor(Math.random() * QUERIES.length)]
  hit('search', `${BASE}/api/v1/articles?limit=30&q=${encodeURIComponent(query)}`, data.session)
  hit('digests', `${BASE}/api/v1/digests?limit=30`, data.session)
  if (data.digestId) hit('digest', `${BASE}/api/v1/digests/${data.digestId}`, data.session)
  hit('feed', `${BASE}/api/v1/feed?limit=20`, data.session)
}
