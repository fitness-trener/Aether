# Aether — Deployment Handoff (H.B.3)

What Cowork can't do: register a domain, push DNS records, or click
"deploy" on a hosting provider. This document is the founder-facing
handoff that turns the artifacts in this repo into a live site at a
public URL.

The build steps below assume the public repo is at
`github.com/aether-lang/aether` and the founder has an account on
**fly.io** OR **Render**. Both work for this stack. Pick one;
instructions for both follow.

## What needs to be live

Three URLs, ideally on the same domain:

1. `https://aether-lang.dev/` → `web/index.html` (homepage).
2. `https://aether-lang.dev/playground` → playground HTTP server.
3. `https://aether-lang.dev/docs` → optional placeholder for now;
   can 302 to `https://github.com/aether-lang/aether#readme`.

The playground is the load-bearing surface. The homepage is a static
file pointing at it. If only one URL ships, ship the playground.

## Option A — fly.io (recommended)

fly.io has the cleanest path for a stateful container app with
`--read-only` rootfs and `--network none`-equivalent egress controls.

### 1. Create the app (one-time)

```sh
fly auth login
fly launch --no-deploy \
    --name aether-playground \
    --region sjc \
    --copy-config=false
```

`fly launch` will prompt to write `fly.toml`. Accept the defaults,
then **overwrite** the generated file with the contents at
`web/fly.toml.template` below.

### 2. fly.toml (commit this to the repo)

```toml
app = "aether-playground"
primary_region = "sjc"

[build]
  dockerfile = "playground/Dockerfile"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

[[services.tcp_checks]]
  grace_period = "5s"
  interval = "30s"
  timeout = "5s"

[[vm]]
  memory_mb = 512
  cpu_kind = "shared"
  cpus = 1

[env]
  PYTHONUNBUFFERED = "1"
```

### 3. Deploy

```sh
fly deploy
```

First deploy takes ~3 minutes. Subsequent deploys: under 60 seconds.

### 4. Confirm the security envelope

After deploy:

```sh
fly ssh console -a aether-playground -C "whoami"
# should print: playground   (NOT root)

fly ssh console -a aether-playground -C "id"
# should print: uid=10001(playground) gid=10001(playground) ...
```

If `whoami` returns `root`, the Dockerfile USER directive didn't
take — re-deploy.

### 5. Custom domain

```sh
fly certs add aether-lang.dev -a aether-playground
fly certs check aether-lang.dev -a aether-playground
```

DNS: at the registrar, add an A record pointing
`aether-lang.dev` to the IPv4 address fly returns from
`fly ips list -a aether-playground`, and an AAAA record to the IPv6.

Homepage at `/` is served by the playground container's HTTP server
(it returns `web/index.html` when the playground static dir is
swapped for the homepage at deploy time — see the static-routing
section below).

## Option B — Render

Render has slightly less infrastructure flexibility but a friendlier
GitHub-integration story. Cleaner for a non-DevOps founder.

### 1. Connect the repo

In the Render dashboard:

1. New → Web Service.
2. Connect `github.com/aether-lang/aether`.
3. **Runtime:** Docker.
4. **Dockerfile path:** `playground/Dockerfile`.
5. **Build context:** `.` (repo root).
6. **Plan:** Starter ($7/month is fine for a YC demo).
7. **Env vars:** `PYTHONUNBUFFERED=1`.
8. **Health check path:** `/api/health`.
9. **Auto-deploy on push:** yes.

### 2. Domain

Render → Settings → Custom Domains → `aether-lang.dev`. Follow the
prompt to add the CNAME at your registrar.

### 3. Confirm security

Render runs each web service as a non-root user by default; the
Dockerfile's `USER playground` directive is honored. Verify via
the Render shell:

```
whoami    # playground
```

## Serving the homepage at /

Two ways. Pick the one that fits your hosting story.

### Way 1 — Combined (recommended for fly / Render)

The playground's HTTP server (`playground/backend/app.py`) already
serves static files from `playground/static/`. To serve the
homepage at `/`, **copy `web/index.html` into
`playground/static/index.html`** at deploy time, replacing the
playground UI's `index.html`. Then move the playground UI to
`/play`.

A 4-line `web/build.sh` does this:

```sh
#!/bin/sh
set -e
mkdir -p playground/static/play
mv playground/static/index.html playground/static/play/index.html
cp web/index.html playground/static/index.html
```

Update the homepage's `href="/playground"` links to `href="/play"`
and run `web/build.sh` once before `fly deploy` / `git push`. The
Dockerfile picks up whatever is in `playground/static/` at that
moment.

### Way 2 — Separate static host

If you'd rather keep the homepage on Vercel / Netlify / Cloudflare
Pages and the playground on fly/Render:

- Push `web/index.html` to Vercel as a static site, point
  `aether-lang.dev` at it.
- Point `playground.aether-lang.dev` at the fly/Render container.
- Update the homepage CTA to `https://playground.aether-lang.dev/`.

Either way is fine. Way 1 minimises moving parts; Way 2 maximises
flexibility.

## The 90-second demo video

Recording instructions are in `yc/DEMO_NOTES.md`. After you record
and upload to YouTube unlisted:

1. Get the embed URL (looks like
   `https://www.youtube.com/embed/<ID>`).
2. Open `web/index.html`, find the `<!-- Founder action: replace
   this placeholder ... -->` block.
3. Uncomment the `<iframe>` tag, paste the embed URL.
4. Commit + push. Render/fly redeploys; the homepage now has the
   video above the fold.

## Pre-launch checklist

- [ ] `python3 -B scripts/run_all.py` exits 0 (all 20 PASS lines).
- [ ] Homepage loads at `https://aether-lang.dev/`.
- [ ] Playground loads at `https://aether-lang.dev/play` (or
      `https://aether-lang.dev/playground`).
- [ ] The "Try it now" CTA on the homepage actually opens the
      playground.
- [ ] Pasting `playground/examples/02_B1_pure_violation.aeth` into
      the playground and clicking "aether check" returns
      `[E0801]` in the output panel.
- [ ] HTTPS green. WAF / rate-limit configured at the
      hosting-provider level (Render: built-in; fly: needs
      `[http_service.concurrency]` config).
- [ ] Homepage video iframe shows the 90-second demo (or the
      placeholder is acceptably honest if the founder ships
      pre-record).
- [ ] `/api/health` returns 200 with `{"ok": true, "version":
      "0.3.0"}`.

When every box is ticked, the playground link goes in the YC
application form and into the demo video voiceover.
