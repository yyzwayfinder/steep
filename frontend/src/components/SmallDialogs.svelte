<script>
  import Dialog from './Dialog.svelte';
  import { app, closeDialog, markAllRead, savePrefs, scopeTitle, scopeUnread } from '../lib/state.svelte.js';

  let { name } = $props();
  let older = $state('none');

  const SHORTCUTS = [
    ['j / k', 'Next / previous article'],
    ['o or Enter', 'Open the selected article'],
    ['Esc', 'Close the article or dialog'],
    ['v', 'Open the original in a new tab'],
    ['c', 'Copy the original link'],
    ['s', 'Save / unsave'],
    ['m', 'Toggle read'],
    ['Shift + A', 'Mark all in view as read'],
    ['r', 'Refresh feeds in view'],
    ['/', 'Search'],
    ['g a / g s', 'Go to All Articles / Saved'],
    ['[', 'Show or hide the sidebar'],
    ['1 / 2', 'Magazine / List view'],
    ['a', 'Add a source'],
    ['?', 'This list'],
  ];
</script>

{#if name === 'shortcuts'}
  <Dialog title="Keyboard shortcuts" width={460}>
    <dl>
      {#each SHORTCUTS as [k, v]}<dt><kbd>{k}</kbd></dt><dd>{v}</dd>{/each}
    </dl>
  </Dialog>
{:else if name === 'markall'}
  <Dialog title="Mark as read" width={440}>
    <p class="lead">{scopeTitle()} has {scopeUnread()} unread.</p>
    <fieldset>
      <legend class="sr-only">Which articles</legend>
      {#each [['none', 'All of them'], ['1d', 'Older than a day'], ['1w', 'Older than a week']] as [v, l]}
        <label class="radio"><input type="radio" name="older" value={v} bind:group={older} />{l}</label>
      {/each}
    </fieldset>
    {#snippet footer()}
      <button class="btn ghost" onclick={closeDialog}>Cancel</button>
      <button class="btn primary" onclick={() => { closeDialog(); markAllRead(older); }}>Mark as read</button>
    {/snippet}
  </Dialog>
{:else if name === 'reader'}
  <Dialog title="Reading" width={420}>
    <div class="group">
      <span class="lbl">Text size</span>
      <div class="seg">
        {#each [[16, 'Small'], [18, 'Medium'], [20, 'Large'], [22, 'Larger']] as [v, l]}
          <button aria-pressed={app.prefs.readerSize === v} onclick={() => { app.prefs.readerSize = v; savePrefs(); }}>{l}</button>
        {/each}
      </div>
      <span class="lbl">Typeface</span>
      <div class="seg">
        {#each [['sans', 'Sans'], ['serif', 'Serif']] as [v, l]}
          <button aria-pressed={app.prefs.readerFont === v} onclick={() => { app.prefs.readerFont = v; savePrefs(); }}>{l}</button>
        {/each}
      </div>
      <span class="lbl">Column width</span>
      <div class="seg">
        {#each [['narrow', 'Narrow'], ['normal', 'Normal'], ['wide', 'Wide']] as [v, l]}
          <button aria-pressed={app.prefs.readerWidth === v} onclick={() => { app.prefs.readerWidth = v; savePrefs(); }}>{l}</button>
        {/each}
      </div>
    </div>
  </Dialog>
{/if}

<style>
  dl { display: grid; grid-template-columns: auto 1fr; gap: 10px 18px; margin: 0; font-size: 14px; }
  dt { white-space: nowrap; } dd { margin: 0; color: var(--muted); }
  kbd { font-family: var(--mono); font-size: 12px; padding: 2px 6px; border: 1px solid var(--border); border-bottom-width: 2px; border-radius: 5px; background: var(--card-2); }
  .lead { margin: 0 0 12px; font-size: 14.5px; color: var(--muted); }
  fieldset { border: 0; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
  .radio { display: flex; gap: 10px; align-items: center; min-height: 40px; font-size: 14.5px; }
  .radio input { width: 18px; height: 18px; accent-color: var(--text); }
  .group { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
  .lbl { font-size: 13.5px; font-weight: 500; margin-top: 6px; }
</style>
