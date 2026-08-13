# Batch jobs: replicate, keyrotate, expire

Batch jobs run large, one-off bulk operations server-side (not streamed
through `mc`), driven by a YAML job definition. Workflow is always
generate → edit → start → monitor.

```bash
mc batch generate ALIAS list           # ask the server which job types it supports
mc batch generate ALIAS replicate > replicate.yaml
mc batch generate ALIAS keyrotate > keyrotate.yaml
mc batch generate ALIAS expire > expire.yaml
```

`generate` prints a real, server-provided YAML skeleton with inline comments
for that job type and that MinIO version — **read the generated file itself**
before editing; do not assume field names from memory, they vary by job type
and version.

```bash
mc batch start ALIAS ./replicate.yaml
```
`batch start` runs immediately once submitted — there is no separate
`--dry-run`. Review the edited YAML (source/target buckets, filters, object
count implications) with the user before running `start`, especially for
`expire` (permanently deletes matching objects) and `keyrotate` (rewrites
every matching object's encryption envelope).

## Monitoring and control

```bash
mc batch list ALIAS
mc batch list ALIAS --type replicate
mc batch list ALIAS --type expire --bucket mybucket

mc batch status ALIAS JOBID
mc batch status ALIAS --all

mc batch describe ALIAS JOBID          # show the job definition that was submitted

mc batch cancel ALIAS --id JOBID       # stop an in-flight job — confirm before cancelling someone else's job
```

## Guardrails

- **`expire` jobs delete data.** Treat a batch `expire` job exactly like
  `mc rm --recursive --force`: confirm the bucket/prefix/filter scope with the
  user before `mc batch start`, and prefer running `mc batch describe` right
  after start to have them re-read what was actually submitted.
- **`keyrotate` touches every matching object's metadata.** Large buckets mean
  a long-running, resource-intensive job — check `mc batch status` before
  assuming it's done, and mention expected duration depends on object count.
- Batch jobs are server state, not `mc` client state — they keep running even
  if the `mc batch start` command / your session ends. Always point the user
  to `mc batch status`/`mc batch list` rather than assuming a job stopped.
