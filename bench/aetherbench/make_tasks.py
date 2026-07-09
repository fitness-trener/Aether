"""AetherBench task generator + verifier.

Single source of truth for all 50 tasks. Running it (re)writes
bench/aetherbench/tasks/<id>/{prompt_full.md,prompt_nl.md,grader.json,
reference.aeth[,vulnerable.aeth]} and verifies every reference:

    python -B bench/aetherbench/make_tasks.py            # write + verify
    python -B bench/aetherbench/make_tasks.py --accept   # snapshot actual
                                                         # stdout into
                                                         # grader.json +
                                                         # prompts

Verification per task: reference must pass `aether check` (exit 0) and
produce expected_stdout; a T4 vulnerable variant must FAIL check with
its expected E-code.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))

from bench.harness import compile_and_run  # noqa: E402

TASKS_DIR = os.path.join(HERE, "tasks")


def T(id, title, spec, nl, reference, expected=None, vulnerable=None,
      vuln_code=None, tags=()):
    return dict(id=id, title=title, spec=spec.strip(), nl=nl.strip(),
                reference=reference.strip() + "\n", expected=expected,
                vulnerable=(vulnerable.strip() + "\n") if vulnerable else None,
                vuln_code=vuln_code, tags=list(tags))


TASKS = [
    # ================= T1 — contracts on pure functions =================
    T("t1_01_clamp", "clamp with range postcondition",
      spec="""
function clamp(x: Int, lo: Int, hi: Int) returns Int
  requires lo <= hi
  ensures result >= lo and result <= hi
  effects pure

main() calls: clamp(5, 0, 10), clamp(-3, 0, 10), clamp(42, 0, 10),
printing each with intToString.
""",
      nl="Write `clamp(x, lo, hi)` returning x limited to [lo, hi]. "
         "Declare a precondition lo <= hi and a postcondition that the "
         "result is within [lo, hi]. Print clamp(5,0,10), clamp(-3,0,10), "
         "clamp(42,0,10), one per line.",
      reference="""
function clamp(x: Int, lo: Int, hi: Int) returns Int
  requires lo <= hi
  ensures result >= lo and result <= hi
  effects pure
do
  if x < lo then
    return lo
  elif x > hi then
    return hi
  else
    return x
  end
end

function main() returns Unit
  effects log
do
  print(intToString(clamp(5, 0, 10)))
  print(intToString(clamp(-3, 0, 10)))
  print(intToString(clamp(42, 0, 10)))
end
""",
      expected="5\n0\n10\n", tags=["contract", "ensures"]),

    T("t1_02_max3", "max of three with witness postcondition",
      spec="""
function max3(a: Int, b: Int, c: Int) returns Int
  ensures result >= a and result >= b and result >= c
  ensures result == a or result == b or result == c
  effects pure

main() prints max3(3, 9, 2) and max3(-1, -5, -2).
""",
      nl="Write `max3(a, b, c)` returning the largest of three Ints, with "
         "postconditions that the result is >= each argument and equals one "
         "of them. Print max3(3,9,2) then max3(-1,-5,-2).",
      reference="""
function max3(a: Int, b: Int, c: Int) returns Int
  ensures result >= a and result >= b and result >= c
  ensures result == a or result == b or result == c
  effects pure
do
  var m: Int = a
  if b > m then
    m = b
  end
  if c > m then
    m = c
  end
  return m
end

function main() returns Unit
  effects log
do
  print(intToString(max3(3, 9, 2)))
  print(intToString(max3(-1, -5, -2)))
end
""",
      expected="9\n-1\n", tags=["contract", "ensures"]),

    T("t1_03_absdiff", "absolute difference is non-negative",
      spec="""
function absDiff(a: Int, b: Int) returns Int
  ensures result >= 0
  effects pure

main() prints absDiff(3, 10) and absDiff(10, 3).
""",
      nl="Write `absDiff(a, b)` returning |a - b| with a postcondition that "
         "the result is non-negative. Print absDiff(3,10) and absDiff(10,3).",
      reference="""
function absDiff(a: Int, b: Int) returns Int
  ensures result >= 0
  effects pure
do
  if a > b then
    return a - b
  else
    return b - a
  end
end

function main() returns Unit
  effects log
do
  print(intToString(absDiff(3, 10)))
  print(intToString(absDiff(10, 3)))
end
""",
      expected="7\n7\n", tags=["contract", "ensures"]),

    T("t1_04_factorial", "factorial with pre- and postcondition",
      spec="""
function factorial(n: Int) returns Int
  requires n >= 0
  ensures result >= 1
  effects pure

main() prints factorial(5) and factorial(0).
""",
      nl="Write iterative `factorial(n)` with precondition n >= 0 and "
         "postcondition result >= 1. Print factorial(5) and factorial(0).",
      reference="""
function factorial(n: Int) returns Int
  requires n >= 0
  ensures result >= 1
  effects pure
do
  var acc: Int = 1
  var i: Int = 2
  while i <= n do
    acc = acc * i
    i = i + 1
  end
  return acc
end

function main() returns Unit
  effects log
do
  print(intToString(factorial(5)))
  print(intToString(factorial(0)))
end
""",
      expected="120\n1\n", tags=["contract", "requires", "ensures"]),

    T("t1_05_sumto", "sum 1..n with non-negativity",
      spec="""
function sumTo(n: Int) returns Int
  requires n >= 0
  ensures result >= 0
  effects pure

main() prints sumTo(10) and sumTo(0).
""",
      nl="Write `sumTo(n)` returning 1+2+...+n (0 for n=0), precondition "
         "n >= 0, postcondition result >= 0. Print sumTo(10) and sumTo(0).",
      reference="""
function sumTo(n: Int) returns Int
  requires n >= 0
  ensures result >= 0
  effects pure
do
  var acc: Int = 0
  var i: Int = 1
  while i <= n do
    acc = acc + i
    i = i + 1
  end
  return acc
end

function main() returns Unit
  effects log
do
  print(intToString(sumTo(10)))
  print(intToString(sumTo(0)))
end
""",
      expected="55\n0\n", tags=["contract"]),

    T("t1_06_safediv", "division guarded by precondition",
      spec="""
function safeDiv(a: Int, b: Int) returns Int
  requires b != 0
  effects pure

main() prints safeDiv(6, 3) and safeDiv(7, 2).
""",
      nl="Write `safeDiv(a, b)` doing integer division with a precondition "
         "that b is non-zero. Print safeDiv(6,3) and safeDiv(7,2).",
      reference="""
function safeDiv(a: Int, b: Int) returns Int
  requires b != 0
  effects pure
do
  return a / b
end

function main() returns Unit
  effects log
do
  print(intToString(safeDiv(6, 3)))
  print(intToString(safeDiv(7, 2)))
end
""",
      expected="2\n3\n", tags=["contract", "requires"]),

    T("t1_07_minlist", "minimum of a non-empty list",
      spec="""
function minList(xs: List<Int>) returns Int
  requires length(xs) > 0
  effects pure

main() prints minList([5, 2, 8]) and minList([7]).
""",
      nl="Write `minList(xs)` returning the smallest element, with a "
         "precondition that the list is non-empty. Print minList([5,2,8]) "
         "and minList([7]).",
      reference="""
function minList(xs: List<Int>) returns Int
  requires length(xs) > 0
  effects pure
do
  var m: Int = xs[0]
  var i: Int = 1
  while i < length(xs) do
    if xs[i] < m then
      m = xs[i]
    end
    i = i + 1
  end
  return m
end

function main() returns Unit
  effects log
do
  print(intToString(minList([5, 2, 8])))
  print(intToString(minList([7])))
end
""",
      expected="2\n7\n", tags=["contract", "requires", "list"]),

    T("t1_08_power", "integer power with contracts",
      spec="""
