// @ts-nocheck
const http = require('node:http');

const PORT = Number(process.env.PORT || 8080);
const UPSTREAM_URL = process.env.UPSTREAM_URL || 'http://127.0.0.1:8081';
const UPSTREAM_API_KEY = process.env.UPSTREAM_API_KEY || '';

function json(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(payload),
  });
  res.end(payload);
}

function isObj(v) {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function validDate(s) {
  if (typeof s !== 'string') return false;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return false;
  const d = new Date(s + 'T00:00:00.000Z');
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

function validateKeyDate(v) {
  return isObj(v) &&
    Object.keys(v).length === 2 &&
    typeof v.label === 'string' &&
    v.label.trim().length > 0 &&
    validDate(v.date);
}

function validateEditableFields(v) {
  if (!isObj(v)) return false;
  const keys = Object.keys(v);
  if (keys.length !== 5) return false;
  const allowed = new Set(['name', 'sector', 'country', 'stage', 'key_dates']);
  for (const k of keys) if (!allowed.has(k)) return false;
  if (typeof v.name !== 'string' || !v.name.trim()) return false;
  if (!['energy', 'mining', 'water', 'transport', 'oil_and_gas', 'ict'].includes(v.sector)) return false;
  if (typeof v.country !== 'string' || !v.country.trim()) return false;
  if (!['idea', 'feasibility', 'tender', 'financing', 'construction', 'operation', 'cancelled'].includes(v.stage)) return false;
  if (!Array.isArray(v.key_dates)) return false;
  for (const d of v.key_dates) if (!validateKeyDate(d)) return false;
  return true;
}

function validateSaveRequest(v) {
  return isObj(v) && Object.keys(v).length === 2 && validateEditableFields(v.base) && validateEditableFields(v.proposed);
}

function detail(p) {
  return { id: p.id, name: p.name, sector: p.sector, country: p.country, stage: p.stage, key_dates: p.key_dates };
}

function summary(p) {
  return { id: p.id, name: p.name, sector: p.sector, country: p.country, stage: p.stage };
}

function mergeEdit(base, proposed, current) {
  const choose = (b, p, c) => {
    if (JSON.stringify(p) === JSON.stringify(b)) return [c, false];
    if (JSON.stringify(c) !== JSON.stringify(b) && JSON.stringify(c) !== JSON.stringify(p)) return [c, true];
    return [p, false];
  };
  const conflicts = [];
  const [name, c1] = choose(base.name, proposed.name, current.name);
  const [sector, c2] = choose(base.sector, proposed.sector, current.sector);
  const [country, c3] = choose(base.country, proposed.country, current.country);
  const [stage, c4] = choose(base.stage, proposed.stage, current.stage);
  const [key_dates, c5] = choose(base.key_dates, proposed.key_dates, current.key_dates);
  if (c1) conflicts.push('name');
  if (c2) conflicts.push('sector');
  if (c3) conflicts.push('country');
  if (c4) conflicts.push('stage');
  if (c5) conflicts.push('key_dates');
  const merged = { name, sector, country, stage, key_dates };
  const changed = JSON.stringify(merged) !== JSON.stringify({
    name: current.name,
    sector: current.sector,
    country: current.country,
    stage: current.stage,
    key_dates: current.key_dates,
  });
  return { merged, conflicts, changed };
}

async function upstream(path, options = {}) {
  const url = new URL(path, UPSTREAM_URL);
  const headers = { ...(options.headers || {}), 'X-Api-Key': UPSTREAM_API_KEY };
  const controller = AbortSignal.timeout(5000);
  return fetch(url, { ...options, headers, signal: controller });
}

async function readProject(id) {
  let res;
  try {
    res = await upstream(`/projects/${encodeURIComponent(id)}`);
  } catch {
    return { kind: 'unavailable' };
  }
  if (res.status === 404) return { kind: 'missing' };
  if (!res.ok) return { kind: 'unavailable' };
  try {
    return { kind: 'ok', project: await res.json() };
  } catch {
    return { kind: 'unavailable' };
  }
}

async function listProjects() {
  let res;
  try {
    res = await upstream('/projects');
  } catch {
    return null;
  }
  if (!res.ok) return null;
  try {
    return await res.json();
  } catch {
    return null;
  }
}

async function putProject(id, body) {
  let res;
  try {
    res = await upstream(`/projects/${encodeURIComponent(id)}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw { uncertain: true };
  }
  if (res.status === 404) return { kind: 'missing' };
  if (!res.ok) throw { uncertain: true };
  try {
    return { kind: 'ok', project: await res.json() };
  } catch {
    throw { uncertain: true };
  }
}

function sendUncertain(res, observed) {
  json(res, 504, { code: 'write_uncertain', observed: observed ?? null });
}

function sendUnavailable(res) {
  json(res, 502, { code: 'upstream_unavailable' });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || '/', 'http://127.0.0.1');
  const method = (req.method || 'GET').toUpperCase();

  if (method === 'GET' && url.pathname === '/api/projects') {
    const projects = await listProjects();
    if (projects === null) return sendUnavailable(res);
    return json(res, 200, { projects: projects.map(summary) });
  }

  const m = url.pathname.match(/^\/api\/projects\/([^/]+)$/);
  if (m && method === 'GET') {
    const r = await readProject(m[1]);
    if (r.kind === 'missing') return json(res, 404, { code: 'project_not_found' });
    if (r.kind === 'unavailable') return sendUnavailable(res);
    return json(res, 200, { project: detail(r.project) });
  }

  if (m && method === 'PUT') {
    let raw = '';
    for await (const chunk of req) raw += chunk;
    let body;
    try {
      body = raw ? JSON.parse(raw) : null;
    } catch {
      return json(res, 422, { detail: 'Validation error' });
    }
    if (!validateSaveRequest(body)) return json(res, 422, { detail: 'Validation error' });

    const r = await readProject(m[1]);
    if (r.kind === 'missing') return json(res, 404, { code: 'project_not_found' });
    if (r.kind === 'unavailable') return sendUnavailable(res);

    const current = r.project;
    const merge = mergeEdit(body.base, body.proposed, current);
    if (merge.conflicts.length) {
      return json(res, 409, {
        code: 'edit_conflict',
        current: detail(current),
        conflicting_fields: merge.conflicts,
      });
    }
    if (!merge.changed) {
      return json(res, 200, { project: detail(current) });
    }

    const upstreamBody = {
      name: merge.merged.name,
      sector: merge.merged.sector,
      country: merge.merged.country,
      stage: merge.merged.stage,
      key_dates: merge.merged.key_dates,
      linked_companies: current.linked_companies,
    };

    try {
      const saved = await putProject(m[1], upstreamBody);
      if (saved.kind === 'missing') return json(res, 404, { code: 'project_not_found' });
      return json(res, 200, { project: detail(saved.project) });
    } catch {
      let observed = null;
      try {
        const reread = await readProject(m[1]);
        if (reread.kind === 'ok') observed = detail(reread.project);
      } catch {}
      return sendUncertain(res, observed);
    }
  }

  json(res, 404, { code: 'not_found' });
});

server.listen(PORT, '0.0.0.0');
