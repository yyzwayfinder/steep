<script>
  import Icon from '../lib/Icon.svelte';
  import { clockLabel } from '../lib/format.js';
  import { api } from '../lib/api.js';
  import { app, closeArticle, markRead, openDialog, shareArticle, toggleSaved } from '../lib/state.svelte.js';

  let { mobile = false } = $props();
  let scroller = $state();
  const a = $derived(app.article);

  // Reset scroll when a new article opens, and restore part-read position.
  let lastId = null;
  $effect(() => {
    const id = a?.id;
    if (!scroller || id === lastId) return;
    lastId = id;
    requestAnimationFrame(() => {
      if (!scroller) return;
      const max = scroller.scrollHeight - scroller.clientHeight;
      const p = a?.read_progress ?? 0;
      scroller.scrollTop = p > 0.05 && p < 0.92 ? p * max : 0;
    });
  });

  let progressTimer;
  function onScroll() {
    if (!a || !scroller) return;
    clearTimeout(progressTimer);
    const id = a.id;
    progressTimer = setTimeout(() => {
      const max = scroller.scrollHeight - scroller.clientHeight;
      if (max < 200) return;
      const p = Math.min(1, Math.max(0, scroller.scrollTop / max));
      api.setProgress(id, Math.round(p * 100) / 100).catch(() => {});
    }, 800);
  }

  const reasons = $derived(
    a && !a.extracted && a.extract_failed
      ? 'Only the feed’s summary is available here; the full article couldn’t be fetched (it may be paywalled).'
      : null
  );
</script>

