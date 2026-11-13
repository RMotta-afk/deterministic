// @ts-nocheck
const http = require('node:http');

const PORT = Number(process.env.PORT || 8080);
const UPSTREAM_URL = process.env.UPSTREAM_URL || 'http://127.0.0.1:8081';
const UPSTREAM_API_KEY = process.env.UPSTREAM_API_KEY || 'local-dev-key';

function json(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(data),
  });
  res.end(data);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      data += chunk;
      if (data.length > 1_000_000) {
        reject(new Error('body too large'));
        req.destroy();
      }
    });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

function isNonblankString(v) {
  return typeof v === 'string' && v.trim().length > 0;
}

function parseDateStrict(s) {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  const d = new Date(s + 'T00:00:00.000Z');
  if (Number.isNaN(d.getTime())) return null;
  const iso = d.toISOString().slice(0, 10);
  return iso === s ? s : null;
}

const SECTORS = new Set(['energy', 'mining', 'water', 'transport', 'oil_and_gas', 'ict']);
const STAGES = new Set(['idea', 'feasibility', 'tender', 'financing', 'construction', 'operation', 'cancelled']);
const COMPANY_ROLES = new Set(['owner', 'developer', 'epc_contractor', 'financier', 'consultant']);

function validateKeyDates(value) {
  if (!Array.isArray(value)) return false;
  for (const item of value) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return false;
    const keys = Object.keys(item);
    if (keys.length !== 2 || !('label' in item) || !('date' in item)) return false;
    if (!isNonblankString(item.label)) return false;
    if (!parseDateStrict(item.date)) return false;
  }
  return true;
}

function validateEditableFields(obj) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return false;
  const keys = Object.keys(obj);
  if (keys.length !== 5) return false;
  if (!('name' in obj) || !('sector' in obj) || !('country' in obj) || !('stage' in obj) || !('key_dates' in obj)) return false;
  if (!isNonblankString(obj.name)) return false;
  if (!SECTORS.has(obj.sector)) return false;
  if (!isNonblankString(obj.country)) return false;
  if (!STAGES.has(obj.stage)) return false;
  if (!validateKeyDates(obj.key_dates)) return false;
  return true;
}

function validateLinkedCompanies(value) {
  if (!Array.isArray(value)) return false;
  for (const item of value) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return false;
    const keys = Object.keys(item);
    if (keys.length !== 2 || !('name' in item) || !('role' in item)) return false;
    if (!isNonblankString(item.name)) return false;
    if (!COMPANY_ROLES.has(item.role)) return false;
  }
  return true;
}

function editableFromStored(project) {
  return {
    name: project.name,
    sector: project.sector,
    country: project.country,
    stage: project.stage,
    key_dates: project.key_dates,
  };
}

function summaryFromStored(project) {
  return {
    id: project.id,
    name: project.name,
    sector: project.sector,
    country: project.country,
    stage: project.stage,
  };
}

function detailFromStored(project) {
  return {
    id: project.id,
    name: project.name,
    sector: project.sector,
    country: project.country,
    stage: project.stage,
    key_dates: project.key_dates,
  };
}

function mergeEdit(base, proposed, current) {
  const choose = (b, p, c) => {
    if (JSON.stringify(p) === JSON.stringify(b)) return [c, false];
    if (JSON.stringify(c) !== JSON.stringify(b) && JSON.stringify(c) !== JSON.stringify(p)) return [c, true];
    return [p, false];
  };
  const conflicts = [];
  const name = choose(base.name, proposed.name, current.name); if (name[1]) conflicts.push('name');
  const sector = choose(base.sector, proposed.sector, current.sector); if (sector[1]) conflicts.push('sector');
  const country = choose(base.country, proposed.country, current.country); if (country[1]) conflicts.push('country');
  const stage = choose(base.stage, proposed.stage, current.stage); if (stage[1]) conflicts.push('stage');
  const key_dates = choose(base.key_dates, proposed.key_dates, current.key_dates); if (key_dates[1]) conflicts.push('key_dates');
  const merged = {
    name: name[0],
    sector: sector[0],
    country: country[0],
    stage: stage[0],
    key_dates: key_dates[0],
  };
  return { merged, conflicts, changed: JSON.stringify(merged) !== JSON.stringify(current) };
}

async function upstreamGet(path) {
  const res = await fetch(new URL(path, UPSTREAM_URL), {
    headers: { 'X-Api-Key': UPSTREAM_API_KEY },
  });
  let jsonBody = null;
  try {
    jsonBody = await res.json();
  } catch {
    jsonBody = null;
  }
  return { res, jsonBody };
}

