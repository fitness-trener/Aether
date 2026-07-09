"""Python equivalent — module capability leak is invisible.

The intent was: "AuditService only needs the log capability". Python
has no module-level capability declaration, so when `persist_audit` is
added to write the audit line to disk too, there is no language-level
way to register that the service now needs filesystem access. The
function compiles, the unit tests for `emit_audit` still pass (it
returns None, doesn't raise), and the architectural promise "this
service only writes to stdout" silently dies.

To keep the demo hermetic we point at a tmp path inside this file's
output directory. The point isn't the file write — it's that Python
has no language-level construct that says "this service's blast radius
is bounded to stdout."

Expected behaviour: prints the audit line, writes the file, exits 0.
NO error. This is the wedge: Aether's B.3 transitive capability check
refuses the same code at compile time.
"""

import os
import tempfile


_AUDIT_PATH = os.path.join(tempfile.gettempdir(), "demo03_audit.log")


def persist_audit(line: str) -> None:
    # ← architectural error: a "log-only" service should not write files
    with open(_AUDIT_PATH, "a") as f:
        f.write(line + "\n")


def emit_audit(line: str) -> None:
    print(line)
    persist_audit(line)


def main() -> None:
    emit_audit("user=42 action=login")


if __name__ == "__main__":
    main()