<article class="reader" class:mobile bind:this={scroller} onscroll={onScroll} aria-busy={app.articleLoading}>
  {#if mobile}
    <header class="m-top">
      <button class="back" onclick={closeArticle}><Icon name="back" size={20} stroke={2} />Back</button>
      <div class="grow"></div>
      <button class="icon-btn" onclick={() => openDialog('reader')} aria-label="Reader settings"><span class="aa">Aa</span></button>
    </header>
  {:else if a}
    <div class="toolbar">
      <button class="btn ghost" onclick={() => toggleSaved(a.id)} aria-pressed={a.is_saved}>
        <Icon name="bookmark" size={16} fill={a.is_saved} />{a.is_saved ? 'Saved' : 'Save'}
      </button>
      <button class="btn ghost" onclick={() => shareArticle(a)} title="Copy the original link (c)"><Icon name="link" size={16} />Copy link</button>
      <a class="btn ghost" href={a.url} target="_blank" rel="noopener noreferrer"><Icon name="external" size={16} />Open original</a>
      <div class="grow"></div>
      <button class="btn ghost quiet" onclick={() => openDialog('reader')} aria-label="Reader settings">Aa</button>
      <button class="btn ghost quiet" onclick={() => markRead(a.id, !a.is_read, { undo: true })}>{a.is_read ? 'Mark unread' : 'Mark read'}</button>
      <button class="icon-btn" onclick={closeArticle} aria-label="Close article (Esc)"><Icon name="close" size={16} /></button>
    </div>
  {/if}

  {#if a}
    <div class="column">
      <div class="meta">
        <span class="mono chip">{a.feed_title}</span>
        <span class="mono when">// {clockLabel(a.published_at)}{a.minutes ? ` · ${a.minutes} min read` : ''}</span>
        {#if a.updated_at}<span class="mono tag">Updated</span>{/if}
      </div>
      <h1>{a.title || 'Untitled'}</h1>
      {#if a.author}<div class="byline">By {a.author}</div>{/if}
      {#if a.image_url && !(a.content_html || '').includes(a.image_url)}
        <img class="hero" src={a.image_url} alt="" referrerpolicy="no-referrer" onerror={(e) => e.currentTarget.remove()} />
      {/if}
      {#if reasons}<p class="notice">{reasons}</p>{/if}
      <div class="prose">
        {@html a.content_html || a.summary_html || '<p>No content in this item.</p>'}
      </div>
      <div class="end">
        <a class="btn" href={a.url} target="_blank" rel="noopener noreferrer"><Icon name="external" size={15} />Read on {a.feed_title}</a>
      </div>
    </div>
  {:else if app.articleLoading}
    <div class="loading">Loading…</div>
  {/if}

  {#if mobile && a}
    <nav class="m-actions" aria-label="Article actions">
      <button onclick={() => toggleSaved(a.id)} aria-pressed={a.is_saved}><Icon name="bookmark" size={21} fill={a.is_saved} />{a.is_saved ? 'Saved' : 'Save'}</button>
      <button onclick={() => markRead(a.id, !a.is_read, { undo: true })}><Icon name="circle" size={21} />{a.is_read ? 'Mark unread' : 'Mark read'}</button>
      <a href={a.url} target="_blank" rel="noopener noreferrer"><Icon name="external" size={21} />Original</a>
      <button onclick={() => shareArticle(a, { preferSheet: true })}><Icon name="share" size={21} />Share link</button>
    </nav>
  {/if}
</article>

<style>
  .reader { flex: 999 1 420px; min-width: 0; overflow-y: auto; display: flex; flex-direction: column; background: var(--card); }
  .toolbar {
    position: sticky; top: 0; z-index: 2; background: var(--card); padding: 10px 20px; border-bottom: 1px solid var(--divider);
    display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
  }
  .toolbar .btn { height: 34px; padding: 0 11px; text-decoration: none; }
  .quiet { color: var(--label); }
  .grow { flex: 1; }
  .column { width: 100%; max-width: var(--reader-width); margin: 0 auto; padding: 32px 40px 64px; display: flex; flex-direction: column; gap: 16px; }
  .meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .chip { font-size: 11px; font-weight: 600; padding: 4px 8px; border-radius: 4px; background: var(--chip); color: var(--text); }
  .when { font-size: 11px; letter-spacing: 0.1em; color: var(--label); }
  .tag { font-size: 9.5px; font-weight: 600; padding: 2px 5px; border-radius: 4px; border: 1px solid var(--border); color: var(--label); }
  h1 { margin: 0; font-size: 40px; line-height: 1.12; font-weight: 600; letter-spacing: -0.025em; overflow-wrap: anywhere; }
  .byline { font-size: 14px; color: var(--muted); }
  .hero { width: 100%; max-height: 420px; object-fit: cover; border-radius: 12px; background: var(--chip); }
  .notice { margin: 0; padding: 12px 14px; border-radius: 10px; background: var(--chip); font-size: 13.5px; color: var(--muted); }
  .end { margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--divider); }
  .end .btn { text-decoration: none; }
  .loading { padding: 60px; text-align: center; color: var(--faint); }

  .reader.mobile { position: fixed; inset: 0; z-index: 20; }
  .m-top { position: sticky; top: 0; z-index: 2; background: var(--card); padding: calc(env(safe-area-inset-top) + 6px) 8px 6px; display: flex; align-items: center; border-bottom: 1px solid var(--divider); }
  .back { height: 44px; padding: 0 10px; border: 0; background: transparent; display: flex; align-items: center; gap: 4px; font-size: 16px; font-weight: 500; color: var(--text); }
  .aa { font-size: 17px; font-weight: 600; color: var(--text); }
  .reader.mobile .column { padding: 22px 22px 120px; gap: 14px; }
  .reader.mobile h1 { font-size: 28px; line-height: 1.18; }
  .m-actions {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 3; background: var(--card); border-top: 1px solid var(--divider);
    padding: 8px 10px calc(env(safe-area-inset-bottom) + 8px); display: flex; justify-content: space-around;
  }
  .m-actions button, .m-actions a {
    width: 80px; height: 54px; border: 0; background: transparent; display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 4px; font-size: 11.5px; font-weight: 500; color: var(--text); text-decoration: none;
  }
</style>
