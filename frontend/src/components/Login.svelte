<script>
  import { login } from '../lib/state.svelte.js';

  let password = $state('');
  let error = $state('');
  let busy = $state(false);

  async function submit(e) {
    e.preventDefault();
    busy = true;
    error = '';
    try {
      await login(password);
    } catch (err) {
      error = err.message;
      password = '';
    } finally {
      busy = false;
    }
  }
</script>

<main class="login dots">
  <form class="card" onsubmit={submit}>
    <div class="word"><span class="mark"><i></i><i></i></span>Steep</div>
    <label for="pw">Password</label>
    <!-- svelte-ignore a11y_autofocus -->
    <input id="pw" type="password" autocomplete="current-password" bind:value={password} required autofocus />
    {#if error}<p class="err" role="alert">{error}</p>{/if}
    <button class="btn primary" type="submit" disabled={busy || !password}>{busy ? 'Signing in…' : 'Sign in'}</button>
    <p class="hint">The password is <code>STEEP_PASSWORD</code> from your container settings, or the one in <code>initial_password.txt</code> in Steep's appdata folder.</p>
  </form>
</main>

<style>
  .login { min-height: 100dvh; display: flex; align-items: center; justify-content: center; padding: 20px; }
  form { width: 100%; max-width: 380px; padding: 32px; display: flex; flex-direction: column; gap: 12px; }
  .word { position: relative; font-size: 30px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 16px; }
  .mark { position: absolute; left: 2px; top: -2px; display: flex; gap: 3px; }
  .mark i { width: 5px; height: 5px; border-radius: 3px; background: var(--accent); display: block; }
  label { font-size: 13.5px; font-weight: 500; }
  .btn { height: 44px; justify-content: center; font-size: 14.5px; }
  .err { margin: 0; color: var(--bad); font-size: 14px; }
  .hint { margin: 8px 0 0; font-size: 12.5px; line-height: 1.5; color: var(--muted); }
  code { font-family: var(--mono); font-size: 11.5px; background: var(--chip); padding: 1px 4px; border-radius: 4px; }
</style>
