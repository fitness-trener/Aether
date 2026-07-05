# Aether Standard Library (v0.1)

Brutally minimal. The list is small enough that a model can hold all of it in working memory.

## Core types (re-exported, always in scope)

    Int Float Bool String Bytes Unit
    List<T> Map<K,V> Set<T>
    Option<T> Result<T,E>

The constructors `Some`, `None`, `Ok`, `Err` are also always in scope.

## List<T>

    function length<T>(xs: List<T>) returns Int
      effects pure
      ensures result >= 0

    function empty?<T>(xs: List<T>) returns Bool
      effects pure
      ensures result == (length(xs) == 0)

    function head<T>(xs: List<T>) returns Option<T>
      effects pure

    function tail<T>(xs: List<T>) returns List<T>
      effects pure
      requires not empty?(xs)
      ensures length(result) == length(xs) - 1

    function append<T>(xs: List<T>, x: T) returns List<T>
      effects pure
      ensures length(result) == length(xs) + 1

    function prepend<T>(x: T, xs: List<T>) returns List<T>
      effects pure
      ensures length(result) == length(xs) + 1

    function concat<T>(xs: List<T>, ys: List<T>) returns List<T>
      effects pure
      ensures length(result) == length(xs) + length(ys)

    function get<T>(xs: List<T>, i: Int) returns Option<T>
      effects pure

    function map<T, U>(xs: List<T>, f: function(T) returns U) returns List<U>
      effects pure
      ensures length(result) == length(xs)

    function filter<T>(xs: List<T>, p: function(T) returns Bool) returns List<T>
      effects pure
      ensures length(result) <= length(xs)

    function foldLeft<T, A>(xs: List<T>, z: A, f: function(A, T) returns A) returns A
      effects pure

    function reverse<T>(xs: List<T>) returns List<T>
      effects pure
      ensures length(result) == length(xs)

    function range(lo: Int, hi: Int) returns List<Int>
      effects pure
      requires lo <= hi
      ensures length(result) == hi - lo

## List — D.1 expansion

    function sort<T>(xs: List<T>) returns List<T>
      effects pure
      ensures length(result) == length(xs)

    function sortBy<T, K>(xs: List<T>, key: function(T) returns K) returns List<T>
      effects pure
      ensures length(result) == length(xs)

    function take<T>(xs: List<T>, n: Int) returns List<T>
      effects pure
      ensures length(result) <= length(xs)

    function drop<T>(xs: List<T>, n: Int) returns List<T>
      effects pure
      ensures length(result) <= length(xs)

    function sum(xs: List<Int>) returns Int
      effects pure

    function product(xs: List<Int>) returns Int
      effects pure

    function all<T>(xs: List<T>, p: function(T) returns Bool) returns Bool
      effects pure

    function any<T>(xs: List<T>, p: function(T) returns Bool) returns Bool
      effects pure

    function find<T>(xs: List<T>, p: function(T) returns Bool) returns Option<T>
      effects pure

    function flatMap<T, U>(xs: List<T>, f: function(T) returns List<U>) returns List<U>
      effects pure

    function count<T>(xs: List<T>, p: function(T) returns Bool) returns Int
      effects pure
      ensures result >= 0

    function flatten<T>(xss: List<List<T>>) returns List<T>
      effects pure

## Map — D.1 expansion

    function mapValues<K, V, W>(m: Map<K, V>, f: function(V) returns W) returns Map<K, W>
      effects pure
      ensures size(result) == size(m)

## Set — D.1 expansion
    (named `setUnion` etc. because `union` is a reserved keyword)

    function setUnion<T>(a: Set<T>, b: Set<T>) returns Set<T>
      effects pure

    function setIntersection<T>(a: Set<T>, b: Set<T>) returns Set<T>
      effects pure

    function setDifference<T>(a: Set<T>, b: Set<T>) returns Set<T>
      effects pure

## String — D.1 expansion

    function repeat(s: String, n: Int) returns String
      effects pure

    function padLeft(s: String, n: Int, c: String) returns String
      effects pure

    function padRight(s: String, n: Int, c: String) returns String
      effects pure

    function chars(s: String) returns List<String>
      effects pure
      ensures length(result) == length(s)

## Math — D.1 expansion

    function gcd(a: Int, b: Int) returns Int
      effects pure
      ensures result >= 0

    function lcm(a: Int, b: Int) returns Int
      effects pure
      ensures result >= 0

## Map<K,V>

    function size<K, V>(m: Map<K, V>) returns Int
      effects pure
      ensures result >= 0

    function get<K, V>(m: Map<K, V>, k: K) returns Option<V>
      effects pure

    function set<K, V>(m: Map<K, V>, k: K, v: V) returns Map<K, V>
      effects pure
      ensures size(result) >= size(m)

    function remove<K, V>(m: Map<K, V>, k: K) returns Map<K, V>
      effects pure
      ensures size(result) <= size(m)

    function has?<K, V>(m: Map<K, V>, k: K) returns Bool
      effects pure

    function keys<K, V>(m: Map<K, V>) returns List<K>
      effects pure

    function values<K, V>(m: Map<K, V>) returns List<V>
      effects pure

