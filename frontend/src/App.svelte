<script>
  import AddSource from './components/AddSource.svelte';
  import DesktopShell from './components/DesktopShell.svelte';
  import FeedSettings from './components/FeedSettings.svelte';
  import Login from './components/Login.svelte';
  import MobileShell from './components/MobileShell.svelte';
  import Settings from './components/Settings.svelte';
  import SmallDialogs from './components/SmallDialogs.svelte';
  import {
    app, applyReader, applyTheme, checkAuth, closeArticle, connectEvents, loadArticles, loadHome, loadTree,
    markRead, openArticle, openDialog, refreshNow, savePrefs, setScope, shareArticle, toggleSaved,
  } from './lib/state.svelte.js';

  const mq = window.matchMedia('(max-width: 820px)');
  let mobile = $state(mq.matches);
  mq.addEventListener('change', (e) => (mobile = e.matches));

  let sidebarHidden = $state(false);
  let started = false;

  applyTheme();
  applyReader();
  checkAuth();

  $effect(() => {
    if (app.authed && !started) {
      started = true;
      start();
    }
    if (app.authed === false) started = false;
  });

  async function start() {
    await Promise.all([loadTree(), loadHome(true)]);
    const params = new URLSearchParams(location.search);
    const add = params.get('add');
    if (add) {
      history.replaceState(null, '', '/');
      openDialog('add', { url: add });
    }
    // Reopen where you left off if the last visit was recent (configurable in Settings).
    const last = app.prefs.lastScope;
    if (app.home?.resume && last) {
      app.scope = { type: last.type, id: last.id ?? null };
      await loadArticles(true);
      if (app.prefs.lastArticle) openArticle(app.prefs.lastArticle);
    } else {
      app.scope = { type: 'all', id: null };
      app.prefs.lastArticle = null;
      savePrefs();
      loadArticles(true);
    }
    connectEvents();
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        loadTree();
        loadHome(true);
      }
    });
  }

  // ---------------------------------------------------------------- keyboard shortcuts
  let pendingG = false;
  function step(delta) {
    const items = app.items;
    if (!items.length) return;
    const idx = items.findIndex((i) => i.id === app.selectedId);
    const next = idx === -1 ? (delta > 0 ? 0 : items.length - 1) : Math.min(items.length - 1, Math.max(0, idx + delta));
    if (items[next] && items[next].id !== app.selectedId) {
      openArticle(items[next].id);
      requestAnimationFrame(() => document.querySelector('[aria-current="true"]')?.scrollIntoView({ block: 'nearest' }));
    }
  }

  function onKey(e) {
    if (!app.authed || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if (t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName))) {
      if (e.key === 'Escape') t.blur();
      return;
    }
    if (app.dialog) return;
    const sel = app.article ?? app.items.find((i) => i.id === app.selectedId);
    const k = e.key;
    if (pendingG) {
      pendingG = false;
      if (k === 'a') return setScope('all');
      if (k === 's') return setScope('saved');
    }
    switch (k) {
      case 'j': return step(1);
      case 'k': return step(-1);
      case 'o':
      case 'Enter':
        if (!app.selectedId && app.items[0]) openArticle(app.items[0].id);
        return;
      case 'Escape': return closeArticle();
      case 'v': if (sel?.url) window.open(sel.url, '_blank', 'noopener,noreferrer'); return;
      case 'c': if (sel) shareArticle(sel); return;
      case 's': if (sel) toggleSaved(sel.id); return;
      case 'm': if (sel) markRead(sel.id, !sel.is_read, { undo: true }); return;
      case 'A': return openDialog('markall');
      case 'r': return refreshNow();
      case 'a': return openDialog('add');
      case '/':
        e.preventDefault();
        document.getElementById('search')?.focus();
        return;
      case 'g': pendingG = true; setTimeout(() => (pendingG = false), 1200); return;
      case '[': sidebarHidden = !sidebarHidden; return;
      case '1': app.prefs.view = 'magazine'; savePrefs(); return;
      case '2': app.prefs.view = 'list'; savePrefs(); return;
      case '?': return openDialog('shortcuts');
    }
  }
</script>

<svelte:window onkeydown={onKey} />

{#if app.authed === null}
  <div class="boot dots" aria-busy="true"></div>
{:else if !app.authed}
  <Login />
{:else}
  {#if mobile}
    <MobileShell />
  {:else}
    <DesktopShell bind:sidebarHidden />
  {/if}

  {#if app.dialog?.name === 'add'}
    <AddSource {...app.dialog.props} />
  {:else if app.dialog?.name === 'settings'}
    <Settings {...app.dialog.props} />
  {:else if app.dialog?.name === 'feed'}
    <FeedSettings {...app.dialog.props} />
  {:else if app.dialog}
    <SmallDialogs name={app.dialog.name} />
  {/if}
{/if}

<style>
  .boot { min-height: 100dvh; }
</style>
