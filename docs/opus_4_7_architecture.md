# Opus 4.7 on Aether — A Cognitive Architecture for AI-Authored Agents

Status: forward-looking design study. Grounded in Aether v0.3 semantics (locked grammar, effect lattice, capability gating, structured diagnostics) and the v0.2 roadmap commitment to an SMT verification pass via Z3. Where the document depends on a not-yet-shipped pass it is flagged "(post-v0.3)".

---

## Part 1 — Architecture

### 1.1 What Opus 4.7 has to be

Opus 4.7 is an agent system: it takes a user goal, decomposes it, calls tools, observes results, repairs its own output when the contract isn't met, and produces a verified deliverable. The interesting engineering question is not "how fast can it run inference" — that is solved upstream by whatever model serves the calls — but "what is the smallest set of invariants the runtime can enforce so that every action the agent takes is provably bounded by the user's intent." That set of invariants is what an Aether substrate buys you and what a Python or Rust substrate, for entirely defensible reasons, does not.

Three subsystems carry the load. The **Cognitive Router** receives a goal and dispatches it to a skill, sub-agent, or tool. The **Tool Execution Sandbox** runs the selected tool under a declared capability profile and surfaces a structured result. The **Self-Healing Metaloop** sits above both, ingests the model's candidate outputs, and re-prompts when the output fails to satisfy its declared contract. Each subsystem maps onto exactly one Aether construct, and the mapping is what gives the architecture its leverage.

### 1.2 The Cognitive Router

A router in conventional designs is a switch statement, possibly augmented with an embedding-similarity lookup. In Aether, the router is a module whose dispatched-to targets each declare their own `requires` (contract precondition), `effects`, and module-level `requires capability` set. The router's job collapses to: prove, for the candidate target *t* and the inbound message *m*, that *m* satisfies *t*'s declared precondition and that *t*'s effect set is a subset of what the router has been granted to forward.

In code:

```aether
module router
  requires capability log
  requires capability dispatch
  exports route

  type Query = String where length(self) > 0 and length(self) <= 65536
  type Verdict = { target: ModuleId, args: Json }

  function route(q: Query) returns Result<Verdict, RouteError>
    effects log
    requires length(q) > 0
    ensures result is Ok implies grantedTo(result.target) >= effectsOf(result.target)
  do
    let candidates = match q
      case classifyAs(IntentSearch)     then [retriever, web_search]
      case classifyAs(IntentCompute)    then [calculator, solver]
      case classifyAs(IntentSideEffect) then [tool_runtime]
      case _                            then []
    end
    return firstSatisfying(candidates, q)
  end
end
```

Three things are happening here that no Python or Rust router gives you for free.

First, the inbound message is a refinement type. The literal string `String where length(self) > 0 and length(self) <= 65536` is checked at the function boundary; the implementation body can assume the predicate without re-proving it. A model writing a downstream skill that consumes `Query` does not need defensive nil-checks. The substrate eliminated the class of bug.

Second, the `ensures` clause references `grantedTo` and `effectsOf` — both stdlib introspection functions over the module graph. Under the v0.2 SMT pass the verifier discharges this proof obligation statically: the router cannot compile if there is any reachable target whose effect set exceeds what the router holds. The router becomes a *capability firewall*, not just a dispatcher.

Third, the body uses `match` exhaustively. The type checker refuses to accept a `match` over a closed union that misses a case. There is no fall-through path the model can forget. Combined with the canonical AST law (`parse(print(ast)) == ast`), the router's dispatch table is itself a manipulable data structure that the agent can rewrite at runtime — and any rewrite that breaks exhaustiveness or violates the ensures clause fails to compile. Self-modification stays inside the safety envelope.

### 1.3 The Tool Execution Sandbox

Tools in Opus 4.7 are first-class Aether modules. A tool declaration looks like:

```aether
module tools.web_fetch
  requires capability net
  requires capability log
  exports fetch

  type Url = String where startsWith?(self, "https://") and length(self) <= 2048

  function fetch(u: Url, timeoutMs: Int) returns Result<HttpResponse, FetchError>
    effects net.fetch(u), log
    requires timeoutMs > 0 and timeoutMs <= 30000
    ensures result is Ok implies result.status >= 100 and result.status < 600
  do
    let client = HttpClient.default()
    return client.get(u, timeoutMs)
  end
end
```

The Sandbox itself is then a meta-module that accepts a tool name, looks up the AST, and invokes it under a *granted* capability set:

