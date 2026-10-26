// Thin fetch wrapper. Every write carries X-Steep: 1, which the server requires as CSRF protection.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(method, path, body, { raw = false } = {}) {
  const opts = { method, headers: { 'X-Steep': '1' }, credentials: 'same-origin' };
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch {
    throw new ApiError(0, "Can't reach your server. Check the connection.");
  }
  if (res.status === 401 && !path.startsWith('/api/login')) onUnauthorized();
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === 'string') message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d) => d.msg).join('; ');
    } catch {}
    throw new ApiError(res.status, message);
  }
  if (raw) return res;
  const type = res.headers.get('content-type') || '';
  return type.includes('json') ? res.json() : res.text();
}

const qs = (params) => {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') sp.set(k, String(v));
  const s = sp.toString();
  return s ? `?${s}` : '';
};

export const api = {
  me: () => request('GET', '/api/me'),
  login: (password) => request('POST', '/api/login', { password }),
  logout: () => request('POST', '/api/logout'),
  tree: () => request('GET', '/api/tree'),
  home: (open = false) => request('GET', `/api/home${open ? '?open=true' : ''}`),
  dismissContinue: () => request('POST', '/api/home/dismiss-continue'),
  articles: (params) => request('GET', `/api/articles${qs(params)}`),
  article: (id) => request('GET', `/api/articles/${id}`),
  setRead: (id, value) => request('POST', `/api/articles/${id}/read`, { value }),
  setSaved: (id, value) => request('POST', `/api/articles/${id}/save`, { value }),
  setProgress: (id, progress) => request('POST', `/api/articles/${id}/progress`, { progress }),
  markRead: (body) => request('POST', '/api/mark-read', body),
  markUnread: (ids) => request('POST', '/api/mark-unread', { ids }),
  discover: (url) => request('POST', '/api/discover', { url }),
  addFeed: (body) => request('POST', '/api/feeds', body),
  updateFeed: (id, body) => request('PATCH', `/api/feeds/${id}`, body),
  deleteFeed: (id) => request('DELETE', `/api/feeds/${id}`),
  restoreFeed: (id) => request('POST', `/api/feeds/${id}/restore`),
  health: () => request('GET', '/api/feeds/health'),
  createFolder: (name) => request('POST', '/api/folders', { name }),
  updateFolder: (id, body) => request('PATCH', `/api/folders/${id}`, body),
  deleteFolder: (id) => request('DELETE', `/api/folders/${id}`),
  importOpml: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return request('POST', '/api/opml/import', fd);
  },
  refresh: (body) => request('POST', '/api/refresh', body),
  settings: () => request('GET', '/api/settings'),
  saveSettings: (body) => request('PATCH', '/api/settings', body),
};
