<script>
  import { monogram } from './format.js';

  let { title = '', src = null, size = 18, radius = 5 } = $props();
  let failed = $state(false);
  const mono = $derived(monogram(title));
</script>

{#if src && !failed}
  <img
    {src}
    alt=""
    width={size}
    height={size}
    loading="lazy"
    referrerpolicy="no-referrer"
    onerror={() => (failed = true)}
    style:border-radius="{radius}px"
    style:flex="none"
    style:background="var(--chip)"
  />
{:else}
  <span
    aria-hidden="true"
    style:width="{size}px"
    style:height="{size}px"
    style:border-radius="{radius}px"
    style:background={mono.color}
    style:font-size="{Math.round(size * 0.56)}px"
    class="mono-tile">{mono.letter}</span
  >
{/if}

<style>
  .mono-tile {
    color: #fff;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
  }
</style>