## Set<T>

    function size<T>(s: Set<T>) returns Int
      effects pure
    function add<T>(s: Set<T>, x: T) returns Set<T>
      effects pure
    function remove<T>(s: Set<T>, x: T) returns Set<T>
      effects pure
    function contains?<T>(s: Set<T>, x: T) returns Bool
      effects pure

## String

    function length(s: String) returns Int
      effects pure
      ensures result >= 0

    function slice(s: String, lo: Int, hi: Int) returns String
      effects pure
      requires 0 <= lo and lo <= hi and hi <= length(s)

    function split(s: String, sep: String) returns List<String>
      effects pure

    function join(parts: List<String>, sep: String) returns String
      effects pure

    function contains?(s: String, needle: String) returns Bool
      effects pure

    function trim(s: String) returns String
      effects pure

    function toLower(s: String) returns String
      effects pure
    function toUpper(s: String) returns String
      effects pure

    function replace(s: String, from: String, to: String) returns String
      effects pure

    function startsWith?(s: String, prefix: String) returns Bool
      effects pure
    function endsWith?(s: String, suffix: String) returns Bool
      effects pure

    function parseInt(s: String) returns Result<Int, String>
      effects pure
    function parseFloat(s: String) returns Result<Float, String>
      effects pure

    function intToString(n: Int) returns String
      effects pure

## IO

    function print(s: String) returns Unit
      effects log

    function readLine() returns Result<String, String>
      effects log

    function readFile(path: String) returns Result<String, String>
      effects fs.read

    function writeFile(path: String, contents: String) returns Result<Unit, String>
      effects fs.write

    function safeJoin(base: String, rel: String) returns String
      effects pure
      // Join `rel` under `base`, discarding any component that would
      // escape it (`..`, `.`, absolute roots, drive/backslash prefixes).
      // The result is guaranteed to stay within `base`. This is the
      // sanctioned way to build a readFile/writeFile path from untrusted
      // input; E0711 refuses dynamic paths that skip it.

    function classify<T>(x: T) returns Secret<T>
      effects pure
      // Wrap a value as Secret<T>, a compile-time-only taint marker
      // (erased at runtime). A Secret value cannot reach a log sink
      // (E0712) until unwrapped.

    function reveal<T>(s: Secret<T>) returns T
      effects pure
      // The sanctioned, auditable unwrap of a Secret<T>. Wrapping a log
      // argument in reveal(...) is how you state "this disclosure is
      // intended" — E0712 does not flag a reveal() subtree.

    function classifyPII<T>(x: T) returns PII<T>
      effects pure
      // Wrap a value as PII<T>, a compile-time-only taint marker for
      // personal data (erased at runtime). A PII value cannot reach a
      // log sink or the contents of writeFile in the clear (E0715).

    function redact<T>(x: PII<T>) returns String
      effects pure
      // The sanctioned, consent-safe masking of a PII<T> value (emails
      // keep first char + domain; else first char). Wrapping a sink
      // argument in redact(...) is the auditable way to log/persist a
      // masked form — E0715 does not flag a redact() subtree.

## Database

    function sqlQuery(q: String) returns String
      effects db.query
      // Execute a query (models a DB call; requires capability `db`).
      // E0713 refuses a `q` built by raw concatenation of untrusted input.

    function sqlBind(template: String, value: String) returns String
      effects pure
      // Parameterized-query binding: substitute the first `?` in
      // `template` with a safely-escaped literal of `value`. The
      // sanctioned way to place untrusted input into a query; E0713
      // accepts a sqlBind(...) result and refuses raw concatenation.

    function sqlExec(stmt: String, auth: Authorized<String>) returns String
      effects db.exec
      // Execute a data-MUTATING statement — UPDATE/DELETE/INSERT (models
      // a DB write; requires capability `db`). E0716 refuses a call whose
      // `auth` argument is not a proven Authorized<...> value (an
      // authorize(...) call, an Authorized<T> parameter, or a binding of
      // one); E0713 refuses a `stmt` built by raw concatenation.

    function authorize(principal: String, action: String) returns Authorized<String>
      effects pure
      // The sanctioned authorization guard: check that `principal` may
      // perform `action` and return an Authorized<String> proof token.
      // Authorized<T> is a compile-time-only marker (erased at runtime);
      // E0716 requires the proof in the dataflow of every mutating sink.
      // Pass the token down as an Authorized<String> parameter to carry
      // the caller's authorization across a call boundary.

    function sqlByOwner(stmt: String, resourceId: String, proof: Authorized<String>) returns String
      effects db.exec
      // Execute a RESOURCE-SCOPED mutating statement — an UPDATE/DELETE
      // on one row (models a DB write; requires capability `db`). E0717
      // refuses a call whose `proof` is not an authorizeResource(...)
      // result bound to the SAME `resourceId` the sink mutates (IDOR /
      // cross-tenant, CWE-639); E0713 refuses a `stmt` built by raw
      // concatenation.

    function authorizeResource(principal: String, action: String, resourceId: String) returns Authorized<String>
      effects pure
      // The object-level authorization guard: check that `principal` may
      // perform `action` ON `resourceId` and return an Authorized<String>
      // proof token bound to that resource. E0717 requires sqlByOwner's
      // proof to name the SAME id the sink mutates — pass the identical
      // literal or a never-rebound name to both; a proof for a different
      // id, or one the checker cannot relate, is refused.

