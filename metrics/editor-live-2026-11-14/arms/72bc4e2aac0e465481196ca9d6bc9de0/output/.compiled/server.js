"use strict";
// @ts-nocheck
const http = require('node:http');
const process = require('node:process');
const PORT = Number(process.env.PORT || 8080);
const UPSTREAM_URL = process.env.UPSTREAM_URL;
const UPSTREAM_API_KEY = process.env.UPSTREAM_API_KEY;
function sendJson(res, status, body) {
    const data = JSON.stringify(body);
    res.writeHead(status, {
        'content-type': 'application/json; charset=utf-8',
        'content-length': Buffer.byteLength(data),
    });
    res.end(data);
}
function isObject(v) {
    return !!v && typeof v === 'object' && !Array.isArray(v);
}
function isNonblankString(v) {
    return typeof v === 'string' && v.trim().length > 0;
}
function isIsoDate(v) {
    return typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v + 'T00:00:00Z'));
}
const SECTORS = new Set(['energy', 'mining', 'water', 'transport', 'oil_and_gas', 'ict']);
const STAGES = new Set(['idea', 'feasibility', 'tender', 'financing', 'construction', 'operation', 'cancelled']);
const COMPANY_ROLES = new Set(['owner', 'developer', 'epc_contractor', 'financier', 'consultant']);
function validateKeyDate(v) {
    return isObject(v) && Object.keys(v).length === 2 && isNonblankString(v.label) && isIsoDate(v.date);
}
function validateEditableFields(v) {
    return (isObject(v) &&
        Object.keys(v).length === 5 &&
        isNonblankString(v.name) &&
        SECTORS.has(v.sector) &&
        isNonblankString(v.country) &&
        STAGES.has(v.stage) &&
        Array.isArray(v.key_dates) &&
        v.key_dates.every(validateKeyDate));
}
function validateSaveRequest(v) {
    return isObject(v) && Object.keys(v).length === 2 && validateEditableFields(v.base) && validateEditableFields(v.proposed);
}
function validateLinkedCompany(v) {
    return isObject(v) && Object.keys(v).length === 2 && isNonblankString(v.name) && COMPANY_ROLES.has(v.role);
}
function toSummary(p) {
    return { id: p.id, name: p.name, sector: p.sector, country: p.country, stage: p.stage };
}
function toDetail(p) {
    return { id: p.id, name: p.name, sector: p.sector, country: p.country, stage: p.stage, key_dates: p.key_dates };
}
function same(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
}
function choose(base, proposed, current) {
    if (same(proposed, base))
        return { value: current, conflict: false };
    if (!same(current, base) && !same(current, proposed))
        return { value: current, conflict: true };
    return { value: proposed, conflict: false };
}
function mergeEdit(base, proposed, current) {
    const conflicts = [];
    const name = choose(base.name, proposed.name, current.name);
    const sector = choose(base.sector, proposed.sector, current.sector);
    const country = choose(base.country, proposed.country, current.country);
    const stage = choose(base.stage, proposed.stage, current.stage);
    const key_dates = choose(base.key_dates, proposed.key_dates, current.key_dates);
    if (name.conflict)
        conflicts.push('name');
    if (sector.conflict)
        conflicts.push('sector');
    if (country.conflict)
        conflicts.push('country');
    if (stage.conflict)
        conflicts.push('stage');
    if (key_dates.conflict)
        conflicts.push('key_dates');
    const merged = { name: name.value, sector: sector.value, country: country.value, stage: stage.value, key_dates: key_dates.value };
    return { merged, conflicts, changed: !same(merged, current) };
}
async function readBody(req) {
    let body = '';
    for await (const chunk of req)
        body += chunk;
    return body;
}
async function upstreamFetch(path, init = {}) {
    if (!UPSTREAM_URL || !UPSTREAM_API_KEY)
        throw new Error('upstream_unavailable');
    const url = new URL(path, UPSTREAM_URL);
    const headers = Object.assign({}, init.headers || {}, { 'X-Api-Key': UPSTREAM_API_KEY });
    return fetch(url, { ...init, headers });
}
async function upstreamJson(path, init = {}) {
    let response;
    try {
        response = await upstreamFetch(path, init);
    }
    catch {
        throw new Error('upstream_unavailable');
    }
    return response;
}
async function listProjects() {
    const r = await upstreamJson('/projects');
    if (r.status === 404)
        throw new Error('not_found');
    if (!r.ok)
        throw new Error('upstream_unavailable');
    const data = await r.json().catch(() => null);
    if (!Array.isArray(data))
        throw new Error('upstream_unavailable');
    return data.map(toSummary);
}
async function getProject(id) {
    const r = await upstreamJson('/projects/' + encodeURIComponent(id));
    if (r.status === 404)
        throw new Error('not_found');
    if (!r.ok)
        throw new Error('upstream_unavailable');
    const data = await r.json().catch(() => null);
    if (!isObject(data))
        throw new Error('upstream_unavailable');
    return {
        id: data.id,
        name: data.name,
        sector: data.sector,
        country: data.country,
        stage: data.stage,
        key_dates: data.key_dates,
        linked_companies: Array.isArray(data.linked_companies) ? data.linked_companies.filter(validateLinkedCompany) : [],
    };
}
async function putProject(id, fields, linkedCompanies) {
    const r = await upstreamJson('/projects/' + encodeURIComponent(id), {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ ...fields, linked_companies: linkedCompanies }),
    });
    if (r.status === 404)
        throw new Error('not_found');
    if (r.status === 504)
        throw new Error('uncertain');
    if (!r.ok)
        throw new Error('uncertain');
    const data = await r.json().catch(() => null);
    if (!isObject(data))
        throw new Error('uncertain');
    return data;
}
async function handle(req, res) {
    const url = new URL(req.url, 'http://127.0.0.1');
    const path = url.pathname;
    if (req.method === 'GET' && path === '/api/projects') {
        try {
            const projects = await listProjects();
            return sendJson(res, 200, { projects });
        }
        catch (e) {
            if (e && e.message === 'not_found')
                return sendJson(res, 404, { code: 'project_not_found' });
            return sendJson(res, 502, { code: 'upstream_unavailable' });
        }
    }
    const m = path.match(/^\/api\/projects\/([^/]+)$/);
    if (m && req.method === 'GET') {
        try {
            const project = await getProject(decodeURIComponent(m[1]));
            return sendJson(res, 200, { project: toDetail(project) });
        }
        catch (e) {
            if (e && e.message === 'not_found')
                return sendJson(res, 404, { code: 'project_not_found' });
            return sendJson(res, 502, { code: 'upstream_unavailable' });
        }
    }
    if (m && req.method === 'PUT') {
        let parsed;
        try {
            const raw = await readBody(req);
            parsed = JSON.parse(raw || '{}');
        }
        catch {
            return sendJson(res, 422, { detail: 'Validation error' });
        }
        if (!validateSaveRequest(parsed))
            return sendJson(res, 422, { detail: 'Validation error' });
        const id = decodeURIComponent(m[1]);
        let current;
        try {
            current = await getProject(id);
        }
        catch (e) {
            if (e && e.message === 'not_found')
                return sendJson(res, 404, { code: 'project_not_found' });
            return sendJson(res, 502, { code: 'upstream_unavailable' });
        }
        const result = mergeEdit(parsed.base, parsed.proposed, current);
        if (result.conflicts.length) {
            return sendJson(res, 409, {
                code: 'edit_conflict',
                current: toDetail(current),
                conflicting_fields: result.conflicts,
            });
        }
        if (!result.changed) {
            return sendJson(res, 200, { project: toDetail(current) });
        }
        try {
            const saved = await putProject(id, result.merged, current.linked_companies);
            return sendJson(res, 200, { project: toDetail(saved) });
        }
        catch (e) {
            if (e && e.message === 'not_found')
                return sendJson(res, 404, { code: 'project_not_found' });
            let observed = null;
            try {
                observed = toDetail(await getProject(id));
            }
            catch { }
            return sendJson(res, 504, { code: 'write_uncertain', observed });
        }
    }
    return sendJson(res, 404, { code: 'not_found' });
}
http.createServer((req, res) => {
    handle(req, res).catch(() => sendJson(res, 502, { code: 'upstream_unavailable' }));
}).listen(PORT, '0.0.0.0');
