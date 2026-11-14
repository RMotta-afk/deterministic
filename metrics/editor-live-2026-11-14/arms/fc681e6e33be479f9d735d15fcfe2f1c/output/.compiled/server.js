"use strict";
// @ts-nocheck
const http = require('node:http');
const PORT = Number(process.env.PORT || 8080);
const UPSTREAM_URL = process.env.UPSTREAM_URL;
const UPSTREAM_API_KEY = process.env.UPSTREAM_API_KEY;
function sendJson(res, status, body) {
    const data = Buffer.from(JSON.stringify(body));
    res.writeHead(status, {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Length': data.length,
        'Cache-Control': 'no-store',
    });
    res.end(data);
}
function notFound(res) {
    sendJson(res, 404, { code: 'project_not_found' });
}
function upstreamUnavailable(res) {
    sendJson(res, 502, { code: 'upstream_unavailable' });
}
function uncertain(res, observed) {
    sendJson(res, 504, { code: 'write_uncertain', observed });
}
function badRequest(res, status = 422) {
    res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ detail: 'Validation error' }));
}
function isNonBlankString(v) {
    return typeof v === 'string' && v.trim().length > 0;
}
function isIsoDate(s) {
    if (typeof s !== 'string')
        return false;
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    if (!m)
        return false;
    const y = Number(m[1]), mo = Number(m[2]), d = Number(m[3]);
    const dt = new Date(Date.UTC(y, mo - 1, d));
    return dt.getUTCFullYear() === y && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === d;
}
function validateKeyDates(arr) {
    if (!Array.isArray(arr))
        return false;
    for (const item of arr) {
        if (!item || typeof item !== 'object' || Array.isArray(item))
            return false;
        const keys = Object.keys(item);
        if (keys.length !== 2 || !('label' in item) || !('date' in item))
            return false;
        if (!isNonBlankString(item.label) || !isIsoDate(item.date))
            return false;
    }
    return true;
}
function validateEditable(obj) {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj))
        return false;
    const keys = Object.keys(obj);
    const allowed = new Set(['name', 'sector', 'country', 'stage', 'key_dates']);
    if (keys.length !== 5 || keys.some((k) => !allowed.has(k)))
        return false;
    const sectors = new Set(['energy', 'mining', 'water', 'transport', 'oil_and_gas', 'ict']);
    const stages = new Set(['idea', 'feasibility', 'tender', 'financing', 'construction', 'operation', 'cancelled']);
    return isNonBlankString(obj.name) && sectors.has(obj.sector) && isNonBlankString(obj.country) && stages.has(obj.stage) && validateKeyDates(obj.key_dates);
}
function validateSave(body) {
    if (!body || typeof body !== 'object' || Array.isArray(body))
        return false;
    const keys = Object.keys(body);
    if (keys.length !== 2 || !('base' in body) || !('proposed' in body))
        return false;
    return validateEditable(body.base) && validateEditable(body.proposed);
}
function summarize(p) {
    return { id: p.id, name: p.name, sector: p.sector, country: p.country, stage: p.stage };
}
function detail(p) {
    return { id: p.id, name: p.name, sector: p.sector, country: p.country, stage: p.stage, key_dates: p.key_dates };
}
function mergeEdit(base, proposed, current) {
    const fields = ['name', 'sector', 'country', 'stage', 'key_dates'];
    const merged = {};
    const conflicts = [];
    for (const f of fields) {
        if (JSON.stringify(proposed[f]) === JSON.stringify(base[f]))
            merged[f] = current[f];
        else if (JSON.stringify(current[f]) !== JSON.stringify(base[f]) && JSON.stringify(current[f]) !== JSON.stringify(proposed[f])) {
            merged[f] = current[f];
            conflicts.push(f);
        }
        else
            merged[f] = proposed[f];
    }
    const changed = JSON.stringify(merged) !== JSON.stringify({
        name: current.name,
        sector: current.sector,
        country: current.country,
        stage: current.stage,
        key_dates: current.key_dates,
    });
    return { merged, conflicts, changed };
}
async function upstreamFetch(path, options = {}) {
    if (!UPSTREAM_URL)
        throw new Error('missing upstream url');
    const url = new URL(path, UPSTREAM_URL);
    const headers = Object.assign({}, options.headers || {});
    if (UPSTREAM_API_KEY)
        headers['X-Api-Key'] = UPSTREAM_API_KEY;
    if (!headers['Content-Type'] && options.body)
        headers['Content-Type'] = 'application/json';
    const resp = await fetch(url, { ...options, headers });
    return resp;
}
async function readUpstreamJson(resp) {
    try {
        return await resp.json();
    }
    catch {
        return null;
    }
}
async function getCurrent(projectId) {
    try {
        const resp = await upstreamFetch(`/projects/${encodeURIComponent(projectId)}`);
        if (resp.status === 404)
            return { kind: 'missing' };
        if (!resp.ok)
            return { kind: 'unavailable' };
        const json = await readUpstreamJson(resp);
        if (!json || typeof json !== 'object')
            return { kind: 'unavailable' };
        return { kind: 'ok', project: json };
    }
    catch {
        return { kind: 'unavailable' };
    }
}
async function listProjectsHandler(res) {
    try {
        const resp = await upstreamFetch('/projects');
        if (!resp.ok)
            return upstreamUnavailable(res);
        const json = await readUpstreamJson(resp);
        if (!Array.isArray(json))
            return upstreamUnavailable(res);
        sendJson(res, 200, { projects: json.map(summarize) });
    }
    catch {
        upstreamUnavailable(res);
    }
}
async function showProjectHandler(res, projectId) {
    const current = await getCurrent(projectId);
    if (current.kind === 'missing')
        return notFound(res);
    if (current.kind !== 'ok')
        return upstreamUnavailable(res);
    sendJson(res, 200, { project: detail(current.project) });
}
async function saveProjectHandler(res, projectId, body) {
    if (!validateSave(body))
        return badRequest(res, 422);
    const base = body.base;
    const proposed = body.proposed;
    const fresh = await getCurrent(projectId);
    if (fresh.kind === 'missing')
        return notFound(res);
    if (fresh.kind !== 'ok')
        return upstreamUnavailable(res);
    const current = fresh.project;
    const result = mergeEdit(base, proposed, current);
    if (result.conflicts.length) {
        return sendJson(res, 409, { code: 'edit_conflict', current: detail(current), conflicting_fields: result.conflicts });
    }
    if (!result.changed) {
        return sendJson(res, 200, { project: detail(current) });
    }
    const putBody = {
        name: result.merged.name,
        sector: result.merged.sector,
        country: result.merged.country,
        stage: result.merged.stage,
        key_dates: result.merged.key_dates,
        linked_companies: current.linked_companies || [],
    };
    try {
        const resp = await upstreamFetch(`/projects/${encodeURIComponent(projectId)}`, {
            method: 'PUT',
            body: JSON.stringify(putBody),
        });
        if (resp.status === 404)
            return notFound(res);
        if (!resp.ok) {
            const observed = await getCurrent(projectId);
            return uncertain(res, observed.kind === 'ok' ? detail(observed.project) : null);
        }
        const json = await readUpstreamJson(resp);
        if (!json || typeof json !== 'object') {
            const observed = await getCurrent(projectId);
            return uncertain(res, observed.kind === 'ok' ? detail(observed.project) : null);
        }
        sendJson(res, 200, { project: detail(json) });
    }
    catch {
        const observed = await getCurrent(projectId);
        return uncertain(res, observed.kind === 'ok' ? detail(observed.project) : null);
    }
}
function parseBody(req) {
    return new Promise((resolve, reject) => {
        let data = '';
        req.on('data', (chunk) => {
            data += chunk;
            if (data.length > 1e7) {
                reject(new Error('too large'));
                req.destroy();
            }
        });
        req.on('end', () => {
            if (!data)
                return resolve(null);
            try {
                resolve(JSON.parse(data));
            }
            catch {
                reject(new Error('bad json'));
            }
        });
        req.on('error', reject);
    });
}
const server = http.createServer(async (req, res) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    const method = req.method || 'GET';
    const url = new URL(req.url || '/', 'http://localhost');
    if (method === 'GET' && url.pathname === '/api/projects') {
        return listProjectsHandler(res);
    }
    const match = /^\/api\/projects\/([^/]+)$/.exec(url.pathname);
    if (!match) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        return res.end('Not Found');
    }
    const projectId = decodeURIComponent(match[1]);
    if (method === 'GET')
        return showProjectHandler(res, projectId);
    if (method === 'PUT') {
        try {
            const body = await parseBody(req);
            return saveProjectHandler(res, projectId, body);
        }
        catch {
            return badRequest(res, 422);
        }
    }
    res.writeHead(405, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Method Not Allowed');
});
server.listen(PORT, '0.0.0.0');