function myPow(base: Int, e: Int) returns Int
  requires base >= 1 and e >= 0
  ensures result >= 1
  effects pure

main() prints myPow(2, 10) and myPow(3, 0).
""",
      nl="Write iterative `myPow(base, e)` with preconditions base >= 1, "
         "e >= 0 and postcondition result >= 1. Print myPow(2,10) and "
         "myPow(3,0).",
      reference="""
function myPow(base: Int, e: Int) returns Int
  requires base >= 1 and e >= 0
  ensures result >= 1
  effects pure
do
  var acc: Int = 1
  var i: Int = 0
  while i < e do
    acc = acc * base
    i = i + 1
  end
  return acc
end

function main() returns Unit
  effects log
do
  print(intToString(myPow(2, 10)))
  print(intToString(myPow(3, 0)))
end
""",
      expected="1024\n1\n", tags=["contract"]),

    T("t1_09_median3", "median of three with witness postcondition",
      spec="""
function median3(a: Int, b: Int, c: Int) returns Int
  ensures result == a or result == b or result == c
  effects pure

main() prints median3(3, 1, 2) and median3(9, 9, 1).
""",
      nl="Write `median3(a, b, c)` returning the middle value, with a "
         "postcondition that the result is one of the inputs. Print "
         "median3(3,1,2) and median3(9,9,1).",
      reference="""
function median3(a: Int, b: Int, c: Int) returns Int
  ensures result == a or result == b or result == c
  effects pure
do
  if (a >= b and a <= c) or (a <= b and a >= c) then
    return a
  elif (b >= a and b <= c) or (b <= a and b >= c) then
    return b
  else
    return c
  end
end

function main() returns Unit
  effects log
do
  print(intToString(median3(3, 1, 2)))
  print(intToString(median3(9, 9, 1)))
end
""",
      expected="2\n9\n", tags=["contract", "ensures"]),

    T("t1_10_fib", "iterative fibonacci with contracts",
      spec="""
function fib(n: Int) returns Int
  requires n >= 0
  ensures result >= 0
  effects pure

main() prints fib(10) and fib(1).
""",
      nl="Write iterative `fib(n)` (fib(0)=0, fib(1)=1) with precondition "
         "n >= 0 and postcondition result >= 0. Print fib(10) and fib(1).",
      reference="""
function fib(n: Int) returns Int
  requires n >= 0
  ensures result >= 0
  effects pure
do
  var a: Int = 0
  var b: Int = 1
  var i: Int = 0
  while i < n do
    let t: Int = a + b
    a = b
    b = t
    i = i + 1
  end
  return a
end

function main() returns Unit
  effects log
do
  print(intToString(fib(10)))
  print(intToString(fib(1)))
end
""",
      expected="55\n1\n", tags=["contract"]),

    # ================= T2 — refinement types =================
    T("t2_01_percentage", "Percentage refinement",
      spec="""
type Percentage = Int where self >= 0 and self <= 100

function discount(price: Int, pct: Percentage) returns Int
  effects pure

main() prints discount(200, 25), discount(200, 0), discount(200, 100).
""",
      nl="Define a Percentage refinement type (0..100) and "
         "`discount(price, pct)` returning price reduced by pct percent. "
         "Print discount(200,25), discount(200,0), discount(200,100).",
      reference="""
type Percentage = Int where self >= 0 and self <= 100

function discount(price: Int, pct: Percentage) returns Int
  effects pure
do
  return price - (price * pct) / 100
end

function main() returns Unit
  effects log
do
  print(intToString(discount(200, 25)))
  print(intToString(discount(200, 0)))
  print(intToString(discount(200, 100)))
end
""",
      expected="150\n200\n0\n", tags=["refinement"]),

    T("t2_02_port", "Port number refinement",
      spec="""
type Port = Int where self >= 1 and self <= 65535

function describePort(p: Port) returns String
  effects pure
  // returns "port:" + the number

main() prints describePort(80) and describePort(65535).
""",
      nl="Define a Port refinement (1..65535) and `describePort(p)` "
         "returning \"port:\" followed by the number. Print for 80 and "
         "65535.",
      reference="""
type Port = Int where self >= 1 and self <= 65535

function describePort(p: Port) returns String
  effects pure
do
  return "port:" + intToString(p)
end

function main() returns Unit
  effects log
do
  print(describePort(80))
  print(describePort(65535))
end
""",
      expected="port:80\nport:65535\n", tags=["refinement"]),

    T("t2_03_age", "Age refinement gating a decision",
      spec="""
type Age = Int where self >= 0 and self <= 150

function votingStatus(a: Age) returns String
  effects pure
  // "yes" if a >= 18 else "no"

main() prints votingStatus(21) and votingStatus(10).
""",
      nl="Define an Age refinement (0..150) and `votingStatus(a)` "
         "returning \"yes\" if a >= 18 else \"no\". Print for 21 and 10.",
      reference="""
type Age = Int where self >= 0 and self <= 150

function votingStatus(a: Age) returns String
  effects pure
do
  if a >= 18 then
    return "yes"
  else
    return "no"
  end
end

function main() returns Unit
  effects log
do
  print(votingStatus(21))
  print(votingStatus(10))
end
""",
      expected="yes\nno\n", tags=["refinement"]),

    T("t2_04_latitude", "Latitude refinement",
      spec="""
type Latitude = Int where self >= -90 and self <= 90

function hemisphere(lat: Latitude) returns String
  effects pure
  // "N" if lat > 0, "S" if lat < 0, "EQ" if 0

main() prints hemisphere(45), hemisphere(-10), hemisphere(0).
""",
      nl="Define a Latitude refinement (-90..90) and `hemisphere(lat)` "
         "returning \"N\", \"S\" or \"EQ\". Print for 45, -10, 0.",
      reference="""
type Latitude = Int where self >= -90 and self <= 90

function hemisphere(lat: Latitude) returns String
  effects pure
do
  if lat > 0 then
    return "N"
  elif lat < 0 then
    return "S"
  else
    return "EQ"
  end
end

function main() returns Unit
  effects log
do
  print(hemisphere(45))
  print(hemisphere(-10))
  print(hemisphere(0))
end
""",
      expected="N\nS\nEQ\n", tags=["refinement"]),

    T("t2_05_month", "Month refinement with lookup",
      spec="""
type Month = Int where self >= 1 and self <= 12

function daysInMonth(m: Month) returns Int
  effects pure
  // non-leap year

main() prints daysInMonth(2) and daysInMonth(12).
""",
      nl="Define a Month refinement (1..12) and `daysInMonth(m)` for a "
         "non-leap year. Print for 2 and 12.",
      reference="""
type Month = Int where self >= 1 and self <= 12

function daysInMonth(m: Month) returns Int
  effects pure
do
  if m == 2 then
    return 28
  elif m == 4 or m == 6 or m == 9 or m == 11 then
    return 30
  else
    return 31
  end
end

function main() returns Unit
  effects log
do
  print(intToString(daysInMonth(2)))
  print(intToString(daysInMonth(12)))
end
""",
      expected="28\n31\n", tags=["refinement"]),

    T("t2_06_score", "Score refinement to letter grade",
      spec="""
type Score = Int where self >= 0 and self <= 100

function grade(s: Score) returns String
  effects pure
  // A >= 90, B >= 80, C >= 70, else F

main() prints grade(95), grade(71), grade(10).
""",
      nl="Define a Score refinement (0..100) and `grade(s)` returning "
         "A/B/C/F (A >= 90, B >= 80, C >= 70). Print for 95, 71, 10.",
      reference="""
type Score = Int where self >= 0 and self <= 100

function grade(s: Score) returns String
  effects pure
do
  if s >= 90 then
    return "A"
  elif s >= 80 then
    return "B"
  elif s >= 70 then
    return "C"
  else
    return "F"
  end
