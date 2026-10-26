<script>
  import Dialog from './Dialog.svelte';
  import Icon from '../lib/Icon.svelte';
  import { api } from '../lib/api.js';
  import { app, closeDialog, fail, findFeed, loadArticles, loadTree, setScope, toast } from '../lib/state.svelte.js';

  let { id } = $props();
  const feed = $derived(findFeed(id));

  let title = $state('');
  let folder = $state('');
  let refresh = $state('');
  let fulltext = $state(true);
  let muted = $state(false);
  let newFolder = $state('');
  let loaded = false;

  $effect(() => {
    if (feed && !loaded) {
      loaded = true;
      title = feed.title;
      folder = feed.folder_id ? String(feed.folder_id) : '';
      refresh = feed.refresh_minutes ? String(feed.refresh_minutes) : '';
      fulltext = feed.fulltext;
      muted = feed.muted;
    }
  });

  async function save() {
    try {
      let folderId = folder === '__new' ? null : folder ? Number(folder) : null;
      if (folder === '__new' && newFolder.trim()) folderId = (await api.createFolder(newFolder.trim())).id;
      await api.updateFeed(id, {
        custom_title: title.trim() === (feed?.title ?? '') ? undefined : title,
        folder_id: folderId ?? undefined,
        move_to_uncategorized: folderId === null,
        refresh_minutes: refresh ? Number(refresh) : null,
        fulltext,
        muted,
      });
      closeDialog();
      await loadTree();
      loadArticles(true);
    } catch (err) {
      fail(err);
    }
  }

  async function unsubscribe() {
    const name = feed?.title ?? 'feed';
    try {
      await api.deleteFeed(id);
      closeDialog();
      if (app.scope.type === 'feed' && app.scope.id === id) setScope('all');
      await loadTree();
      toast(`Unsubscribed from ${name}`, {
        undo: async () => {
          await api.restoreFeed(id);
          await loadTree();
          loadArticles(true);
        },
      });
    } catch (err) {
      fail(err);
    }
  }

  async function renameFolder(f) {
    const name = prompt('Rename folder', f.name);
    if (!name || name === f.name) return;
    try {
      await api.updateFolder(f.id, { name });
      loadTree();
    } catch (err) {
      fail(err);
    }
  }
</script>

<Dialog title={feed ? feed.title : 'Feed'} width={520}>
  {#if feed}
    <div class="form">
      <a class="url" href={feed.site_url || feed.url} target="_blank" rel="noopener noreferrer">{feed.url}</a>
      {#if feed.error}<p class="err"><Icon name="warning" size={14} stroke={2} />This feed keeps failing: {feed.error}</p>{/if}
      <div class="field">
        <label for="f-title">Name</label>
        <input id="f-title" type="text" bind:value={title} maxlength="300" />
      </div>
      <div class="field">
        <label for="f-folder">Folder</label>
        <select id="f-folder" bind:value={folder}>
          <option value="">Uncategorized</option>
          {#each app.tree?.folders ?? [] as f (f.id)}<option value={String(f.id)}>{f.name}</option>{/each}
          <option value="__new">New folder…</option>
        </select>
        {#if folder === '__new'}<input type="text" bind:value={newFolder} placeholder="Folder name" maxlength="100" aria-label="New folder name" />{/if}
        {#if folder && folder !== '__new'}
          {@const f = app.tree.folders.find((x) => String(x.id) === folder)}
          {#if f}<button class="link" onclick={() => renameFolder(f)}>Rename “{f.name}”</button>{/if}
        {/if}
      </div>
      <div class="field">
        <label for="f-refresh">Check for new articles</label>
        <select id="f-refresh" bind:value={refresh}>
          <option value="">Default (every 30 minutes)</option>
          <option value="15">Every 15 minutes</option>
          <option value="60">Every hour</option>
          <option value="180">Every 3 hours</option>
          <option value="720">Twice a day</option>
          <option value="1440">Once a day</option>
        </select>
      </div>
      <label class="check"><input type="checkbox" bind:checked={fulltext} />Fetch full article text when the feed only has a teaser</label>
      <label class="check"><input type="checkbox" bind:checked={muted} />Mute (hide from All Articles and counts)</label>
    </div>
  {:else}
    <p>That feed no longer exists.</p>
  {/if}
  {#snippet footer()}
    <button class="btn ghost danger" onclick={unsubscribe} style="margin-right:auto"><Icon name="trash" size={15} />Unsubscribe</button>
    <button class="btn ghost" onclick={closeDialog}>Cancel</button>
    <button class="btn primary" onclick={save}>Save</button>
  {/snippet}
</Dialog>

<style>
  .form { display: flex; flex-direction: column; gap: 16px; }
  .url { font-size: 13px; color: var(--faint); word-break: break-all; }
  .err { margin: 0; display: flex; gap: 8px; align-items: center; font-size: 13.5px; color: var(--warn); }
  .field { display: flex; flex-direction: column; gap: 8px; }
  label { font-size: 13.5px; font-weight: 500; }
  .check { display: flex; align-items: center; gap: 10px; font-weight: 400; font-size: 14px; }
  .check input { width: 18px; height: 18px; accent-color: var(--text); flex: none; }
  .link { align-self: flex-start; border: 0; background: none; padding: 0; font-size: 13px; color: var(--label); text-decoration: underline; }
</style>
