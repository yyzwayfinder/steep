<script>
  import Icon from '../lib/Icon.svelte';
  import SourceIcon from '../lib/SourceIcon.svelte';
  import { agoLabel } from '../lib/format.js';
  import { app, openDialog, savePrefs, setScope } from '../lib/state.svelte.js';

  let { rail = false, onnavigate = () => {} } = $props();

  const KEY = 'steep.collapsed';
  let collapsed = $state(loadCollapsed());
  function loadCollapsed() {
    try {
      return JSON.parse(localStorage.getItem(KEY) || '{}');
    } catch {
      return {};
    }
  }
  function toggleFolder(id) {
    collapsed[id] = !(collapsed[id] ?? true);
    try {
      localStorage.setItem(KEY, JSON.stringify(collapsed));
    } catch {}
  }
  const isOpen = (id) => collapsed[id] === false;

  const is = (type, id = null) => app.scope.type === type && (app.scope.id ?? null) === id && !app.query;

  function go(type, id = null) {
    setScope(type, id);
    onnavigate();
  }

  function cycleTheme() {
    const order = ['system', 'light', 'dark'];
    app.prefs.theme = order[(order.indexOf(app.prefs.theme) + 1) % order.length];
    savePrefs();
  }
  const themeLabel = $derived({ system: 'Theme: match system', light: 'Theme: light', dark: 'Theme: dark' }[app.prefs.theme]);
  const short = (name) => name.replace(/\s+/g, '').slice(0, 2);
</script>

