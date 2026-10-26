<script>
  import ArticleList from './ArticleList.svelte';
  import Reader from './Reader.svelte';
  import Sidebar from './Sidebar.svelte';
  import Toasts from './Toasts.svelte';
  import Icon from '../lib/Icon.svelte';
  import Thumb from '../lib/Thumb.svelte';
  import { api } from '../lib/api.js';
  import { clockLabel, agoLabel } from '../lib/format.js';
  import {
    app, loadArticles, openArticle, openDialog, refreshNow, savePrefs, scopeTitle, scopeUnread, setQuery, setScope,
  } from '../lib/state.svelte.js';

  let drawer = $state(false);
  let menu = $state(false);
  let searching = $state(false);
  let search = $state('');

  const isHome = $derived(app.scope.type === 'all' && !app.query);
  const filter = $derived(app.scope.type === 'saved' ? 'saved' : app.prefs.unreadOnly ? 'unread' : 'all');

  function setFilter(f) {
    if (f === 'saved') return setScope('saved');
    app.prefs.unreadOnly = f === 'unread';
    savePrefs();
    if (app.scope.type === 'saved') setScope('all');
    else loadArticles(true);
  }
  function submitSearch(e) {
    e.preventDefault();
    setQuery(search.trim());
  }
  function endSearch() {
    searching = false;
    search = '';
    if (app.query) setQuery('');
  }
  async function dismissContinue() {
    app.home.continue = null;
    api.dismissContinue().catch(() => {});
  }
  function act(fn) {
    menu = false;
    fn();
  }

  // Pull to refresh at the top of the list.
  let pullStart = null;
  let pull = $state(0);
  function touchStart(e) {
    pullStart = window.scrollY <= 0 ? e.touches[0].clientY : null;
  }
  function touchMove(e) {
    if (pullStart === null) return;
    pull = Math.max(0, Math.min(90, (e.touches[0].clientY - pullStart) * 0.5));
  }
  function touchEnd() {
    if (pull > 60) {
      refreshNow();
      setTimeout(() => loadArticles(true), 3000);
    }
    pull = 0;
    pullStart = null;
  }
  const chips = $derived(app.tree?.folders ?? []);
</script>

