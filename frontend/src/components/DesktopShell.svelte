<script>
  import ArticleList from './ArticleList.svelte';
  import Reader from './Reader.svelte';
  import Sidebar from './Sidebar.svelte';
  import Toasts from './Toasts.svelte';
  import Icon from '../lib/Icon.svelte';
  import { app, openDialog, savePrefs, scopeTitle, scopeUnread, setQuery, loadArticles } from '../lib/state.svelte.js';

  let { sidebarHidden = $bindable(false) } = $props();
  let search = $state(app.query);

  const reading = $derived(app.selectedId !== null);
  const rail = $derived(reading && !app.prefs.sidebarPinned);
  const listVariant = $derived(app.prefs.view === 'list' ? 'list' : reading ? 'narrow' : 'wide');

  function setView(v) {
    app.prefs.view = v;
    savePrefs();
  }
  function submitSearch(e) {
    e.preventDefault();
    setQuery(search.trim());
  }
  function clearSearch() {
    search = '';
    setQuery('');
  }
  function toggleUnread() {
    app.prefs.unreadOnly = !app.prefs.unreadOnly;
    savePrefs();
    loadArticles(true);
  }
  $effect(() => {
    if (!app.query) search = '';
  });
</script>

<div class="desk dots">
  {#if !sidebarHidden}<Sidebar {rail} />{/if}

  <main class="main card">
    <header class="bar">
      <button class="icon-btn" onclick={() => (sidebarHidden = !sidebarHidden)} aria-label={sidebarHidden ? 'Show sidebar' : 'Hide sidebar'} title="Sidebar ([)">
        <Icon name="sidebar" stroke={1.7} />
      </button>
      <h1>{scopeTitle()}</h1>
      {#if app.scope.type !== 'saved' && !app.query}
        <span class="mono count">{scopeUnread()} unread</span>
      {:else if app.total !== null}
        <span class="mono count">{app.total} {app.total === 1 ? 'article' : 'articles'}</span>
      {/if}
      <div class="grow"></div>
      <div class="seg" role="group" aria-label="View">
        <button aria-pressed={app.prefs.view === 'magazine'} onclick={() => setView('magazine')}><Icon name="magazine" size={15} />Magazine</button>
        <button aria-pressed={app.prefs.view === 'list'} onclick={() => setView('list')}><Icon name="list" size={15} />List</button>
      </div>
      <form class="search" role="search" onsubmit={submitSearch}>
        <Icon name="search" size={15} />
        <label class="sr-only" for="search">Search articles</label>
        <input id="search" type="search" placeholder="Search" bind:value={search} />
        {#if app.query}
          <button type="button" class="clear" onclick={clearSearch} aria-label="Clear search"><Icon name="close" size={13} /></button>
        {:else}
          <kbd>/</kbd>
        {/if}
      </form>
      <button class="btn primary" onclick={() => openDialog('add')}><Icon name="plus" size={14} stroke={2.2} />Add source</button>
    </header>

    {#if reading}
      <div class="split">
        <div class="pane">
          <ArticleList variant={listVariant} />
        </div>
        <Reader />
      </div>
    {:else}
      <div class="scroll">
        <div class="inner" class:wide={app.prefs.view === 'list'}>
          <div class="subbar">
            {#if app.scope.type !== 'saved' && !app.query}
              <label class="toggle"><input type="checkbox" role="switch" checked={app.prefs.unreadOnly} onchange={toggleUnread} />Unread only</label>
              <button class="btn small" onclick={() => openDialog('markall')} disabled={!scopeUnread()}><Icon name="checks" size={15} stroke={1.9} />Mark all read…</button>
            {/if}
          </div>
          <ArticleList variant={listVariant} />
        </div>
      </div>
    {/if}
  </main>
</div>
<Toasts />

<style>
  .desk { height: 100dvh; padding: 20px; display: flex; gap: 20px; align-items: stretch; overflow: hidden; }
  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
  .bar { padding: 14px 20px; border-bottom: 1px solid var(--divider); display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
  h1 { margin: 0; font-size: 26px; font-weight: 600; letter-spacing: -0.02em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 40%; }
  .count { color: var(--label); white-space: nowrap; }
  .grow { flex: 1; }
  .search { display: flex; align-items: center; gap: 8px; padding: 0 10px 0 12px; height: 36px; border-radius: 10px; background: var(--field); width: 220px; color: var(--faint); }
  .search input { border: 0; background: transparent; height: 34px; padding: 0; font-size: 13.5px; color: var(--text); }
  .search input::-webkit-search-cancel-button { display: none; }
  kbd { font-family: var(--mono); font-size: 11px; border: 1px solid var(--border); border-radius: 4px; padding: 0 5px; color: var(--faint); }
  .clear { border: 0; background: transparent; color: var(--faint); display: flex; padding: 4px; }

  .scroll { flex: 1; overflow-y: auto; }
  .inner { max-width: 880px; margin: 0 auto; padding: 4px 24px 96px; }
  .inner.wide { max-width: 1100px; }
  .subbar { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 12px 4px; min-height: 58px; }
  .toggle { display: flex; align-items: center; gap: 8px; font-size: 13.5px; cursor: pointer; }
  .toggle input { width: 16px; height: 16px; accent-color: var(--text); }
  .btn.small { height: 34px; padding: 0 12px; font-size: 13px; }

  .split { flex: 1; display: flex; min-height: 0; }
  .pane { flex: 0 1 380px; min-width: 300px; overflow-y: auto; border-right: 1px solid var(--divider); }
  .pane :global(.day) { padding-left: 20px; }

  @media (max-width: 1180px) {
    .search { width: 160px; }
    .pane { flex-basis: 320px; min-width: 260px; }
  }
</style>
