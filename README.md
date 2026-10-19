# FroogleDrive

A small Flask + HTMX app. You log in, browse a directory tree, and create
public share links (`/shares/<token>`) for files or folders. Only the share
links work without logging in.

## Run with Docker

```sh
cp .env.example .env
docker compose run --rm froogledrive python -m app.hash_password   # paste output into .env
docker compose up -d --build
```

Open http://localhost:8000. Compose mounts `./data` read-only at `/data`.
Change the bind mount in `docker-compose.yml` to point at your own directory.

## Configuration (environment)

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | — (required) | Flask session signing key |
| `FROOGLEDRIVE_USERNAME` | — (required) | Login username |
| `FROOGLEDRIVE_PASSWORD_HASH` | — (required) | Werkzeug hash from `python -m app.hash_password` |
| `FROOGLEDRIVE_SUBTITLE` | — | Text shown in parentheses after the name in the header |
| `FROOGLEDRIVE_ROOT` | `/data` | Directory to browse; nothing outside it is reachable |
| `PUBLIC_BASE_URL` | request host | Origin used in generated share links |
| `FROOGLEDRIVE_TRUST_PROXY` | `0` | Number of reverse proxies to trust for `X-Forwarded-*` |
| `FROOGLEDRIVE_SECURE_COOKIES` | `0` | Set `1` when served over HTTPS |
| `DATABASE` | `instance/shares.db` | SQLite file holding share links |

## Share links

- Tokens are 32 random URL-safe characters (`secrets.token_urlsafe(24)`).
- File links open a download page. Add `?dl=1` to download directly.
- Folder links can be browsed (but not left), let you download single files,
  and offer `/shares/<token>.zip` for the whole folder as a streamed zip.
- Expiry can be never, 1, 7, or 30 days. Revoke links from the **Shares** page.
  Revoked, expired, unknown, and deleted-target links all return a plain 404.

## Third-party assets

- Icons: [Adwaita icon theme](https://gitlab.gnome.org/GNOME/adwaita-icon-theme)
  (LGPLv3 / CC-BY-SA 3.0) in `app/static/icons/`, licence files included.
- Fonts: [Adwaita Sans / Adwaita Mono](https://gitlab.gnome.org/GNOME/adwaita-fonts)
  (SIL OFL 1.1), GNOME's interface fonts, in `app/static/fonts/`, converted to WOFF2.
- [HTMX](https://htmx.org) 2.0.4 (BSD Zero Clause).

## Development

```sh
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
.venv/bin/coverage run -m pytest && .venv/bin/coverage report   # line + branch, currently 100%
```

Note: the failed-login throttle (5 attempts / 5 min per IP) is kept in memory per worker process.
