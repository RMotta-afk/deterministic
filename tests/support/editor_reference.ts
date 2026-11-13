// @ts-nocheck
// Contract oracle candidate. The benchmark builder never reads this file.
const http = require('node:http')

const fields = ['name', 'sector', 'country', 'stage', 'key_dates']
const sectors = new Set(['energy', 'mining', 'water', 'transport', 'oil_and_gas', 'ict'])
const stages = new Set(['idea', 'feasibility', 'tender', 'financing', 'construction', 'operation', 'cancelled'])
const upstreamUrl = process.env.UPSTREAM_URL || 'http://127.0.0.1:8081'
const apiKey = process.env.UPSTREAM_API_KEY || 'local-dev-key'

function send(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify(body))
}

function detail(record) {
  return Object.fromEntries(['id', ...fields].map((key) => [key, record[key]]))
}

function summary(record) {
  return Object.fromEntries(['id', 'name', 'sector', 'country', 'stage'].map((key) => [key, record[key]]))
}

function validDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const date = new Date(value + 'T00:00:00Z')
  return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value
}

function validFields(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  if (Object.keys(value).sort().join(',') !== fields.slice().sort().join(',')) return false
  if (typeof value.name !== 'string' || !value.name.trim()) return false
  if (typeof value.country !== 'string' || !value.country.trim()) return false
  if (!sectors.has(value.sector) || !stages.has(value.stage)) return false
  if (!Array.isArray(value.key_dates)) return false
  return value.key_dates.every((item) => item && typeof item === 'object' &&
    Object.keys(item).sort().join(',') === 'date,label' &&
    typeof item.label === 'string' && !!item.label.trim() && validDate(item.date))
}

async function upstream(method, path, body) {
  try {
    const response = await fetch(upstreamUrl + path, {
      method,
      headers: { 'X-Api-Key': apiKey, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(5000),
    })
    let payload = null
    try { payload = await response.json() } catch { return { status: response.status, invalid: true } }
    return { status: response.status, payload }
  } catch {
    return { status: 0, invalid: true }
  }
}

function choose(base, proposed, current) {
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b)
  if (same(proposed, base)) return [current, false]
  if (!same(current, base) && !same(current, proposed)) return [current, true]
  return [proposed, false]
}

async function observed(id) {
  const reread = await upstream('GET', '/projects/' + encodeURIComponent(id))
  return reread.status === 200 && !reread.invalid ? detail(reread.payload) : null
}

async function handle(req, res) {
  const url = new URL(req.url, 'http://localhost')
  const match = /^\/api\/projects\/([^/]+)$/.exec(url.pathname)
  if (req.method === 'GET' && url.pathname === '/api/projects') {
    const result = await upstream('GET', '/projects')
    if (result.status !== 200 || !Array.isArray(result.payload)) {
      send(res, 502, { code: 'upstream_unavailable' })
      return
    }
    send(res, 200, { projects: result.payload.map(summary) })
    return
  }
  if (!match) { send(res, 404, { code: 'project_not_found' }); return }
  const id = decodeURIComponent(match[1])
  if (req.method === 'GET') {
    const result = await upstream('GET', '/projects/' + encodeURIComponent(id))
    if (result.status === 404) send(res, 404, { code: 'project_not_found' })
    else if (result.status !== 200 || result.invalid) send(res, 502, { code: 'upstream_unavailable' })
    else send(res, 200, { project: detail(result.payload) })
    return
  }
  if (req.method !== 'PUT') { send(res, 405, { code: 'method_not_allowed' }); return }
  let update
  try {
    let raw = ''
    for await (const chunk of req) raw += chunk
    update = JSON.parse(raw)
  } catch { send(res, 422, { detail: 'invalid JSON' }); return }
  if (!update || Object.keys(update).sort().join(',') !== 'base,proposed' ||
      !validFields(update.base) || !validFields(update.proposed)) {
    send(res, 422, { detail: 'invalid update' })
    return
  }
  const currentResult = await upstream('GET', '/projects/' + encodeURIComponent(id))
  if (currentResult.status === 404) { send(res, 404, { code: 'project_not_found' }); return }
  if (currentResult.status !== 200 || currentResult.invalid) {
    send(res, 502, { code: 'upstream_unavailable' }); return
  }
  const current = currentResult.payload
  const merged = {}
  const conflicts = []
  for (const field of fields) {
    const [selected, conflict] = choose(update.base[field], update.proposed[field], current[field])
    merged[field] = selected
    if (conflict) conflicts.push(field)
  }
  if (conflicts.length) {
    send(res, 409, { code: 'edit_conflict', current: detail(current), conflicting_fields: conflicts })
    return
  }
  if (fields.every((field) => JSON.stringify(merged[field]) === JSON.stringify(current[field]))) {
    send(res, 200, { project: detail(current) })
    return
  }
  const saved = await upstream('PUT', '/projects/' + encodeURIComponent(id), {
    ...merged, linked_companies: current.linked_companies,
  })
  if (saved.status === 404) { send(res, 404, { code: 'project_not_found' }); return }
  if (saved.status !== 200 || saved.invalid) {
    send(res, 504, { code: 'write_uncertain', observed: await observed(id) })
    return
  }
  send(res, 200, { project: detail(saved.payload) })
}

http.createServer((req, res) => {
  handle(req, res).catch(() => send(res, 502, { code: 'upstream_unavailable' }))
}).listen(Number(process.env.PORT || 8080), '0.0.0.0')