async function upstreamPut(path, body) {
  const res = await fetch(new URL(path, UPSTREAM_URL), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'X-Api-Key': UPSTREAM_API_KEY },
    body: JSON.stringify(body),
  });
  let jsonBody = null;
  try {
    jsonBody = await res.json();
  } catch {
    jsonBody = null;
  }
  return { res, jsonBody };
}

async function listProjectsHandler(res) {
  const { res: up, jsonBody } = await upstreamGet('/projects');
  if (!up.ok) return json(res, 502, { code: 'upstream_unavailable' });
  if (!Array.isArray(jsonBody)) return json(res, 502, { code: 'upstream_unavailable' });
  const projects = jsonBody.map(summaryFromStored);
  return json(res, 200, { projects });
}

async function showProjectHandler(res, id) {
  const { res: up, jsonBody } = await upstreamGet('/projects/' + encodeURIComponent(id));
  if (up.status === 404) return json(res, 404, { code: 'project_not_found' });
  if (!up.ok) return json(res, 502, { code: 'upstream_unavailable' });
  return json(res, 200, { project: detailFromStored(jsonBody) });
}

async function saveProjectHandler(req, res, id) {
  let parsed;
  try {
    const raw = await readBody(req);
    parsed = JSON.parse(raw);
  } catch {
    return json(res, 422, { detail: 'Invalid request body' });
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed) || !('base' in parsed) || !('proposed' in parsed)) {
    return json(res, 422, { detail: 'Invalid request body' });
  }
  if (!validateEditableFields(parsed.base) || !validateEditableFields(parsed.proposed)) {
    return json(res, 422, { detail: 'Invalid request body' });
  }

  const { res: curRes, jsonBody: currentBody } = await upstreamGet('/projects/' + encodeURIComponent(id));
  if (curRes.status === 404) return json(res, 404, { code: 'project_not_found' });
  if (!curRes.ok) return json(res, 502, { code: 'upstream_unavailable' });

  const current = {
    id: currentBody.id,
    name: currentBody.name,
    sector: currentBody.sector,
    country: currentBody.country,
    stage: currentBody.stage,
    key_dates: currentBody.key_dates,
    linked_companies: Array.isArray(currentBody.linked_companies) ? currentBody.linked_companies : [],
  };

  const merge = mergeEdit(parsed.base, parsed.proposed, editableFromStored(current));
  if (merge.conflicts.length) {
    return json(res, 409, {
      code: 'edit_conflict',
      current: detailFromStored(current),
      conflicting_fields: merge.conflicts,
    });
  }

  if (!merge.changed) {
    return json(res, 200, { project: detailFromStored(current) });
  }

  const body = {
    name: merge.merged.name,
    sector: merge.merged.sector,
    country: merge.merged.country,
    stage: merge.merged.stage,
    key_dates: merge.merged.key_dates,
    linked_companies: current.linked_companies,
  };

  const { res: putRes, jsonBody: putBody } = await upstreamPut('/projects/' + encodeURIComponent(id), body);
  if (putRes.status === 404) return json(res, 404, { code: 'project_not_found' });
  if (putRes.status === 504) {
    let observed = null;
    const { res: diagRes, jsonBody: diagBody } = await upstreamGet('/projects/' + encodeURIComponent(id));
    if (diagRes.ok) observed = detailFromStored(diagBody);
    return json(res, 504, { code: 'write_uncertain', observed });
  }
  if (!putRes.ok) return json(res, 502, { code: 'upstream_unavailable' });
  return json(res, 200, { project: detailFromStored(putBody) });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || '/', 'http://127.0.0.1');
  if (req.method === 'GET' && url.pathname === '/api/projects') {
    listProjectsHandler(res).catch(() => json(res, 502, { code: 'upstream_unavailable' }));
    return;
  }
  const m = url.pathname.match(/^\/api\/projects\/([^/]+)$/);
  if (req.method === 'GET' && m) {
    showProjectHandler(res, decodeURIComponent(m[1])).catch(() => json(res, 502, { code: 'upstream_unavailable' }));
    return;
  }
  if (req.method === 'PUT' && m) {
    saveProjectHandler(req, res, decodeURIComponent(m[1])).catch(() => json(res, 502, { code: 'upstream_unavailable' }));
    return;
  }
  json(res, 404, { code: 'not_found' });
});

server.listen(PORT, '0.0.0.0');