end

function main() returns Unit
  effects log
do
  print(grade(95))
  print(grade(71))
  print(grade(10))
end
""",
      expected="A\nC\nF\n", tags=["refinement"]),

    T("t2_07_kelvin", "Kelvin refinement (physical lower bound)",
      spec="""
type Kelvin = Int where self >= 0

function toCelsius(k: Kelvin) returns Int
  effects pure

main() prints toCelsius(300) and toCelsius(0).
""",
      nl="Define a Kelvin refinement (>= 0) and `toCelsius(k)` = k - 273. "
         "Print for 300 and 0.",
      reference="""
type Kelvin = Int where self >= 0

function toCelsius(k: Kelvin) returns Int
  effects pure
do
  return k - 273
end

function main() returns Unit
  effects log
do
  print(intToString(toCelsius(300)))
  print(intToString(toCelsius(0)))
end
""",
      expected="27\n-273\n", tags=["refinement"]),

    T("t2_08_quantity", "Quantity refinement in an order total",
      spec="""
type Quantity = Int where self >= 1

function total(price: Int, qty: Quantity) returns Int
  effects pure

main() prints total(7, 3) and total(10, 1).
""",
      nl="Define a Quantity refinement (>= 1) and `total(price, qty)`. "
         "Print total(7,3) and total(10,1).",
      reference="""
type Quantity = Int where self >= 1

function total(price: Int, qty: Quantity) returns Int
  effects pure
do
  return price * qty
end

function main() returns Unit
  effects log
do
  print(intToString(total(7, 3)))
  print(intToString(total(10, 1)))
end
""",
      expected="21\n10\n", tags=["refinement"]),

    T("t2_09_bps", "Basis points refinement",
      spec="""
type BasisPoints = Int where self >= 0 and self <= 10000

function applyBps(amount: Int, bps: BasisPoints) returns Int
  effects pure
  // amount * bps / 10000

main() prints applyBps(20000, 250) and applyBps(100, 10000).
""",
      nl="Define a BasisPoints refinement (0..10000) and "
         "`applyBps(amount, bps)` = amount * bps / 10000. Print "
         "applyBps(20000,250) and applyBps(100,10000).",
      reference="""
type BasisPoints = Int where self >= 0 and self <= 10000

function applyBps(amount: Int, bps: BasisPoints) returns Int
  effects pure
do
  return (amount * bps) / 10000
end

function main() returns Unit
  effects log
do
  print(intToString(applyBps(20000, 250)))
  print(intToString(applyBps(100, 10000)))
end
""",
      expected="500\n100\n", tags=["refinement"]),

    T("t2_10_prob", "Scaled probability refinement",
      spec="""
type Prob = Int where self >= 0 and self <= 1000

function andProb(p: Prob, q: Prob) returns Int
  effects pure
  // joint probability of independent events, scaled by 1000

main() prints andProb(500, 500) and andProb(1000, 250).
""",
      nl="Define a Prob refinement (0..1000, probability scaled by 1000) "
         "and `andProb(p, q)` = p * q / 1000. Print andProb(500,500) and "
         "andProb(1000,250).",
      reference="""
type Prob = Int where self >= 0 and self <= 1000

function andProb(p: Prob, q: Prob) returns Int
  effects pure
do
  return (p * q) / 1000
end

function main() returns Unit
  effects log
do
  print(intToString(andProb(500, 500)))
  print(intToString(andProb(1000, 250)))
end
""",
      expected="250\n250\n", tags=["refinement"]),

    # ================= T3 — effects + capabilities =================
    T("t3_01_logger", "module with log capability",
      spec="""
module Logger
  requires capability log
  exports emit
end

function emit(line: String) returns Unit
  effects log
  // prints "LOG " + line

main() emits "startup" and "ready".
""",
      nl="Write a Logger module that requires the log capability and "
         "exports `emit(line)`, which prints \"LOG \" + line. main() emits "
         "\"startup\" then \"ready\".",
      reference="""
module Logger
  requires capability log
  exports emit
end

function emit(line: String) returns Unit
  effects log
do
  print("LOG " + line)
end

function main() returns Unit
  effects log
do
  emit("startup")
  emit("ready")
end
""",
      expected="LOG startup\nLOG ready\n", tags=["module", "capability"]),

    T("t3_02_pinned_fetch", "pinned net.fetch effect propagation",
      spec="""
function fetchStatus() returns String
  effects net.fetch("https://api.example.com/status")
  // returns "UP" (no real network in this exercise)

function report() returns Unit
  effects log, net.fetch("https://api.example.com/status")
  // prints "STATUS " + fetchStatus()

main() calls report() and declares the same effects.
""",
      nl="Write `fetchStatus()` that declares a net.fetch effect pinned to "
         "https://api.example.com/status and returns \"UP\", and `report()` "
         "that prints \"STATUS \" + fetchStatus(). Declare effects all the "
         "way up to main.",
      reference="""
function fetchStatus() returns String
  effects net.fetch("https://api.example.com/status")
do
  return "UP"
end

function report() returns Unit
  effects log, net.fetch("https://api.example.com/status")
do
  print("STATUS " + fetchStatus())
end

function main() returns Unit
  effects log, net.fetch("https://api.example.com/status")
do
  report()
end
""",
      expected="STATUS UP\n", tags=["effects", "net"]),

    T("t3_03_audit", "two capabilities declared and used",
      spec="""
module Audit
  requires capability log
  requires capability fs
  exports emit
end

function persist(line: String) returns Unit
  effects fs.write

function emit(line: String) returns Unit
  effects log, fs.write
  // prints "AUDIT " + line, then persists it

main() emits "login".
""",
      nl="Write an Audit module requiring log and fs capabilities. "
         "`persist(line)` writes the line to \"aetherbench_audit.tmp\" "
         "(fs.write effect); `emit(line)` prints \"AUDIT \" + line and "
         "persists it. main() emits \"login\".",
      reference="""
module Audit
  requires capability log
  requires capability fs
  exports emit
end

function persist(line: String) returns Unit
  effects fs.write
do
  let _r: Result<Unit, String> = writeFile("aetherbench_audit.tmp", line)
end

function emit(line: String) returns Unit
  effects log, fs.write
do
  print("AUDIT " + line)
  persist(line)
end

function main() returns Unit
  effects log, fs.write
do
  emit("login")
end
""",
      expected="AUDIT login\n", tags=["module", "capability", "fs"]),

    T("t3_04_pure_shell", "pure core, effectful shell",
      spec="""
function square(x: Int) returns Int
  effects pure

function cube(x: Int) returns Int
  effects pure

main() (effects log) prints square(7) and cube(3).
""",
      nl="Write pure `square(x)` and `cube(x)`; only main() has the log "
         "effect. Print square(7) and cube(3).",
      reference="""
function square(x: Int) returns Int
  effects pure
do
  return x * x
end

function cube(x: Int) returns Int
  effects pure
do
  return x * x * x
end

function main() returns Unit
  effects log
do
  print(intToString(square(7)))
  print(intToString(cube(3)))
end
""",
      expected="49\n27\n", tags=["effects", "pure"]),

    T("t3_05_fs_roundtrip", "file write/read roundtrip",
      spec="""
function save(path: String, body: String) returns Unit
  effects fs.write
  // writeFile(safeJoin(".", path), body) — dynamic paths must go
  // through safeJoin

function load(path: String) returns String
  effects fs.read
  // unwrapOr(readFile(safeJoin(".", path)), "ERR")

main() saves "hello-fs" to "aetherbench_scratch.tmp", loads it back,
prints it.
""",
      nl="Write `save(path, body)` (fs.write) and `load(path)` (fs.read, "
         "returning the file text or \"ERR\"). Dynamic paths must be "
         "routed through safeJoin(\".\", path). main() writes \"hello-fs\" "
         "to \"aetherbench_scratch.tmp\", reads it back and prints it.",
      reference="""
