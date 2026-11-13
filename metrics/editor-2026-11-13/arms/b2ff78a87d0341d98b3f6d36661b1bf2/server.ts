// @ts-nocheck
const http = require('node:http');

const PORT = Number(process.env.PORT || 8080);
const UPSTREAM_URL = process.env.UPSTREAM_URL || 'http://127.0.0.1:8081';
const UPSTREAM_API_KEY = process.env.UPSTREAM_API_KEY || 'local-dev-key';

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
  });
  res.end(payload);
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', chunk => {
      data += chunk;
      if (data.length > 1024 * 1024) {
        reject(Object.assign(new Error('Body too large'), { statusCode: 413 }));
        req.destroy();
      }
    });
    req.on('end', () => {
      if (!data) return resolve(null);
      try {
        resolve(JSON.parse(data));
      } catch {
        reject(Object.assign(new Error('Invalid JSON'), { statusCode: 422 }));
      }
    });
    req.on('error', reject);
  });
}

function isNonBlankString(v) {
  return typeof v === 'string' && v.trim().length > 0;
}

function isValidDateString(s) {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(s + 'T00:00:00.000Z');
  if (Number.isNaN(d.getTime())) return false;
  return d.toISOString().slice(0, 10) === s;
}

const VALID_SECTORS = new Set(['energy', 'mining', 'water', 'transport', 'oil_and_gas', 'ict']);
const VALID_STAGES = new Set(['idea', 'feasibility', 'tender', 'financing', 'construction', 'operation', 'cancelled']);
const VALID_ROLES = new Set(['owner', 'developer', 'epc_contractor', 'financier', 'consultant']);

function validateKeyDate(v) {
  return v && typeof v === 'object' && !Array.isArray(v) && isNonBlankString(v.label) && isValidDateString(v.date) && Object.keys(v).every(k => k === 'label' || k === 'date');
}

function validateEditableFields(v) {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return false;
  const keys = Object.keys(v);
  const required = ['name', 'sector', 'country', 'stage', 'key_dates'];
  if (keys.length !== required.length) return false;
  for (const k of required) if (!Object.prototype.hasOwnProperty.call(v, k)) return false;
  if (!isNonBlankString(v.name)) return false;
  if (!VALID_SECTORS.has(v.sector)) return false;
  if (!isNonBlankString(v.country)) return false;
  if (!VALID_STAGES.has(v.stage)) return false;
  if (!Array.isArray(v.key_dates) || !v.key_dates.every(validateKeyDate)) return false;
  return true;
}

function validateLinkedCompany(v) {
  return v && typeof v === 'object' && !Array.isArray(v) && isNonBlankString(v.name) && VALID_ROLES.has(v.role) && Object.keys(v).every(k => k === 'name' || k === 'role');
}

function normalizeProject(p) {
  return {
    id: p.id,
    name: p.name,
    sector: p.sector,
    country: p.country,
    stage: p.stage,
    key_dates: Array.isArray(p.key_dates) ? p.key_dates.map(k => ({ label: k.label, date: k.date })) : [],
    linked_companies: Array.isArray(p.linked_companies) ? p.linked_companies.map(c => ({ name: c.name, role: c.role })) : [],
  };
}

function projectSummary(p) {
  return {
    id: p.id,
    name: p.name,
    sector: p.sector,
    country: p.country,
    stage: p.stage,
  };
}

function projectDetail(p) {
  return {
    id: p.id,
    name: p.name,
    sector: p.sector,
    country: p.country,
    stage: p.stage,
    key_dates: p.key_dates,
  };
}

async function upstreamFetch(path, options = {}) {
  const url = new URL(path, UPSTREAM_URL);
  const headers = Object.assign({}, options.headers || {});
  if (UPSTREAM_API_KEY) headers['X-Api-Key'] = UPSTREAM_API_KEY;
  const res = await fetch(url, { ...options, headers });
  return res;
}

async function upstreamJson(path, options = {}) {
  const res = await upstreamFetch(path, options);
  let json = null;
  try {
    json = await res.json();
  } catch {
    json = null;
  }
  return { res, json };
}

