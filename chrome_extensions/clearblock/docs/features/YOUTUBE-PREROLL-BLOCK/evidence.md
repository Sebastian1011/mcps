---
feature: YOUTUBE-PREROLL-BLOCK
stage: evidence
status: accepted
branch: main
---


# Evidence: YouTube preroll filtering

## Verification results

### subs-convert and subs-generate (new list only)

```text
$ subs-convert and subs-generate (new list only)
Converting rules-work/youtube/subscriptions/D4028CDD-3D39-4624-ACC7-8140F4EC3238 to rules/rulesets/D4028CDD-3D39-4624-ACC7-8140F4EC3238 ...
Not ruleset file (1D7F590C-B752-4BA0-9473-6A26DE1326B1.map) skipped
Not ruleset file (8C13E995-8F06-4927-BEA7-6C845FB7EEBF.map) skipped
Not ruleset file (D4028CDD-3D39-4624-ACC7-8140F4EC3238.map) skipped
Not ruleset file (D72B6F06-52B2-4FED-96A2-1BF59CDD7AEC.map) skipped
Web extension manifest fragment file (rules/rulesets.json) generated.
```

### npm run build

```text
$ npm run build

> clearblock@1.0.0 build
> node scripts/build.mjs

Built ClearBlock 1.0.0 in /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/dist
```

### npm run lint

```text
$ npm run lint

> clearblock@1.0.0 lint
> tsc --noEmit

```

### npm test

```text
$ npm test

> clearblock@1.0.0 test
> vitest run


 RUN  v4.1.11 /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock


 Test Files  4 passed (4)
      Tests  14 passed (14)
   Start at  18:33:14
   Duration  380ms (transform 56ms, setup 0ms, import 102ms, tests 21ms, environment 1.03s)

```

### npm run test:e2e

```text
$ npm run test:e2e

> clearblock@1.0.0 test:e2e
> playwright test


Running 4 tests using 1 worker

(node:3180141) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)


[1/4] tests/e2e/extension.spec.ts:49:1 › blocks a matching EasyList request and honors a site allowlist
[2/4] tests/e2e/extension.spec.ts:102:1 › publishes and applies synchronized user rules
[3/4] tests/e2e/extension.spec.ts:165:1 › loads the popup and options pages from the installed extension
[4/4] tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button
  4 passed (6.6s)
```

### npm run package

```text
$ npm run package

> clearblock@1.0.0 package
> node scripts/package.mjs

Packaged /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/artifacts/clearblock-1.0.0.zip
```

### ZIP validation

```text
$ ZIP validation
Verified ZIP: four rulesets; official anti-circumvention list matches source; no custom youtube.js.
```

### git diff --check

```text
$ git diff --check
```



## Defect fix, before and after

### Initial player selection test: before fix

```text
$ Initial player selection test: before fix

> clearblock@1.0.0 test:e2e
> playwright test --grep YouTube


Running 1 test using 1 worker

(node:3175745) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)


[1/1] tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button
  1) tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button 

    Error: expect(received).toBe(expected) // Object.is equality

    Expected: "/fixture-content"
    Received: "/fixture-commercial"

      239 |   const play = async (expected: string) => {
      240 |     await page.locator("#play").click();
    > 241 |     expect(await page.evaluate(() => (window as typeof window & {selectedMedia: string}).selectedMedia)).toBe(expected);
          |                                                                                                          ^
      242 |     await expect.poll(() => requests.at(-1)).toBe(expected);
      243 |   };
      244 |   await page.goto(url);
        at play (/home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/tests/e2e/extension.spec.ts:241:106)
        at /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/tests/e2e/extension.spec.ts:245:3

    Error Context: test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/error-context.md

    Error Context: test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/trace.zip
    Usage:

        npx playwright show-trace test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────


  1 failed
    tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button 
```

### After adding subscription alone: still failing

```text
$ After adding subscription alone: still failing

> clearblock@1.0.0 test:e2e
> playwright test --grep YouTube


Running 1 test using 1 worker

(node:3176466) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)


[1/1] tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button
  1) tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button 

    Error: expect(received).toBe(expected) // Object.is equality

    Expected: "/fixture-content"
    Received: "/fixture-commercial"

      239 |   const play = async (expected: string) => {
      240 |     await page.locator("#play").click();
    > 241 |     expect(await page.evaluate(() => (window as typeof window & {selectedMedia: string}).selectedMedia)).toBe(expected);
          |                                                                                                          ^
      242 |     await expect.poll(() => requests.at(-1)).toBe(expected);
      243 |   };
      244 |   await page.goto(url);
        at play (/home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/tests/e2e/extension.spec.ts:241:106)
        at /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/tests/e2e/extension.spec.ts:245:3

    Error Context: test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/error-context.md

    Error Context: test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/trace.zip
    Usage:

        npx playwright show-trace test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────


  1 failed
    tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button 
```

### Local message diagnostic before routing fix

