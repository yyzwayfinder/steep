<script>
  import Dialog from './Dialog.svelte';
  import Icon from '../lib/Icon.svelte';
  import SourceIcon from '../lib/SourceIcon.svelte';
  import { api } from '../lib/api.js';
  import { app, closeDialog, loadArticles, loadTree, setScope, toast } from '../lib/state.svelte.js';

  let { url: initialUrl = '' } = $props();

  let url = $state(initialUrl);
  let found = $state([]);
  let chosen = $state(null);
  let folderId = $state(app.scope.type === 'folder' && app.scope.id ? String(app.scope.id) : '');
  let newFolder = $state('');
  let fulltext = $state(true);
  let busy = $state(false);
  let error = $state('');

  async function find(e) {
    e?.preventDefault();
    if (!url.trim()) return;
    busy = true;
    error = '';
    found = [];
    chosen = null;
    try {
      const res = await api.discover(url);
      found = res.feeds;
      chosen = found[0]?.url ?? null;
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
    }
  }

  async function subscribe() {
    const feed = found.find((f) => f.url === chosen);
    if (!feed) return;
    busy = true;
    error = '';
    try {
      let folder = folderId === '__new' ? null : folderId ? Number(folderId) : null;
      if (folderId === '__new' && newFolder.trim()) folder = (await api.createFolder(newFolder.trim())).id;
      const res = await api.addFeed({ url: feed.url, folder_id: folder, title: feed.title, fulltext });
      closeDialog();
      toast(`Subscribed to ${feed.title}. Fetching articles…`);
      await loadTree();
      setScope('feed', res.id);
      setTimeout(() => loadArticles(true), 2500);
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
    }
  }

  // Bookmarklet / Shortcut: open with ?add=<url> and run discovery straight away.
  $effect(() => {
    if (initialUrl) find();
  });
</script>

<Dialog title="Add a source">
  <form class="find" onsubmit={find}>
    <label for="src-url">Website or feed URL</label>
    <div class="row">
      <input id="src-url" type="text" inputmode="url" autocapitalize="off" autocomplete="off" spellcheck="false"
        placeholder="theverge.com or a feed address" bind:value={url} required />
      <button class="btn find-btn" type="submit" disabled={busy || !url.trim()}>{busy && !found.length ? 'Finding…' : 'Find feeds'}</button>
    </div>
  </form>

  {#if error}<p class="error" role="alert">{error}</p>{/if}

  {#if found.length}
    <div class="found mono"><Icon name="check" size={14} stroke={2.2} />Found {found.length} feed{found.length === 1 ? '' : 's'}</div>
    <fieldset>
      <legend class="sr-only">Choose a feed</legend>
      {#each found as f (f.url)}
        <label class="option" class:on={chosen === f.url}>
          <input type="radio" name="feed" value={f.url} bind:group={chosen} />
          <span class="opt-body">
            <span class="opt-head">
              <SourceIcon title={f.title} size={20} />
              <span class="opt-title">{f.title}</span>
              <span class="mono opt-meta">{f.format}{f.per_week != null ? ` · ~${f.per_week} / week` : ''}</span>
            </span>
            {#each f.recent as r}<span class="recent">{r}</span>{/each}
            <span class="feed-url">{f.url}</span>
          </span>
        </label>
      {/each}
    </fieldset>

    <div class="opts">
      <div class="field">
        <label for="src-folder">Folder</label>
        <select id="src-folder" bind:value={folderId}>
          <option value="">Uncategorized</option>
          {#each app.tree?.folders ?? [] as folder (folder.id)}<option value={String(folder.id)}>{folder.name}</option>{/each}
          <option value="__new">New folder…</option>
        </select>
      </div>
      {#if folderId === '__new'}
        <div class="field">
          <label for="src-newfolder">Folder name</label>
          <input id="src-newfolder" type="text" bind:value={newFolder} maxlength="100" />
        </div>
      {/if}
      <label class="check"><input type="checkbox" bind:checked={fulltext} />Fetch full article text</label>
    </div>
  {/if}

  {#snippet footer()}
    <span class="hint">Tip: the bookmarklet and iPhone Shortcut in Settings open this from any site.</span>
    <button class="btn ghost" onclick={closeDialog}>Cancel</button>
    <button class="btn primary" onclick={subscribe} disabled={!chosen || busy || (folderId === '__new' && !newFolder.trim())}>Subscribe</button>
  {/snippet}
</Dialog>

<style>
  label { font-size: 13.5px; font-weight: 500; }
  .find { display: flex; flex-direction: column; gap: 8px; }
  .row { display: flex; gap: 8px; }
  .row input { flex: 1; min-width: 0; height: 44px; }
  .find-btn { height: 44px; }
  .error { color: var(--bad); font-size: 14px; margin: 12px 0 0; }
  .found { display: flex; align-items: center; gap: 8px; color: var(--good); margin: 18px 0 10px; }
  fieldset { border: 0; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
  .option { display: flex; gap: 14px; padding: 14px 16px; border: 1px solid var(--border); border-radius: 12px; cursor: pointer; font-weight: 400; }
  .option.on { border: 1.5px solid var(--text); padding: 13.5px 15.5px; }
  .option input { margin: 3px 0 0; width: 18px; height: 18px; accent-color: var(--text); flex: none; }
  .opt-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
  .opt-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .opt-title { font-size: 15px; font-weight: 600; }
  .opt-meta { font-size: 10.5px; color: var(--label); letter-spacing: 0.1em; }
  .recent { font-size: 13px; color: var(--muted); line-height: 1.4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .feed-url { font-size: 12px; color: var(--faint); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .opts { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; margin-top: 18px; }
  .field { flex: 1 1 200px; display: flex; flex-direction: column; gap: 8px; }
  .check { flex: 1 1 200px; height: 42px; display: flex; align-items: center; gap: 10px; font-weight: 400; font-size: 14px; }
  .check input { width: 18px; height: 18px; accent-color: var(--text); }
  .hint { flex: 1 1 220px; font-size: 12.5px; color: var(--muted); }
</style>