## Shell

    function shellExec(cmd: String) returns String
      effects exec.run
      // Execute a shell command (models an exec; requires capability
      // `exec`). E0714 refuses a `cmd` built by raw concatenation of
      // untrusted input.

    function shellArg(template: String, value: String) returns String
      effects pure
      // Quoted-argument binding: substitute the first `?` in `template`
      // with `value` quoted as a single shell argument (so it cannot
      // inject `;`/`|`/`$( )` syntax). The sanctioned way to place
      // untrusted input on a command line; E0714 accepts a shellArg(...)
      // result and refuses raw concatenation.

## HTTP redirect

    function redirect(target: String) returns String
      effects net.redirect
      // Issue an HTTP redirect (requires capability `net`). E0718 refuses
      // a target steerable by untrusted input (open redirect).

    function safeRedirect(host: String, path: String) returns String
      effects pure
      // Build a redirect target pinned to `host`: strips any scheme,
      // authority, and leading slashes from `path` so the result can only
      // point at `host`. The sanctioned repair for E0718 — defeats both
      // absolute-url and protocol-relative (//evil.com) open redirects.

## Time

    record Instant do
      epochMillis: Int
    end

    record Duration do
      millis: Int
    end

    function now() returns Instant
      effects time.now

    function plus(t: Instant, d: Duration) returns Instant
      effects pure

    function minus(a: Instant, b: Instant) returns Duration
      effects pure

## Hash

    function sha256(b: Bytes) returns Bytes
      effects pure
    function sha1(b: Bytes) returns Bytes
      effects pure
    function md5(b: Bytes) returns Bytes
      effects pure

## Bytes

    function bytesLen(b: Bytes) returns Int
      effects pure

    function byteAt(b: Bytes, i: Int) returns Int
      requires i >= 0 and i < bytesLen(b)
      ensures result >= 0 and result <= 255
      effects pure

    function bytesFromList(xs: List<Int>) returns Bytes
      // every element must satisfy 0 <= x <= 255 (checked at runtime, E0305)
      effects pure

    function bytesToList(b: Bytes) returns List<Int>
      ensures length(result) == bytesLen(b)
      effects pure

    function stringToBytes(s: String) returns Bytes
      // UTF-8 encoding
      effects pure

    function bytesToString(b: Bytes) returns String
      // UTF-8 decoding; non-UTF-8 input fails with E0305
      effects pure

## Char codes

    function ord(s: String) returns Int
      requires length(s) == 1
      ensures result >= 0 and result <= 1114111
      effects pure

    function chr(n: Int) returns String
      requires n >= 0 and n <= 1114111
      ensures length(result) == 1
      effects pure

## Math

    function abs(x: Int) returns Int
      effects pure
    function min(a: Int, b: Int) returns Int
      effects pure
    function max(a: Int, b: Int) returns Int
      effects pure
    function floor(x: Float) returns Int
      effects pure
    function ceil(x: Float) returns Int
      effects pure
    function pow(base: Float, exp: Float) returns Float
      effects pure
    function sqrt(x: Float) returns Float
      effects pure
      requires x >= 0.0

## Result / Option helpers

    function isOk?<T, E>(r: Result<T, E>) returns Bool
      effects pure
    function isErr?<T, E>(r: Result<T, E>) returns Bool
      effects pure
    function unwrapOr<T, E>(r: Result<T, E>, default: T) returns T
      effects pure

    function isSome?<T>(o: Option<T>) returns Bool
      effects pure
    function isNone?<T>(o: Option<T>) returns Bool
      effects pure
    function unwrapOrElse<T>(o: Option<T>, default: T) returns T
      effects pure

## What is *not* in v0.1

- Regex.
- JSON parser/printer (the AST tooling has its own; user code does not get one).
- Crypto beyond hash digests.
- Any kind of async / channel / actor primitive.
- Mutable collections (`var` of a `List` is allowed but operations are still pure-functional).
- Numeric tower (no `BigInt`, `Decimal`, `Rational`).

## Naming and overloading

There is *no* function overloading. `length` is defined separately for `List<T>` and `String`, and the parser dispatches by argument type at the call site. All other names are unique.