<div class="mob" aria-hidden={app.selectedId !== null} ontouchstart={touchStart} ontouchmove={touchMove} ontouchend={touchEnd} role="presentation">
  {#if pull > 0}<div class="pull mono" style:height="{pull}px">{pull > 60 ? 'Release to refresh' : 'Pull to refresh'}</div>{/if}

  <header class="top">
    {#if searching}
      <form class="search-row" role="search" onsubmit={submitSearch}>
        <label class="sr-only" for="m-search">Search articles</label>
        <!-- svelte-ignore a11y_autofocus -->
        <input id="m-search" type="search" placeholder="Search all articles" bind:value={search} autofocus enterkeyhint="search" />
        <button type="button" class="text-btn" onclick={endSearch}>Cancel</button>
      </form>
    {:else if isHome}
      <div class="home-top">
        <button class="brand" onclick={() => (drawer = true)} aria-label="Show sources"><span class="mark"><i></i><i></i></span>Steep</button>
        <div class="right">
          <button class="icon-btn big" onclick={() => (searching = true)} aria-label="Search"><Icon name="search" size={20} /></button>
          <button class="icon-btn big" onclick={() => openDialog('settings')} aria-label="Settings"><Icon name="settings" size={19} stroke={1.7} /></button>
        </div>
      </div>
      <h1>All Articles</h1>
      <div class="mono status">
        {#if app.home}{app.home.new} new since {clockLabel(app.home.since)} · {/if}{app.online ? `synced ${agoLabel(app.tree?.last_sync)}` : 'offline'}
      </div>
    {:else}
      <div class="sub-top">
        <button class="icon-btn big" onclick={() => (drawer = true)} aria-label="Show sources"><Icon name="sidebar" size={20} stroke={1.7} /></button>
        <h1 class="small">{scopeTitle()}</h1>
        {#if app.scope.type !== 'saved' && !app.query}<span class="mono count">{scopeUnread()}</span>{/if}
        <div class="grow"></div>
        <button class="icon-btn big" onclick={() => (searching = true)} aria-label="Search"><Icon name="search" size={20} /></button>
      </div>
    {/if}
  </header>

  {#if !searching && (isHome || app.scope.type === 'folder' || app.scope.type === 'feed')}
    <nav class="chips" aria-label="Folders">
      <button class="chip" class:on={isHome} onclick={() => setScope('all')}>All<span class="mono n">{app.tree?.unread ?? ''}</span></button>
      {#each chips as f (f.id)}
        <button class="chip" class:on={app.scope.type === 'folder' && app.scope.id === f.id} onclick={() => setScope('folder', f.id)}>{f.name}<span class="mono n">{f.unread || ''}</span></button>
      {/each}
      <button class="chip" class:on={app.scope.type === 'saved'} onclick={() => setScope('saved')}>Saved<span class="mono n">{app.tree?.saved || ''}</span></button>
    </nav>
  {/if}

  <div class="body">
    {#if isHome && app.home?.continue}
      {@const c = app.home.continue}
      <div class="continue">
        <button class="cont-main" onclick={() => openArticle(c.id)}>
          <Thumb src={c.image_url} title={c.feed_title} size={44} />
          <span class="cont-text">
            <span class="mono cont-label">Continue reading · {Math.round((c.read_progress ?? 0) * 100)}%</span>
            <span class="cont-title">{c.title}</span>
            <span class="bar" aria-hidden="true"><span style:width="{Math.round((c.read_progress ?? 0) * 100)}%"></span></span>
          </span>
        </button>
        <button class="icon-btn" onclick={dismissContinue} aria-label="Dismiss"><Icon name="close" size={14} /></button>
      </div>
    {/if}
    <ArticleList variant={app.prefs.view === 'list' ? 'list' : 'mobile'} />
  </div>

  <nav class="toolbar" aria-label="List controls">
    <div class="seg filter" role="group" aria-label="Filter">
      <button aria-pressed={filter === 'unread'} onclick={() => setFilter('unread')}>Unread</button>
      <button aria-pressed={filter === 'all'} onclick={() => setFilter('all')}>All</button>
      <button aria-pressed={filter === 'saved'} onclick={() => setFilter('saved')}>Saved</button>
    </div>
    <button class="icon-btn big" onclick={() => (menu = true)} aria-label="More: mark all read, add source, refresh" aria-haspopup="menu"><Icon name="more" size={22} /></button>
  </nav>
</div>

{#if app.selectedId !== null}
  <Reader mobile />
{/if}

{#if drawer}
  <div class="scrim" role="presentation" onclick={() => (drawer = false)}></div>
  <div class="drawer" role="dialog" aria-modal="true" aria-label="Sources">
    <Sidebar onnavigate={() => (drawer = false)} />
  </div>
{/if}

{#if menu}
  <div class="scrim" role="presentation" onclick={() => (menu = false)}></div>
  <div class="sheet" role="menu" aria-label="More actions">
    <button role="menuitem" onclick={() => act(() => openDialog('markall'))} disabled={!scopeUnread()}><Icon name="checks" />Mark all read…</button>
    <button role="menuitem" onclick={() => act(() => openDialog('add'))}><Icon name="plus" />Add source</button>
    <button role="menuitem" onclick={() => act(refreshNow)}><Icon name="refresh" />Refresh</button>
    <button role="menuitem" onclick={() => act(() => { app.prefs.view = app.prefs.view === 'list' ? 'magazine' : 'list'; savePrefs(); })}>
      <Icon name={app.prefs.view === 'list' ? 'magazine' : 'list'} />{app.prefs.view === 'list' ? 'Magazine view' : 'Compact list view'}
    </button>
    <button role="menuitem" onclick={() => act(() => openDialog('settings'))}><Icon name="settings" />Settings</button>
    <button class="cancel" onclick={() => (menu = false)}>Cancel</button>
  </div>
{/if}

<Toasts bottom={app.selectedId !== null ? 92 : 96} />

<style>
  .mob { min-height: 100dvh; background: var(--card); padding-bottom: calc(84px + env(safe-area-inset-bottom)); }
  .pull { display: flex; align-items: flex-end; justify-content: center; padding-bottom: 6px; color: var(--faint); font-size: 10.5px; overflow: hidden; }
  .top { background: var(--canvas); padding: calc(env(safe-area-inset-top) + 8px) 16px 8px; }
  .home-top { display: flex; align-items: center; justify-content: space-between; }
  .brand { position: relative; border: 0; background: transparent; font-size: 15px; font-weight: 700; color: var(--label); padding: 10px 0; }
  .mark { position: absolute; left: 1px; top: 7px; display: flex; gap: 2px; }
  .mark i { width: 3px; height: 3px; border-radius: 2px; background: var(--accent); display: block; }
  .right { display: flex; margin-right: -10px; }
  .icon-btn.big { width: 44px; height: 44px; color: var(--text); }
  h1 { margin: 2px 0 4px; font-size: 30px; font-weight: 700; letter-spacing: -0.025em; }
  h1.small { font-size: 24px; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .status { font-size: 10.5px; color: var(--label); letter-spacing: 0.1em; }
  .sub-top { display: flex; align-items: center; gap: 6px; margin-left: -10px; margin-right: -10px; }
  .count { color: var(--label); }
  .grow { flex: 1; }
  .search-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
  .search-row input { height: 40px; }
  .text-btn { border: 0; background: transparent; font-size: 15px; font-weight: 500; padding: 0 4px; color: var(--text); }

  .chips { background: var(--canvas); padding: 6px 16px 12px; display: flex; gap: 8px; overflow-x: auto; scrollbar-width: none; border-bottom: 1px solid var(--border); }
  .chips::-webkit-scrollbar { display: none; }
  .chip { flex: none; height: 36px; padding: 0 14px; border-radius: 18px; border: 1px solid var(--border); background: var(--card); display: flex; align-items: center; gap: 7px; font-size: 14px; font-weight: 500; color: var(--text); }
  .chip.on { background: var(--invert-bg); color: var(--invert-text); border-color: transparent; }
  .chip .n { font-size: 11px; color: inherit; opacity: 0.7; letter-spacing: 0.04em; }

  .continue { margin: 12px 16px 6px; padding: 10px 6px 10px 12px; border-radius: 12px; border: 1px solid var(--border); background: var(--card-2); display: flex; align-items: center; gap: 4px; }
  .cont-main { flex: 1; min-width: 0; display: flex; align-items: center; gap: 12px; border: 0; background: transparent; text-align: left; color: var(--text); padding: 0; }
  .cont-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .cont-label { font-size: 10px; font-weight: 600; color: var(--label); letter-spacing: 0.14em; }
  .cont-title { font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bar { height: 3px; border-radius: 2px; background: var(--border); display: flex; }
  .bar span { border-radius: 2px; background: var(--text); }

  .toolbar {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 10; background: var(--canvas); border-top: 1px solid var(--border);
    padding: 10px 12px calc(env(safe-area-inset-bottom) + 10px); display: flex; align-items: center; gap: 8px;
  }
  .filter { flex: 1; }
  .filter button { flex: 1; height: 38px; justify-content: center; font-size: 14px; }

  .scrim { position: fixed; inset: 0; z-index: 30; background: rgba(26, 26, 26, 0.32); }
  .drawer { position: fixed; top: 0; bottom: 0; left: 0; z-index: 31; padding: calc(env(safe-area-inset-top) + 12px) 0 12px 12px; display: flex; animation: slide 0.2s ease; }
  .drawer :global(.sidebar) { max-height: none; height: 100%; position: static; width: min(300px, 85vw); }
  .sheet { position: fixed; left: 0; right: 0; bottom: 0; z-index: 31; background: var(--card); border-radius: 18px 18px 0 0; padding: 10px 12px calc(env(safe-area-inset-bottom) + 12px); display: flex; flex-direction: column; animation: up 0.2s ease; }
  .sheet button { min-height: 52px; border: 0; background: transparent; display: flex; align-items: center; gap: 14px; padding: 0 12px; font-size: 16px; color: var(--text); text-align: left; border-radius: 10px; }
  .sheet button:disabled { opacity: 0.45; }
  .sheet .cancel { justify-content: center; font-weight: 600; margin-top: 6px; background: var(--hover); }
  @keyframes slide { from { transform: translateX(-100%); } }
  @keyframes up { from { transform: translateY(100%); } }
</style>
