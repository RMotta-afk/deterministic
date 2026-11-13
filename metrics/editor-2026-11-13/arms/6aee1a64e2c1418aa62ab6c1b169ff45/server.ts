// @ts-nocheck
const http = require('node:http');

const PORT = Number(process.env.PORT || 8080);
const UPSTREAM_URL = process.env.UPSTREAM_URL || 'http://127.0.0.1:8081';
const UPSTREAM_API_KEY = process.env.UPSTREAM_API_KEY || 'local-dev-key';

function jsonResponse(res, status, body) {
  const data = Buffer.from(JSON.stringify(body));
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': String(data.length),
  });
  res.end(data);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      data += chunk;
      if (data.length > 1024 * 1024) reject(new Error('body too large'));
    });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

function normalizeBase(url) {
  return String(url).replace(/\/+$/, '');
}

function upstreamUrl(path) {
  return new URL(path, normalizeBase(UPSTREAM_URL) + '/');
}

async function upstreamFetch(path, options) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const headers = Object.assign({}, options && options.headers ? options.headers : {});
    headers['X-Api-Key'] = UPSTREAM_API_KEY;
    const res = await fetch(upstreamUrl(path), Object.assign({}, options, { headers, signal: controller.signal }));
    return res;
  } finally {
    clearTimeout(timeout);
  }
}

