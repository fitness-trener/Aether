# Can Aether Run a Copy of Facebook?

A capability audit of Aether v0.3 against the engineering reality of a Facebook-class social platform, with an honest accounting of what's missing, what would have to ship, and what the question is actually asking.

---

## TL;DR

No. Not today, not in any direct sense. Aether v0.3 cannot serve a single HTTP request without external scaffolding, cannot parse JSON, cannot hold a TCP socket open, cannot run two functions concurrently, and emits Python source against a roughly three-hundred-line standard library. Asking it to run Facebook is like asking a freshly minted theorem prover to host a CDN — the categories don't overlap.

The interesting question is the one underneath. Facebook is not a single program; it is roughly two thousand services held together by a handful of disciplines (capability boundaries, contract enforcement at API edges, structured failure handling, policy as code). Aether is, by design, a language for those disciplines. The honest answer is that Aether could plausibly host the *authored policy and agent layers* of a Facebook-class system once a list of named substrate gaps closes — and that list is long but finite. The rest of the report enumerates it.

---

## 1. What Facebook actually is

To answer the question seriously, the bar has to be named. A Facebook clone in any meaningful sense includes at minimum:

A **stateless web/API tier** serving GraphQL or a thrift-style RPC at sustained millions of requests per second. A **social-graph store** — internally TAO, a write-through cache layered over sharded MySQL, handling trillions of edges. A **News Feed ranking pipeline** combining hundreds of ML models with per-user candidate retrieval, page-build, and rendering, all on a sub-second budget. A **media subsystem** — Haystack for photos, F4 for cold storage, custom encoders for video, live-streaming infrastructure for millions of concurrent broadcasts. A **search backend** (Unicorn) indexing the social graph in near-real-time. A **messaging tier** carrying end-to-end-encrypted traffic at WhatsApp-class volume with delivery guarantees. An **ads serving stack** picking from billions of candidates in under a hundred milliseconds. A **content integrity stack** running spam, abuse, and policy classifiers on every upload. **Mobile clients** in native iOS and Android with offline support and background sync. A **build and deploy substrate** (Buck, Tupperware, Conveyor) sized for a monorepo whose changes are measured per hour, not per release. **ML training and serving** at exabyte scale. **Observability** — distributed tracing, logging, metrics, alerting, all custom because off-the-shelf doesn't scale to the volume.

The list is bounded but not small. Importantly, almost none of it is "business logic" in the textbook sense. It is mostly substrate — TCP, encoding, scheduling, storage, networking, accelerator orchestration. The fraction of Facebook's code that is genuine *policy* — who can see what, which post ranks above which, when a comment counts as harassment — is small relative to the substrate, but it is the part that matters for correctness, and it is the part that fails most expensively when it is wrong.

This decomposition matters because Aether's reach corresponds almost exactly to the policy fraction, not to the substrate.

---

## 2. Subsystem-by-subsystem mapping

This table is the audit. For each Facebook subsystem, the question is: can Aether v0.3 host it, host part of it, or not approach it at all?

| Subsystem | Aether v0.3 capacity | Why |
|---|---|---|
| HTTP/RPC server | None | No socket, no TLS, no protocol parser, no async I/O in the language. |
| GraphQL schema definition | Partial | Refinement types could express the schema; resolvers cannot be hosted natively. |
| Social graph storage | None | No DB driver, no connection pool, no MVCC primitives. |
| Feed ranking — ML inference | None | No tensor types, no GPU bindings, no vector ops, no FFI to PyTorch. |
| Feed ranking — candidate filtering | Plausible | Pure-functional list/set/map operations are exactly Aether's wheelhouse. |
| Photo/video encoding | None | No FFI to libavcodec or equivalent; no bytes manipulation beyond hashes. |
| Search indexing | None | No on-disk B-tree, no inverted index primitives, no concurrent writers. |
| Messaging delivery | None | No long-lived connections, no presence, no queue primitives. |
| End-to-end crypto | Partial | sha256/sha1/md5 only; no AES, no Curve25519, no Signal protocol primitives. |
| Ads auction logic | Plausible | The decision math is small, pure, and contract-friendly. |
| Spam/integrity classifier composition | Plausible | Pipeline-of-classifiers is a clean Aether shape. |
| Privacy/visibility rules | Strong fit | This is the canonical Aether use case — refinement-typed policy. |
| Content moderation rules | Strong fit | Same — declarative predicates over typed content. |
| Mobile native code | None | Aether targets Python source; no iOS/Android codegen path. |
| Build/deploy | None | No package manager, no incremental compilation infrastructure. |
| Observability — tracing/metrics | None | No spans, no statsd, no metric registry. |
| Schema validation at API edges | Strong fit | Refinement types are exactly this. |
| Database migration scripts | Plausible | Once a DB driver exists; the contract layer is a real win here. |
| A/B experiment gating | Strong fit | Policy predicates with capability scope. |
| Permission/role checks | Strong fit | The capability system was designed for this. |

