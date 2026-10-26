<script>
  import Icon from '../lib/Icon.svelte';
  import Thumb from '../lib/Thumb.svelte';
  import { timeLabel } from '../lib/format.js';
  import { app, markRead, openArticle, toggleSaved } from '../lib/state.svelte.js';

  let { item, variant = 'wide' } = $props(); // wide | narrow | mobile | list

  const selected = $derived(app.selectedId === item.id);
  const lines = $derived(app.prefs.excerptLines);

  // ---- swipe (touch lists only): right = toggle read, left = save (F-27)
  const THRESHOLD = 96;
  let dx = $state(0);
  let startX = 0;
  let startY = 0;
  let tracking = false;
  let swiping = false;

  function down(e) {
    if (variant !== 'mobile' || e.pointerType === 'mouse') return;
    startX = e.clientX;
    startY = e.clientY;
    tracking = true;
    swiping = false;
  }
  function move(e) {
    if (!tracking) return;
    const x = e.clientX - startX;
    const y = e.clientY - startY;
    if (!swiping) {
      if (Math.abs(y) > 10 && Math.abs(y) > Math.abs(x)) return (tracking = false);
      if (Math.abs(x) > 12) {
        swiping = true;
        e.currentTarget.setPointerCapture?.(e.pointerId);
      }
    }
    if (swiping) dx = Math.max(-160, Math.min(160, x));
  }
  function up() {
    if (!tracking) return;
    tracking = false;
    if (swiping) {
      if (dx > THRESHOLD) markRead(item.id, !item.is_read, { undo: true });
      else if (dx < -THRESHOLD) toggleSaved(item.id, { undo: true });
    }
    dx = 0;
    setTimeout(() => (swiping = false), 0);
  }
  function click(e) {
    if (swiping) {
      e.preventDefault();
      return;
    }
    openArticle(item.id);
  }
</script>

<div class="wrap" class:mobile={variant === 'mobile'}>
  {#if variant === 'mobile' && dx !== 0}
    <div class="action left" class:armed={dx > THRESHOLD} aria-hidden="true">
      <Icon name={item.is_read ? 'circle' : 'check'} size={22} stroke={2.2} />{item.is_read ? 'Unread' : 'Read'}
    </div>
    <div class="action right" class:armed={dx < -THRESHOLD} aria-hidden="true">
      <Icon name="bookmark" size={20} stroke={2} />{item.is_saved ? 'Unsave' : 'Save'}
    </div>
  {/if}
  <button
    class="row {variant}"
    class:selected
    class:read={item.is_read}
    style:transform={dx ? `translateX(${dx}px)` : undefined}
    style:transition={dx ? 'none' : undefined}
    onpointerdown={down}
    onpointermove={move}
    onpointerup={up}
    onpointercancel={up}
    onclick={click}
    aria-current={selected ? 'true' : undefined}
  >
    {#if variant === 'list'}
      {#if !item.is_read}<span class="dot" aria-label="Unread"></span>{:else}<span class="dot-gap"></span>{/if}
      <span class="list-title">{item.title || 'Untitled'}</span>
      <span class="mono src">{item.feed_title}</span>
      <span class="mono time">{timeLabel(item.published_at)}</span>
    {:else}
      <div class="text">
        {#if variant !== 'mobile'}{@render meta()}{/if}
        <div class="title">{item.title || 'Untitled'}</div>
        {#if variant !== 'narrow' && lines > 0 && item.excerpt}
          <div class="excerpt" style:-webkit-line-clamp={lines}>{item.excerpt}</div>
        {/if}
        {#if variant === 'mobile'}{@render meta()}{/if}
      </div>
      {#if variant === 'wide'}
        <Thumb src={item.image_url} title={item.feed_title} width={132} height={88} />
      {:else if variant === 'narrow'}
        <Thumb src={item.image_url} title={item.feed_title} size={56} />
      {:else}
        <Thumb src={item.image_url} title={item.feed_title} size={68} />
      {/if}
    {/if}
  </button>
</div>

{#snippet meta()}
  <div class="meta">
    {#if !item.is_read}<span class="dot" aria-label="Unread"></span>{/if}
    <span class="mono src">{item.feed_title}</span>
    <span class="mono time">{timeLabel(item.published_at)}</span>
    {#if item.updated_at}<span class="mono tag">Updated</span>{/if}
    {#if item.is_saved}<span class="saved" aria-label="Saved"><Icon name="bookmark" size={12} stroke={2} fill /></span>{/if}
  </div>
{/snippet}

<style>
  .wrap { position: relative; overflow: hidden; }
  .row {
    width: 100%; display: flex; gap: 16px; text-align: left; border: 0; background: var(--card); color: var(--text);
    padding: 18px 4px; border-top: 1px solid var(--divider); position: relative; transition: transform 0.18s ease;
    touch-action: pan-y;
  }
  .row:hover { background: color-mix(in srgb, var(--hover) 60%, var(--card)); }
  .row.selected { background: var(--selected); box-shadow: inset 3px 0 0 var(--text); }
  .text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
  .title { font-size: 18px; line-height: 1.3; font-weight: 600; letter-spacing: -0.015em; }
  .row.read .title { color: var(--read); }
  .excerpt { font-size: 14px; line-height: 1.55; color: var(--muted); display: -webkit-box; -webkit-box-orient: vertical; overflow: hidden; }
  .meta { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .dot { width: 7px; height: 7px; border-radius: 4px; background: var(--accent); flex: none; }
  .dot-gap { width: 7px; flex: none; }
  .src { font-size: 10.5px; font-weight: 600; letter-spacing: 0.12em; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .time { font-size: 10.5px; letter-spacing: 0.08em; color: var(--faint); white-space: nowrap; flex: none; }
  .tag { font-size: 9.5px; font-weight: 600; padding: 1px 5px; border-radius: 4px; border: 1px solid var(--border); color: var(--label); flex: none; }
  .saved { color: var(--text); display: inline-flex; }

  .row.narrow { padding: 15px 20px; gap: 12px; border-top: 0; border-bottom: 1px solid var(--divider); }
  .row.narrow .title { font-size: 14.5px; line-height: 1.35; letter-spacing: -0.01em; }
  .row.narrow .src, .row.narrow .time { font-size: 10px; }

  .row.mobile { padding: 14px 16px; gap: 14px; border-top: 0; border-bottom: 1px solid var(--divider); }
  .row.mobile .text { gap: 5px; }
  .row.mobile .title { font-size: 17px; letter-spacing: -0.012em; }
  .row.mobile .excerpt { font-size: 14px; line-height: 1.42; }
  .row.mobile .meta { margin-top: 2px; }
  .row.mobile.selected { box-shadow: none; }

  .row.list { padding: 11px 8px; gap: 12px; align-items: center; }
  .list-title { flex: 1; min-width: 0; font-size: 14.5px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .row.list:not(.read) .list-title { font-weight: 600; }
  .row.list.read .list-title { color: var(--read); }
  .row.list .src { max-width: 180px; font-weight: 500; color: var(--label); }

  .action { position: absolute; top: 0; bottom: 0; width: 120px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; color: #fff; font-size: 12px; font-weight: 600; opacity: 0.75; }
  .action.left { left: 0; background: #2e6b45; }
  .action.right { right: 0; background: #8f4b2e; }
  .action.armed { opacity: 1; }
</style>