function save(path: String, body: String) returns Unit
  effects fs.write
do
  let _r: Result<Unit, String> = writeFile(safeJoin(".", path), body)
end

function load(path: String) returns String
  effects fs.read
do
  let r: Result<String, String> = readFile(safeJoin(".", path))
  return unwrapOr(r, "ERR")
end

function main() returns Unit
  effects log, fs.write, fs.read
do
  save("aetherbench_scratch.tmp", "hello-fs")
  print(load("aetherbench_scratch.tmp"))
end
""",
      expected="hello-fs\n", tags=["effects", "fs"]),

    T("t3_06_db_literal", "db.query with a fixed literal",
      spec="""
module Repo
  requires capability db
  requires capability log
  exports listUsers
end

function listUsers() returns Unit
  effects db.query, log
  // runs sqlQuery("SELECT id FROM users") and prints "QUERIED"

main() calls listUsers().
""",
      nl="Write a Repo module (db + log capabilities) with `listUsers()` "
         "that runs the fixed query \"SELECT id FROM users\" via sqlQuery "
         "and prints \"QUERIED\". main() calls it.",
      reference="""
module Repo
  requires capability db
  requires capability log
  exports listUsers
end

function listUsers() returns Unit
  effects db.query, log
do
  let _r: String = sqlQuery("SELECT id FROM users")
  print("QUERIED")
end

function main() returns Unit
  effects db.query, log
do
  listUsers()
end
""",
      expected="QUERIED\n", tags=["effects", "db"]),

    T("t3_07_two_hosts", "two pinned fetch hosts",
      spec="""
function syncA() returns String
  effects net.fetch("https://a.example.com/*")

function syncB() returns String
  effects net.fetch("https://b.example.com/*")

function syncBoth() returns Unit
  effects log, net.fetch("https://a.example.com/*"), net.fetch("https://b.example.com/*")
  // prints results of both

main() calls syncBoth() with the same effects.
""",
      nl="Write `syncA()` returning \"a-ok\" (fetch pinned to "
         "https://a.example.com/*) and `syncB()` returning \"b-ok\" (pinned "
         "to https://b.example.com/*). `syncBoth()` prints both results. "
         "Declare both fetch effects wherever needed.",
      reference="""
function syncA() returns String
  effects net.fetch("https://a.example.com/*")
do
  return "a-ok"
end

function syncB() returns String
  effects net.fetch("https://b.example.com/*")
do
  return "b-ok"
end

function syncBoth() returns Unit
  effects log, net.fetch("https://a.example.com/*"), net.fetch("https://b.example.com/*")
do
  print(syncA())
  print(syncB())
end

function main() returns Unit
  effects log, net.fetch("https://a.example.com/*"), net.fetch("https://b.example.com/*")
do
  syncBoth()
end
""",
      expected="a-ok\nb-ok\n", tags=["effects", "net"]),

    T("t3_08_path_glob", "host pinned, path wildcard",
      spec="""
function charge(amount: Int) returns String
  effects net.fetch("https://api.payments.example.com/charge/*")
  // returns "charged:" + amount

main() prints charge(100).
""",
      nl="Write `charge(amount)` with a fetch effect pinned to host "
         "api.payments.example.com under path /charge/* returning "
         "\"charged:\" + the amount. main() prints charge(100).",
      reference="""
function charge(amount: Int) returns String
  effects net.fetch("https://api.payments.example.com/charge/*")
do
  return "charged:" + intToString(amount)
end

function main() returns Unit
  effects log, net.fetch("https://api.payments.example.com/charge/*")
do
  print(charge(100))
end
""",
      expected="charged:100\n", tags=["effects", "net"]),

    T("t3_09_exports", "module export discipline",
      spec="""
module MathApi
  requires capability log
  exports doubled
end

function helper(x: Int) returns Int
  effects pure
  // internal, NOT exported

function doubled(x: Int) returns Int
  effects pure

main() prints doubled(21).
""",
      nl="Write a MathApi module exporting only `doubled(x)` (= x * 2, "
         "implemented via an internal non-exported helper). main() prints "
         "doubled(21).",
      reference="""
module MathApi
  requires capability log
  exports doubled
end

function helper(x: Int) returns Int
  effects pure
do
  return x + x
end

function doubled(x: Int) returns Int
  effects pure
do
  return helper(x)
end

function main() returns Unit
  effects log
do
  print(intToString(doubled(21)))
end
""",
      expected="42\n", tags=["module"]),

    T("t3_10_chain", "effect propagation three deep",
      spec="""
function inner(msg: String) returns Unit
  effects log

function middle(msg: String) returns Unit
  effects log

function outer(msg: String) returns Unit
  effects log

main() calls outer("deep"); every level declares log.
""",
      nl="Write outer -> middle -> inner, where inner prints \"GOT \" + "
         "msg and every level declares the log effect. main() calls "
         "outer(\"deep\").",
      reference="""
function inner(msg: String) returns Unit
  effects log
do
  print("GOT " + msg)
end

function middle(msg: String) returns Unit
  effects log
do
  inner(msg)
end

function outer(msg: String) returns Unit
  effects log
do
  middle(msg)
end

function main() returns Unit
  effects log
do
  outer("deep")
end
""",
      expected="GOT deep\n", tags=["effects"]),

    # ================= T4 — security sinks, sanctioned forms =================
    T("t4_01_sqlbind", "parameterized query (E0713)",
      spec="""
module UserRepo
  requires capability db
  requires capability log
  exports findUser
end

function findUser(userId: String) returns Unit
  effects db.query, log
  // query users by id with sqlBind; then print "LOOKED-UP " + userId

main() calls findUser("42").
""",
      nl="Write `findUser(userId)` that queries "
         "\"SELECT * FROM users WHERE id = ?\" with the id bound via "
         "sqlBind (never concatenated), then prints \"LOOKED-UP \" + "
         "userId. main() calls findUser(\"42\"). Must pass aether check.",
      reference="""
module UserRepo
  requires capability db
  requires capability log
  exports findUser
end

function findUser(userId: String) returns Unit
  effects db.query, log
do
  let _r: String = sqlQuery(sqlBind("SELECT * FROM users WHERE id = ?", userId))
  print("LOOKED-UP " + userId)
end

function main() returns Unit
  effects db.query, log
do
  findUser("42")
end
""",
      expected="LOOKED-UP 42\n",
      vulnerable="""
module UserRepo
  requires capability db
  requires capability log
  exports findUser
end

function findUser(userId: String) returns Unit
  effects db.query, log
do
  let _r: String = sqlQuery("SELECT * FROM users WHERE id = " + userId)
  print("LOOKED-UP " + userId)
end

function main() returns Unit
  effects db.query, log
do
  findUser("42")
end
""",
      vuln_code="E0713", tags=["security", "sqli"]),

    T("t4_02_shellarg", "quoted shell argument (E0714)",
      spec="""
module Thumbnailer
  requires capability exec
  requires capability log
  exports convert
end

function convert(filename: String) returns Unit
  effects exec.run, log
  // shell out to "convert ? out.png" with filename via shellArg;
  // then print "CONVERTED " + filename

main() calls convert("photo.jpg").
""",
      nl="Write `convert(filename)` that runs the shell command "
         "\"convert ? out.png\" with the filename quoted via shellArg "
         "(never concatenated), then prints \"CONVERTED \" + filename. "
         "main() calls convert(\"photo.jpg\"). Must pass aether check.",
      reference="""
module Thumbnailer
  requires capability exec
  requires capability log
  exports convert
end

function convert(filename: String) returns Unit
  effects exec.run, log
