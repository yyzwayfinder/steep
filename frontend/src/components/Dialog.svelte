<script>
  import Icon from '../lib/Icon.svelte';
  import { closeDialog } from '../lib/state.svelte.js';

  let { title, width = 560, children, footer = null, onclose = closeDialog } = $props();
  let panel = $state();
  const id = `dlg-${Math.random().toString(36).slice(2, 8)}`;
  let opener = null;

  $effect(() => {
    opener = document.activeElement;
    const first = panel?.querySelector('input, select, textarea, button:not(.close)');
    (first || panel)?.focus();
    return () => opener?.focus?.();
  });

  function keydown(e) {
    if (e.key === 'Escape') {
      e.stopPropagation();
      onclose();
    }
    if (e.key === 'Tab' && panel) {
      const items = [...panel.querySelectorAll('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])')];
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        last.focus();
        e.preventDefault();
      } else if (!e.shiftKey && document.activeElement === last) {
        first.focus();
        e.preventDefault();
      }
    }
  }
</script>

<div class="scrim" role="presentation" onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div
    class="panel"
    role="dialog"
    aria-modal="true"
    aria-labelledby={id}
    style:max-width="{width}px"
    bind:this={panel}
    tabindex="-1"
    onkeydown={keydown}
  >
    <header>
      <h2 {id}>{title}</h2>
      <button class="icon-btn close" onclick={onclose} aria-label="Close"><Icon name="close" /></button>
    </header>
    <div class="body">{@render children()}</div>
    {#if footer}<footer>{@render footer()}</footer>{/if}
  </div>
</div>

<style>
  .scrim {
    position: fixed; inset: 0; z-index: 50; background: rgba(26, 26, 26, 0.32); display: flex; align-items: flex-start;
    justify-content: center; padding: max(48px, env(safe-area-inset-top)) 16px 16px; overflow-y: auto;
    animation: fade 0.15s ease;
  }
  .panel { width: 100%; background: var(--card); color: var(--text); border-radius: 18px; border: 1px solid var(--border); display: flex; flex-direction: column; outline: none; max-height: calc(100dvh - 64px); }
  header { padding: 20px 20px 12px 24px; display: flex; align-items: center; justify-content: space-between; }
  h2 { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.01em; }
  .body { padding: 0 24px 20px; overflow-y: auto; }
  footer { padding: 14px 24px; border-top: 1px solid var(--divider); display: flex; flex-wrap: wrap; align-items: center; gap: 10px; justify-content: flex-end; }
  @keyframes fade { from { opacity: 0; } }
  @media (max-width: 600px) {
    .scrim { padding: 0; align-items: flex-end; }
    .panel { border-radius: 18px 18px 0 0; max-height: 92dvh; padding-bottom: env(safe-area-inset-bottom); }
  }
</style>
