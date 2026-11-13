// @ts-nocheck
const http = require('node:http');

const HOST = '0.0.0.0';
const PORT = Number(process.env.PORT || 8080);
const UPSTREAM_URL = process.env.UPSTREAM_URL || 'http://127.0.0.1:8081';
const UPSTREAM_API_KEY = process.env.UPSTREAM_API_KEY || 'local-dev-key';

function jsonResponse(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(payload),
  });
  res.end(payload);
}

function notFound(res) {
  jsonResponse(res, 404, { code: 'project_not_found' });
}

function upstreamUnavailable(res) {
  jsonResponse(res, 502, { code: 'upstream_unavailable' });
}

function uncertainWrite(res, observed) {
  jsonResponse(res, 504, { code: 'write_uncertain', observed: observed ?? null });
}

function isNonEmptyString(v) {
  return typeof v === 'string' && v.length > 0;
}

function isValidDateString(s) {
  if (typeof s !== 'string') return false;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return false;
  const y = Number(m[1]), mo = Number(m[2]), d = Number(m[3]);
  const dt = new Date(Date.UTC(y, mo - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d;
}

function validateKeyDate(v) {
  return v && typeof v === 'object' && !Array.isArray(v) && isNonEmptyString(v.label) && v.label.trim() !== '' && isValidDateString(v.date);
}

function validateEditableFields(v) {
  const sectors = new Set(['energy', 'mining', 'water', 'transport', 'oil_and_gas', 'ict']);
  const stages = new Set(['idea', 'feasibility', 'tender', 'financing', 'construction', 'operation', 'cancelled']);
  return v && typeof v === 'object' && !Array.isArray(v) &&
    isNonEmptyString(v.name) && v.name.trim() !== '' &&
    sectors.has(v.sector) &&
    isNonEmptyString(v.country) && v.country.trim() !== '' &&
    stages.has(v.stage) &&
    Array.isArray(v.key_dates) && v.key_dates.every(validateKeyDate);
}

function projectDetailFromWide(v) {
  return { id: v.id, name: v.name, sector: v.sector, country: v.country, stage: v.stage, key_dates: v.key_dates };
}

function projectSummaryFromWide(v) {
  return { id: v.id, name: v.name, sector: v.sector, country: v.country, stage: v.stage };
}

function conflictMerge(base, proposed, current) {
  const fields = ['name', 'sector', 'country', 'stage', 'key_dates'];
  const merged = {};
  const conflicts = [];
  for (const f of fields) {
    if (JSON.stringify(proposed[f]) === JSON.stringify(base[f])) {
      merged[f] = current[f];
    } else if (JSON.stringify(current[f]) !== JSON.stringify(base[f]) && JSON.stringify(current[f]) !== JSON.stringify(proposed[f])) {
      merged[f] = current[f];
      conflicts.push(f);
    } else {
      merged[f] = proposed[f];
    }
  }
  return { merged, conflicts, changed: JSON.stringify(merged) !== JSON.stringify({
    name: current.name, sector: current.sector, country: current.country, stage: current.stage, key_dates: current.key_dates
  }) };
}

async function fetchJson(url, init) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 5000);
  try {
    const res = await fetch(url, { ...init, signal: controller.signal });
    const text = await res.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch { data = null; }
    }
    return { res, data };
  } finally {
    clearTimeout(t);
  }
}

async function upstreamListProjects() {
  const { res, data } = await fetchJson(new URL('/projects', UPSTREAM_URL), {
    headers: { 'X-Api-Key': UPSTREAM_API_KEY },
  });
  if (res.status === 404) throw Object.assign(new Error('not found'), { kind: 'not_found' });
  if (!res.ok) throw Object.assign(new Error('upstream unavailable'), { kind: 'upstream' });
  if (!Array.isArray(data)) throw Object.assign(new Error('upstream unavailable'), { kind: 'upstream' });
  return data;
}