function mergeEdit(base, proposed, current) {
  const merged = {
    name: current.name,
    sector: current.sector,
    country: current.country,
    stage: current.stage,
    key_dates: current.key_dates,
  };
  const conflicts = [];
  for (const field of ['name', 'sector', 'country', 'stage', 'key_dates']) {
    const b = base[field];
    const p = proposed[field];
    const c = current[field];
    if (JSON.stringify(p) === JSON.stringify(b)) {
      merged[field] = c;
    } else if (JSON.stringify(c) !== JSON.stringify(b) && JSON.stringify(c) !== JSON.stringify(p)) {
      merged[field] = c;
      conflicts.push(field);
    } else {
      merged[field] = p;
    }
  }
  return { merged, conflicts, changed: JSON.stringify(merged) !== JSON.stringify(current) };
}

async function handleListProjects(res) {
  const { res: up, json } = await upstreamJson('/projects');
  if (!up.ok) return sendJson(res, 502, { code: 'upstream_unavailable' });
  const projects = Array.isArray(json) ? json.map(normalizeProject).map(projectSummary) : [];
  return sendJson(res, 200, { projects });
}

async function handleShowProject(res, projectId) {
  const { res: up, json } = await upstreamJson(`/projects/${encodeURIComponent(projectId)}`);
  if (up.status === 404) return sendJson(res, 404, { code: 'project_not_found' });
  if (!up.ok) return sendJson(res, 502, { code: 'upstream_unavailable' });
  return sendJson(res, 200, { project: projectDetail(normalizeProject(json)) });
}

async function handlePutProject(req, res, projectId) {
  let body;
  try {
    body = await readJsonBody(req);
  } catch (e) {
    return sendJson(res, e.statusCode || 422, { code: 'validation_error' });
  }
  if (!body || typeof body !== 'object' || Array.isArray(body) || !Object.prototype.hasOwnProperty.call(body, 'base') || !Object.prototype.hasOwnProperty.call(body, 'proposed')) {
    return sendJson(res, 422, { code: 'validation_error' });
  }
  if (!validateEditableFields(body.base) || !validateEditableFields(body.proposed)) {
    return sendJson(res, 422, { code: 'validation_error' });
  }
  const { res: currentRes, json: currentJson } = await upstreamJson(`/projects/${encodeURIComponent(projectId)}`);
  if (currentRes.status === 404) return sendJson(res, 404, { code: 'project_not_found' });
  if (!currentRes.ok) return sendJson(res, 502, { code: 'upstream_unavailable' });
  const current = normalizeProject(currentJson);
  const merge = mergeEdit(body.base, body.proposed, {
    name: current.name,
    sector: current.sector,
    country: current.country,
    stage: current.stage,
    key_dates: current.key_dates,
  });
  if (merge.conflicts.length) {
    return sendJson(res, 409, {
      code: 'edit_conflict',
      current: projectDetail(current),
      conflicting_fields: merge.conflicts,
    });
  }
  if (!merge.changed) {
    return sendJson(res, 200, { project: projectDetail(current) });
  }
  const putBody = {
    name: merge.merged.name,
    sector: merge.merged.sector,
    country: merge.merged.country,
    stage: merge.merged.stage,
    key_dates: merge.merged.key_dates,
    linked_companies: current.linked_companies,
  };
  const putRes = await upstreamFetch(`/projects/${encodeURIComponent(projectId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(putBody),
  });
  if (putRes.status === 504) {
    let observed = null;
    const diag = await upstreamJson(`/projects/${encodeURIComponent(projectId)}`);
    if (diag.res.ok) observed = projectDetail(normalizeProject(diag.json));
    return sendJson(res, 504, { code: 'write_uncertain', observed });
  }
  if (putRes.status === 404) return sendJson(res, 404, { code: 'project_not_found' });
  if (!putRes.ok) return sendJson(res, 502, { code: 'upstream_unavailable' });
  const saved = normalizeProject(await putRes.json());
  return sendJson(res, 200, { project: projectDetail(saved) });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || '/', 'http://localhost');
  if (url.pathname === '/api/projects' && req.method === 'GET') {
    return void handleListProjects(res);
  }
  const m = url.pathname.match(/^\/api\/projects\/([^/]+)$/);
  if (m && req.method === 'GET') {
    return void handleShowProject(res, decodeURIComponent(m[1]));
  }
  if (m && req.method === 'PUT') {
    return void handlePutProject(req, res, decodeURIComponent(m[1]));
  }
  sendJson(res, 404, { code: 'not_found' });
});

server.listen(PORT, '0.0.0.0');
