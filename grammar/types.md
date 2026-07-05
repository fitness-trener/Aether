# Aether Type System (v0.1)

Aether is gradually typed at function bodies, statically typed at function/module boundaries. v0.1 ships a working type *checker* — not a solver. Refinement predicates are checked at runtime. Everything else is checked statically.

## Primitive types

    Int        // arbitrary-precision signed integer
    Float      // 64-bit IEEE-754
    Bool       // true | false
    String     // immutable UTF-8 string
    Bytes      // immutable byte sequence
    Unit       // the trivial type, sole value `()`

`Int` is arbitrary-precision: arithmetic never overflows or wraps. This is
specified, not an accident of the Python runtime — contract reasoning
(`ensures`, SMT proving) assumes mathematical integers. Code that needs
fixed-width wrapping semantics must mask explicitly, e.g.
`x band 18446744073709551615` for u64.

## Parameterised types

    List<T>          // ordered sequence
    Map<K, V>        // key-value map, K must be hashable
    Set<T>           // unordered set, T must be hashable
    Option<T>        // Some(T) | None
    Result<T, E>     // Ok(T) | Err(E)

These are the *only* built-in collection and sum-type families. There is no `Array`, `Tuple` (records cover that), `Either`, or `Maybe`.

## Records

    record Point do
      x: Float
      y: Float
    end

Records have structural equality and are immutable by default. In v0.1, construct
records positionally — the record decl emits a constructor with parameters in
declared order:

    let p1 = Point(0.0, 0.0)
    let p2 = Point(p1.x + 1.0, p1.y)        // works in v0.1

A planned brace-init form is **not in v0.1** (see SPEC_ISSUES S-006):

    let p2 = Point { x = p.x + 1.0, y = p.y }   // ❌ parses as map literal, will fail

## Tagged unions

    union Shape do
      case Circle(radius: Float)
      case Rectangle(width: Float, height: Float)
      case Triangle(base: Float, height: Float)
    end

Constructors are accessed as `Shape.Circle(2.0)`. Pattern matching is exhaustive — the type checker emits an error if any `case` is missing.

## Refinement types

    type Email = String where matches?(self, EMAIL_REGEX)
    type PositiveInt = Int where self > 0
    type Probability = Float where self >= 0.0 and self <= 1.0

Inside the refinement clause, `self` is the candidate value. The predicate is checked at runtime when a value crosses a function or module boundary into the refined type. Inside a function body, the refinement is *assumed* — the type checker does not re-prove it.

This is intentional: v0.1 trades static guarantees for low complexity. v0.2 may add an SMT pass.

## Capability types

    FileHandle<Read>
    FileHandle<Write>
    FileHandle<ReadWrite>
    Connection<Postgres>
    HttpClient<JsonApi>

The parameter is a phantom tag — operations are typed against it at the standard library level. v0.1 enforces capability tags via the type checker; runtime checks are stub.

## Type ascription

    let x: Int = parseInt!("42")    // ascription on `let` — works in v0.1
    let y = (3.14 as Float)         // ❌ NOT IN v0.1 — value-level `as` is parked (see SPEC_ISSUES S-013)

`as` performs a *checked* conversion when the target is a refinement type, an *infallible* coercion otherwise (e.g. `Int as Float`). There is no implicit numeric coercion.

## Type tests

    if x is Email then ... end

`is` returns `Bool` and, in the `then` branch, narrows the static type of `x` to `Email`.

## Generic functions

    function map<T, U>(xs: List<T>, f: function(T) returns U) returns List<U>
      effects pure
      ensures result.length == xs.length
    do
      ...
    end

Type parameters are written in angle brackets after the function name. They may appear in parameters, return type, contracts, and effect rows.

## Subtyping

There is no subtyping. Refinement types are *not* subtypes of their base — they are convertible via `as` (checked) or implicitly when passed where the base is expected (the refinement predicate is asserted at the boundary).

## Inference

Inside a function body, every `let` binding is inferred from its initializer. Function parameters and return types are never inferred — they are always written.

## Equality and hashability

    Int Float Bool String Bytes Unit                          — hashable, comparable
    record / union of hashable fields                          — hashable
    List<T> / Map<K,V> / Set<T> with hashable elements/keys    — hashable
    function types                                             — neither hashable nor comparable

## Disallowed in v0.1

- Higher-kinded types (no `F<_>`).
- Trait/typeclass abstraction.
- Subtyping.
- Implicit numeric coercion.
- Variadic arguments.
- Default argument values.
- Method-call syntax (`x.foo(y)`); use `foo(x, y)`. Field access `x.field` is the only `.` form.
