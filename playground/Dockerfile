# H.B.2 playground container.
#
# Minimal image: Python 3.11 + the Aether checkout + nothing else.
# The aether-lang package is stdlib-only; the playground backend is
# also stdlib-only. Deliberately no `pip install` step at build time.
#
# Build:
#   docker build -t aether-playground -f playground/Dockerfile .
#
# Run (production-grade — see playground/SECURITY.md for full
# rationale on each flag):
#   docker run \
#       --read-only \
#       --tmpfs /tmp:size=64m,mode=1777 \
#       --network none \
#       --user nobody \
#       --memory 512m \
#       --cpus 1.0 \
#       --pids-limit 64 \
#       --cap-drop ALL \
#       --security-opt no-new-privileges \
#       -p 8080:8080 \
#       aether-playground

FROM python:3.11-slim

WORKDIR /aether

# Copy the toolchain + playground. The build context is the repo root,
# so this picks up transpiler/, playground/, plus the layout the
# server expects (examples, static UI).
COPY transpiler/ /aether/transpiler/
COPY playground/ /aether/playground/

# Run as an unprivileged user. Real deployments override this with
# --user nobody (or the Kubernetes-equivalent) anyway, but having a
# default below root is the right baseline.
RUN useradd --no-create-home --shell /sbin/nologin --uid 10001 playground \
 && chown -R playground:playground /aether
USER playground

EXPOSE 8080

# stdlib-only server. No CMD shell, exec form so signals reach Python.
ENTRYPOINT ["python3", "-B", "/aether/playground/backend/app.py"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
