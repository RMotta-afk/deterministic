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

function send(res, status, code, extra) {
  json(res, status, Object.assign({ code }, extra || {}));
}

function isObj(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function validDate(s) {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(s + 'T00:00:00.000Z');
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

function validateKeyDate(v) {
  return isObj(v) && Object.keys(v).length === 2 && typeof v.label === 'string' && v.label.trim().length > 0 && validDate(v.date);
}

function validateEditable(v) {
  return (
    isObj(v) &&
    Object.keys(v).length === 5 &&
    typeof v.name === 'string' &&
    v.name.trim().length > 0 &&
    typeof v.country === 'string' &&
    v.country.trim().length > 0 &&
    ['energy', 'mining', 'water', 'transport', 'oil_and_gas', 'ict'].includes(v.sector) &&
    ['idea', 'feasibility', 'tender', 'financing', 'construction', 'operation', 'cancelled'].includes(v.stage) &&
    Array.isArray(v.key_dates) &&
    v.key_dates.every(validateKeyDate)
  );
}

function validateProject(v) {
  return isObj(v) && typeof v.id === 'string' && validateEditable(v);
}

function editableFields(project) {
  return {
    name: project.name,
    sector: project.sector,
    country: project.country,
    stage: project.stage,
    key_dates: Array.isArray(project.key_dates) ? project.key_dates.map((d) => ({ label: d.label, date: d.date })) : [],
  };
}

function projectSummary(project) {
  return {
    id: project.id,
    name: project.name,
    sector: project.sector,
    country: project.country,
    stage: project.stage,
  };
}

function projectDetail(project) {
  return {
    id: project.id,
    name: project.name,
    sector: project.sector,
    country: project.country,
    stage: project.stage,
    key_dates: Array.isArray(project.key_dates) ? project.key_dates.map((d) => ({ label: d.label, date: d.date })) : [],
  };
}

function conflictFields(base, proposed, current) {
  const fields = [];
  for (const key of ['name', 'sector', 'country', 'stage', 'key_dates']) {
    if (JSON.stringify(proposed[key]) === JSON.stringify(base[key])) continue;
    if (JSON.stringify(current[key]) !== JSON.stringify(base[key]) && JSON.stringify(current[key]) !== JSON.stringify(proposed[key])) {
      fields.push(key);
    }
  }
  return fields;
}

async function readJsonSafe(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function upstream(path, options) {
  const headers = Object.assign({ 'X-Api-Key': UPSTREAM_API_KEY }, options && options.headers ? options.headers : {});
  const res = await fetch(UPSTREAM_URL + path, Object.assign({}, options || {}, { headers }));
  const body = await readJsonSafe(res);
  return { res, body };
}

async function listProjects() {
  const { res, body } = await upstream('/projects', { method: 'GET' });
  if (!res.ok) return { error: true, status: 502 };
  if (!Array.isArray(body)) return { error: true, status: 502 };
  const projects = body.filter(validateProject).map(projectSummary);
  return { projects };
}

async function getProject(projectId) {
  const { res, body } = await upstream('/projects/' + encodeURIComponent(projectId), { method: 'GET' });
  if (res.status === 404) return { error: true, status: 404 };
  if (!res.ok || !validateProject(body)) return { error: true, status: 502 };
  return { project: projectDetail(body) };
}

async function handlePut(projectId, req, res) {
  const body = await new Promise((resolve) => {
    let raw = '';
    req.on('data', (chunk) => {
      raw += chunk;
      if (raw.length > 1e6) req.destroy();
    });
    req.on('end', () => {
      try {
        resolve(JSON.parse(raw || '{}'));
      } catch {
        resolve(null);
      }
    });
    req.on('error', () => resolve(null));
  });

  if (!isObj(body) || Object.keys(body).length !== 2 || !validateEditable(body.base) || !validateEditable(body.proposed)) {
    return send(res, 422, 'validation_error');
  }

  const currentResp = await upstream('/projects/' + encodeURIComponent(projectId), { method: 'GET' });
  if (currentResp.res.status === 404) return send(res, 404, 'project_not_found');
  if (!currentResp.res.ok || !validateProject(currentResp.body)) return send(res, 502, 'upstream_unavailable');
  const current = currentResp.body;

  const conflicts = conflictFields(body.base, body.proposed, editableFields(current));
  if (conflicts.length) {
    return json(res, 409, { code: 'edit_conflict', current: projectDetail(current), conflicting_fields: conflicts });
  }

  const merged = {
    name: body.base.name === body.proposed.name ? current.name : body.proposed.name,
    sector: body.base.sector === body.proposed.sector ? current.sector : body.proposed.sector,
    country: body.base.country === body.proposed.country ? current.country : body.proposed.country,
    stage: body.base.stage === body.proposed.stage ? current.stage : body.proposed.stage,
    key_dates: JSON.stringify(body.base.key_dates) === JSON.stringify(body.proposed.key_dates) ? current.key_dates : body.proposed.key_dates,
  };

  if (
    merged.name === current.name &&
    merged.sector === current.sector &&
    merged.country === current.country &&
    merged.stage === current.stage &&
    JSON.stringify(merged.key_dates) === JSON.stringify(current.key_dates)
  ) {
    return json(res, 200, { project: projectDetail(current) });
  }

  const putBody = {
    name: merged.name,
    sector: merged.sector,
    country: merged.country,
    stage: merged.stage,
    key_dates: merged.key_dates,
    linked_companies: Array.isArray(current.linked_companies) ? current.linked_companies : [],
  };

  const putResp = await upstream('/projects/' + encodeURIComponent(projectId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(putBody),
  });

  if (putResp.res.status === 404) return send(res, 404, 'project_not_found');
  if (putResp.res.status === 504) {
    let observed = null;
    const diag = await upstream('/projects/' + encodeURIComponent(projectId), { method: 'GET' });
    if (diag.res.ok && validateProject(diag.body)) observed = projectDetail(diag.body);
    return json(res, 504, { code: 'write_uncertain', observed });
  }
  if (!putResp.res.ok || !validateProject(putResp.body)) return send(res, 502, 'upstream_unavailable');
  return json(res, 200, { project: projectDetail(putResp.body) });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || '/', 'http://localhost');
  if (req.method === 'GET' && url.pathname === '/api/projects') {
    const result = await listProjects();
    if (result.error) return send(res, result.status, result.status === 404 ? 'project_not_found' : 'upstream_unavailable');
    return json(res, 200, { projects: result.projects });
  }
  const match = url.pathname.match(/^\/api\/projects\/([^/]+)$/);
  if (req.method === 'GET' && match) {
    const result = await getProject(decodeURIComponent(match[1]));
    if (result.error) return send(res, result.status, result.status === 404 ? 'project_not_found' : 'upstream_unavailable');
    return json(res, 200, result);
  }
  if (req.method === 'PUT' && match) {
    return handlePut(decodeURIComponent(match[1]), req, res);
  }
  res.statusCode = 404;
  res.end('Not Found');
});

server.listen(PORT, '0.0.0.0');
