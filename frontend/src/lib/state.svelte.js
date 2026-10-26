// App state with Svelte 5 runes. One object, mutated in place; components read what they need.
import { api, setUnauthorizedHandler } from './api.js';

const PREFS_KEY = 'steep.prefs';
const DEFAULT_PREFS = {
  theme: 'system', // system | light | dark
  view: 'magazine', // magazine | list
  unreadOnly: true,
  sidebarPinned: false, // keep the full sidebar even while reading
  readerSize: 18,
  readerFont: 'sans', // sans | serif
  readerWidth: 'normal', // narrow | normal | wide
  excerptLines: 2, // 0 | 2 | 3
  lastScope: null,
  lastArticle: null,
};

function loadPrefs() {
  try {
    return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export const app = $state({
  authed: null, // null while checking
  version: '',
  tree: null,
  home: null,
  scope: { type: 'all', id: null },
  query: '',
  items: [],
  cursor: null,
  total: null,
  loading: false,
  loadError: '',
  hasNew: false,
  selectedId: null,
  article: null,
  articleLoading: false,
  dialog: null, // { name, props }
  toasts: [],
  prefs: loadPrefs(),
  online: true,
});

let toastSeq = 0;
let listToken = 0;

export function savePrefs() {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(app.prefs));
  } catch {}
  applyTheme();
  applyReader();
}

export function applyTheme() {
  const root = document.documentElement;
  if (app.prefs.theme === 'system') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', app.prefs.theme);
}

export function applyReader() {
  const s = document.documentElement.style;
  s.setProperty('--reader-size', `${app.prefs.readerSize}px`);
  s.setProperty('--reader-font', app.prefs.readerFont === 'serif' ? 'var(--serif)' : 'var(--sans)');
  s.setProperty('--reader-width', { narrow: '600px', normal: '680px', wide: '800px' }[app.prefs.readerWidth] || '680px');
}

// ---------------------------------------------------------------- toasts

export function toast(message, { undo, duration = 6000, tone } = {}) {
  const id = ++toastSeq;
  app.toasts = [...app.toasts.slice(-2), { id, message, undo, tone }];
  setTimeout(() => dismissToast(id), duration);
  return id;
}

export function dismissToast(id) {
  app.toasts = app.toasts.filter((t) => t.id !== id);
}

export function fail(err) {
  toast(err?.message || String(err), { tone: 'error' });
}

// ---------------------------------------------------------------- auth

setUnauthorizedHandler(() => {
  app.authed = false;
});

export async function checkAuth() {
  try {
    const me = await api.me();
    app.version = me.version;
    app.authed = me.authenticated;
  } catch {
    app.authed = false;
    app.online = false;
  }
}

export async function login(password) {
  await api.login(password);
  app.authed = true;
}

export async function logout() {
  await api.logout();
  app.authed = false;
  app.tree = null;
  app.items = [];
  app.article = null;
}

// ---------------------------------------------------------------- tree and scope

let treeTimer = null;
export async function loadTree() {
  try {
    app.tree = await api.tree();
    app.online = true;
  } catch (err) {
    if (err.status === 0) app.online = false;
  }
}

export function reloadTreeSoon(delay = 400) {
  clearTimeout(treeTimer);
  treeTimer = setTimeout(loadTree, delay);
}

export async function loadHome(open = false) {
  try {
    app.home = await api.home(open);
  } catch {}
}

export function folders() {
  return app.tree?.folders ?? [];
}

export function findFeed(id) {
  if (!app.tree) return null;
  for (const f of app.tree.folders) {
    const hit = f.feeds.find((x) => x.id === id);
    if (hit) return hit;
  }
  return app.tree.uncategorized.find((x) => x.id === id) ?? null;
}

export function scopeTitle(scope = app.scope) {
  if (app.query) return `Search: ${app.query}`;
  if (scope.type === 'all') return 'All Articles';
  if (scope.type === 'saved') return 'Saved';
  if (scope.type === 'folder') {
    if (!scope.id) return 'Uncategorized';
    return folders().find((f) => f.id === scope.id)?.name ?? 'Folder';
  }
  if (scope.type === 'feed') return findFeed(scope.id)?.title ?? 'Feed';
  return '';
}

export function scopeUnread(scope = app.scope) {
  const t = app.tree;
  if (!t) return 0;
  if (scope.type === 'all') return t.unread;
  if (scope.type === 'saved') return t.saved;
  if (scope.type === 'folder') {
    if (!scope.id) return t.uncategorized.reduce((n, f) => n + (f.muted ? 0 : f.unread), 0);
    return folders().find((f) => f.id === scope.id)?.unread ?? 0;
  }
  if (scope.type === 'feed') return findFeed(scope.id)?.unread ?? 0;
  return 0;
}

export function setScope(type, id = null) {
  app.scope = { type, id };
  app.query = '';
  app.prefs.lastScope = { type, id };
  savePrefs();
  closeArticle();
  loadArticles(true);
}

export function setQuery(q) {
  app.query = q;
  loadArticles(true);
}

// ---------------------------------------------------------------- article list

function listParams() {
  const s = app.scope;
  return {
    scope: s.type,
    id: s.id ?? undefined,
    unread: app.query || s.type === 'saved' ? false : app.prefs.unreadOnly,
    q: app.query || undefined,
  };
}

