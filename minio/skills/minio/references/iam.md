# IAM: users, groups, policies, access keys, STS, external identity providers

All commands take `ALIAS` (a server, not a bucket) as `TARGET`. Everything
here changes who can access data — confirm intent with the user before
granting, attaching, or revoking access.

## `mc admin user` — builtin users

```bash
mc admin user list ALIAS
mc admin user info ALIAS USERNAME
mc admin user policy ALIAS USERNAME           # policy document(s) attached to this user

mc admin user add ALIAS ACCESSKEY SECRETKEY   # ACCESSKEY=username, SECRETKEY=password
mc admin user add ALIAS                        # omit keys to be prompted, or pipe them on stdin
mc admin user disable ALIAS USERNAME
mc admin user enable ALIAS USERNAME
mc admin user remove ALIAS USERNAME            # irreversible — confirm before running
```

**Guardrail**: never put a real secret key as a literal argv token. Prompt
interactively or pipe via stdin (`printf '%s\n%s\n' "$KEY" "$SECRET" | mc admin user add ALIAS`),
and wrap manual typing with `set +o history` / `set -o history` as `mc`'s own
examples do.

```bash
mc admin user sts info ALIAS STS-ACCOUNT           # only inspection; STS accounts are minted via the S3 STS API, not created with mc
mc admin user sts info --policy ALIAS STS-ACCOUNT  # include the policy JSON
```

## `mc admin group` — groups of users

```bash
mc admin group list ALIAS
mc admin group info ALIAS GROUPNAME
mc admin group add ALIAS GROUPNAME                    # empty group
mc admin group add ALIAS GROUPNAME user1 user2        # create/extend with members
mc admin group remove ALIAS GROUPNAME user1           # remove one member
mc admin group remove ALIAS GROUPNAME                 # remove the whole group — confirm first
mc admin group enable ALIAS GROUPNAME
mc admin group disable ALIAS GROUPNAME
```

## `mc admin policy` — IAM policies (canned JSON policy documents)

```bash
mc admin policy list ALIAS
mc admin policy info ALIAS POLICYNAME
mc admin policy info ALIAS POLICYNAME --policy-file /tmp/policy.json   # also save it locally

mc admin policy create ALIAS POLICYNAME /path/to/policy.json
mc admin policy remove ALIAS POLICYNAME        # fails if still attached to anyone; confirm before force-detaching first

mc admin policy attach ALIAS POLICYNAME --user USERNAME
mc admin policy attach ALIAS POLICYNAME1 POLICYNAME2 --group GROUPNAME
mc admin policy detach ALIAS POLICYNAME --user USERNAME

mc admin policy entities ALIAS                                    # all policy<->entity associations
mc admin policy entities ALIAS --policy POLICYNAME
mc admin policy entities ALIAS --user USERNAME --group GROUPNAME
```
`attach`/`detach` require exactly one of `--user`/`--group`. Write new policy
JSON with explicit `Resource` ARNs and the minimum `Action` list the task
needs — do not default to `"Resource": ["arn:aws:s3:::*"]` or `"Action": ["s3:*"]`
unless the user explicitly asks for full access.

## `mc admin accesskey` — access keys for builtin users (incl. service accounts)

```bash
mc admin accesskey list ALIAS --self                # keys for the currently authenticated identity
mc admin accesskey list ALIAS --all                  # every builtin user's keys (admin only)
mc admin accesskey list ALIAS --all --users-only
mc admin accesskey list ALIAS --temp-only
mc admin accesskey list ALIAS USERNAME

mc admin accesskey info ALIAS ACCESSKEY
mc admin accesskey create ALIAS                                       # new key for the caller, same policy
mc admin accesskey create ALIAS USERNAME --policy /path/to/policy.json --expiry-duration 24h
mc admin accesskey create ALIAS --access-key CUSTOMKEY --secret-key CUSTOMSECRET
mc admin accesskey edit ALIAS ACCESSKEY --expiry-duration 24h
mc admin accesskey edit ALIAS ACCESSKEY --secret-key 'NEWSECRET'
mc admin accesskey enable ALIAS ACCESSKEY
mc admin accesskey disable ALIAS ACCESSKEY
mc admin accesskey remove ALIAS ACCESSKEY                              # irreversible — confirm first

mc admin accesskey sts-revoke ALIAS USERNAME --all                     # kill all active STS sessions for a user
mc admin accesskey sts-revoke ALIAS --self --token-type app-1

mc admin accesskey diagnose ALIAS ACCESSKEY                            # walk the auth chain when a service account gets 403s
```
`accesskey create`/`edit` return a plaintext secret in their output — hand it
to the user directly and do not persist it into a file, log, or chat history
you control.

## `mc admin cluster iam` — bulk IAM export/import

```bash
mc admin cluster iam export ALIAS                                # zip to a default path
mc admin cluster iam export ALIAS --output /tmp/alias-iam.zip
mc admin cluster iam import ALIAS /tmp/alias-iam.zip              # REPLACES cluster IAM state — confirm before running
```

## `mc idp openid` / `mc idp ldap` — external identity providers

```bash
mc idp openid list ALIAS
mc idp openid info ALIAS [CFG_NAME]
mc idp openid add ALIAS \
  client_id=CLIENT_ID client_secret=CLIENT_SECRET \
  config_url="https://idp.example.com/.well-known/openid-configuration" \
  scopes="openid,groups" redirect_uri="https://console.example.com/oauth_callback" \
  role_policy="consoleAdmin"
mc idp openid update ALIAS [CFG_NAME] KEY=VALUE...
mc idp openid enable ALIAS [CFG_NAME]
mc idp openid disable ALIAS [CFG_NAME]
mc idp openid remove ALIAS [CFG_NAME]
mc idp openid accesskey ...          # OpenID-derived access key management (mirrors mc admin accesskey)

mc idp ldap list ALIAS
mc idp ldap add ALIAS \
  server_addr=ldap.example.com:636 \
  lookup_bind_dn="cn=admin,dc=example,dc=com" lookup_bind_password=SECRET \
  user_dn_search_base_dn="dc=example,dc=com" user_dn_search_filter="(uid=%s)" \
  group_search_base_dn="ou=groups,dc=example,dc=com" \
  group_search_filter="(&(objectclass=groupofnames)(member=%d))"
mc idp ldap policy ...               # attach/detach policies to LDAP DNs (mirrors mc admin policy)
mc idp ldap accesskey ...            # LDAP-derived access key management
```
Both `add`/`update` take `key=value` pairs as free-form config params rather
than fixed flags — run `mc idp openid add --help` / `mc idp ldap add --help`
to see the current parameter names before constructing one, and never place
`lookup_bind_password`/`client_secret` as a bare argv token if it can be
avoided (prefer `mc idp ldap update` reading from a param, or confirm with the
user that CLI-arg exposure is acceptable for their environment).
