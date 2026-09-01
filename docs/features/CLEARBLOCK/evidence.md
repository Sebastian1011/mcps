---
feature: CLEARBLOCK
stage: evidence
status: accepted
branch: main
---

# Evidence: ClearBlock Chrome extension

## Verification results

### `npm run lint`

```text
$ cd chrome_extensions/clearblock && npm run lint

> clearblock@1.0.0 lint
> tsc --noEmit
```

### `npm test`

```text
$ cd chrome_extensions/clearblock && npm test

> clearblock@1.0.0 test
> vitest run


 RUN  v4.1.11 /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock


 Test Files  2 passed (2)
      Tests  10 passed (10)
   Start at  15:29:39
   Duration  549ms (transform 51ms, setup 0ms, import 68ms, tests 11ms, environment 831ms)
```

### `npm run build`

```text
$ cd chrome_extensions/clearblock && npm run build

> clearblock@1.0.0 build
> node scripts/build.mjs

Built ClearBlock 1.0.0 in /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/dist
```

### `npm run test:e2e`

The first sandboxed run could not open the local fixture server:

```text
$ cd chrome_extensions/clearblock && npm run test:e2e

> clearblock@1.0.0 test:e2e
> playwright test


Running 2 tests using 1 worker

[1/2] tests/e2e/extension.spec.ts:49:1 › blocks a matching EasyList request and honors a site allowlist
  1) tests/e2e/extension.spec.ts:49:1 › blocks a matching EasyList request and honors a site allowlist

    Error: listen EPERM: operation not permitted 127.0.0.1

    Error: Server is not running.

[2/2] tests/e2e/extension.spec.ts:102:1 › loads the popup and options pages from the installed extension
  1 failed
    tests/e2e/extension.spec.ts:49:1 › blocks a matching EasyList request and honors a site allowlist
  1 did not run
```

The same command passed outside the network-listener sandbox:

```text
$ cd chrome_extensions/clearblock && npm run test:e2e

> clearblock@1.0.0 test:e2e
> playwright test


Running 2 tests using 1 worker

(node:3242041) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)


[1/2] tests/e2e/extension.spec.ts:49:1 › blocks a matching EasyList request and honors a site allowlist
[2/2] tests/e2e/extension.spec.ts:102:1 › loads the popup and options pages from the installed extension
  2 passed (3.2s)
```

### `npm audit --omit=dev`

The first sandboxed request could not resolve the npm registry:

```text
$ cd chrome_extensions/clearblock && npm audit --omit=dev
npm warn audit request to https://registry.npmjs.org/-/npm/v1/security/advisories/bulk failed, reason: getaddrinfo EAI_AGAIN registry.npmjs.org
undefined
npm error audit endpoint returned an error
npm error Log files were not written due to an error writing to the directory: /home/debian/.npm/_logs
npm error You can rerun the command with `--loglevel=verbose` to see the logs in your terminal
```

The same read-only audit passed with network access:

```text
$ cd chrome_extensions/clearblock && npm audit --omit=dev
found 0 vulnerabilities
```

### `npm run package`

```text
$ cd chrome_extensions/clearblock && npm run package

> clearblock@1.0.0 package
> node scripts/package.mjs

Packaged /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/artifacts/clearblock-1.0.0.zip
```

### `unzip -t artifacts/clearblock-1.0.0.zip`

```text
$ cd chrome_extensions/clearblock && unzip -t artifacts/clearblock-1.0.0.zip
Archive:  artifacts/clearblock-1.0.0.zip
    testing: COPYING                  OK
    testing: _locales/                OK
    testing: _locales/en/             OK
    testing: _locales/en/messages.json   OK
    testing: _locales/zh_CN/          OK
    testing: _locales/zh_CN/messages.json   OK
    testing: _metadata/               OK
    testing: _metadata/generated_indexed_rulesets/   OK
    testing: _metadata/generated_indexed_rulesets/_ruleset1   OK
    testing: _metadata/generated_indexed_rulesets/_ruleset2   OK
    testing: _metadata/generated_indexed_rulesets/_ruleset3   OK
    testing: background.js            OK
    testing: icons/                   OK
    testing: icons/icon-128.png       OK
    testing: icons/icon-16.png        OK
    testing: icons/icon-32.png        OK
    testing: icons/icon-48.png        OK
    testing: manifest.json            OK
    testing: options.css              OK
    testing: options.html             OK
    testing: options.js               OK
    testing: picker.js                OK
    testing: popup.css                OK
    testing: popup.html               OK
    testing: popup.js                 OK
    testing: rulesets/                OK
    testing: rulesets/1D7F590C-B752-4BA0-9473-6A26DE1326B1   OK
    testing: rulesets/1D7F590C-B752-4BA0-9473-6A26DE1326B1.map   OK
    testing: rulesets/8C13E995-8F06-4927-BEA7-6C845FB7EEBF   OK
    testing: rulesets/8C13E995-8F06-4927-BEA7-6C845FB7EEBF.map   OK
    testing: rulesets/D72B6F06-52B2-4FED-96A2-1BF59CDD7AEC   OK
    testing: rulesets/D72B6F06-52B2-4FED-96A2-1BF59CDD7AEC.map   OK
    testing: subscriptions/           OK
    testing: subscriptions/1D7F590C-B752-4BA0-9473-6A26DE1326B1   OK
    testing: subscriptions/8C13E995-8F06-4927-BEA7-6C845FB7EEBF   OK
    testing: subscriptions/D72B6F06-52B2-4FED-96A2-1BF59CDD7AEC   OK
    testing: vendor/                  OK
    testing: vendor/ewe-api.js        OK
    testing: vendor/ewe-content-main.js   OK
    testing: vendor/ewe-content.js    OK
No errors detected in compressed data of artifacts/clearblock-1.0.0.zip.
```

## Defect fix, before and after

None. This is a new feature.

## Departures from plan.md

The artifact chain was introduced by repository instructions after implementation was already complete. These files therefore document the accepted intent, implemented design, and actual plan during finalization rather than representing four historical stage commits. No functional departure from the recorded plan is known.

## Known gaps

- Stage-by-stage artifact commits cannot be reconstructed honestly after implementation, and no commit was requested in this task.
- YouTube and other dynamically delivered video advertising remain best effort under standard filter lists.