The pattern is visible without reading the table closely. Aether is empty on the infrastructure rows and strong on the policy rows. The substrate gap is what makes "run Facebook" unanswerable in the literal sense; the policy fit is what makes it answerable in the useful sense.

---

## 3. The hard blockers

These are the gaps that prevent Aether from being a substrate for a Facebook-class service today. They are listed in roughly the order in which they would have to be addressed for the question to become live.

### 3.1 Single-threaded execution

Aether v0.3 transpiles to single-threaded Python. The keywords `async`, `await`, `spawn`, and `defer` are reserved in the grammar but unimplemented. A Facebook tier handling tens of thousands of concurrent connections per host is impossible to express in a language with no concurrency primitives. Every parallel agent loop, every fan-out RPC call, every background timer has to be orchestrated from outside the language — which means Aether is, today, a script-shaped tool, not a service-shaped one.

The path forward is named (the keywords are reserved, the grammar slot exists), but the implementation is non-trivial. A sound effect system in the presence of `async` requires deciding what happens to declared effects across `.await` points — Rust's answer is `Send` and `Sync` bounds; Aether will need an equivalent that respects its capability lattice. This is an open design problem, not a transcription job.

### 3.2 No async I/O, no protocol surface

Even with `async`, the standard library has no socket, no TLS, no HTTP parser, no DNS resolver, no protobuf codec, no thrift codec, no gRPC stack, no Postgres wire protocol, no Redis protocol. The IO surface is `print`, `readLine`, `readFile`, `writeFile`. A Facebook clone has to speak roughly thirty wire protocols on the read path alone. Each one is a multi-thousand-line library elsewhere; Aether has none of them and no mechanism for binding to existing ones.

### 3.3 No FFI

This is the meta-blocker. Python and Rust both win the Facebook question principally because they have decades of curated libraries. Aether has no FFI. There is no `import C.libavcodec`, no `extern "C" fn`, no ctypes equivalent. A model writing Aether cannot reach into the surrounding ecosystem; everything must be re-implemented inside Aether's grammar. This is acceptable for a research substrate, ruinous for a production one.

The fix is well-understood — emit Python source that calls into existing Python wheels, or compile to a target with a real ABI — but the semantic question is harder: an Aether function calling into an arbitrary C library cannot have its effects verified. The capability system stops at the FFI boundary. Any FFI design will have to introduce *effect ascription on imports* — the importer asserts which effects the foreign function performs, and the runtime enforces them at the call site — or accept that FFI is an unverified escape hatch.

### 3.4 SMT solver scaling

The post-v0.3 verifier roadmap commits to Z3 for refinement-type discharge. Z3 is excellent at small obligations and exponential at large ones. A Facebook-scale module graph — hundreds of thousands of functions, millions of contract clauses — will not be verifiable end-to-end in any feasible time. The only mitigation is modular and incremental verification: prove each module against the *interfaces* of its dependencies, cache the proof, re-verify only the modules whose interfaces or bodies changed. This is research-grade infrastructure (similar to what Liquid Haskell does with its proof cache), and it does not yet exist in Aether.

Until it does, Aether's verification story scales to one module, not to a graph the size of WWW.

### 3.5 Memory model

Aether transpiles to Python and inherits Python's memory model: refcounted heap, GIL, no zero-copy. A News Feed ranker that needs to traverse a serialized graph without copying gigabytes per request cannot do so in this substrate. Even after a native backend lands, Aether has no notion of ownership or borrowing — every value is conceptually copied at every binding. For data-plane code this is a non-starter. A real backend will need to either layer a borrow analysis on top of the contract system or accept that data-plane code lives in Rust.

### 3.6 Stdlib is too small to bootstrap a service