do
  let _r: String = shellExec(shellArg("convert ? out.png", filename))
  print("CONVERTED " + filename)
end

function main() returns Unit
  effects exec.run, log
do
  convert("photo.jpg")
end
""",
      expected="CONVERTED photo.jpg\n",
      vulnerable="""
module Thumbnailer
  requires capability exec
  requires capability log
  exports convert
end

function convert(filename: String) returns Unit
  effects exec.run, log
do
  let _r: String = shellExec("convert " + filename + " out.png")
  print("CONVERTED " + filename)
end

function main() returns Unit
  effects exec.run, log
do
  convert("photo.jpg")
end
""",
      vuln_code="E0714", tags=["security", "cmdi"]),

    T("t4_03_safejoin", "contained dynamic path (E0711)",
      spec="""
module Extractor
  requires capability fs
  requires capability log
  exports writeEntry
end

function writeEntry(baseDir: String, entryName: String, body: String) returns Unit
  effects fs.write, log
  // write body under baseDir with the untrusted entryName routed
  // through safeJoin; then print "WROTE " + entryName

main() calls writeEntry(".", "aetherbench_entry.tmp", "data").
""",
      nl="Write `writeEntry(baseDir, entryName, body)` that writes body to "
         "the path safeJoin(baseDir, entryName) (never raw concatenation) "
         "and prints \"WROTE \" + entryName. main() calls "
         "writeEntry(\".\", \"aetherbench_entry.tmp\", \"data\"). Must "
         "pass aether check.",
      reference="""
module Extractor
  requires capability fs
  requires capability log
  exports writeEntry
end

function writeEntry(baseDir: String, entryName: String, body: String) returns Unit
  effects fs.write, log
do
  let _r: Result<Unit, String> = writeFile(safeJoin(baseDir, entryName), body)
  print("WROTE " + entryName)
end

function main() returns Unit
  effects fs.write, log
do
  writeEntry(".", "aetherbench_entry.tmp", "data")
end
""",
      expected="WROTE aetherbench_entry.tmp\n",
      vulnerable="""
module Extractor
  requires capability fs
  requires capability log
  exports writeEntry
end

function writeEntry(baseDir: String, entryName: String, body: String) returns Unit
  effects fs.write, log
do
  let _r: Result<Unit, String> = writeFile(baseDir + "/" + entryName, body)
  print("WROTE " + entryName)
end

function main() returns Unit
  effects fs.write, log
do
  writeEntry(".", "aetherbench_entry.tmp", "data")
end
""",
      vuln_code="E0711", tags=["security", "path"]),

    T("t4_04_pinned_ssrf", "pinned fetch authority (E0710)",
      spec="""
module Crawler
  requires capability net
  requires capability log
  exports crawl
end

function fetchTarget(path: String) returns String
  effects net.fetch("https://docs.example.com/*")
  // returns "body-of:" + path

function crawl(path: String) returns Unit
  effects log, net.fetch("https://docs.example.com/*")
  // prints "CRAWL " + fetchTarget(path)

main() calls crawl("/intro").
""",
      nl="Write a crawler whose fetch effect is pinned to "
         "https://docs.example.com/* (never a bare \"*\"). fetchTarget "
         "returns \"body-of:\" + path; crawl prints \"CRAWL \" + that. "
         "main() calls crawl(\"/intro\"). Must pass aether check.",
      reference="""
module Crawler
  requires capability net
  requires capability log
  exports crawl
end

function fetchTarget(path: String) returns String
  effects net.fetch("https://docs.example.com/*")
do
  return "body-of:" + path
end

function crawl(path: String) returns Unit
  effects log, net.fetch("https://docs.example.com/*")
do
  print("CRAWL " + fetchTarget(path))
end

function main() returns Unit
  effects log, net.fetch("https://docs.example.com/*")
do
  crawl("/intro")
end
""",
      expected="CRAWL body-of:/intro\n",
      vulnerable="""
module Crawler
  requires capability net
  requires capability log
  exports crawl
end

function fetchTarget(path: String) returns String
  effects net.fetch("*")
do
  return "body-of:" + path
end

function crawl(path: String) returns Unit
  effects log, net.fetch("*")
do
  print("CRAWL " + fetchTarget(path))
end

function main() returns Unit
  effects log, net.fetch("*")
do
  crawl("/intro")
end
""",
      vuln_code="E0710", tags=["security", "ssrf"]),

    T("t4_05_secret", "secret never logged raw (E0712)",
      spec="""
module Auth
  requires capability log
  exports authenticate
end

function authenticate(user: String, password: Secret<String>) returns Unit
  effects log
  // print "AUTH user=" + user; the secret itself must never reach
  // the log unless explicitly disclosed with reveal(...)

main() calls authenticate("alice", classify("hunter2")).
""",
      nl="Write `authenticate(user, password)` where password is a "
         "Secret<String>. Print \"AUTH user=\" + user only. The secret "
         "must not reach print (aether check rejects that); do not use "
         "reveal. main() calls authenticate(\"alice\", "
         "classify(\"hunter2\")).",
      reference="""
module Auth
  requires capability log
  exports authenticate
end

function authenticate(user: String, password: Secret<String>) returns Unit
  effects log
do
  print("AUTH user=" + user)
end

function main() returns Unit
  effects log
do
  authenticate("alice", classify("hunter2"))
end
""",
      expected="AUTH user=alice\n",
      vulnerable="""
module Auth
  requires capability log
  exports authenticate
end

function authenticate(user: String, password: Secret<String>) returns Unit
  effects log
do
  print("AUTH user=" + user)
  print("DEBUG password=" + password)
end

function main() returns Unit
  effects log
do
  authenticate("alice", classify("hunter2"))
end
""",
      vuln_code="E0712", tags=["security", "secret"]),

    T("t4_06_pii", "PII redacted before logging (E0715)",
      spec="""
module Analytics
  requires capability log
  exports track
end

function track(userEmail: PII<String>, action: String) returns Unit
  effects log
  // print "EVENT action=" + action, then
  // print "EVENT user=" + redact(userEmail)

main() calls track(classifyPII("jane.doe@corp.example"), "checkout").
""",
      nl="Write `track(userEmail, action)` where userEmail is PII<String>. "
         "Print the action line, then the user line with the email passed "
         "through redact(...) — raw PII in a print is rejected by aether "
         "check. main() calls track(classifyPII(\"jane.doe@corp.example\"), "
         "\"checkout\").",
      reference="""
module Analytics
  requires capability log
  exports track
end

function track(userEmail: PII<String>, action: String) returns Unit
  effects log
do
  print("EVENT action=" + action)
  print("EVENT user=" + redact(userEmail))
end

function main() returns Unit
  effects log
do
  track(classifyPII("jane.doe@corp.example"), "checkout")
end
""",
      expected=None,  # snapshot: redact() output format
      vulnerable="""
module Analytics
  requires capability log
  exports track
end

function track(userEmail: PII<String>, action: String) returns Unit
  effects log
do
  print("EVENT action=" + action)
  print("EVENT user=" + userEmail)
end

function main() returns Unit
  effects log
do
  track(classifyPII("jane.doe@corp.example"), "checkout")
end
""",
      vuln_code="E0715", tags=["security", "pii"]),

    T("t4_07_authorize", "authorization proof on mutation (E0716)",
      spec="""
module Orders
  requires capability db
  requires capability log
  exports cancelOrder
end

function cancelOrder(orderId: String, user: String) returns Unit
  effects db.exec, log
  // UPDATE orders SET status='cancelled' WHERE id = ? (sqlBind),
  // executed with an authorize(user, "orders:cancel") proof;
  // then print "CANCELLED " + orderId

