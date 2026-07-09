"""Phase 1 regressions: scoped inference soundness + admission decisions.

Locks in that inference NEVER introduces a false negative (a region with a real
capability is never cleared), and that the admission controller fails safe.
Run: python3 tests/test_phase1.py
"""
from __future__ import annotations
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler")); sys.path.insert(0, ROOT)

import tools.cap_delta as cd
from tools.cap_delta import capability_delta
from tools.admission import parse_policy, decide, TAXONOMY
from tools.scoped_infer import augment_module


def test_inference_no_false_negative_on_traps():
    cd.USE_INFERENCE = True
    traps = {
        "pprint": ("def d(s):\n    return s\n",
                   "import pprint\ndef d(s):\n    pprint.pprint(s)\n    return s\n"),
        "append_disk": ("def r(a,e):\n    return e\n",
                        "def r(a,e):\n    a.append(e)\n    return e\n"),
        "codecs": ("def rd(p):\n    return p\n",
                   "import codecs\ndef rd(p):\n    return codecs.open(p,'r').read()\n"),
        "local_class_append": (
            "class L:\n    def __init__(s,p):\n        s.p=p\n"
            "def use():\n    return 1\n",
            "class L:\n    def __init__(s,p):\n        s.p=p\n"
            "    def append(s,e):\n        open(s.p,'a').write(e)\n"
            "def use():\n    x=L('f')\n    x.append('y')\n    return 1\n"),
    }
    for name, (b, h) in traps.items():
        d = capability_delta(b, h)
        assert d["verdict"] != "NO_NEW_CAPABILITY", f"{name} was silently cleared!"
    print("  [ok] inference introduces no false negative on 4 trap diffs")


def test_inference_resolves_typed_receivers():
    cd.USE_INFERENCE = True
    b = "import redis\nclass K:\n    def __init__(self):\n        self.c=redis.Redis()\n    def look(self,k):\n        return 1\n"
    h = "import redis\nclass K:\n    def __init__(self):\n        self.c=redis.Redis()\n    def look(self,k):\n        return self.c.get(k)\n"
    d = capability_delta(b, h)
    assert "db" in d["newly_introduces"], f"expected db identified, got {d['newly_introduces']}"
    print("  [ok] inference resolves self-attr typed receiver -> db named")


def test_local_class_append_is_violation_not_clean():
    # the disk-writing local .append, resolved one-hop, must surface fs (never clean)
    cd.USE_INFERENCE = True
    h = ("class L:\n    def __init__(s,p):\n        s.p=p\n"
         "    def append(s,e):\n        open(s.p,'a').write(e)\n"
         "def use():\n    x=L('f')\n    x.append('y')\n    return 1\n")
    d = capability_delta("def use():\n    return 1\n", h)
    assert "fs" in d["newly_introduces"] or d["verdict"] == "UNPROVABLE", \
        f"local disk-append must surface fs or stay UNPROVABLE, got {d}"
    print("  [ok] one-hop local class .append surfaces fs (sound)")


def test_policy_coverage_and_conflict():
    assert parse_policy("default deny *\n").check_coverage()["ok"]
    assert not parse_policy("deny new net in a/**\n").check_coverage()["complete"]
    c = parse_policy("default deny *\nallow new net in a/**\ndeny new net in a/**\n").check_coverage()
    assert c["conflicts"], "should detect allow/deny conflict"
    print("  [ok] policy coverage + conflict checks fire correctly")


def test_admission_failsafe():
    pol = parse_policy("default allow *\ndeny new net in payments/**\n")
    d = capability_delta("import requests\ndef f(x):\n    return x\n",
                         "import requests\ndef f(x):\n    requests.get(x)\n    return x\n")
    assert decide(d, pol, "payments/c.py")["decision"] == "BLOCK"
    assert decide(d, pol, "svc/c.py")["decision"] == "ALLOW"
    # UNPROVABLE residual must carry a runtime guard and ESCALATE when autonomous
    du = capability_delta("def r(a,e):\n    return e\n",
                          "def r(a,e):\n    a.append(e)\n    return e\n")
    auto = decide(du, pol, "svc/x.py", autonomous=True)
    assert auto["decision"] == "ESCALATE" and auto["runtime_policy"] is not None
    print("  [ok] admission fails safe: BLOCK on denied cap, ESCALATE+guard on UNPROVABLE")


def main():
    tests = [test_inference_no_false_negative_on_traps,
             test_inference_resolves_typed_receivers,
             test_local_class_append_is_violation_not_clean,
             test_policy_coverage_and_conflict,
             test_admission_failsafe]
    fails = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fails += 1; print(f"  [FAIL] {t.__name__}: {e}")
    print(f"\n{len(tests)-fails}/{len(tests)} Phase 1 tests passed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