```aether
module sandbox
  requires capability dispatch
  exports invoke

  function invoke(toolId: ModuleId, args: Json, grant: CapabilitySet)
      returns Result<Json, SandboxError>
    effects log
    requires verifiedAst?(toolId)
    requires capabilitiesOf(toolId) <= grant
    ensures result is Err implies result.err in {Timeout, ContractViolation, CapabilityDenied}
  do
    return runUnder(toolId, args, grant)
  end
end
```

The `requires capabilitiesOf(toolId) <= grant` clause is the linchpin. The check is at the contract layer, not the runtime; under SMT verification the sandbox cannot even *be called* with a tool whose capabilities exceed the grant. This collapses what is, in a Python or Rust system, a maze of allow-list configuration, optional middleware, and per-call argument validation into a single proof obligation that the type system either discharges or refuses.

Two further properties matter for Opus 4.7. Aether's effect lattice has `pure` at the bottom and a strict subset rule for composition, so a tool that declares `effects net.fetch(u)` cannot be silently wrapped in a pure helper that exfiltrates data through `fs.write` — the wrapping won't type-check. And the sandbox's structured diagnostics — every failure carries a stable code from the E01xx–E08xx ranges with a machine-readable `extra` dict — feed the metaloop without requiring the parent system to parse English error text. Failure is data.

### 1.4 The Self-Healing Metaloop

The metaloop is the loop that takes a fuzzy intent, asks the model for an Aether candidate, runs `aether check`, and re-prompts if the check fails. The structure is:

```aether
module metaloop
  requires capability llm
  requires capability log
  exports synthesize

  function synthesize(spec: Spec, budget: Int)
      returns Result<Module, SynthesisError>
    effects llm.complete, log
    requires budget > 0 and budget <= 16
    ensures result is Ok implies aetherCheckPasses?(result.module)
  do
    var attempt = 0
    var lastDiag: List<Diagnostic> = []
    while attempt < budget do
      let candidate = llmEmit(spec, lastDiag)
      let diag = aetherCheck(candidate)
      if diag.empty?() then
        return Ok(candidate)
      end
      lastDiag = diag
      attempt = attempt + 1
    end
    return Err(BudgetExhausted(lastDiag))
  end
end
```

Three properties make this loop converge in practice where a corresponding Python loop would oscillate.

**Canonical AST.** The model's output is parsed to an AST, then printed back canonically. The next iteration's prompt never contains stylistic noise — whitespace, comment placement, identifier reordering, redundant parentheses are gone. The model sees its own previous attempt in exactly the form the verifier saw it. This is what kills the "model fixes a syntactic ghost while the real bug persists" failure mode.

**Diagnostic-as-API.** Each E03xx (contract), E07xx (capability), and E08xx (effect) diagnostic carries a typed `extra` dict — the failing clause text, the offending arguments, the unsatisfied effect, the missing capability. The metaloop ships this dict to the model rather than the human-readable rendering. The model gets a structured patch target, not a paragraph to comprehend.

**Monotone progress (post-v0.3).** Once the SMT pass lands, each successful narrowing — a refinement clause satisfied, an effect dropped from the violated set, a capability constraint discharged — is verifiable independently. The loop has a measurable progress metric: the cardinality of the residual obligation set. Termination is no longer a leap of faith; it's a property of the verifier's output. Until then, the budget cap is the safety net.

### 1.5 How the three compose

The router calls the sandbox; the sandbox calls a tool; the metaloop wraps any model-authored module before it enters the tool registry. The composition is type-correct by construction:

```
user goal
  → router.route(q: Query)                  -- precondition checked
    → sandbox.invoke(toolId, args, grant)   -- capability subset proved
      → tool.fetch(u: Url, t: Int)          -- contract checked, effect declared
↳ if any contract violation surfaces, metaloop.synthesize re-emits the tool
```

No subsystem trusts another's claims; each is checked at the boundary. The agent runtime becomes a chain of small, individually verifiable steps rather than a monolith that has to be audited as a whole.

---

## Part 2 — Comparative Analysis

The comparison should be honest, not partisan. Python and Rust did not lose any race they were entered in. The question is whether they are the right substrate for *the specific subset of agent code that an LLM is authoring* — not for the inference engine, not for the embedding store, not for the orchestration runtime, but for the agent's reasoning and acting layer. Aether is a wager that for that subset, the human-readable affordances of mainstream languages are net negatives.

### 2.1 Python

Python is the default substrate of contemporary AI work and has earned that position. Its ecosystem advantage is real: PyTorch, Transformers, LangChain, llama-cpp, every embedding service, every vector database. Anything that touches model weights or vectors is shorter in Python than in any alternative.