```text
$ Local message diagnostic before routing fix
state {"ok":true,"data":{"allowlist":[],"elementRules":[],"userSync":{"enabled":false,"error":null},"subscriptions":[{"id":"8C13E995-8F06-4927-BEA7-6C845FB7EEBF","title":"EasyList","url":"https://easylist-downloads.adblockplus.org/v3/full/easylist.txt","downloading":false,"downloadStatus":"synchronize_ok","lastSuccess":1788863405},{"id":"D72B6F06-52B2-4FED-96A2-1BF59CDD7AEC","title":"EasyPrivacy","url":"https://easylist-downloads.adblockplus.org/v3/full/easyprivacy.txt","downloading":false,"downloadStatus":"synchronize_ok","lastSuccess":1788863405},{"id":"1D7F590C-B752-4BA0-9473-6A26DE1326B1","title":"EasyList China (compliance)","url":"https://easylist-downloads.adblockplus.org/v3/full/easylistchina.txt","downloading":false,"downloadStatus":"synchronize_ok","lastSuccess":1788863405},{"id":"D4028CDD-3D39-4624-ACC7-8140F4EC3238","title":"ABP filters (compliance)","url":"https://easylist-downloads.adblockplus.org/v3/full/abp-filters-anti-cv.txt","downloading":false,"downloadStatus":"synchronize_ok","lastSuccess":1788863405}]}}
pageerror Cannot read properties of undefined (reading 'length')
data {
  data: { adSlots: [ 1 ], adPlacements: [ 1 ], playerAds: [ 1 ] },
  descriptor: false
}
context ClearBlock
config {"result":{"type":"object","value":{"ok":true}}}
```

### After routing fix: early initialization still races

```text
$ After routing fix: early initialization still races

> clearblock@1.0.0 test:e2e
> playwright test --grep YouTube


Running 1 test using 1 worker

(node:3177809) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)


[1/1] tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button
  1) tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button 

    Error: expect(received).toBe(expected) // Object.is equality

    Expected: "/fixture-content"
    Received: "/fixture-commercial"

      239 |   const play = async (expected: string) => {
      240 |     await page.locator("#play").click();
    > 241 |     expect(await page.evaluate(() => (window as typeof window & {selectedMedia: string}).selectedMedia)).toBe(expected);
          |                                                                                                          ^
      242 |     await expect.poll(() => requests.at(-1)).toBe(expected);
      243 |   };
      244 |   await page.goto(url);
        at play (/home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/tests/e2e/extension.spec.ts:241:106)
        at /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/tests/e2e/extension.spec.ts:245:3

    Error Context: test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/error-context.md

    Error Context: test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/trace.zip
    Usage:

        npx playwright show-trace test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────


  1 failed
    tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button 
```

### After cache setting: test still starts before cache initialization

```text
$ After cache setting: test still starts before cache initialization

> clearblock@1.0.0 test:e2e
> playwright test --grep YouTube


Running 1 test using 1 worker

(node:3178930) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)


[1/1] tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button
  1) tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button 

    Error: expect(received).toBe(expected) // Object.is equality

    Expected: "/fixture-content"
    Received: "/fixture-commercial"

      239 |   const play = async (expected: string) => {
      240 |     await page.locator("#play").click();
    > 241 |     expect(await page.evaluate(() => (window as typeof window & {selectedMedia: string}).selectedMedia)).toBe(expected);
          |                                                                                                          ^
      242 |     await expect.poll(() => requests.at(-1)).toBe(expected);
      243 |   };
      244 |   await page.goto(url);
        at play (/home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/tests/e2e/extension.spec.ts:241:106)
        at /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/tests/e2e/extension.spec.ts:245:3

    Error Context: test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/error-context.md

    Error Context: test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/trace.zip
    Usage:

        npx playwright show-trace test-results/extension-YouTube-filters--87d08-yback-without-a-Skip-button/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────


  1 failed
    tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button 
```

### After explicitly observing cache initialization in the test

```text
$ After explicitly observing cache initialization in the test

> clearblock@1.0.0 test:e2e
> playwright test --grep YouTube


Running 1 test using 1 worker

(node:3179465) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)


[1/1] tests/e2e/extension.spec.ts:200:1 › YouTube filters preroll data before playback without a Skip button
  1 passed (5.1s)
```



## Departures from plan.md

The initial plan expected a missing subscription only. Diagnostics also proved that ClearBlock answered engine-owned ewe: messages with {ok:true}, causing content initialization to fail. The message guard and early snippet cache were added to plan/spec. The regression was strengthened to inspect the first inline script after cache initialization and to request media through immediate cached autoplay. It deliberately waits for cache-driven reloads when initializing or changing allowlists; the original cold-start race is recorded above, not claimed fixed. Original three list baselines were retained instead of refreshing unrelated lists.


## Known gaps

Live YouTube advertising behavior is not yet verified. A YouTube homepage tab was available, but no failing-video link was supplied. Reloading the installed extension through the browser tool was unavailable:

```text
Error: Navigating to chrome: URLs is not allowed.
```

The user must reload ClearBlock and the YouTube tab to activate this build. Initial cold cache setup is asynchronous and may allow early player initialization to race; cache initialization/updates can reload pages. Upstream rules contain fallbacks; the successful fixture has no Skip button or media element and does not exercise those fallbacks. Artifacts are in the working tree of the shared parent repository, without commits.

