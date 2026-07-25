# Real-world shape — the guard is not the argument (BUGS.md BUG-004).
#
# These sinks decide safety from something OTHER than the argument the
# rule judges: a keyword's value, or a flag bound in an earlier statement.
# Every one of these was silent until 2026-07-26 because the gates
# defaulted the unknown case to "safe".
#
# Loader safety verified by execution on PyYAML 6.0.3 with the payload
# `!!python/object/apply:os.system [...]`:
#   yaml.Loader -> CONSTRUCTED   yaml.UnsafeLoader -> CONSTRUCTED
#   yaml.FullLoader -> refused   yaml.SafeLoader   -> refused
# FullLoader is still not sanctioned: CVE-2020-1747, CVE-2020-14343 are
# FullLoader bypasses.
#
# The vulnerable shapes:

import subprocess

import yaml


def load_explicit_unsafe(raw: str):
    # The commonest WRONG fix for PyYAML's deprecation warning: add a
    # Loader= to silence it, and pick the unsafe one. This is the RCE,
    # written at the call site.
    return yaml.load(raw, Loader=yaml.Loader)


def load_unsafe_bound_elsewhere(raw: str):
    # Same RCE, one statement of indirection.
    loader = yaml.Loader
    return yaml.load(raw, Loader=loader)


def load_full_loader(raw: str):
    # Refuses this plan's probe payload, but has its own bypass CVEs.
    # Deliberately not sanctioned - over-flag.
    return yaml.load(raw, Loader=yaml.FullLoader)


def run_shell_bound_elsewhere(cmd: str) -> int:
    # A shell flag held in a variable is still a shell.
    sh = True
    return subprocess.run("convert " + cmd, shell=sh).returncode


def query_concat_with_params(cur, name: str, extra):
    # A second argument does NOT launder a concatenated query. Partial
    # parameterization is the trap: the bound value is safe, the
    # concatenated one is not.
    return cur.execute("SELECT * FROM t WHERE n=" + name, extra)


# The fixes, each of which must be silent:

def load_explicit_unsafe_safe(raw: str):
    return yaml.load(raw, Loader=yaml.SafeLoader)


def load_unsafe_bound_elsewhere_safe(raw: str):
    loader = yaml.SafeLoader
    return yaml.load(raw, Loader=loader)


def run_shell_bound_elsewhere_safe(cmd: str) -> int:
    sh = False
    return subprocess.run(["convert", cmd], shell=sh).returncode


def query_concat_with_params_safe(cur, name: str):
    return cur.execute("SELECT * FROM t WHERE n = ?", (name,))
