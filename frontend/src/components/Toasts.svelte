<script>
  import { app, dismissToast } from '../lib/state.svelte.js';

  let { bottom = 40 } = $props();
</script>

<div class="toasts" role="status" aria-live="polite" style:bottom="calc({bottom}px + env(safe-area-inset-bottom))">
  {#each app.toasts as t (t.id)}
    <div class="toast" class:error={t.tone === 'error'}>
      <span class="msg">{t.message}</span>
      {#if t.undo}
        <button onclick={() => { t.undo(); dismissToast(t.id); }}>Undo</button>
      {/if}
    </div>
  {/each}
</div>

<style>
  .toasts { position: fixed; left: 0; right: 0; z-index: 60; display: flex; flex-direction: column; align-items: center; gap: 8px; pointer-events: none; padding: 0 16px; }
  .toast {
    pointer-events: auto; min-height: 44px; max-width: min(560px, 100%); padding: 6px 8px 6px 18px; border-radius: 22px;
    background: var(--invert-bg); color: var(--invert-text); display: flex; align-items: center; gap: 14px;
    font-size: 13.5px; font-weight: 500; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.18); animation: up 0.18s ease;
  }
  .toast.error { background: var(--bad); color: #fff; }
  .msg { padding: 6px 10px 6px 0; overflow-wrap: anywhere; }
  button { height: 32px; padding: 0 14px; border: 0; border-radius: 16px; background: var(--invert-sub); color: var(--invert-text); font-size: 13px; font-weight: 600; flex: none; }
  :global(:root[data-theme='dark']) button { color: #1c1c1e; }
  @keyframes up { from { transform: translateY(8px); opacity: 0; } }
</style>