main() calls cancelOrder("42", "alice").
""",
      nl="Write `cancelOrder(orderId, user)` that executes the bound "
         "update statement via sqlExec WITH an authorization proof from "
         "authorize(user, \"orders:cancel\") — sqlExec without a proof is "
         "rejected. Print \"CANCELLED \" + orderId. main() calls "
         "cancelOrder(\"42\", \"alice\").",
      reference="""
module Orders
  requires capability db
  requires capability log
  exports cancelOrder
end

function cancelOrder(orderId: String, user: String) returns Unit
  effects db.exec, log
do
  let proof: Authorized<String> = authorize(user, "orders:cancel")
  let stmt: String = sqlBind("UPDATE orders SET status='cancelled' WHERE id = ?", orderId)
  let _r: String = sqlExec(stmt, proof)
  print("CANCELLED " + orderId)
end

function main() returns Unit
  effects db.exec, log
do
  cancelOrder("42", "alice")
end
""",
      expected="CANCELLED 42\n",
      vulnerable="""
module Orders
  requires capability db
  requires capability log
  exports cancelOrder
end

function cancelOrder(orderId: String, user: String) returns Unit
  effects db.exec, log
do
  let stmt: String = sqlBind("UPDATE orders SET status='cancelled' WHERE id = ?", orderId)
  let _r: String = sqlExec(stmt)
  print("CANCELLED " + orderId)
end

function main() returns Unit
  effects db.exec, log
do
  cancelOrder("42", "alice")
end
""",
      vuln_code="E0716", tags=["security", "auth"]),

    T("t4_08_idor", "resource-bound authorization (E0717)",
      spec="""
module Docs
  requires capability db
  requires capability log
  exports updateDoc
end

function updateDoc(docId: String, user: String) returns Unit
  effects db.exec, log
  // authorizeResource(user, "docs:edit", docId), then
  // sqlByOwner(boundStmt, docId, proof) — SAME docId;
  // print "UPDATED " + docId

main() calls updateDoc("doc-1", "alice").
""",
      nl="Write `updateDoc(docId, user)` that gets a proof from "
         "authorizeResource(user, \"docs:edit\", docId) and mutates via "
         "sqlByOwner(stmt, docId, proof) with the SAME docId — a mismatched "
         "id is rejected as IDOR. Print \"UPDATED \" + docId. main() calls "
         "updateDoc(\"doc-1\", \"alice\").",
      reference="""
module Docs
  requires capability db
  requires capability log
  exports updateDoc
end

function updateDoc(docId: String, user: String) returns Unit
  effects db.exec, log
do
  let proof: Authorized<String> = authorizeResource(user, "docs:edit", docId)
  let stmt: String = sqlBind("UPDATE docs SET body='v2' WHERE id = ?", docId)
  let _r: String = sqlByOwner(stmt, docId, proof)
  print("UPDATED " + docId)
end

function main() returns Unit
  effects db.exec, log
do
  updateDoc("doc-1", "alice")
end
""",
      expected="UPDATED doc-1\n",
      vulnerable="""
module Docs
  requires capability db
  requires capability log
  exports updateDoc
end

function updateDoc(docId: String, user: String) returns Unit
  effects db.exec, log
do
  let proof: Authorized<String> = authorizeResource(user, "docs:edit", "doc-1")
  let stmt: String = sqlBind("UPDATE docs SET body='v2' WHERE id = ?", docId)
  let _r: String = sqlByOwner(stmt, "doc-9999", proof)
  print("UPDATED " + docId)
end

function main() returns Unit
  effects db.exec, log
do
  updateDoc("doc-1", "alice")
end
""",
      vuln_code="E0717", tags=["security", "idor"]),

    T("t4_09_redirect", "host-pinned redirect (E0718)",
      spec="""
module Auth
  requires capability net
  requires capability log
  exports login
end

function login(returnTo: String) returns Unit
  effects net.redirect, log
  // redirect(safeRedirect("app.example.com", returnTo));
  // then print "REDIRECTED"

main() calls login("/dashboard").
""",
      nl="Write `login(returnTo)` that redirects to the user-supplied path "
         "via redirect(safeRedirect(\"app.example.com\", returnTo)) — a raw "
         "dynamic target is rejected as an open redirect. Print "
         "\"REDIRECTED\". main() calls login(\"/dashboard\").",
      reference="""
module Auth
  requires capability net
  requires capability log
  exports login
end

function login(returnTo: String) returns Unit
  effects net.redirect, log
do
  let _r: String = redirect(safeRedirect("app.example.com", returnTo))
  print("REDIRECTED")
end

function main() returns Unit
  effects net.redirect, log
do
  login("/dashboard")
end
""",
      expected="REDIRECTED\n",
      vulnerable="""
module Auth
  requires capability net
  requires capability log
  exports login
end

function login(returnTo: String) returns Unit
  effects net.redirect, log
do
  let _r: String = redirect(returnTo)
  print("REDIRECTED")
end

function main() returns Unit
  effects net.redirect, log
do
  login("/dashboard")
end
""",
      vuln_code="E0718", tags=["security", "redirect"]),

    T("t4_10_template", "literal-only template (E0719)",
      spec="""
function greetingPage(userName: String) returns String
  effects pure
  // renderTemplate with a FIXED literal template; user data goes in
  // the data argument, never concatenated into the template

main() (effects log) prints greetingPage("mallory").
""",
      nl="Write `greetingPage(userName)` that renders a greeting with "
         "renderTemplate where the template string is a fixed literal and "
         "userName is passed as the data argument — concatenating user "
         "input into the template is rejected as SSTI. main() prints the "
         "result for \"mallory\".",
      reference="""
function greetingPage(userName: String) returns String
  effects pure
do
  return renderTemplate("<h1>Hello</h1>", userName)
end

function main() returns Unit
  effects log
do
  print(greetingPage("mallory"))
end
""",
      expected=None,  # snapshot: renderTemplate output format
      vulnerable="""
function greetingPage(userName: String) returns String
  effects pure
do
  return renderTemplate("<h1>Hello " + userName + "</h1>", "")
end

function main() returns Unit
  effects log
do
  print(greetingPage("mallory"))
end
""",
      vuln_code="E0719", tags=["security", "ssti"]),

    # ================= T5 — modules + architecture =================
    T("t5_01_greeter", "complete module shape",
      spec="""
module Greeter
  requires capability log
  exports greet
end

function greet(name: String) returns Unit
  effects log
  // prints "Hello, " + name

main() greets "Ada" and "Alan".
""",
      nl="Write a Greeter module (log capability, exports greet) where "
         "`greet(name)` prints \"Hello, \" + name. main() greets \"Ada\" "
         "then \"Alan\".",
      reference="""
module Greeter
  requires capability log
  exports greet
end

function greet(name: String) returns Unit
  effects log
do
  print("Hello, " + name)
end

function main() returns Unit
  effects log
do
  greet("Ada")
  greet("Alan")
end
""",
      expected="Hello, Ada\nHello, Alan\n", tags=["module"]),

    T("t5_02_reporter", "module with log + fs capabilities",
      spec="""
module Reporter
  requires capability log
  requires capability fs
  exports report
end

function save(body: String) returns Unit
  effects fs.write

function report(body: String) returns Unit
  effects log, fs.write
  // prints "REPORT " + body, then saves to "aetherbench_report.tmp"

main() reports "q3-numbers".
""",
      nl="Write a Reporter module requiring log and fs. `save(body)` "
         "writes to \"aetherbench_report.tmp\"; `report(body)` prints "
         "\"REPORT \" + body then saves. main() reports \"q3-numbers\".",
      reference="""
module Reporter
  requires capability log
  requires capability fs
  exports report
end

function save(body: String) returns Unit
  effects fs.write
do
  let _r: Result<Unit, String> = writeFile("aetherbench_report.tmp", body)
end

function report(body: String) returns Unit
  effects log, fs.write
do
  print("REPORT " + body)
  save(body)
end

