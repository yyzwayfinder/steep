# Steep

A calm, self-hosted RSS reader for one person. It runs as a single Docker container on Unraid (or anywhere Docker runs), keeps everything in one SQLite file, and gives you a clean reading experience on desktop, iPad and iPhone.

- Full article text for feeds that only publish teasers
- OPML import (including Feedly exports) and export
- Magazine and List views, day headers, unread counts that update live
- Light and dark (charcoal) themes, keyboard shortcuts, swipe gestures on touch screens
- Share sends the article's original link, with tracking parameters stripped
- Installable as a web app on iPhone and iPad

## Install on Unraid

The image is private, so Unraid needs to sign in to GitHub's container registry once.

### 1. Create a read-only token (one time)

1. On GitHub, go to **Settings → Developer settings → Personal access tokens → Tokens (classic)** and choose **Generate new token (classic)**.
2. Name it `unraid-ghcr`, pick an expiry, and tick only **read:packages**.
3. Generate it and copy the token. You won't see it again.

### 2. Let Unraid pull the image (one time)

Open the Unraid terminal (the `>_` icon) and run:

```sh
docker login ghcr.io -u yyzwayfinder
```

Paste the token when it asks for a password. Unraid remembers this login.

### 3. Add the container

1. Open [`unraid/steep.xml`](unraid/steep.xml) on GitHub and copy its contents. In the Unraid terminal run:

   ```sh
   nano /boot/config/plugins/dockerMan/templates-user/my-steep.xml
   ```

   Paste, then save with Ctrl+O, Enter, Ctrl+X.
2. In Unraid go to **Docker → Add Container**, pick **steep** from the Template list.
3. Set a **Password** (or leave it blank and read the generated one from `/mnt/user/appdata/steep/initial_password.txt`).
4. Apply. Open `http://<unraid-ip>:8095`.

To update later: **Docker → Check for Updates**, then **apply update** on steep, like any other container.

### 4. Bring over your Feedly subscriptions

1. In a browser, open **feedly.com/i/opml** to download your subscriptions.
2. In Steep: **Settings → Import & export → Choose OPML file**.

Folders come across. Feedly saved articles and read state don't, and Reddit feeds are skipped because Reddit ended RSS on 13 November 2026. After importing, **Mark all read… → Older than a day** clears the backlog.

## Using it on iPhone and iPad

Open Steep in Safari, tap **Share → Add to Home Screen**. It then opens full screen like an app.

For one-tap subscribing from Safari, see **Settings → Quick add** for a two-minute Shortcuts recipe. On desktop, the same tab has a bookmarklet.

Remote access: keep the port on your LAN and reach it the way you reach the rest of Megaplex (Tailscale, WireGuard or a reverse proxy). Don't forward the port to the internet directly.

## Settings reference

| Variable | Default | What it does |
| --- | --- | --- |
| `STEEP_PASSWORD` | generated | Sign-in password. If unset, one is written to `/data/initial_password.txt`. |
| `TZ` | `America/Toronto` | Time zone for logs. |
| `PUID` / `PGID` / `UMASK` | `99` / `100` / `022` | File ownership in appdata (Unraid's nobody:users). |
| `FETCH_CONCURRENCY` | `8` | Feeds fetched at once. |
| `STEEP_REFRESH_MINUTES` | `30` | Default check interval per feed (minimum 5). Can be changed per feed. |
| `STEEP_TRUST_PROXY_HEADER` | unset | Header set by an authenticating reverse proxy (e.g. `Remote-User`) to skip Steep's own sign-in. |
| `STEEP_SECRET_KEY` | generated | Cookie signing key; generated and stored in `/data/.secret_key` if unset. |

Everything Steep stores is in the appdata folder: `steep.db` (plus `-wal`/`-shm` files while running). Your existing Appdata Backup covers it.

## Keyboard shortcuts

`j`/`k` next/previous · `o` open · `Esc` close · `v` original · `c` copy link · `s` save · `m` toggle read · `Shift+A` mark all read · `r` refresh · `/` search · `g a` / `g s` All / Saved · `[` sidebar · `1`/`2` Magazine/List · `a` add source · `?` help

## Development

```sh
# backend
cd backend
pip install -r requirements.txt pytest
STEEP_DATA_DIR=../data STEEP_PASSWORD=dev uvicorn steep.main:app --reload --port 8000
python -m pytest -q

# frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

`docker compose up --build` runs the whole thing on port 8095.

Pushing to `main` runs the tests and publishes `ghcr.io/yyzwayfinder/steep:latest`. Tagging `v1.2.3` also publishes `1.2.3`.

## How it works

- **Backend:** Python 3.12, FastAPI, APScheduler (polls due feeds every minute), httpx, feedparser, trafilatura for full text, nh3 for HTML sanitizing, SQLite in WAL mode with FTS5 search.
- **Frontend:** Svelte 5 + Vite, served by the backend as static files. Fonts are bundled; the page loads nothing from third parties except article images.
- **Security:** single password, signed HttpOnly cookie, a required `X-Steep` header on every write (blocks cross-site request forgery), strict Content-Security-Policy, and all feed HTML sanitized on the server.
