<script>
  import Dialog from './Dialog.svelte';
  import Icon from '../lib/Icon.svelte';
  import { api } from '../lib/api.js';
  import { agoLabel } from '../lib/format.js';
  import { app, closeDialog, fail, loadArticles, loadTree, logout, openDialog, savePrefs, toast } from '../lib/state.svelte.js';

  let { tab: initialTab = 'general' } = $props();
  let tab = $state(initialTab);
  let server = $state(null);
  let health = $state(null);
  let importing = $state(false);
  let report = $state(null);
  let fileInput = $state();

  $effect(() => {
    api.settings().then((s) => (server = s)).catch(fail);
  });
  $effect(() => {
    if (tab === 'health' && !health) api.health().then((h) => (health = h.feeds)).catch(fail);
  });

  async function saveServer(key, value) {
    server[key] = String(value);
    try {
      await api.saveSettings({ [key]: String(value) });
    } catch (err) {
      fail(err);
    }
  }

  async function importFile(e) {
    const file = e.currentTarget.files?.[0];
    if (!file) return;
    importing = true;
    report = null;
    try {
      report = await api.importOpml(file);
      await loadTree();
      loadArticles(true);
      setTimeout(() => { loadTree(); loadArticles(true); }, 8000);
    } catch (err) {
      fail(err);
    } finally {
      importing = false;
      e.currentTarget.value = '';
    }
  }

  const origin = typeof location !== 'undefined' ? location.origin : '';
  const bookmarklet = $derived(`javascript:location.href='${origin}/?add='+encodeURIComponent(location.href)`);
  const tabs = [
    ['general', 'General'],
    ['import', 'Import & export'],
    ['health', 'Feed health'],
    ['addons', 'Quick add'],
    ['account', 'Account'],
  ];
</script>

