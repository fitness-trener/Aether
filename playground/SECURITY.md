# Aether Playground — Security Model

The playground at `playground/` accepts arbitrary user code over HTTP
and runs it through the Aether toolchain. The threat model below
describes what we defend against and what we explicitly punt to the
deployment environment.

## Threat model

A request body arriving at `POST /api/run` is *user-controlled* and
*untrusted*. The user can:

- Submit any byte string up to 8 KB as the `source` field.
- Pick any of the three allowed subcommands (`check`, `run`,
  `fix-loop`).

What they *cannot* do (these are the playground's contracts):

- Pass arbitrary CLI flags to `aether`.
- Spawn subprocesses outside the allowlist.
- Access any host file beyond the per-request temp directory.
- Hold any subprocess open longer than the documented timeout.
- Exfiltrate ambient environment secrets (the subprocess sees only
  `PATH`, `PYTHONDONTWRITEBYTECODE`, and `PYTHONPATH`).

## Defense layers

### Layer 1 — in-process (`playground/backend/sandbox.py`)

Every defense in this layer ships in the public repo and is exercised
by `tests/test_playground.py`. They are the floor of the security
guarantees; the deployment-time layers (below) are stacked on top.

1. **Input size cap** — 8 KB. Larger requests are rejected with a
   structured error before any subprocess is spawned.
2. **Subcommand allowlist** — only `check`, `run`, `fix-loop`. The
   string is checked verbatim against a tuple; nothing else reaches
   `subprocess.run`.
3. **Temp-file isolation** — the user's source is written to
   `tempfile.mkdtemp(prefix="aether_play_")/main.aeth`. The
   subprocess only sees that file. The directory is removed in a
   `finally` block whether the subprocess succeeds, fails, or times
   out.
4. **Resource limits via `setrlimit` in `preexec_fn`** — applied
   before `exec()`, so the limits are in force the instant the child
   starts:
       RLIMIT_AS      256 MB    (address space)
       RLIMIT_CPU       5 s     (cpu seconds, hard)
       RLIMIT_FSIZE     1 MB    (any single file the child writes)
       RLIMIT_NOFILE   64       (concurrent open files)
   We also `os.setsid()` so the child gets a fresh process group and
   the wall-clock timeout can `kill -PG` the entire tree if it spawns
   children.
5. **Wall-clock timeout** — `subprocess.run(timeout=5.0)`. Fires
   before the CPU rlimit if the child is sleeping or blocked on I/O.
6. **Output size cap** — 100 KB. Anything beyond is truncated and
   the response surfaces a `output_truncated: true` flag.
7. **Minimal environment** — the subprocess inherits only `PATH`,
   `PYTHONDONTWRITEBYTECODE`, and `PYTHONPATH`. Ambient secrets like
   `ANTHROPIC_API_KEY` (which the founder uses for the LLM fix-loop
   demo on their laptop) do NOT leak into the playground subprocess.

### Layer 2 — container-time

The `playground/Dockerfile` produces a minimal image. The
recommended `docker run` invocation:

```sh
docker run \
    --read-only \
    --tmpfs /tmp:size=64m,mode=1777 \
    --network none \
    --user nobody \
    --memory 512m \
    --cpus 1.0 \
    --pids-limit 64 \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    -p 8080:8080 \
    aether-playground
```

What each flag adds on top of Layer 1:

- **`--network none`** — closes the gap that the in-process sandbox
  does NOT close. A `fix-loop` invocation theoretically reaches the
  network via a Python escape; with `--network none` it can't.
  **This is the most important deploy-time flag.**
- **`--read-only` + `--tmpfs /tmp`** — the only writable surface is
  the per-request temp dir. A malicious program that escapes the
  rlimit on file-write still can't persist anywhere.
- **`--user nobody`** — even a full RCE bottoms out at an unprivileged
  user with no host access.
- **`--cap-drop ALL --security-opt no-new-privileges`** — defense in
  depth.
- **`--memory` + `--cpus` + `--pids-limit`** — outer caps that
  catch anything the in-process rlimits miss.

### Layer 3 — host-time

Run the container under a non-root account. Behind a reverse proxy
that enforces:

- HTTPS only.
- Rate limit per IP (e.g. 30 requests/minute).
- Request body size cap (e.g. 16 KB).
- WAF rule that drops requests where the JSON `source` field exceeds
  a per-deploy threshold.

## Known gaps (not closed at Layer 1)

These are deliberate scope choices for the in-process sandbox. The
container layer closes them. Without the container layer, the
playground is **not safe to expose to the public internet**.

- **Network access from the subprocess.** Closed by `--network none`.
- **Filesystem read access beyond the temp dir.** A malicious
  Aether program can `readFile("/etc/passwd")` through the stdlib;
  Layer 1 rlimits don't cover read access. Closed by `--read-only`
  + a minimal rootfs.
- **DoS via repeated requests.** Layer 1 enforces per-request
  resource caps; Layer 3 enforces per-IP request rate.

## What the regression test covers

`tests/test_playground.py` exercises the Layer 1 floor:

- Subcommand allowlist (reject unknown subcommand).
- Input size cap (reject 10 KB source).
- Output size cap (truncate 200 KB of stdout, set `output_truncated`).
- Wall-clock timeout (5 s of `print(...)` in a tight loop).
- Subprocess receives a clean env (no `ANTHROPIC_API_KEY` leak).
- Aether check on a known E0801 source returns the right diagnostic.

The Layer 2 and Layer 3 defenses are documented; their enforcement
is verified at deploy time, not in CI.

## How to report a security issue

Open an issue at `https://github.com/aether-lang/aether/issues` with
the label `security`. Critical issues: email the address in
`yc/marketing/ONE_PAGER.md`. Public disclosure after fix + 14 days.