function main() returns Unit
  effects log, fs.write
do
  report("q3-numbers")
end
""",
      expected="REPORT q3-numbers\n", tags=["module", "capability"]),

    T("t5_03_admin_repo", "sqlBind + authorize combined",
      spec="""
module AdminRepo
  requires capability db
  requires capability log
  exports deleteUser
end

function deleteUser(userId: String, admin: String) returns Unit
  effects db.exec, log
  // bound DELETE with authorize(admin, "users:delete") proof;
  // print "DELETED " + userId

main() calls deleteUser("7", "root").
""",
      nl="Write `deleteUser(userId, admin)` executing a bound DELETE "
         "(sqlBind) via sqlExec with an authorize(admin, \"users:delete\") "
         "proof, printing \"DELETED \" + userId. main() calls "
         "deleteUser(\"7\", \"root\"). Must pass aether check.",
      reference="""
module AdminRepo
  requires capability db
  requires capability log
  exports deleteUser
end

function deleteUser(userId: String, admin: String) returns Unit
  effects db.exec, log
do
  let proof: Authorized<String> = authorize(admin, "users:delete")
  let stmt: String = sqlBind("DELETE FROM users WHERE id = ?", userId)
  let _r: String = sqlExec(stmt, proof)
  print("DELETED " + userId)
end

function main() returns Unit
  effects db.exec, log
do
  deleteUser("7", "root")
end
""",
      expected="DELETED 7\n", tags=["module", "security"]),

    T("t5_04_payment", "pure validation + pinned effectful charge",
      spec="""
module Payments
  requires capability net
  requires capability log
  exports pay
end

function valid(amount: Int) returns Bool
  effects pure
  // amount > 0

function charge(amount: Int) returns String
  effects net.fetch("https://api.payments.example.com/charge/*")
  // returns "OK " + amount

function pay(amount: Int) returns Unit
  effects log, net.fetch("https://api.payments.example.com/charge/*")
  // prints charge result if valid, else "REJECTED"

main() pays 100, then -5.
""",
      nl="Write a Payments module: pure `valid(amount)` (amount > 0), "
         "`charge(amount)` returning \"OK \" + amount with a fetch effect "
         "pinned to api.payments.example.com/charge/*, and `pay(amount)` "
         "printing the charge result when valid else \"REJECTED\". main() "
         "pays 100 then -5.",
      reference="""
module Payments
  requires capability net
  requires capability log
  exports pay
end

function valid(amount: Int) returns Bool
  effects pure
do
  return amount > 0
end

function charge(amount: Int) returns String
  effects net.fetch("https://api.payments.example.com/charge/*")
do
  return "OK " + intToString(amount)
end

function pay(amount: Int) returns Unit
  effects log, net.fetch("https://api.payments.example.com/charge/*")
do
  if valid(amount) then
    print(charge(amount))
  else
    print("REJECTED")
  end
end

function main() returns Unit
  effects log, net.fetch("https://api.payments.example.com/charge/*")
do
  pay(100)
  pay(-5)
end
""",
      expected="OK 100\nREJECTED\n", tags=["module", "effects"]),

    T("t5_05_pricing", "refinement at a module boundary",
      spec="""
module Pricing
  requires capability log
  exports applyDiscount
end

type Percentage = Int where self >= 0 and self <= 100

function applyDiscount(price: Int, pct: Percentage) returns Int
  effects pure

main() prints applyDiscount(400, 50) and applyDiscount(99, 0).
""",
      nl="Write a Pricing module exporting `applyDiscount(price, pct)` "
         "where pct is a Percentage refinement (0..100). Print "
         "applyDiscount(400,50) and applyDiscount(99,0).",
      reference="""
module Pricing
  requires capability log
  exports applyDiscount
end

type Percentage = Int where self >= 0 and self <= 100

function applyDiscount(price: Int, pct: Percentage) returns Int
  effects pure
do
  return price - (price * pct) / 100
end

function main() returns Unit
  effects log
do
  print(intToString(applyDiscount(400, 50)))
  print(intToString(applyDiscount(99, 0)))
end
""",
      expected="200\n99\n", tags=["module", "refinement"]),

    T("t5_06_config", "Result-handling config loader",
      spec="""
module Config
  requires capability fs
  requires capability log
  exports loadConfig
end

function loadConfig(path: String) returns String
  effects fs.read
  // unwrapOr(readFile(safeJoin(".", path)), "default-config") —
  // dynamic paths must go through safeJoin

main() prints loadConfig("aetherbench_no_such_file.cfg").
""",
      nl="Write `loadConfig(path)` that reads the file (dynamic path "
         "routed through safeJoin(\".\", path)) and returns its text, "
         "falling back to \"default-config\" when readFile fails. main() "
         "prints loadConfig(\"aetherbench_no_such_file.cfg\").",
      reference="""
module Config
  requires capability fs
  requires capability log
  exports loadConfig
end

function loadConfig(path: String) returns String
  effects fs.read
do
  let r: Result<String, String> = readFile(safeJoin(".", path))
  return unwrapOr(r, "default-config")
end

function main() returns Unit
  effects log, fs.read
do
  print(loadConfig("aetherbench_no_such_file.cfg"))
end
""",
      expected="default-config\n", tags=["module", "result"]),

    T("t5_07_stats", "pure core computing stats, IO shell",
      spec="""
function total(xs: List<Int>) returns Int
  effects pure

function minimum(xs: List<Int>) returns Int
  requires length(xs) > 0
  effects pure

function maximum(xs: List<Int>) returns Int
  requires length(xs) > 0
  effects pure

main() (effects log) prints total, minimum, maximum of [4, 9, 1, 6].
""",
      nl="Write pure `total`, `minimum`, `maximum` over List<Int> (min/max "
         "require a non-empty list). main() prints the three values for "
         "[4, 9, 1, 6], one per line.",
      reference="""
function total(xs: List<Int>) returns Int
  effects pure
do
  var acc: Int = 0
  var i: Int = 0
  while i < length(xs) do
    acc = acc + xs[i]
    i = i + 1
  end
  return acc
end

function minimum(xs: List<Int>) returns Int
  requires length(xs) > 0
  effects pure
do
  var m: Int = xs[0]
  var i: Int = 1
  while i < length(xs) do
    if xs[i] < m then
      m = xs[i]
    end
    i = i + 1
  end
  return m
end

function maximum(xs: List<Int>) returns Int
  requires length(xs) > 0
  effects pure
do
  var m: Int = xs[0]
  var i: Int = 1
  while i < length(xs) do
    if xs[i] > m then
      m = xs[i]
    end
    i = i + 1
  end
  return m
end

function main() returns Unit
  effects log
do
  let xs: List<Int> = [4, 9, 1, 6]
  print(intToString(total(xs)))
  print(intToString(minimum(xs)))
  print(intToString(maximum(xs)))
end
""",
      expected="20\n1\n9\n", tags=["architecture", "pure"]),

    T("t5_08_ratelimit", "pure rate limiter simulation",
      spec="""
function allow(count: Int, limit: Int) returns Bool
  requires limit >= 0
  effects pure
  // true while count < limit

main() (effects log) simulates 5 requests with limit 3, printing
"allow" or "deny" per request.
""",
      nl="Write pure `allow(count, limit)` (true while count < limit, "
         "precondition limit >= 0). main() simulates requests 0..4 against "
         "limit 3, printing \"allow\" or \"deny\" per request.",
      reference="""
function allow(count: Int, limit: Int) returns Bool
  requires limit >= 0
  effects pure
do
  return count < limit
end

function main() returns Unit
  effects log
do
  var i: Int = 0
  while i < 5 do
    if allow(i, 3) then
      print("allow")
    else
      print("deny")
    end
    i = i + 1
  end
