---
feature: CLEARBLOCK-SYNC
stage: evidence
status: accepted
branch: main
---

# Evidence: ClearBlock user-rule synchronization

## Verification results

### Test-first failure before `src/shared/sync.ts` existed

```text
$ cd chrome_extensions/clearblock && npm test -- tests/unit/sync.test.ts

> clearblock@1.0.0 test
> vitest run tests/unit/sync.test.ts


 RUN  v4.1.11 /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock

 ❯ tests/unit/sync.test.ts (0 test)

 FAIL  tests/unit/sync.test.ts [ tests/unit/sync.test.ts ]
Error: Failed to resolve import "../../src/shared/sync" from "tests/unit/sync.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/tests/unit/sync.test.ts:7:7
  1  |  import { describe, expect, it } from "vitest";
  2  |  import { decodeSyncSnapshot, encodeSyncSnapshot, mergeSyncedRules } from "../../src/shared/sync";
     |                                                                            ^

 Test Files  1 failed (1)
      Tests  no tests
   Start at  16:05:47
   Duration  356ms (transform 0ms, setup 0ms, import 0ms, tests 0ms, environment 234ms)
```

### Test-data correction

The first implemented run showed that the Unicode fixture was smaller than the intended chunk boundary. The fixture was changed to three valid-sized element rules; the production chunk size was not changed.

```text
$ cd chrome_extensions/clearblock && npm test -- tests/unit/sync.test.ts

> clearblock@1.0.0 test
> vitest run tests/unit/sync.test.ts


 RUN  v4.1.11 /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock

 ❯ tests/unit/sync.test.ts (3 tests | 1 failed) 5ms
     × round trips Unicode data using quota-safe chunks 3ms

 FAIL  tests/unit/sync.test.ts > sync snapshot encoding > round trips Unicode data using quota-safe chunks
AssertionError: expected 1 to be greater than 1
 ❯ tests/unit/sync.test.ts:34:35
     34|     expect(encoded.chunks.length).toBeGreaterThan(1);

 Test Files  1 failed (1)
      Tests  1 failed | 2 passed (3)
   Start at  16:06:22
   Duration  338ms (transform 18ms, setup 0ms, import 26ms, tests 5ms, environment 227ms)
```

### Focused synchronization unit tests after implementation

```text
$ cd chrome_extensions/clearblock && npm test -- tests/unit/sync.test.ts

> clearblock@1.0.0 test
> vitest run tests/unit/sync.test.ts


 RUN  v4.1.11 /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock


 Test Files  1 passed (1)
      Tests  3 passed (3)
   Start at  16:06:47
   Duration  363ms (transform 25ms, setup 0ms, import 34ms, tests 6ms, environment 249ms)
```

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


 Test Files  3 passed (3)
      Tests  13 passed (13)
   Start at  16:11:05
   Duration  463ms (transform 77ms, setup 0ms, import 316ms, tests 16ms, environment 772ms)
```

### `npm run build`

```text
$ cd chrome_extensions/clearblock && npm run build

> clearblock@1.0.0 build
> node scripts/build.mjs

Built ClearBlock 1.0.0 in /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/dist
```

### `npm run test:e2e`

```text
$ cd chrome_extensions/clearblock && npm run test:e2e

> clearblock@1.0.0 test:e2e
> playwright test


Running 3 tests using 1 worker

(node:3259838) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)
[1/3] tests/e2e/extension.spec.ts:49:1 › blocks a matching EasyList request and honors a site allowlist
[2/3] tests/e2e/extension.spec.ts:102:1 › publishes and applies synchronized user rules
[3/3] tests/e2e/extension.spec.ts:165:1 › loads the popup and options pages from the installed extension
  3 passed (3.9s)
```

### `npm audit --omit=dev`

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

None.

## Known gaps

- Chrome Sync resolves simultaneous offline edits using its eventual storage state; ClearBlock does not provide a conflict-resolution UI.
- Stage artifacts are not committed separately because the working tree already contains the preceding uncommitted ClearBlock feature and the user did not request commits.
