# T03 — `cacheLookup` declared `log`-only secretly performs `fs.write`

## Architectural promise
`cacheLookup(key)` should at most emit a log line on miss; certainly
should not touch the disk. Deployments running in a read-only sandbox
rely on it.

## Naive-agent failure
A "let's persist the miss for analytics" refactor adds a `writeFile`
call. The function still returns a string, callers still get cache
values, but the read-only sandbox now crashes at deploy time — or
worse, the deploy succeeds in a non-read-only env and fills the disk.

## Aether outcome
[E0801] refuses: caller declared `log` cannot transitively perform
`fs.write`.

## Python outcome
Runs, writes the file silently.