The current standard library is 300-odd lines. No regex, no JSON parser (the AST tooling has its own; user code does not get one), no UUID, no base64, no datetime arithmetic beyond Instant/Duration, no logging framework, no test framework beyond what `aether test` provides for reference programs. Building anything HTTP-shaped requires building dozens of these from scratch. Each one is straightforward; the aggregate is years of work to reach Python's standard-library breadth, and that's before third-party libraries.

### 3.7 No deployment story

There is no Aether package manager (`pip install aether-lang` installs the toolchain, not user packages). There is no version resolution, no semantic-versioning convention, no lockfile format, no binary distribution. A Facebook-scale system has tens of thousands of internal packages; Aether has no way to express dependency graphs at that scale, let alone resolve them. This is purely engineering work, not research, but it is engineering work that has not happened.

### 3.8 No observability hooks

Facebook's runtime is instrumented at every RPC boundary, every cache miss, every async wakeup. Aether has `print` and a structured log effect. There is no span tracing, no metric counter, no histogram, no flight recorder. A service built in Aether would be operationally blind in production.

### 3.9 Effect lattice granularity

The effect lattice (`pure`, `fs.read`, `net.fetch(url-glob)`, `db.read`, etc.) is well-designed for AI-authorable business logic but too coarse for systems work. There is no effect for *blocking on a mutex*, no effect for *waiting on a channel*, no effect for *holding a connection from a pool*, no effect for *consuming a token bucket*. A service-shaped language needs a richer lattice that captures contention and resource ownership, not just I/O categories. This is design work; the lattice is intentionally minimal in v0.3 because the focus was on what an LLM can reliably declare. Expanding it changes that calculus.

### 3.10 No incremental compilation infrastructure

`aether check` and `aether run` re-parse and re-elaborate the whole program every invocation. At a few hundred functions this is fine; at Facebook scale it is unacceptable. Incremental compilation — change a function, re-check only the affected dominators — is standard in modern compiler design (rustc, Roc, Unison) and absent in Aether. Without it, the edit-verify loop that is Aether's central pitch becomes minute-scale, not second-scale, at any nontrivial size.

---

## 4. Where Aether would legitimately contribute

If the question shifts from "can Aether *be* the substrate" to "can Aether *meaningfully participate in* a Facebook-class system," the answer changes. These are the layers where Aether's design pays for itself even today, with v0.3 semantics and a Python transpile target.

### 4.1 The privacy and visibility policy DSL

Who can see this post? Who can comment? Who is blocked? Who is a restricted-mode follower? Facebook's privacy rules are policy predicates over a typed social graph, and policy bugs are the most expensive bugs the company ships. A refinement-typed predicate language with capability scoping is what you would design from scratch to express these rules. Aether's `requires`/`ensures` with refinement types maps directly onto "this rule must satisfy this invariant for every viewer/post pair." The SMT pass, once it lands, can prove things like "no rule chain admits a post visible to a user the author has blocked" — properties that are unprovable in Python's type system and only tediously testable in Hack's.

This is the use case where Aether could justify its existence inside an organization that already runs Python and Rust for everything else.

### 4.2 Content moderation rule composition

Spam, integrity, hate-speech, and impersonation rules are similarly predicate-shaped, similarly high-stakes, and similarly hard to audit when written in general-purpose code. Composing classifiers into rule chains where each chain has a contractually defined output type and a declared set of side effects (logging only, no DB write, no model fetch) is exactly the shape Aether is built for. The capability system prevents a rule from accidentally calling out to a third-party scoring API; the effect system prevents a "read-only" classifier from silently mutating user state.

### 4.3 API schema and edge validation

The contract layer at every GraphQL or RPC entry point is a refinement-type discipline. Today Facebook expresses these in Hack with custom annotations and runtime checks; an Aether-authored schema layer would compile-time discharge most of them. The wire protocol itself stays in C++; the validation layer rides on top in Aether and is verified.

### 4.4 Agent-authored automation

Meta runs increasing amounts of LLM-authored code — internal tools, content classifiers, scripted operations against the social graph, automated SRE workflows. Anywhere an LLM produces a program intended to run autonomously against production data, the fix-loop discipline of Aether (canonical AST, structured diagnostics, contract verification) is materially safer than the equivalent Python-with-a-test-suite. Bounded verification beats unbounded testing on the kind of program a model emits.

### 4.5 Migration scripts and data-massaging jobs

Schema migrations, backfills, one-off cleanups against billion-row tables — the script-shaped work where a wrong WHERE clause is a billion-dollar incident. Aether's contract layer turns "this migration touches only rows where status='pending'" into a checkable predicate at the call site. The single-threaded execution model is a feature here, not a bug; migration scripts want determinism, not parallelism.