async function readJsonResponse(res) {
  const text = await res.text();
  if (!text) return null;
  return JSON.parse(text);
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

const SECTORS = new Set(['energy', 'mining', 'water', 'transport', 'oil_and_gas', 'ict']);
const STAGES = new Set(['idea', 'feasibility', 'tender', 'financing', 'construction', 'operation', 'cancelled']);

function validateKeyDate(v) {
  return isObject(v) &&
    Object.keys(v).length === 2 &&
    typeof v.label === 'string' &&
    v.label.trim() &&
    typeof v.date === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(v.date) &&
    !Number.isNaN(Date.parse(v.date + 'T00:00:00Z')) &&
    new Date(Date.parse(v.date + 'T00:00:00Z')).toISOString().slice(0, 10) === v.date;
}

function validateEditableFields(obj) {
  if (!isObject(obj)) return false;
  const keys = Object.keys(obj).sort();
  const required = ['country', 'key_dates', 'name', 'sector', 'stage'];
  if (keys.length !== 5 || required.some((k, i) => keys[i] !== k)) return false;
  if (typeof obj.name !== 'string' || !obj.name.trim()) return false;
  if (typeof obj.country !== 'string' || !obj.country.trim()) return false;
  if (!SECTORS.has(obj.sector)) return false;
  if (!STAGES.has(obj.stage)) return false;
  if (!Array.isArray(obj.key_dates) || !obj.key_dates.every(validateKeyDate)) return false;
  return true;
}

function validateSaveRequest(obj) {
  return isObject(obj) && validateEditableFields(obj.base) && validateEditableFields(obj.proposed) && Object.keys(obj).length === 2;
}

function projectSummary(p) {
  return { id: p.id, name: p.name, sector: p.sector, country: p.country, stage: p.stage };
}

function projectDetail(p) {
  return { id: p.id, name: p.name, sector: p.sector, country: p.country, stage: p.stage, key_dates: p.key_dates };
}

function conflictResponse(current, fields) {
  return { code: 'edit_conflict', current: projectDetail(current), conflicting_fields: fields };
}

function uncertainResponse(observed) {
  return { code: 'write_uncertain', observed: observed ? projectDetail(observed) : null };
}

function choose(base, proposed, current) {
  if (JSON.stringify(proposed) === JSON.stringify(base)) return [current, false];
  if (JSON.stringify(current) !== JSON.stringify(base) && JSON.stringify(current) !== JSON.stringify(proposed)) return [current, true];
  return [proposed, false];
}

function mergeEdit(base, proposed, current) {
  const out = {};
  const conflicts = [];
  for (const field of ['name', 'sector', 'country', 'stage', 'key_dates']) {
    const [v, conflict] = choose(base[field], proposed[field], current[field]);
    out[field] = v;
    if (conflict) conflicts.push(field);
  }
  return { merged: out, conflicts, changed: JSON.stringify(out) !== JSON.stringify({
    name: current.name,
    sector: current.sector,
    country: current.country,
    stage: current.stage,
    key_dates: current.key_dates,
  }) };
}

async function listProjects(res) {
  try {
    const upstream = await upstreamFetch('/projects', { method: 'GET' });
    if (!upstream.ok) return jsonResponse(res, upstream.status === 404 ? 404 : 502, upstream.status === 404 ? { code: 'project_not_found' } : { code: 'upstream_unavailable' });
    const data = await readJsonResponse(upstream);
    if (!Array.isArray(data)) return jsonResponse(res, 502, { code: 'upstream_unavailable' });
    jsonResponse(res, 200, { projects: data.map(projectSummary) });
  } catch {
    jsonResponse(res, 502, { code: 'upstream_unavailable' });
  }
}

async function getProject(res, id) {
  try {
    const upstream = await upstreamFetch(`/projects/${encodeURIComponent(id)}`, { method: 'GET' });
    if (upstream.status === 404) return jsonResponse(res, 404, { code: 'project_not_found' });
    if (!upstream.ok) return jsonResponse(res, 502, { code: 'upstream_unavailable' });
    const data = await readJsonResponse(upstream);
    if (!isObject(data)) return jsonResponse(res, 502, { code: 'upstream_unavailable' });
    jsonResponse(res, 200, { project: projectDetail(data) });
  } catch {
    jsonResponse(res, 502, { code: 'upstream_unavailable' });
  }
}

async function putProject(req, res, id) {
  let parsed;
  try {
    parsed = JSON.parse(await readBody(req) || '{}');
  } catch {
    jsonResponse(res, 422, { detail: 'Invalid JSON' });
    return;
  }
  if (!validateSaveRequest(parsed)) {
    jsonResponse(res, 422, { detail: 'Invalid body' });
    return;
  }

  let current;
  try {
    const upstream = await upstreamFetch(`/projects/${encodeURIComponent(id)}`, { method: 'GET' });
    if (upstream.status === 404) return jsonResponse(res, 404, { code: 'project_not_found' });
    if (!upstream.ok) return jsonResponse(res, 502, { code: 'upstream_unavailable' });
    current = await readJsonResponse(upstream);
    if (!isObject(current)) return jsonResponse(res, 502, { code: 'upstream_unavailable' });
  } catch {
    return jsonResponse(res, 502, { code: 'upstream_unavailable' });
  }

  const result = mergeEdit(parsed.base, parsed.proposed, current);
  if (result.conflicts.length) {
    jsonResponse(res, 409, conflictResponse(current, result.conflicts));
    return;
  }
  if (!result.changed) {
    jsonResponse(res, 200, { project: projectDetail(current) });
    return;
  }

  const payload = {
    name: result.merged.name,
    sector: result.merged.sector,
    country: result.merged.country,
    stage: result.merged.stage,
    key_dates: result.merged.key_dates,
    linked_companies: current.linked_companies,
  };

  try {
    const upstream = await upstreamFetch(`/projects/${encodeURIComponent(id)}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (upstream.status === 404) return jsonResponse(res, 404, { code: 'project_not_found' });

    if (upstream.status === 504) {
      let observed = null;
      try {
        const reread = await upstreamFetch(`/projects/${encodeURIComponent(id)}`, { method: 'GET' });
        if (reread.ok) {
          const data = await readJsonResponse(reread);
          if (isObject(data)) observed = data;
        } else if (reread.status === 404) {
          observed = null;
        }
      } catch {}
      jsonResponse(res, 504, uncertainResponse(observed));
      return;
    }

    if (!upstream.ok) {
      jsonResponse(res, 502, { code: 'upstream_unavailable' });
      return;
    }

    const saved = await readJsonResponse(upstream);
    if (!isObject(saved)) {
      let observed = null;
      try {
        const reread = await upstreamFetch(`/projects/${encodeURIComponent(id)}`, { method: 'GET' });
        if (reread.ok) {
          const data = await readJsonResponse(reread);
          if (isObject(data)) observed = data;
        }
      } catch {}
      jsonResponse(res, 504, uncertainResponse(observed));
      return;
    }

    jsonResponse(res, 200, { project: projectDetail(saved) });
  } catch {
    let observed = null;
    try {
      const reread = await upstreamFetch(`/projects/${encodeURIComponent(id)}`, { method: 'GET' });
      if (reread.ok) {
        const data = await readJsonResponse(reread);
        if (isObject(data)) observed = data;
      }
    } catch {}
    jsonResponse(res, 504, uncertainResponse(observed));
  }
}

const server = http.createServer((req, res) => {
  const method = req.method || 'GET';
  const url = new URL(req.url || '/', 'http://127.0.0.1');

  if (url.pathname === '/api/projects' && method === 'GET') {
    void listProjects(res);
    return;
  }

  const match = url.pathname.match(/^\/api\/projects\/([^/]+)$/);
  if (match && method === 'GET') {
    void getProject(res, decodeURIComponent(match[1]));
    return;
  }
  if (match && method === 'PUT') {
    void putProject(req, res, decodeURIComponent(match[1]));
    return;
  }

  jsonResponse(res, 404, { code: 'not_found' });
});

server.listen(PORT, '0.0.0.0');