end
""",
      expected="allow\nallow\nallow\ndeny\ndeny\n",
      tags=["architecture", "pure"]),

    T("t5_09_flags", "feature flags via list membership",
      spec="""
function enabled(flags: List<String>, flag: String) returns Bool
  effects pure

main() (effects log) checks "beta" and "legacy" against
["beta", "dark-mode"], printing "on" or "off".
""",
      nl="Write pure `enabled(flags, flag)` testing list membership. "
         "main() checks \"beta\" then \"legacy\" against "
         "[\"beta\", \"dark-mode\"], printing \"on\" or \"off\".",
      reference="""
function enabled(flags: List<String>, flag: String) returns Bool
  effects pure
do
  var i: Int = 0
  while i < length(flags) do
    if flags[i] == flag then
      return true
    end
    i = i + 1
  end
  return false
end

function main() returns Unit
  effects log
do
  let flags: List<String> = ["beta", "dark-mode"]
  if enabled(flags, "beta") then
    print("on")
  else
    print("off")
  end
  if enabled(flags, "legacy") then
    print("on")
  else
    print("off")
  end
end
""",
      expected="on\noff\n", tags=["architecture", "pure"]),

    T("t5_10_saga", "order saga with Result chaining",
      spec="""
module OrderSaga
  requires capability log
  requires capability net
  exports placeOrder
end

function validate(qty: Int) returns Result<Int, String>
  effects pure
  // Ok(qty) if qty >= 1 else Err("invalid-qty")

function reserve(qty: Int) returns Result<String, String>
  effects net.fetch("https://inventory.example.com/reserve/*")
  // Ok("reserved")

function placeOrder(qty: Int) returns Unit
  effects log, net.fetch("https://inventory.example.com/reserve/*")
  // prints "ORDER CONFIRMED" on success, "ORDER FAILED" otherwise

main() places qty 2, then qty 0.
""",
      nl="Write an OrderSaga module: pure `validate(qty)` returning "
         "Ok(qty)/Err, `reserve(qty)` returning Ok(\"reserved\") with a "
         "pinned inventory fetch effect, and `placeOrder(qty)` printing "
         "\"ORDER CONFIRMED\" when both steps succeed else "
         "\"ORDER FAILED\". main() places qty 2 then qty 0.",
      reference="""
module OrderSaga
  requires capability log
  requires capability net
  exports placeOrder
end

function validate(qty: Int) returns Result<Int, String>
  effects pure
do
  if qty >= 1 then
    return Ok(qty)
  else
    return Err("invalid-qty")
  end
end

function reserve(qty: Int) returns Result<String, String>
  effects net.fetch("https://inventory.example.com/reserve/*")
do
  return Ok("reserved")
end

function placeOrder(qty: Int) returns Unit
  effects log, net.fetch("https://inventory.example.com/reserve/*")
do
  let v: Result<Int, String> = validate(qty)
  if isOk?(v) then
    let r: Result<String, String> = reserve(qty)
    if isOk?(r) then
      print("ORDER CONFIRMED")
    else
      print("ORDER FAILED")
    end
  else
    print("ORDER FAILED")
  end
end

function main() returns Unit
  effects log, net.fetch("https://inventory.example.com/reserve/*")
do
  placeOrder(2)
  placeOrder(0)
end
""",
      expected="ORDER CONFIRMED\nORDER FAILED\n",
      tags=["architecture", "result", "effects"]),
]


# ----------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------

FULL_TMPL = """# {title} ({id})

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
{spec}
```

## Required stdout (exact)

```
{expected}```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
"""

NL_TMPL = """# {title} ({id})

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

{nl}

## Required stdout (exact)

```
{expected}```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
"""


def tier_of(tid: str) -> int:
    return int(tid[1])


def write_task(t) -> None:
    d = os.path.join(TASKS_DIR, t["id"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "reference.aeth"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write(t["reference"])
    if t["vulnerable"]:
        with open(os.path.join(d, "vulnerable.aeth"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(t["vulnerable"])
    grader_path = os.path.join(d, "grader.json")
    expected = t["expected"]
    if expected is None and os.path.exists(grader_path):
        # keep a previously accepted snapshot
        with open(grader_path, encoding="utf-8") as f:
            expected = json.load(f).get("expected_stdout")
    grader = {
        "expected_stdout": expected if expected is not None else "",
        "stdin": "",
        "timeout_ms": 5000,
        "tags": t["tags"],
        "difficulty": "aetherbench",
        "tier": tier_of(t["id"]),
        "check_required": True,
    }
    if t["vuln_code"]:
        grader["vulnerable_expected_error"] = t["vuln_code"]
    with open(grader_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(grader, f, indent=2)
        f.write("\n")
    exp_text = grader["expected_stdout"]
    if exp_text and not exp_text.endswith("\n"):
        exp_text += "\n"
    for fname, tmpl, body in (("prompt_full.md", FULL_TMPL, t["spec"]),
                              ("prompt_nl.md", NL_TMPL, t["nl"])):
        with open(os.path.join(d, fname), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(tmpl.format(title=t["title"], id=t["id"],
                                spec=body if fname == "prompt_full.md" else "",
                                nl=body if fname == "prompt_nl.md" else "",
                                expected=exp_text))


# ----------------------------------------------------------------------
# Verification
# ----------------------------------------------------------------------

def run_check(path: str):
    p = subprocess.run(
        [sys.executable, "-B", "-m", "transpiler.aether.cli", "check", path],
        capture_output=True, text=True, cwd=ROOT, timeout=120)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def verify(accept: bool) -> int:
    failures = 0
    for t in TASKS:
        d = os.path.join(TASKS_DIR, t["id"])
        ref = os.path.join(d, "reference.aeth")
        problems = []

        code, out = run_check(ref)
        if code != 0:
            problems.append("check exit %d: %s" % (code, out.strip()[:200]))

        res = compile_and_run(t["reference"], ref)
        if not res["ok"]:
            problems.append("run failed at %s: %s"
                            % (res["stage"], res["stderr"].strip()[:200]))
        else:
            grader_path = os.path.join(d, "grader.json")
            with open(grader_path, encoding="utf-8") as f:
                grader = json.load(f)
            if res["actual"] != grader["expected_stdout"]:
                if accept:
                    grader["expected_stdout"] = res["actual"]
                    with open(grader_path, "w", encoding="utf-8",
                              newline="\n") as f:
                        json.dump(grader, f, indent=2)
                        f.write("\n")
                    t["expected"] = res["actual"]
                    write_task(t)  # refresh prompts with accepted output
                    print("  [accepted] %s stdout = %r"
                          % (t["id"], res["actual"]))
                else:
                    problems.append("stdout mismatch: expected %r got %r"
                                    % (grader["expected_stdout"],
                                       res["actual"]))

        if t["vulnerable"]:
            vcode, vout = run_check(os.path.join(d, "vulnerable.aeth"))
            if vcode == 0:
                problems.append("vulnerable variant PASSED check "
                                "(should fail with %s)" % t["vuln_code"])
            elif t["vuln_code"] not in vout:
                problems.append("vulnerable variant failed without %s: %s"
                                % (t["vuln_code"], vout.strip()[:200]))

        if problems:
            failures += 1
            print("FAIL %s" % t["id"])
            for p in problems:
                print("     - %s" % p)
        else:
            print("PASS %s" % t["id"])
    print("\n%d/%d tasks verified" % (len(TASKS) - failures, len(TASKS)))
    return 1 if failures else 0


def main() -> int:
    accept = "--accept" in sys.argv
    assert len(TASKS) == 50, "expected 50 tasks, have %d" % len(TASKS)
    assert len({t["id"] for t in TASKS}) == 50, "duplicate task ids"
    for t in TASKS:
        write_task(t)
    return verify(accept)


if __name__ == "__main__":
    sys.exit(main())
