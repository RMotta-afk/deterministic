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

function isObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => {
      data += chunk;
      if (data.length > 1e6) reject(new Error('payload too large'));
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

function validDate(s) {
  return typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s);
}

function validateKeyDate(v) {
  return (
    isObject(v) &&
    Object.keys(v).length === 2 &&
    typeof v.label === 'string' &&
    v.label.trim().length > 0 &&
    validDate(v.date)
  );
}

function validateEditableFields(v) {
  return (
    isObject(v) &&
    Object.keys(v).length === 5 &&
    typeof v.name === 'string' &&
    v.name.trim().length > 0 &&
    typeof v.country === 'string' &&
    v.country.trim().length > 0 &&
    typeof v.sector === 'string' &&
    typeof v.stage === 'string' &&
    Array.isArray(v.key_dates) &&
    v.key_dates.every(validateKeyDate)
  );
}

function summary(project) {
  return {
    id: project.id,
    name: project.name,
    sector: project.sector,
    country: project.country,
    stage: project.stage,
  };
}

function detail(project) {
  return {
    id: project.id,
    name: project.name,
    sector: project.sector,
    country: project.country,
    stage: project.stage,
    key_dates: project.key_dates,
  };
}

function choose(base, proposed, current) {
  if (JSON.stringify(proposed) === JSON.stringify(base)) return [current, false];
  if (
    JSON.stringify(current) !== JSON.stringify(base) &&
    JSON.stringify(current) !== JSON.stringify(proposed)
  ) return [current, true];
  return [proposed, false];
}

function mergeEdit(base, proposed, current) {
  const merged = {};
  const conflicts = [];
  let v, c;

  [v, c] = choose(base.name, proposed.name, current.name);
  merged.name = v;
  if (c) conflicts.push('name');

  [v, c] = choose(base.sector, proposed.sector, current.sector);
  merged.sector = v;
  if (c) conflicts.push('sector');

  [v, c] = choose(base.country, proposed.country, current.country);
  merged.country = v;
  if (c) conflicts.push('country');

  [v, c] = choose(base.stage, proposed.stage, current.stage);
  merged.stage = v;
  if (c) conflicts.push('stage');

  [v, c] = choose(base.key_dates, proposed.key_dates, current.key_dates);
  merged.key_dates = v;
  if (c) conflicts.push('key_dates');

  const changed = JSON.stringify(merged) !== JSON.stringify({
    name: current.name,
    sector: current.sector,
    country: current.country,
    stage: current.stage,
    key_dates: current.key_dates,
  });

  return { merged, conflicts, changed };
}

async function upstream(path, options) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  const headers = Object.assign({}, options && options.headers ? options.headers : {});
  headers.accept = 'application/json';
  if (UPSTREAM_API_KEY) headers['X-Api-Key'] = UPSTREAM_API_KEY;
  try {
    return await fetch(new URL(path, UPSTREAM_URL), {
      ...(options || {}),
      headers,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function readJsonResponse(res) {
  return await res.json();
}

async function readProject(id) {
  let res;
  try {
    res = await upstream(`/projects/${encodeURIComponent(id)}`);
  } catch {
    return { kind: 'upstream' };
  }
  if (res.status === 404) return { kind: 'missing' };
  if (!res.ok) return { kind: 'upstream' };
  try {
    return { kind: 'ok', project: await readJsonResponse(res) };
  } catch {
    return { kind: 'upstream' };
  }
}

async function readList() {
  let res;
  try {
    res = await upstream('/projects');
  } catch {
    return { kind: 'upstream' };
  }
  if (!res.ok) return { kind: 'upstream' };
  try {
    return { kind: 'ok', projects: await readJsonResponse(res) };
  } catch {
    return { kind: 'upstream' };
  }
}

async function handle(req, res) {
  const url = new URL(req.url, 'http://localhost');
  if (req.method === 'GET' && url.pathname === '/api/projects') {
    const result = await readList();
    if (result.kind === 'upstream') return json(res, 502, { code: 'upstream_unavailable' });
    return json(res, 200, { projects: result.projects.map(summary) });
  }

  const match = url.pathname.match(/^\/api\/projects\/([^/]+)$/);
  if (!match) return json(res, 404, { detail: 'Not Found' });
  const id = decodeURIComponent(match[1]);

  if (req.method === 'GET') {
    const result = await readProject(id);
    if (result.kind === 'missing') return json(res, 404, { code: 'project_not_found' });
    if (result.kind === 'upstream') return json(res, 502, { code: 'upstream_unavailable' });
    return json(res, 200, { project: detail(result.project) });
  }

  if (req.method === 'PUT') {
    let body;
    try {
      body = await parseBody(req);
    } catch {
      return json(res, 422, {});
    }
    if (!isObject(body) || !validateEditableFields(body.base) || !validateEditableFields(body.proposed)) {
      return json(res, 422, {});
    }

    const currentResult = await readProject(id);
    if (currentResult.kind === 'missing') return json(res, 404, { code: 'project_not_found' });
    if (currentResult.kind === 'upstream') return json(res, 502, { code: 'upstream_unavailable' });

    const current = currentResult.project;
    const merged = mergeEdit(body.base, body.proposed, current);

    if (merged.conflicts.length) {
      return json(res, 409, {
        code: 'edit_conflict',
        current: detail(current),
        conflicting_fields: merged.conflicts,
      });
    }

    if (!merged.changed) {
      return json(res, 200, { project: detail(current) });
    }

    const payload = {
      ...merged.merged,
      linked_companies: current.linked_companies,
    };

    let putRes;
    try {
      putRes = await upstream(`/projects/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch {
      let observed = null;
      const reread = await readProject(id);
      if (reread.kind === 'ok') observed = detail(reread.project);
      return json(res, 504, { code: 'write_uncertain', observed });
    }

    if (putRes.status === 404) return json(res, 404, { code: 'project_not_found' });
    if (putRes.status === 504) {
      let observed = null;
      const reread = await readProject(id);
      if (reread.kind === 'ok') observed = detail(reread.project);
      return json(res, 504, { code: 'write_uncertain', observed });
    }
    if (!putRes.ok) return json(res, 502, { code: 'upstream_unavailable' });

    try {
      const saved = await readJsonResponse(putRes);
      return json(res, 200, { project: detail(saved) });
    } catch {
      let observed = null;
      const reread = await readProject(id);
      if (reread.kind === 'ok') observed = detail(reread.project);
      return json(res, 504, { code: 'write_uncertain', observed });
    }
  }

  return json(res, 405, { detail: 'Method Not Allowed' });
}

http.createServer((req, res) => {
  handle(req, res).catch(() => json(res, 502, { code: 'upstream_unavailable' }));
}).listen(PORT, '0.0.0.0');