async function upstreamGetProject(projectId) {
  const { res, data } = await fetchJson(new URL(`/projects/${encodeURIComponent(projectId)}`, UPSTREAM_URL), {
    headers: { 'X-Api-Key': UPSTREAM_API_KEY },
  });
  if (res.status === 404) throw Object.assign(new Error('not found'), { kind: 'not_found' });
  if (!res.ok) throw Object.assign(new Error('upstream unavailable'), { kind: 'upstream' });
  if (!data || typeof data !== 'object') throw Object.assign(new Error('upstream unavailable'), { kind: 'upstream' });
  return data;
}

async function upstreamPutProject(projectId, body) {
  const { res, data } = await fetchJson(new URL(`/projects/${encodeURIComponent(projectId)}`, UPSTREAM_URL), {
    method: 'PUT',
    headers: { 'X-Api-Key': UPSTREAM_API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.status === 404) throw Object.assign(new Error('not found'), { kind: 'not_found' });
  if (res.status === 504 || !res.ok) throw Object.assign(new Error('uncertain'), { kind: 'uncertain', observed: data });
  if (!data || typeof data !== 'object') throw Object.assign(new Error('uncertain'), { kind: 'uncertain', observed: null });
  return data;
}

function sendValidationError(res) {
  jsonResponse(res, 422, { detail: [{ loc: ['body'], msg: 'Validation error', type: 'value_error' }] });
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    const path = url.pathname;
    if (req.method === 'GET' && path === '/api/projects') {
      try {
        const projects = await upstreamListProjects();
        jsonResponse(res, 200, { projects: projects.map(projectSummaryFromWide) });
      } catch (e) {
        if (e && e.kind === 'not_found') return notFound(res);
        return upstreamUnavailable(res);
      }
      return;
    }
    const m = /^\/api\/projects\/([^/]+)$/.exec(path);
    if (!m) return notFound(res);
    const projectId = decodeURIComponent(m[1]);
    if (req.method === 'GET') {
      try {
        const project = await upstreamGetProject(projectId);
        jsonResponse(res, 200, { project: projectDetailFromWide(project) });
      } catch (e) {
        if (e && e.kind === 'not_found') return notFound(res);
        return upstreamUnavailable(res);
      }
      return;
    }
    if (req.method === 'PUT') {
      let raw = '';
      for await (const chunk of req) raw += chunk;
      let body;
      try { body = raw ? JSON.parse(raw) : null; } catch { return sendValidationError(res); }
      if (!body || typeof body !== 'object' || Array.isArray(body) || !validateEditableFields(body.base) || !validateEditableFields(body.proposed)) {
        return sendValidationError(res);
      }
      let current;
      try {
        current = await upstreamGetProject(projectId);
      } catch (e) {
        if (e && e.kind === 'not_found') return notFound(res);
        return upstreamUnavailable(res);
      }
      const result = conflictMerge(body.base, body.proposed, current);
      if (result.conflicts.length) {
        return jsonResponse(res, 409, { code: 'edit_conflict', current: projectDetailFromWide(current), conflicting_fields: result.conflicts });
      }
      if (!result.changed) {
        return jsonResponse(res, 200, { project: projectDetailFromWide(current) });
      }
      try {
        const saved = await upstreamPutProject(projectId, { ...result.merged, linked_companies: current.linked_companies });
        return jsonResponse(res, 200, { project: projectDetailFromWide(saved) });
      } catch (e) {
        if (e && e.kind === 'not_found') return notFound(res);
        if (e && e.kind === 'uncertain') {
          let observed = null;
          try {
            const reread = await upstreamGetProject(projectId);
            observed = projectDetailFromWide(reread);
          } catch (_) {
            observed = null;
          }
          return uncertainWrite(res, observed);
        }
        return upstreamUnavailable(res);
      }
    }
    return notFound(res);
  } catch (_) {
    return upstreamUnavailable(res);
  }
});

server.listen(PORT, HOST);