### 4.6 Fuzz harness and property-based testing

The canonical AST is a free property-based testing substrate. Generating well-typed Aether programs is mechanical; running them through `aether check` and the runtime is a one-loop fuzz harness. Facebook already runs internal fuzzers; an Aether-authored property suite over its policy modules would catch contract violations that Hyperion-style randomized testers miss.

---

## 5. What would have to ship for Aether to be a plausible substrate

If the question were "could a future Aether (call it v1.0) host the majority of a Facebook-class system," here is the minimum roadmap that would have to land. Each item is a known, named problem. None is research-novel beyond the SMT scaling work.

1. **A real concurrency story.** Implement the reserved `async`/`await`/`spawn` with an effect system that survives the introduction of suspension points. Decide how capabilities flow across futures.
2. **A native or JVM/CLR backend.** The Python transpile target makes Aether a script substrate. A real backend — LLVM, Cranelift, or .NET — turns it into a service substrate. Memory model decisions (ownership? GC? refcounting?) have to be made at this point.
3. **An FFI with effect ascription.** Bind to C/Rust libraries with declared effect signatures. Accept that the ascription is unverified; treat it as the trust boundary.
4. **Modular, incremental SMT verification.** Cache discharged obligations. Re-verify only what changed. Get end-to-end verification of a hundred-module program from minutes to seconds.
5. **A standard library of order 50,000 lines.** HTTP/1.1 and HTTP/2 server and client, TLS, JSON, protobuf, gRPC, a SQL driver protocol, Redis protocol, base64, UUID, regex, robust datetime, logging, metrics, tracing. None of this is novel; all of it is missing.
6. **A package manager and dependency resolver.** Names, versions, lockfiles, a registry. The model where every program is a single repo is fine for v0.3; it is not fine for production.
7. **An LSP and IDE story.** The fix-loop is great for autonomous synthesis; it is not the only authoring path. Human-in-the-loop authoring needs hover-types, go-to-definition, on-the-fly diagnostics.
8. **A richer effect lattice for systems work.** Mutex acquisition, channel send/recv, pool checkout, token consumption, GPU dispatch. Without these, systems-level reasoning about contention is impossible.
9. **Observability primitives.** Spans, metrics, structured events as first-class language constructs, not as logging calls.
10. **A deployment artifact format.** A signed bundle of verified bytecode plus capability manifest. Production deploys cannot re-verify on every host startup; the verifier's output has to be persistable and trusted.

This is roughly five to ten engineer-years of focused work, comparable in scope to what Rust did between 0.5 and 1.0. It is not impossible; it is the work that has not happened yet.

---

## 6. The right framing

The question "can Aether run a copy of Facebook" presumes that Aether is competing with C++, Java, Hack, and Rust to be the substrate of a planetary-scale service. It is not, and treating it as if it were sets the comparison up to fail in a way that obscures the more interesting answer.

Aether is competing for a narrower and newer category: the language in which *AI-authored, verification-critical components* live, inside a polyglot system where the substrate is already excellent at being a substrate. Facebook's C++ is not waiting to be replaced; Facebook's *Hack policy code* and *Python automation code* and *increasingly, LLM-emitted internal tooling* arguably are. Those are the rows in the table that came up "plausible" or "strong fit." The substrate rows came up empty, and they will stay empty.

The right way to think about an Aether-on-Facebook future is the three-substrate decomposition from the earlier Opus 4.7 document: C++/Rust for the data plane, Python for the ML and the glue, Aether for the policy and the agents. Each substrate does what it was designed for. The boundaries are at the AST level (Aether emits source for the other two) and at the FFI level (Aether calls into them through a typed ascription). Neither boundary is novel; the discipline of crossing them safely is what Aether brings.

So: no, Aether cannot run a copy of Facebook today, and it cannot in any plausible v1.0 future run *all* of Facebook. What it can do — and what the question should really be asking — is whether it can run the parts of Facebook where the cost of getting policy wrong vastly exceeds the cost of running the policy slowly. For those parts, the answer is that Aether is closer to the right tool than anything else currently on offer, and the gap between v0.3 and a production deployment is a list of known engineering tasks rather than open research problems. That is a defensible position for a research substrate to be in. It is not the same as "ready to host the data plane of a planetary-scale social network," and the document does not pretend otherwise.
