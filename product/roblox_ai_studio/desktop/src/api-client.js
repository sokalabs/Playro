(function initPlayroApiClient(root) {
  'use strict';

  const DEFAULT_API_BASE = 'http://127.0.0.1:8765';
  const TOKEN_HEADER = 'X-Playro-API-Token';

  function createPlayroApiClient(options = {}) {
    let apiBase = options.apiBase || options.baseUrl || DEFAULT_API_BASE;
    let apiToken = options.apiToken || options.token || '';
    const fetchImpl = options.fetch || ((...args) => root.fetch(...args));
    const EventSourceProvider = options.EventSource || (() => root.EventSource);

    function setConfig(config = {}) {
      if (Object.prototype.hasOwnProperty.call(config, 'apiBase') || Object.prototype.hasOwnProperty.call(config, 'baseUrl')) {
        apiBase = config.apiBase || config.baseUrl || DEFAULT_API_BASE;
      }
      if (Object.prototype.hasOwnProperty.call(config, 'apiToken') || Object.prototype.hasOwnProperty.call(config, 'token')) {
        apiToken = config.apiToken || config.token || '';
      }
    }

    function getConfig() {
      return { apiBase, apiToken };
    }

    function apiHeaders(extra = {}) {
      return apiToken ? { ...extra, [TOKEN_HEADER]: apiToken } : { ...extra };
    }

    function apiUrl(path) {
      if (/^https?:\/\//i.test(String(path))) return String(path);
      const normalizedPath = String(path || '').startsWith('/') ? String(path || '') : `/${path || ''}`;
      return `${apiBase}${normalizedPath}`;
    }

    function apiEventUrl(path) {
      const base = apiUrl(path);
      if (!apiToken) return base;
      const separator = base.includes('?') ? '&' : '?';
      return `${base}${separator}api_token=${encodeURIComponent(apiToken)}`;
    }

    function isEventSourceConstructor(candidate) {
      if (typeof candidate !== 'function') return false;
      if (/^class\s/.test(Function.prototype.toString.call(candidate))) return true;
      return Boolean(candidate.prototype && (
        typeof candidate.prototype.close === 'function'
        || typeof candidate.prototype.addEventListener === 'function'
      ));
    }

    function resolveEventSourceCtor() {
      if (isEventSourceConstructor(EventSourceProvider)) return EventSourceProvider;
      return typeof EventSourceProvider === 'function' ? EventSourceProvider() : EventSourceProvider;
    }

    async function parseResponseBody(response) {
      try {
        return await response.json();
      } catch (_jsonError) {
        try {
          const text = await response.text();
          return text ? { ok: response.ok, error: text } : { ok: response.ok };
        } catch (_textError) {
          return { ok: response.ok };
        }
      }
    }

    async function requestJson(path, options = {}) {
      const headers = apiHeaders(options.headers || {});
      const response = await fetchImpl(apiUrl(path), { ...options, headers });
      const data = await parseResponseBody(response);
      if (data && typeof data === 'object' && data.ok === undefined) data.ok = response.ok;
      return data;
    }

    function get(path, options = {}) {
      return requestJson(path, { ...options, method: options.method || 'GET' });
    }

    function post(path, body, options = {}) {
      return requestJson(path, {
        ...options,
        method: options.method || 'POST',
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
        body: JSON.stringify(body || {}),
      });
    }

    function getBuilds() { return get('/builds'); }
    function getDesktopAnalytics() { return get('/desktop/analytics'); }
    function getDesktopLogs() { return get('/desktop/logs'); }
    function getDesktopKeys() { return get('/desktop/keys'); }
    function getDesktopCapabilities() { return get('/desktop/capabilities'); }
    function getHealth() { return get('/health'); }
    function getProject(projectId) { return get(`/projects/${encodeURIComponent(projectId)}`); }
    function updateBuildStatus(payload) { return post('/builds/status', payload); }
    function setContinuousBuild(payload) { return post('/builds/continuous', payload); }
    function generateProject(payload) { return post('/generate', payload); }
    function refineProject(payload) { return post('/refine', payload); }
    function exportProject(projectId) { return requestJson(`/projects/${encodeURIComponent(projectId)}/export`, { method: 'POST' }); }

    function projectIdFromJob(job) {
      if (!job) return null;
      if (job.project_id) return job.project_id;
      if (job.project_path) return String(job.project_path).split(/[\\/]/).filter(Boolean).pop() || null;
      if (job.rojo_project) {
        const parts = String(job.rojo_project).split(/[\\/]/).filter(Boolean);
        return parts.length > 1 ? parts[parts.length - 2] : null;
      }
      return null;
    }

    function normalizeBuildCompletion(raw, buildId) {
      if (!raw) return null;
      const nested = raw.data || {};
      return {
        build_id: raw.build_id || nested.build_id || buildId,
        project_id: raw.project_id || nested.project_id || null,
        files: raw.files || nested.files || raw.generated_files || nested.generated_files || [],
        ok: raw.ok ?? nested.ok,
        status: raw.status || nested.status,
        prompt: raw.prompt || nested.prompt || '',
      };
    }

    async function firstBuildCompletion(waiters, options = {}) {
      const onWinner = options.onWinner;
      return new Promise(resolve => {
        let pending = waiters.length;
        let fallback = null;
        let settled = false;
        const finish = (value) => {
          if (settled) return;
          settled = true;
          resolve(value);
        };
        waiters.forEach(waiter => {
          Promise.resolve(waiter)
            .then(result => {
              if (result?.project_id) {
                if (onWinner) onWinner();
                finish(result);
                return;
              }
              fallback = fallback || result;
              pending -= 1;
              if (pending === 0) finish(fallback);
            })
            .catch(() => {
              pending -= 1;
              if (pending === 0) finish(fallback);
            });
        });
      });
    }

    function waitForBuildSSE(buildId, options = {}) {
      const maxWaitMs = options.maxWaitMs || 120000;
      const onStage = options.onStage || (() => {});
      const onComplete = options.onComplete || (() => {});
      const url = apiEventUrl(`/generate/${encodeURIComponent(buildId)}/events`);
      return new Promise(resolve => {
        let settled = false;
        let es = null;
        const finish = (value) => {
          if (settled) return;
          settled = true;
          try { es?.close(); } catch (_e) { /* ignore close errors */ }
          resolve(value);
        };
        const EventSourceCtor = resolveEventSourceCtor();
        es = new EventSourceCtor(url);
        const timer = root.setTimeout(() => finish(null), maxWaitMs);
        const complete = (event) => {
          try {
            const data = JSON.parse(event.data);
            const normalized = normalizeBuildCompletion(data, buildId);
            onComplete(normalized);
            root.clearTimeout(timer);
            finish(normalized);
          } catch (_e) { /* ignore malformed SSE data */ }
        };
        es.addEventListener('stage', onStage);
        es.addEventListener('complete', complete);
        es.addEventListener('error', () => {
          root.clearTimeout(timer);
          finish(null);
        });
        es.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.stage === 'complete') {
              complete(event);
              return;
            }
            if (data.stage === 'error') {
              root.clearTimeout(timer);
              finish(null);
              return;
            }
            onStage(event);
          } catch (_e) { /* ignore malformed SSE data */ }
        };
      });
    }

    async function waitForBuildComplete(buildId, projectId, options = {}) {
      const maxWaitMs = options.maxWaitMs || 120000;
      const shouldAbort = options.shouldAbort || (() => false);
      const getLastComplete = options.getLastComplete || (() => null);
      const sleep = options.sleep || (ms => new Promise(resolve => root.setTimeout(resolve, ms)));
      await sleep(50);
      const start = Date.now();
      const pollInterval = options.pollInterval || 2000;
      while (Date.now() - start < maxWaitMs) {
        const lastComplete = getLastComplete();
        if (shouldAbort() || lastComplete?.build_id === buildId) {
          return lastComplete?.build_id === buildId ? lastComplete : null;
        }
        try {
          const data = await getBuilds();
          const job = (data.builds || []).find(b => b.id === buildId);
          if (job && (job.status === 'completed' || job.status === 'failed')) {
            return { project_id: projectId || projectIdFromJob(job), files: job.generated_files || job.files || [], status: job.status };
          }
        } catch (_e) { /* poll continues */ }
        if (getLastComplete()?.build_id === buildId) return getLastComplete();
        await sleep(pollInterval);
      }
      return getLastComplete()?.build_id === buildId ? getLastComplete() : null;
    }

    return {
      apiEventUrl,
      apiHeaders,
      apiUrl,
      exportProject,
      firstBuildCompletion,
      generateProject,
      getBuilds,
      getConfig,
      getDesktopAnalytics,
      getDesktopCapabilities,
      getDesktopKeys,
      getDesktopLogs,
      getHealth,
      getProject,
      normalizeBuildCompletion,
      projectIdFromJob,
      refineProject,
      requestJson,
      setConfig,
      setContinuousBuild,
      updateBuildStatus,
      waitForBuildComplete,
      waitForBuildSSE,
    };
  }

  const api = { create: createPlayroApiClient, DEFAULT_API_BASE, TOKEN_HEADER };
  root.PlayroApiClient = api;
  if (root.window) root.window.PlayroApiClient = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : window);
