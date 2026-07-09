# T07 — `MetricReporter` module declared `log, time` adds a net upload

## Architectural promise
The metric reporter is deployed in a sandbox that allows only `log`
and `time` capabilities. The deployment manifest reflects this; a
network-policy gate refuses to permit `net` for this module.

## Naive-agent failure
"Let's stream metrics to a hosted vendor" — agent adds an HTTP POST
to a helper, doesn't update the module declaration.

## Aether outcome
[E0701] — transitive net.fetch requires capability `net`, which the
module hasn't declared.
