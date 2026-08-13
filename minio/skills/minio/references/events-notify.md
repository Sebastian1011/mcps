# Event notifications and live event watching

Two mechanisms: `mc event` configures durable bucket notifications delivered
to a target service (queue/webhook/etc, identified by ARN). `mc watch`/`mc find --watch`
stream events to your terminal/process live and stop when the command exits.

## `mc event` — durable bucket notifications (ARN-based)

```bash
mc event list ALIAS/BUCKET                                     # all configured notifications
mc event list ALIAS/BUCKET arn:aws:sqs:us-west-2:444455556666:your-queue

mc event add ALIAS/BUCKET arn:aws:sqs:us-west-2:444455556666:your-queue
mc event add ALIAS/BUCKET ARN --event put,delete,get --prefix photos/ --suffix .jpg
mc event add ALIAS/BUCKET ARN -p --event put,delete,get   # -p = ignore if an identical config already exists
mc event add ALIAS/BUCKET ARN --event replica,ilm          # notify on replication / ILM-transition events too

mc event remove ALIAS/BUCKET ARN
mc event remove ALIAS/BUCKET --force                        # remove ALL notifications on the bucket — confirm first
```

The ARN identifies a **notification target** that must already be configured
server-side (see below) — `mc event add` only wires a bucket to an existing
target, it does not create the target.

## Configuring notification targets (server-side, via `mc admin config`)

Notification targets are MinIO server config subsystems named `notify_<type>`
(e.g. `notify_webhook`, `notify_kafka`, `notify_mqtt`, `notify_mysql`,
`notify_postgres`, `notify_elasticsearch`, `notify_redis`, `notify_amqp`,
`notify_nats`, `notify_nsq`). The exact parameter names can differ by MinIO
version — always confirm against the live server before configuring one:

```bash
mc admin config set ALIAS --tree | grep notify        # which target types this server supports
mc admin config get ALIAS notify_webhook                # current settings + parameter names
mc admin config set ALIAS notify_webhook endpoint="http://localhost:8080/minio/events"
mc admin config get ALIAS notify_webhook --env           # env-var equivalents, if you'd rather set it that way
mc admin service restart ALIAS                           # required after changing a notify_* subsystem
```
After configuring a target and restarting, its ARN appears in
`mc admin config get ALIAS notify_webhook` / server logs — use that ARN with
`mc event add`. See `admin-ops.md` for the full `mc admin config` reference.

## `mc watch` — live event stream (foreground, no target needed)

```bash
mc watch ALIAS/BUCKET
mc watch --events put,delete ALIAS/BUCKET
mc watch --prefix "output/" --suffix ".jpg" ALIAS/BUCKET
mc watch ALIAS/                 # site-level (buckets existing at start time only)
mc watch /usr/share              # also works on a local directory
```
Long-running/blocking — run it in the background or with a time-bounded
expectation, and stop it explicitly rather than leaving it attached.

## `mc find --watch` — filtered live matches with an action per match

```bash
mc find ALIAS/BUCKET --name "*.jpg" --watch --exec 'mc cp {} ALIAS2/BUCKET2'
```
See `objects.md` for the full `mc find` reference and format tokens.
`--exec` runs a real command per event — treat it like any other command
execution and confirm with the user if the exec'd command is destructive.
