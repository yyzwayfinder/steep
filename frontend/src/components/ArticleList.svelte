<script>
  import ArticleRow from './ArticleRow.svelte';
  import Icon from '../lib/Icon.svelte';
  import { groupByDay } from '../lib/format.js';
  import { app, loadArticles, loadMore, openDialog, scopeTitle } from '../lib/state.svelte.js';

  let { variant = 'wide' } = $props();

  let sentinel = $state();
  const sortKey = $derived(app.scope.type === 'saved' ? 'published_at' : 'published_at');
  const groups = $derived(variant === 'list' || variant === 'narrow' ? [{ label: null, items: app.items }] : groupByDay(app.items, sortKey));

  $effect(() => {
    if (!sentinel) return;
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) loadMore();
    }, { rootMargin: '600px' });
    io.observe(sentinel);
    return () => io.disconnect();
  });

  const emptyText = $derived(
    app.query
      ? `Nothing matches “${app.query}”.`
      : app.scope.type === 'saved'
        ? 'Nothing saved yet. Save an article to keep it here forever.'
        : app.prefs.unreadOnly
          ? 'You’re all caught up.'
          : 'No articles here yet.'
  );
</script>

<section class="list {variant}" aria-label="Articles in {scopeTitle()}">
  {#if app.hasNew}
    <div class="new-pill-wrap">
      <button class="new-pill" onclick={() => loadArticles(true)}><Icon name="refresh" size={14} />New articles · Show</button>
    </div>
  {/if}

  {#each groups as group (group.label ?? 'all')}
    {#if group.label}
      <div class="day mono" class:mobile={variant === 'mobile'}>{group.label}</div>
    {/if}
    {#each group.items as item (item.id)}
      <ArticleRow {item} {variant} />
    {/each}
  {/each}

  {#if app.loading}
    <div class="status" aria-live="polite">Loading…</div>
  {:else if app.loadError}
    <div class="status error">{app.loadError} <button class="btn ghost" onclick={() => loadArticles(true)}>Try again</button></div>
  {:else if !app.items.length}
    <div class="empty">
      <p>{emptyText}</p>
      {#if app.tree && !app.tree.folders.length && !app.tree.uncategorized.length}
        <button class="btn primary" onclick={() => openDialog('add')}><Icon name="plus" size={14} stroke={2.2} />Add your first source</button>
      {/if}
    </div>
  {/if}
  <div bind:this={sentinel} class="sentinel" aria-hidden="true"></div>
</section>

<style>
  .list { display: flex; flex-direction: column; }
  .day {
    position: sticky; top: 0; z-index: 2; padding: 14px 4px 8px; background: var(--card); color: var(--label);
    font-size: 11px; font-weight: 600; letter-spacing: 0.14em;
  }
  .day.mobile { padding: 10px 16px 8px; background: var(--canvas); border-bottom: 1px solid var(--border); border-top: 1px solid var(--border); }
  .status, .empty { padding: 40px 16px; text-align: center; color: var(--faint); font-size: 14px; }
  .status.error { color: var(--bad); }
  .empty p { margin: 0 0 16px; font-size: 15px; color: var(--muted); }
  .sentinel { height: 1px; }
  .new-pill-wrap { position: sticky; top: 8px; z-index: 3; display: flex; justify-content: center; height: 0; overflow: visible; }
  .new-pill { height: 34px; padding: 0 14px; border-radius: 17px; border: 0; background: var(--invert-bg); color: var(--invert-text); font-size: 13px; font-weight: 500; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 4px 14px rgba(0,0,0,.15); }
</style>
