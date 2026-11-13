// @ts-nocheck
const http = require('node:http');

const PORT = Number(process.env.PORT || 8080);
const UPSTREAM_URL = process.env.UPSTREAM_URL || 'http://127.0.0.1:8081';
const UPSTREAM_API_KEY = process.env.UPSTREAM_API_KEY || 'local-dev-key';

function send(res, status, body) {
  const json = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(json),
  });
  res.end(json);
}

function sendText(res, status, text) {
  res.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end(text);
}

function notFound(res, code) {
  send(res, 404, { code });
}

function isObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function parseJson(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => {
      data += chunk;
      if (data.length > 1e7) reject(new Error('body too large'));
    });
    req.on('end', () => {
      if (!data) return resolve(null);
      try {
        resolve(JSON.parse(data));
      } catch {
        reject(new Error('invalid json'));
      }
    });
    req.on('error', reject);
  });
}

function isNonblankString(v) {
  return typeof v === 'string' && v.trim().length > 0;
}

function isValidDateString(s) {
  if (typeof s !== 'string') return false;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return false;
  const y = Number(m[1]), mo = Number(m[2]), d = Number(m[3]);
  const dt = new Date(Date.UTC(y, mo - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d;
}

function validateKeyDates(arr) {
  if (!Array.isArray(arr)) return false;
  for (const item of arr) {
    if (!isObject(item)) return false;
    if (Object.keys(item).some((k) => k !== 'label' && k !== 'date')) return false;
    if (!isNonblankString(item.label)) return false;
    if (!isValidDateString(item.date)) return false;
  }
  return true;
}

function validateEditableFields(obj) {
  if (!isObject(obj)) return false;
  const keys = Object.keys(obj);
  for (const k of ['name', 'sector', 'country', 'stage', 'key_dates']) if (!keys.includes(k)) return false;
  if (keys.some((k) => !['name', 'sector', 'country', 'stage', 'key_dates'].includes(k))) return false;
  if (!isNonblankString(obj.name)) return false;
  if (!isNonblankString(obj.sector)) return false;
  if (!isNonblankString(obj.country)) return false;
  if (!isNonblankString(obj.stage)) return false;
  if (!validateKeyDates(obj.key_dates)) return false;
  return true;
}

function validateLinkedCompanies(arr) {
  if (!Array.isArray(arr)) return false;
  for (const item of arr) {
    if (!isObject(item)) return false;
    if (Object.keys(item).some((k) => k !== 'name' && k !== 'role')) return false;
    if (!isNonblankString(item.name)) return false;
    if (!isNonblankString(item.role)) return false;
  }
  return true;
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

function summaryFromStored(project) {
  return {
    id: project.id,
    name: project.name,
    sector: project.sector,
    country: project.country,
    stage: project.stage,
  };
}

function mergeEdit(base, proposed, current) {
  const conflicts = [];
  function choose(field) {
    if (JSON.stringify(proposed[field]) === JSON.stringify(base[field])) return current[field];
    if (JSON.stringify(current[field]) !== JSON.stringify(base[field]) && JSON.stringify(current[field]) !== JSON.stringify(proposed[field])) {
      conflicts.push(field);
      return current[field];
    }
    return proposed[field];
  }
  const merged = {
    name: choose('name'),
    sector: choose('sector'),
    country: choose('country'),
    stage: choose('stage'),
    key_dates: choose('key_dates'),
  };
  return { merged, conflicts, changed: JSON.stringify(merged) !== JSON.stringify(current) };
}

async function upstreamFetch(path, options = {}) {
  return fetch(new URL(path, UPSTREAM_URL), {
    ...options,
    headers: {
      ...(options.headers || {}),
      'X-Api-Key': UPSTREAM_API_KEY,
    },
  });
}

async function readUpstreamJson(path) {
  const response = await upstreamFetch(path);
  let json;
  try {
    json = await response.json();
  } catch {
    throw { kind: 'upstream_unavailable' };
  }
  if (response.status === 404) throw { kind: 'not_found' };
  if (!response.ok) throw { kind: 'upstream_unavailable' };
  return json;
}

async function getCurrent(projectId) {
  const json = await readUpstreamJson(`/projects/${encodeURIComponent(projectId)}`);
  if (!isObject(json)) throw { kind: 'upstream_unavailable' };
  return json;
}

async function listProjects(res) {
  try {
    const json = await readUpstreamJson('/projects');
    if (!Array.isArray(json)) throw { kind: 'upstream_unavailable' };
    send(res, 200, { projects: json.map(summaryFromStored) });
  } catch (e) {
    if (e && e.kind === 'not_found') return notFound(res, 'project_not_found');
    send(res, 502, { code: 'upstream_unavailable' });
  }
}

async function showProject(res, projectId) {
  try {
    const project = await getCurrent(projectId);
    send(res, 200, { project: detailFromStored(project) });
  } catch (e) {
    if (e && e.kind === 'not_found') return notFound(res, 'project_not_found');
    send(res, 502, { code: 'upstream_unavailable' });
  }
}

async function saveProject(req, res, projectId) {
  let body;
  try {
    body = await parseJson(req);
  } catch {
    send(res, 422, { detail: 'Invalid JSON' });
    return;
  }
  if (!isObject(body) || !validateEditableFields(body.base) || !validateEditableFields(body.proposed)) {
    send(res, 422, { detail: 'Validation error' });
    return;
  }
  let current;
  try {
    current = await getCurrent(projectId);
  } catch (e) {
    if (e && e.kind === 'not_found') return notFound(res, 'project_not_found');
    return send(res, 502, { code: 'upstream_unavailable' });
  }
  if (!validateLinkedCompanies(current.linked_companies)) {
    return send(res, 502, { code: 'upstream_unavailable' });
  }
  const currentEditable = {
    name: current.name,
    sector: current.sector,
    country: current.country,
    stage: current.stage,
    key_dates: current.key_dates,
  };
  const result = mergeEdit(body.base, body.proposed, currentEditable);
  if (result.conflicts.length) {
    send(res, 409, {
      code: 'edit_conflict',
      current: detailFromStored(current),
      conflicting_fields: result.conflicts,
    });
    return;
  }
  if (!result.changed) {
    send(res, 200, { project: detailFromStored(current) });
    return;
  }
  const upstreamBody = {
    ...result.merged,
    linked_companies: current.linked_companies,
  };
  let putResponse;
  try {
    putResponse = await upstreamFetch(`/projects/${encodeURIComponent(projectId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(upstreamBody),
    });
  } catch {
    send(res, 504, { code: 'write_uncertain', observed: detailFromStored(current) });
    return;
  }
  let putJson;
  try {
    putJson = await putResponse.json();
  } catch {
    send(res, 504, { code: 'write_uncertain', observed: detailFromStored(current) });
    return;
  }
  if (putResponse.status === 504) {
    let observed = detailFromStored(current);
    try {
      const reread = await getCurrent(projectId);
      observed = detailFromStored(reread);
    } catch {}
    send(res, 504, { code: 'write_uncertain', observed });
    return;
  }
  if (putResponse.status === 404) {
    notFound(res, 'project_not_found');
    return;
  }
  if (!putResponse.ok) {
    send(res, 502, { code: 'upstream_unavailable' });
    return;
  }
  if (!isObject(putJson)) {
    send(res, 502, { code: 'upstream_unavailable' });
    return;
  }
  send(res, 200, { project: detailFromStored(putJson) });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || '/', 'http://127.0.0.1');
  const method = req.method || 'GET';
  if (url.pathname === '/api/projects' && method === 'GET') return void listProjects(res);
  const match = /^\/api\/projects\/([^/]+)$/.exec(url.pathname);
  if (match) {
    const id = decodeURIComponent(match[1]);
    if (method === 'GET') return void showProject(res, id);
    if (method === 'PUT') return void saveProject(req, res, id);
  }
  sendText(res, 404, 'Not Found');
});

server.listen(PORT, '0.0.0.0');