<Dialog title="Settings" width={680}>
  <div class="tabs" role="tablist">
    {#each tabs as [key, label]}
      <button role="tab" aria-selected={tab === key} class:on={tab === key} onclick={() => (tab = key)}>{label}</button>
    {/each}
  </div>

  {#if tab === 'general'}
    <div class="group">
      <div class="field">
        <span class="lbl">Theme</span>
        <div class="seg">
          {#each [['system', 'Match system'], ['light', 'Light'], ['dark', 'Dark']] as [v, l]}
            <button aria-pressed={app.prefs.theme === v} onclick={() => { app.prefs.theme = v; savePrefs(); }}>{l}</button>
          {/each}
        </div>
      </div>
      <div class="field">
        <span class="lbl">Excerpt in lists</span>
        <div class="seg">
          {#each [[2, '2 lines'], [3, '3 lines'], [0, 'Off']] as [v, l]}
            <button aria-pressed={app.prefs.excerptLines === v} onclick={() => { app.prefs.excerptLines = v; savePrefs(); }}>{l}</button>
          {/each}
        </div>
      </div>
      <label class="check"><input type="checkbox" bind:checked={app.prefs.sidebarPinned} onchange={savePrefs} />Keep the full sidebar open while reading (desktop)</label>
    </div>

    {#if server}
      <div class="group">
        <div class="field inline">
          <label for="ret">Keep read articles for</label>
          <select id="ret" value={server.retention_days} onchange={(e) => saveServer('retention_days', e.currentTarget.value)}>
            {#each [30, 60, 90, 180, 365] as d}<option value={String(d)}>{d} days</option>{/each}
          </select>
        </div>
        <p class="help">Saved articles are never deleted.</p>
        <div class="field inline">
          <label for="resume">Reopen where I left off if I was here within</label>
          <select id="resume" value={server.resume_minutes} onchange={(e) => saveServer('resume_minutes', e.currentTarget.value)}>
            {#each [[0, 'Never'], [15, '15 minutes'], [60, '1 hour'], [240, '4 hours']] as [v, l]}<option value={String(v)}>{l}</option>{/each}
          </select>
        </div>
        <label class="check">
          <input type="checkbox" checked={server.updated_marks_unread === '1'} onchange={(e) => saveServer('updated_marks_unread', e.currentTarget.checked ? 1 : 0)} />
          Mark articles unread again when the publisher updates them
        </label>
      </div>
    {/if}
  {:else if tab === 'import'}
    <div class="group">
      <h3>Import subscriptions</h3>
      <p class="help">Upload an OPML file. From Feedly, open <strong>feedly.com/i/opml</strong> in a browser to download yours. Folders come across; saved articles and read state don't.</p>
      <input bind:this={fileInput} class="sr-only" type="file" accept=".opml,.xml,text/xml,application/xml" onchange={importFile} />
      <button class="btn" onclick={() => fileInput.click()} disabled={importing}><Icon name="upload" size={15} />{importing ? 'Importing…' : 'Choose OPML file'}</button>
      {#if server}
        <label class="check"><input type="checkbox" checked={server.skip_reddit_on_import === '1'} onchange={(e) => saveServer('skip_reddit_on_import', e.currentTarget.checked ? 1 : 0)} />Skip Reddit feeds (Reddit ended RSS on 13 November 2026)</label>
      {/if}
      {#if report}
        <div class="report" role="status">
          <strong>Added {report.added} feed{report.added === 1 ? '' : 's'}</strong>{report.folders_created ? ` in ${report.folders_created} new folder${report.folders_created === 1 ? '' : 's'}` : ''}.
          {#if report.existing} {report.existing} were already here.{/if}
          {#if report.skipped_reddit.length} Skipped {report.skipped_reddit.length} Reddit feed{report.skipped_reddit.length === 1 ? '' : 's'}: {report.skipped_reddit.join(', ')}.{/if}
          {#if report.invalid} {report.invalid} entr{report.invalid === 1 ? 'y was' : 'ies were'} not valid feed links.{/if}
          Articles are arriving now.
        </div>
      {/if}
    </div>
    <div class="group">
      <h3>Export</h3>
      <a class="btn" href="/api/opml/export" download><Icon name="download" size={15} />Download OPML</a>
    </div>
  {:else if tab === 'health'}
    {#if !health}
      <p class="help">Loading…</p>
    {:else if !health.length}
      <p class="help">No feeds yet.</p>
    {:else}
      <div class="health" role="table" aria-label="Feed health">
        {#each health as f (f.id)}
          <div class="h-row" role="row" class:bad={f.fail_count >= 3} class:warn={f.fail_count > 0 && f.fail_count < 3}>
            <span class="h-state" role="cell" aria-label={f.fail_count ? 'Failing' : 'OK'}><i></i></span>
            <span class="h-name" role="cell">
              <button class="link" onclick={() => openDialog('feed', { id: f.id })}>{f.title}</button>
              <span class="h-sub">{f.last_error ? `${f.last_error} · ` : ''}checked {agoLabel(f.last_fetch_at)}{f.newest_article ? ` · newest item ${agoLabel(f.newest_article)}` : ''}</span>
            </span>
          </div>
        {/each}
      </div>
    {/if}
  {:else if tab === 'addons'}
    <div class="group">
      <h3>Desktop bookmarklet</h3>
      <p class="help">Drag this to your bookmarks bar. Click it on any site to open Add Source with that page ready.</p>
      <!-- svelte-ignore a11y_invalid_attribute -->
      <a class="btn bookmarklet" href={bookmarklet} onclick={(e) => { e.preventDefault(); toast('Drag the button to your bookmarks bar.'); }}><Icon name="plus" size={14} />Add to Steep</a>
    </div>
    <div class="group">
      <h3>iPhone and iPad share sheet</h3>
      <ol class="steps">
        <li>Open the <strong>Shortcuts</strong> app and tap <strong>+</strong> to make a new shortcut. Name it <strong>Add to Steep</strong>.</li>
        <li>Tap the <strong>ⓘ</strong> button and turn on <strong>Show in Share Sheet</strong>; set it to receive <strong>URLs</strong> and <strong>Safari web pages</strong>.</li>
        <li>Add the action <strong>Open URLs</strong> with this address, replacing the last part with the <strong>Shortcut Input</strong> variable:<br /><code>{origin}/?add=</code><em>Shortcut Input</em></li>
      </ol>
      <p class="help">Now Share › Add to Steep on any page opens Steep with that site's feeds ready to subscribe.</p>
    </div>
  {:else if tab === 'account'}
    <div class="group">
      <p class="help">Steep {app.version} · single user · data stays on your server.</p>
      <button class="btn" onclick={() => { closeDialog(); openDialog('shortcuts'); }}><Icon name="keyboard" size={16} />Keyboard shortcuts</button>
      <button class="btn danger" onclick={() => { closeDialog(); logout(); }}><Icon name="logout" size={16} />Sign out on this device</button>
    </div>
  {/if}
</Dialog>

<style>
  .tabs { display: flex; gap: 4px; flex-wrap: wrap; margin: 0 0 18px; border-bottom: 1px solid var(--divider); }
  .tabs button { border: 0; background: transparent; padding: 10px 10px; font-size: 13.5px; font-weight: 500; color: var(--label); border-bottom: 2px solid transparent; margin-bottom: -1px; }
  .tabs button.on { color: var(--text); border-bottom-color: var(--text); }
  .group { display: flex; flex-direction: column; gap: 12px; align-items: flex-start; padding: 6px 0 18px; }
  .group + .group { border-top: 1px solid var(--divider); padding-top: 18px; }
  h3 { margin: 0; font-size: 15px; font-weight: 600; }
  .field { display: flex; flex-direction: column; gap: 8px; }
  .field.inline { flex-direction: row; align-items: center; gap: 12px; flex-wrap: wrap; }
  .field.inline select { width: auto; height: 38px; }
  .lbl, label { font-size: 13.5px; font-weight: 500; }
  .check { display: flex; align-items: center; gap: 10px; font-weight: 400; font-size: 14px; }
  .check input { width: 18px; height: 18px; accent-color: var(--text); flex: none; }
  .help { margin: 0; font-size: 13.5px; line-height: 1.5; color: var(--muted); }
  .report { font-size: 13.5px; line-height: 1.5; padding: 12px 14px; background: var(--chip); border-radius: 10px; }
  .btn { text-decoration: none; }
  .bookmarklet { cursor: grab; }
  .steps { margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.55; display: flex; flex-direction: column; gap: 6px; }
  code { font-family: var(--mono); font-size: 12.5px; background: var(--chip); padding: 1px 5px; border-radius: 4px; word-break: break-all; }
  .health { display: flex; flex-direction: column; width: 100%; }
  .h-row { display: flex; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--divider); align-items: flex-start; }
  .h-state i { width: 8px; height: 8px; border-radius: 4px; display: block; background: var(--good); margin-top: 6px; }
  .h-row.warn .h-state i { background: var(--warn); }
  .h-row.bad .h-state i { background: var(--bad); }
  .h-name { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .h-sub { font-size: 12.5px; color: var(--faint); }
  .link { border: 0; background: none; padding: 0; text-align: left; font-size: 14px; font-weight: 500; color: var(--text); }
  .link:hover { text-decoration: underline; }
</style>