{#if rail}
  <nav class="rail card" aria-label="Sources (collapsed)">
    <button class="logo" onclick={() => { app.prefs.sidebarPinned = true; savePrefs(); }} aria-label="Expand sidebar">
      <span class="dots-mark"><i></i><i></i></span>S
    </button>
    <button class="rail-btn" class:on={is('all')} onclick={() => go('all')} aria-label="All Articles, {app.tree?.unread ?? 0} unread">
      <Icon name="inbox" size={19} stroke={1.7} />
    </button>
    <button class="rail-btn" class:on={is('saved')} onclick={() => go('saved')} aria-label="Saved, {app.tree?.saved ?? 0}">
      <Icon name="bookmark" size={18} stroke={1.7} />
    </button>
    <div class="rule"></div>
    <div class="rail-folders">
      {#each app.tree?.folders ?? [] as folder (folder.id)}
        <button
          class="tile"
          class:on={is('folder', folder.id)}
          onclick={() => go('folder', folder.id)}
          aria-label="{folder.name}, {folder.unread} unread"
          title={folder.name}
        >
          {short(folder.name)}
          {#if folder.unread}<span class="badge">{folder.unread > 999 ? '999+' : folder.unread}</span>{/if}
        </button>
      {/each}
    </div>
    <div class="grow"></div>
    <button class="rail-btn" onclick={() => openDialog('settings')} aria-label="Settings"><Icon name="settings" /></button>
  </nav>
{:else}
  <aside class="sidebar card" aria-label="Sources">
    <div class="brand">
      <span class="word"><span class="dots-mark"><i></i><i></i></span>Steep</span>
      {#if !app.online}<span class="offline mono">Offline</span>{/if}
    </div>

    <nav class="primary" aria-label="Library">
      <button class="nav-item" class:on={is('all')} onclick={() => go('all')}>
        <span>All Articles</span><span class="count">{app.tree?.unread ?? ''}</span>
      </button>
      <button class="nav-item" class:on={is('saved')} onclick={() => go('saved')}>
        <span>Saved</span><span class="count">{app.tree?.saved || ''}</span>
      </button>
      <button class="nav-item" onclick={() => { openDialog('add'); onnavigate(); }}>
        <span class="with-icon"><Icon name="compass" size={16} stroke={1.7} />Follow Sources</span>
      </button>
    </nav>

    <div class="section mono">Sources</div>

    <div class="folders">
      {#each app.tree?.folders ?? [] as folder (folder.id)}
        <div class="folder-row" class:on={is('folder', folder.id)}>
          <button class="chev" onclick={() => toggleFolder(folder.id)} aria-label="{isOpen(folder.id) ? 'Collapse' : 'Expand'} {folder.name}" aria-expanded={isOpen(folder.id)}>
            <Icon name={isOpen(folder.id) ? 'chevronDown' : 'chevronRight'} size={14} stroke={2} />
          </button>
          <button class="folder-name" onclick={() => go('folder', folder.id)}>
            <span class="label">{folder.name}</span>
            {#if folder.unread}<span class="count">{folder.unread}</span>{/if}
          </button>
        </div>
        {#if isOpen(folder.id)}
          <div class="feeds">
            {#each folder.feeds as feed (feed.id)}
              {@render feedRow(feed)}
            {/each}
            {#if !folder.feeds.length}<div class="empty">No feeds yet</div>{/if}
          </div>
        {/if}
      {/each}

      {#if app.tree?.uncategorized?.length}
        <div class="folder-row" class:on={is('folder', null)}>
          <button class="chev" onclick={() => toggleFolder('none')} aria-label="Toggle Uncategorized" aria-expanded={isOpen('none')}>
            <Icon name={isOpen('none') ? 'chevronDown' : 'chevronRight'} size={14} stroke={2} />
          </button>
          <button class="folder-name" onclick={() => go('folder', null)}>
            <span class="label">Uncategorized</span>
            <span class="count">{app.tree.uncategorized.reduce((n, f) => n + (f.muted ? 0 : f.unread), 0) || ''}</span>
          </button>
        </div>
        {#if isOpen('none')}
          <div class="feeds">
            {#each app.tree.uncategorized as feed (feed.id)}{@render feedRow(feed)}{/each}
          </div>
        {/if}
      {/if}

      {#if app.tree && !app.tree.folders.length && !app.tree.uncategorized.length}
        <div class="welcome">
          <p>No sources yet.</p>
          <button class="btn" onclick={() => openDialog('add')}><Icon name="plus" size={14} stroke={2.2} />Add a source</button>
          <button class="btn ghost" onclick={() => openDialog('settings', { tab: 'import' })}>Import from Feedly (OPML)</button>
        </div>
      {/if}
    </div>

    <div class="grow"></div>
    <footer>
      <span class="mono sync" title="Last synced"><i class:stale={!app.online}></i>{app.online ? agoLabel(app.tree?.last_sync) : 'Offline'}</span>
      <div class="tools">
        <button class="icon-btn" onclick={cycleTheme} aria-label={themeLabel} title={themeLabel}>
          <Icon name={app.prefs.theme === 'dark' ? 'moon' : 'sun'} size={17} stroke={1.7} />
        </button>
        <button class="icon-btn" onclick={() => openDialog('shortcuts')} aria-label="Keyboard shortcuts" title="Keyboard shortcuts (?)">
          <Icon name="keyboard" size={18} stroke={1.7} />
        </button>
        <button class="icon-btn" onclick={() => openDialog('settings')} aria-label="Settings" title="Settings">
          <Icon name="settings" size={17} stroke={1.7} />
        </button>
      </div>
    </footer>
  </aside>
{/if}

{#snippet feedRow(feed)}
  <div class="feed-row" class:on={is('feed', feed.id)} class:muted={feed.muted}>
    <button class="feed-name" onclick={() => go('feed', feed.id)} title={feed.title}>
      <SourceIcon title={feed.title} src={feed.favicon_url} size={18} />
      <span class="label">{feed.title}</span>
      {#if feed.error}<span class="err" title="This feed keeps failing: {feed.error}"><Icon name="warning" size={13} stroke={2} /></span>{/if}
      {#if feed.unread && !feed.muted}<span class="count small">{feed.unread}</span>{/if}
    </button>
    <button class="feed-more" onclick={() => openDialog('feed', { id: feed.id })} aria-label="Settings for {feed.title}">
      <Icon name="more" size={16} />
    </button>
  </div>
{/snippet}

<style>
  .sidebar {
    width: 264px; flex: none; display: flex; flex-direction: column; overflow: hidden;
    max-height: calc(100dvh - 40px); position: sticky; top: 20px;
  }
  .brand { padding: 22px 22px 18px; border-bottom: 1px solid var(--divider); display: flex; align-items: center; justify-content: space-between; }
  .word { position: relative; font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }
  .dots-mark { position: absolute; left: 1px; top: -3px; display: flex; gap: 3px; }
  .dots-mark i { width: 4px; height: 4px; border-radius: 2px; background: var(--accent); display: block; }
  .offline { font-size: 10px; padding: 3px 6px; border-radius: 4px; background: var(--accent-soft); color: var(--text); }

  .primary { padding: 12px 12px 4px; display: flex; flex-direction: column; gap: 2px; }
  .nav-item {
    display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-radius: 10px;
    border: 0; background: transparent; font-size: 14px; font-weight: 500; text-align: left; color: var(--text);
  }
  .nav-item:hover { background: var(--hover); }
  .nav-item.on { background: var(--active); font-weight: 600; }
  .with-icon { display: inline-flex; align-items: center; gap: 10px; }
  .count { font-family: var(--mono); font-size: 12px; color: var(--label); }
  .count.small { font-size: 11px; }

  .section { padding: 16px 24px 8px; color: var(--faint); font-size: 11px; }
  .folders { padding: 0 12px; display: flex; flex-direction: column; gap: 4px; overflow-y: auto; min-height: 0; }
  .folder-row { display: flex; align-items: center; border-radius: 10px; background: var(--hover); }
  .folder-row.on { background: var(--active); }
  .folder-row.on .label { font-weight: 600; }
  .chev { width: 32px; height: 40px; border: 0; background: transparent; display: flex; align-items: center; justify-content: center; color: var(--text); padding-left: 6px; }
  .folder-name { flex: 1; min-width: 0; height: 40px; display: flex; align-items: center; gap: 10px; padding: 0 12px 0 2px; border: 0; background: transparent; font-size: 14px; font-weight: 500; text-align: left; color: var(--text); }
  .label { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .feeds { margin-left: 22px; padding-left: 10px; border-left: 1px solid var(--border); display: flex; flex-direction: column; gap: 1px; margin-bottom: 4px; }
  .feed-row { display: flex; align-items: center; border-radius: 8px; }
  .feed-row:hover, .feed-row.on { background: var(--hover); }
  .feed-row.on .label { font-weight: 600; }
  .feed-row.muted .label { color: var(--faint); }
  .feed-name { flex: 1; min-width: 0; display: flex; align-items: center; gap: 10px; padding: 7px 4px 7px 10px; border: 0; background: transparent; font-size: 13px; text-align: left; color: var(--text); }
  .feed-more { width: 28px; height: 28px; border: 0; background: transparent; border-radius: 6px; color: var(--faint); opacity: 0; display: flex; align-items: center; justify-content: center; }
  .feed-row:hover .feed-more, .feed-more:focus-visible { opacity: 1; }
  @media (hover: none) { .feed-more { opacity: 1; } }
  .err { color: var(--warn); display: inline-flex; }
  .empty { font-size: 12.5px; color: var(--faint); padding: 6px 10px; }
  .welcome { padding: 12px 6px; display: flex; flex-direction: column; gap: 8px; align-items: flex-start; font-size: 14px; color: var(--muted); }
  .welcome p { margin: 0 0 4px; }

  .grow { flex: 1; min-height: 12px; }
  footer { padding: 12px 16px; border-top: 1px solid var(--divider); display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .sync { font-size: 10.5px; color: var(--label); display: flex; align-items: center; gap: 6px; white-space: nowrap; overflow: hidden; }
  .sync i { width: 6px; height: 6px; border-radius: 3px; background: var(--good); display: block; flex: none; }
  .sync i.stale { background: var(--warn); }
  .tools { display: flex; gap: 0; }

  .rail {
    width: 72px; flex: none; display: flex; flex-direction: column; align-items: center; padding: 18px 0 12px; gap: 6px;
    max-height: calc(100dvh - 40px); position: sticky; top: 20px;
  }
  .logo { position: relative; width: 44px; height: 40px; border: 0; background: transparent; font-size: 22px; font-weight: 700; margin-bottom: 10px; color: var(--text); }
  .logo .dots-mark { left: 13px; top: 4px; }
  .rail-btn { width: 44px; height: 44px; border: 0; border-radius: 10px; background: transparent; color: var(--text); display: flex; align-items: center; justify-content: center; }
  .rail-btn:hover { background: var(--hover); }
  .rail-btn.on { background: var(--active); }
  .rule { width: 28px; height: 1px; background: var(--border); margin: 6px 0; }
  .rail-folders { display: flex; flex-direction: column; gap: 8px; overflow-y: auto; padding: 4px 6px; }
  .tile { position: relative; width: 44px; height: 44px; border: 0; border-radius: 10px; background: var(--hover); font-size: 14px; font-weight: 600; color: var(--text); }
  .tile.on { background: var(--invert-bg); color: var(--invert-text); }
  .badge { position: absolute; right: -5px; top: -4px; min-width: 18px; height: 16px; padding: 0 4px; border-radius: 8px; background: var(--card); border: 1px solid var(--border); font-family: var(--mono); font-size: 9.5px; font-weight: 400; color: var(--text); display: flex; align-items: center; justify-content: center; }
</style>