export async function loadArticles(reset = false) {
  const token = ++listToken;
  if (reset) {
    app.items = [];
    app.cursor = null;
    app.total = null;
    app.hasNew = false;
  }
  app.loading = true;
  app.loadError = '';
  try {
    const page = await api.articles({ ...listParams(), cursor: reset ? undefined : app.cursor || undefined });
    if (token !== listToken) return;
    app.items = reset ? page.items : [...app.items, ...page.items.filter((i) => !app.items.some((x) => x.id === i.id))];
    app.cursor = page.next_cursor;
    if (page.total !== null && page.total !== undefined) app.total = page.total;
  } catch (err) {
    if (token === listToken) app.loadError = err.message;
  } finally {
    if (token === listToken) app.loading = false;
  }
}

export function loadMore() {
  if (app.cursor && !app.loading) loadArticles(false);
}

function patchItem(id, patch) {
  const item = app.items.find((i) => i.id === id);
  if (item) Object.assign(item, patch);
  if (app.article?.id === id) Object.assign(app.article, patch);
}

// ---------------------------------------------------------------- reading

export async function openArticle(id) {
  app.selectedId = id;
  app.articleLoading = true;
  app.prefs.lastArticle = id;
  savePrefs();
  try {
    const a = await api.article(id);
    if (app.selectedId !== id) return;
    app.article = a;
    if (!a.is_read) markRead(id, true, { quiet: true });
  } catch (err) {
    fail(err);
  } finally {
    app.articleLoading = false;
  }
}

export function closeArticle() {
  app.article = null;
  app.selectedId = null;
  app.prefs.lastArticle = null;
  savePrefs();
}

export async function markRead(id, value = true, { quiet = false, undo = false } = {}) {
  patchItem(id, { is_read: value });
  try {
    await api.setRead(id, value);
    reloadTreeSoon();
    if (undo) toast(value ? 'Marked as read' : 'Marked as unread', { undo: () => markRead(id, !value) });
  } catch (err) {
    patchItem(id, { is_read: !value });
    if (!quiet) fail(err);
  }
}

export async function toggleSaved(id, { undo = false } = {}) {
  const item = app.items.find((i) => i.id === id) || (app.article?.id === id ? app.article : null);
  const value = !(item?.is_saved ?? false);
  patchItem(id, { is_saved: value });
  try {
    await api.setSaved(id, value);
    reloadTreeSoon();
    toast(value ? 'Saved' : 'Removed from Saved', undo ? { undo: () => toggleSaved(id) } : {});
  } catch (err) {
    patchItem(id, { is_saved: !value });
    fail(err);
  }
}

export async function markAllRead(olderThan = 'none') {
  try {
    const res = await api.markRead({ scope: app.scope.type, id: app.scope.id, older_than: olderThan, q: app.query || undefined });
    const ids = new Set(res.ids);
    for (const item of app.items) if (ids.has(item.id)) item.is_read = true;
    reloadTreeSoon(0);
    const what = olderThan === '1d' ? ' older than a day' : olderThan === '1w' ? ' older than a week' : '';
    toast(`${res.count} article${res.count === 1 ? '' : 's'}${what} marked as read`, {
      undo: async () => {
        await api.markUnread(res.ids);
        for (const item of app.items) if (ids.has(item.id)) item.is_read = false;
        reloadTreeSoon(0);
      },
    });
    if (app.prefs.unreadOnly && !app.query) loadArticles(true);
  } catch (err) {
    fail(err);
  }
}

/** Share = the original article URL only (F-25). */
export async function shareArticle(article, { preferSheet = false } = {}) {
  const url = article?.url;
  if (!url) return toast('This article has no original link.');
  if (preferSheet && navigator.share) {
    try {
      await navigator.share({ url });
      return;
    } catch (err) {
      if (err?.name === 'AbortError') return;
    }
  }
  try {
    await navigator.clipboard.writeText(url);
    toast(`Link copied · ${url.replace(/^https?:\/\/(www\.)?/, '').slice(0, 48)}`);
  } catch {
    toast(url, { duration: 10000 });
  }
}

export async function refreshNow() {
  try {
    const r = await api.refresh({ scope: app.scope.type === 'saved' ? 'all' : app.scope.type, id: app.scope.id });
    toast(`Checking ${r.queued} feed${r.queued === 1 ? '' : 's'}…`, { duration: 2500 });
  } catch (err) {
    fail(err);
  }
}

// ---------------------------------------------------------------- live updates

let source = null;
export function connectEvents() {
  if (source) source.close();
  source = new EventSource('/api/events');
  source.onmessage = (e) => {
    let msg;
    try {
      msg = JSON.parse(e.data);
    } catch {
      return;
    }
    if (msg.type === 'articles' || msg.type === 'sync' || msg.type === 'tree' || msg.type === 'counts') reloadTreeSoon();
    if (msg.type === 'articles' && msg.new > 0) {
      if (!app.items.length && !app.loading) loadArticles(true);
      else app.hasNew = true;
      loadHome(false);
    }
  };
  source.onerror = () => {
    app.online = navigator.onLine;
  };
}

// ---------------------------------------------------------------- dialogs

export function openDialog(name, props = {}) {
  app.dialog = { name, props };
}

export function closeDialog() {
  app.dialog = null;
}
