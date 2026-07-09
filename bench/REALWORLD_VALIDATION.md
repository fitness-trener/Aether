# Real-world validation — Aether vs. vulnerability classes in high-user OSS

**Iteration 14 (loop phase 2).** After 13 improvement iterations (11
default-on detectors, E0710–E0720), this is the loop's second directive:
*implement Aether into programs that have a lot of users to find their
current issues in code.* Each case below takes the documented vulnerable
**shape** of a very-high-user open-source project, models the boundary
flow faithfully in Aether, and shows Aether refuses the composition the
real project permitted.

## What this proves — and what it does not (read first)

- Aether checks **Aether source**, not raw Python/C. These are faithful
  **models** of the real vulnerable shape, not literal transpilations of
  the upstream internals. The claim is: *the architecture-class maps 1:1,
  and Aether's compiler refuses it where the real toolchain accepted it.*
- The mapping for each case is stated explicitly (`<project>_repro.py`
  carries the real call and the `<->` Aether equivalent). A reader can
  check the map is honest.
- This is **not** a scan of live upstream repos producing new CVEs. It is
  evidence that the detector fires on the real-world *shape*, which is the
  precondition for a future in-language port to find live issues.

## Cases

| Project | Downloads | Class | CVE precedent | Aether verdict |
|---|---|---|---|---|
| **PyYAML** `yaml.load` | ~300M/mo | Insecure deserialization (CWE-502) | CVE-2017-18342, CVE-2020-1747 | **E0720** on `deserialize(raw)`; `schemaDecode` clean |
| **Flask/Jinja2** `render_template_string` | ~30M/mo | SSTI (CWE-94) | staple SSTI class | **E0719** on `renderTemplate("..."+name, "")`; fixed template clean |
| **requests** `get(user_url)` | ~500M/mo | SSRF (CWE-918) | metadata-endpoint theft | **E0710** on `net.fetch("*")`; host-pinned scope clean |
| **subprocess** `call(shell=True)` | stdlib (universal) | Command injection (CWE-78) | CVE-2022-1292 (same shape) | **E0714** on `shellExec("..."+arg)`; `shellArg` clean |
| **AWS IMDS fetch** (Capital One 2019) | ~100M records breached | SSRF→metadata (CWE-918) | the canonical real SSRF breach | **E0722** + **E0721** on the pinned `http://169.254.169.254/...` scope; https non-metadata clean |
| **Express** `res.send(reflected)` | ~30M/wk | Reflected XSS (CWE-79) | OWASP #2, ubiquitous | **E0725** on `htmlResponse("..."+q)`; `htmlEscape` clean (payload → `&lt;script&gt;`) |
| **lxml** `fromstring` (entities on) | ~50M/mo | XXE (CWE-611) | file read / SSRF via `<!ENTITY SYSTEM>` | **E0727** on `parseXml(raw)`; `parseXmlSafe` clean |

Each directory holds `<project>_repro.py` (the real shape + the 1:1 map),
`vulnerable.aeth` (refused), and `fixed.aeth` (passes + runs the payload
inert).

### PyYAML — `bench/realworld_pyyaml/`
`yaml.load(raw)` without a safe loader constructs arbitrary Python objects
(`!!python/object/apply:os.system`). Modeled as `deserialize(raw)` →
**E0720**. Fix `yaml.safe_load` ↔ `schemaDecode("ConfigV1", raw)` →
`aether run` prints the gadget string inert under the schema.

### Flask/Jinja2 — `bench/realworld_flask_ssti/`
`render_template_string("<h1>Hello " + name + "</h1>")` evaluates
`{{7*7}}`. Modeled as `renderTemplate("..." + name, "")` → **E0719**. Fix
= fixed template + escaped data ↔ `renderTemplate("...{}", name)` →
`aether run` prints `<h1>Hello {{7*7}}</h1>` inert.

### requests — `bench/realworld_requests_ssrf/`
`requests.get(user_url)` reaches any host, including the cloud-metadata
endpoint `169.254.169.254`. In Aether the reachable host set IS the effect
annotation: a fetcher of an arbitrary user authority must declare
`net.fetch("*")`, which **E0710** refuses (the SSRF precondition) before
any request is made. Fix = host-pinned scope
`net.fetch("https://api.trusted.example/preview/*")` → clean.

### subprocess — `bench/realworld_subprocess_cmdi/`
`subprocess.call("convert " + filename, shell=True)` runs
`x.jpg; rm -rf /`. Modeled as `shellExec("convert " + filename + ...)` →
**E0714**. Fix = quoted arg ↔ `shellExec(shellArg("convert ? ...", filename))`
→ `aether run` prints `EXEC(convert 'x.jpg; rm -rf /' ...)` — payload
quoted inert as one argument.

### Express reflected XSS — `bench/realworld_xss/`
`res.send("<h1>Results for " + req.query.q + "</h1>")` reflects the search
term unescaped → `<script>` runs in the victim's browser (OWASP #2).
Modeled as `htmlResponse("..." + q)` with `q: Untrusted<String>` →
**E0725**. Fix = `escapeHtml(q)` ↔ `htmlEscape(q)` → `aether run` shows the
payload as inert text `&lt;script&gt;...`.

### lxml XXE — `bench/realworld_xxe/`
`etree.fromstring(raw, resolve_entities=True)` on untrusted XML resolves
`<!ENTITY SYSTEM "file:///etc/passwd">` (file read / SSRF). Modeled as
`parseXml(raw)` → **E0727**. Fix = a hardened parser
(`resolve_entities=False`) ↔ `parseXmlSafe(raw)` → clean.

### AWS IMDS / Capital One 2019 — `bench/realworld_metadata_ssrf/`
The most-cited real SSRF breach: a server-side request to
`http://169.254.169.254/latest/meta-data/iam/...` returned IAM
credentials, replayed to read ~100M records from S3. The metadata host is
a fixed IP, so it is host-*pinned* — a wildcard-only allowlist (and
Aether's own E0710) accepts it. Modeled as
`net.fetch("http://169.254.169.254/latest/meta-data/iam/*")` → **E0722**
(metadata reach) **and** **E0721** (cleartext) on one line. This is the
case that motivated E0722: pinning is not enough; the *destination* is the
crown jewel. Fix = never fetch IMDS; use the credential provider ↔ an
https non-metadata endpoint → clean.

## Reproduce

    python -B -m transpiler.aether.cli check bench/realworld_pyyaml/vulnerable.aeth      # E0720, exit 2
    python -B -m transpiler.aether.cli run   bench/realworld_pyyaml/fixed.aeth           # inert
    python -B -m transpiler.aether.cli check bench/realworld_flask_ssti/vulnerable.aeth  # E0719, exit 2
    python -B -m transpiler.aether.cli run   bench/realworld_flask_ssti/fixed.aeth       # inert
    python -B -m transpiler.aether.cli check bench/realworld_requests_ssrf/vulnerable.aeth   # E0710, exit 2
    python -B -m transpiler.aether.cli check bench/realworld_subprocess_cmdi/vulnerable.aeth # E0714, exit 2
    python -B -m transpiler.aether.cli run   bench/realworld_subprocess_cmdi/fixed.aeth      # inert

## Next (surfaced for the loop)

The honest limitation above — model, not live-repo scan — is the real
phase-2 gap. Closing it needs either (a) an in-language port of a real
high-user module written natively in Aether, or (b) the source-taint
provenance pass (q3 convergent signal) so a Python→Aether importer could
auto-flag untrusted-read→sink flows in ported code. (b) is the higher
-leverage unlock and is the standing structural investment.