Where it stops earning its keep is the agent layer. Python's type system is advisory — `mypy --strict` is opt-in, the `Any` escape hatch is one annotation away, and the runtime ignores types entirely. A model writing `def route(query: str) -> dict` and then returning a list of dicts produces code that runs, fails downstream, and surfaces the error several call frames removed from the bug. The fix-loop has nothing structured to grip on. Diagnostics are tracebacks: prose, line-anchored, and almost impossible to re-prompt with mechanically. Capability scoping in Python is conventionally enforced by sandboxing the entire subprocess — `--network none`, seccomp filters, restricted exec — because the language itself has no notion of which functions are permitted to make network calls. The check, when it happens, fires at runtime, after side effects have begun.

For Opus 4.7 specifically, the contrast is: in Python, the agent layer is a defensive shell of asserts, allowlists, retry decorators, and ad-hoc parsers wrapping LLM output. In Aether, those concerns are language features. The honest synthesis is that Opus 4.7's *substrate* — the inference client, the embedding pipeline, the vector index — should be Python, because that's where the ecosystem is. Its *agent layer* — the router, the sandbox, the metaloop, the tool registry — should be Aether, because that's where the verifier earns its keep. The boundary between them is the canonical AST: Aether transpiles to Python at the seam.

### 2.2 Rust

Rust is the harder comparison because Rust takes safety seriously. The borrow checker is a sound static analysis; the type system rejects data races; `unsafe` is a syntactically visible escape hatch the reviewer can grep for. Rust would be a defensible choice for the agent layer in a way Python is not.

The comparison turns on what is being proved. Rust proves memory safety and freedom from data races. Aether proves *which observable effects a function performs and which capabilities its containing module holds*. These are orthogonal properties; neither subsumes the other. A Rust function can be memory-safe and still leak data over the network; an Aether function with `effects pure` provably cannot. Conversely, an Aether function can be effect-correct and still own a buffer it shouldn't free, because Aether's substrate manages memory for it. The two type systems are answering different questions.

For an LLM-authored agent the relevant question is the Aether one. The bugs a model writes are almost never "use after free" — the substrate eliminates the entire class. They are "this tool was supposed to be a pure transform but it stamped a timestamp into the database." Rust's type system has no opinion on that bug; Aether's rejects the program at the call site of `db.write`. Rust would catch it only with a hand-built effect-tracking library — at which point you are reinventing Aether on top of a substrate whose strengths you're not using.

There is also a substrate-quality argument the other direction. Rust's concurrency model — async/await with sound borrow-checking across `.await` points — is a thing Aether v0.3 does not have. The keywords `async`, `await`, `spawn` are reserved but unimplemented. An agent that fans a routing decision out to twelve parallel tool calls cannot do so inside Aether today; it must orchestrate from outside, in Rust or Python. For Opus 4.7 the implication is similar to the Python case but inverted: Rust earns its place as the *orchestrator and the substrate VM*, while Aether is the agent's authored layer. The natural decomposition is Aether-on-Rust: Rust executes the AST, Rust schedules the fanout, Aether is the language in which the agent writes its own modules.

### 2.3 The three-substrate stack

Pursued honestly, the right answer for Opus 4.7 is not one substrate but three: Rust as the runtime VM and scheduler, Python as the inference and vector ecosystem bridge, and Aether as the language in which all *agent-authored* code is written. Each substrate is used for what it is best at. The boundaries are exactly two: the AST-to-bytecode boundary between Aether and Rust, and the FFI boundary between Aether and Python. Both are narrow, both are well-defined, and both are auditable.

---

## Part 3 — Insights

### 3.1 Fundamental advantages

The advantage that subsumes the others is that **the output of the compiler is the specification**. In a conventional language a function's signature and a function's behavior are loosely coupled — the signature constrains the types, the docstring describes the intent, and the implementation is correct if a human reviewer says so. Aether collapses signature, intent, and implementation into one artifact: the contract is the type, the type is checked, the implementation either satisfies it or fails to compile. When the metaloop produces a module that passes `aether check`, no human review step is required to confirm that the module does what the spec said; the verifier already did it.

The second advantage is that **diagnostics are an API, not a string**. Every error code is stable, every `extra` dict is typed, every fix-loop iteration consumes a machine-readable patch target. This makes the loop bounded in a way prose-based loops are not. A model can in principle correct a typed contract violation by inspecting which clause failed and what argument failed it; it cannot, in practice, correct a Python traceback in fewer than several iterations because the signal is too noisy.

The third advantage is **capability as a parse-time property**. An agent built on Aether cannot exfiltrate data through a tool it wasn't granted network access for, not because a sandbox catches the attempt at runtime, but because the program containing the attempt does not compile. This shifts the security posture from "detect and contain" to "refuse to construct." The two are not equivalent; the latter is the only one that's robust under the assumption that the author is an LLM and the author is fast.

