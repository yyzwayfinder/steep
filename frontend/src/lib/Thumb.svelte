<script>
  // Article thumbnail with a source-monogram fallback when there is no image or it fails.
  import { monogram } from './format.js';

  let { src = null, title = '', size = 68, width = null, height = null } = $props();
  let failed = $state(false);
  const mono = $derived(monogram(title));
  const w = $derived(width ?? size);
  const h = $derived(height ?? size);
</script>

<div class="thumb" style:width="{w}px" style:height="{h}px" aria-hidden="true">
  {#if src && !failed}
    <img {src} alt="" loading="lazy" referrerpolicy="no-referrer" onerror={() => (failed = true)} />
  {:else}
    <span style:color={mono.color} style:font-size="{Math.round(Math.min(w, h) * 0.36)}px">{mono.letter}</span>
  {/if}
</div>

<style>
  .thumb {
    flex: none;
    border-radius: 10px;
    overflow: hidden;
    background: color-mix(in srgb, var(--chip) 70%, var(--card));
    display: flex;
    align-items: center;
    justify-content: center;
  }
  img { width: 100%; height: 100%; object-fit: cover; display: block; }
  span { font-weight: 700; filter: saturate(0.9); }
  :global(:root[data-theme='dark']) span { filter: brightness(1.6) saturate(0.7); }
  @media (prefers-color-scheme: dark) {
    :global(:root:not([data-theme='light'])) span { filter: brightness(1.6) saturate(0.7); }
  }
</style>