The fourth advantage is **AST-first authorship**. Models emit structured output better than line-oriented text; the gap is widening, not narrowing. Aether centers the AST in the toolchain — parse, print, canonicalize, edit, diff. The format the model is best at producing is the format the verifier wants. There is no impedance mismatch.

### 3.2 Critical drawbacks

The drawbacks are real and naming them is the only honest move.

**Single-threaded substrate.** Aether v0.3 has no parallelism primitives. The cognitive router cannot fan out twelve tool calls in parallel from inside Aether. Every concurrent agent is, today, an Aether AST orchestrated by an external Rust or Python event loop. For an interactive agent this is acceptable; for a batch agent processing thousands of queries it is a hard ceiling. The path forward — implementing the reserved `async`/`await`/`spawn` keywords — is on the roadmap but not in the substrate.

**No mature ecosystem.** Every integration — LLM client, vector DB, embedding service, OAuth flow, payment gateway — is a hand-built FFI shim to a Python or Rust library. The shim is small but it is not free, and there is no equivalent of `pip install` for a developer who needs Stripe. This is a function of age, not design, but it is a fact about today.

**SMT solver scaling (post-v0.3).** Once the verification pass lands, Z3 will not be free. Refinement-heavy modules — those with predicates that involve string operations, integer-modular arithmetic, or quantified properties — can take seconds to verify. For interactive synthesis loops this is a real cost. The mitigation is incremental verification — only re-prove the obligation set affected by the diff — but that is research, not shipping infrastructure.

**Cold-start verification cost.** Even with incremental checking, a fresh checkout of an Opus 4.7 module graph must be verified end-to-end the first time. For a hundred-module agent this is minutes, not milliseconds. Production deploys will need a verified-artifact cache, signed by the verifier, distributed alongside source.

**Closed grammar.** By design Aether has exactly one syntactic form per semantic operation. The 47 keywords are locked. There is no record brace-init syntax (parked to v0.2; see SPEC_ISSUES S-006), no value-level `as` cast (S-013), no async story. A human engineer expecting the affordances of a mature language will find Aether spartan. The trade is deliberate — the smaller the surface, the easier the verifier — but it is a trade.

### 3.3 The paradigm shift

The deeper insight is that when the author of code is no longer a human, the design pressure on the language inverts.

Conventional language design has, for fifty years, optimized for human comprehension. Indentation conveys structure; comments carry intent; whitespace is rhetorical; naming is mnemonic. Type systems exist as much to communicate to the next maintainer as to constrain the compiler. The compiler is, in the end, a translator between two human-facing artifacts: source and binary.

When the author is an LLM, that pressure inverts. The language no longer needs to be easy for a human to read first; it needs to be easy for a verifier to check, and easy for a model to emit. Three consequences follow, and they are not incremental improvements — they are a different design space.

The first consequence is that **readability becomes a derived property**, not a design constraint. Canonical printing means there is exactly one rendering of any program. Style debates evaporate not because everyone agreed on the right answer but because the question stopped being well-formed. The model and the verifier both consume the canonical form; the human reads it last, if at all.

The second consequence is that **documentation moves into types**. An `ensures` clause is not a comment about the function's behavior; it is the function's behavior, expressed in a form the verifier can discharge. The docstring becomes redundant; worse, it becomes a place where stale information lives undetected. Aether's deliberate absence of a docstring convention is a statement.

The third consequence is the most consequential: **trust moves to the substrate, not to the author**. In a Python codebase, the reader trusts that the previous author understood what they were doing. In an Aether codebase, the reader trusts the verifier. The author — model or human — could be adversarial, careless, or simply wrong; if the program type-checks, the safety properties hold. This is the same shift that happened when banking moved from "trust the teller" to "trust the cryptographic protocol," and it is what makes LLM-authored code at scale workable. The middle layer — the model — remains nondeterministic; everything around it is forced to determinism. That is the only configuration in which a system whose author is a sampling process can be reasoned about.

The conclusion is not that Aether is finished or that Python and Rust are obsolete. They are not, and the comparison is not zero-sum. The conclusion is that an architecture like Opus 4.7 — an agent system whose code is authored by a model, executed under capability constraints, and repaired by a verification loop — is a different shape of system than what mainstream languages were designed to host. Aether is a wager that the right substrate for that shape of system is one that was designed for it on purpose, not retrofitted onto a language whose strengths were never about contract proofs and effect locality. The wager will be settled by whether the verifier scales, whether the ecosystem catches up, and whether the fix-loop converges in production. Each is a real question. None is rhetorical.
