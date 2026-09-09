---
feature: YOUTUBE-AD-SKIP
stage: evidence
status: superseded
branch: main
---


# Evidence: YouTube automatic ad skipping

## Verification results

### npm run build

```text
$ npm run build

> clearblock@1.0.0 build
> node scripts/build.mjs

Built ClearBlock 1.0.0 in /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/dist
```

### npm run lint (initial typing error)

```text
$ npm run lint (initial typing error)

> clearblock@1.0.0 lint
> tsc --noEmit

tests/e2e/extension.spec.ts(227,17): error TS2339: Property 'currentTime' does not exist on type 'HTMLElement | SVGElement'.
  Property 'currentTime' does not exist on type 'HTMLElement'.
tests/e2e/extension.spec.ts(227,42): error TS2339: Property 'playbackRate' does not exist on type 'HTMLElement | SVGElement'.
  Property 'playbackRate' does not exist on type 'HTMLElement'.
tests/e2e/extension.spec.ts(227,69): error TS2339: Property 'muted' does not exist on type 'HTMLElement | SVGElement'.
  Property 'muted' does not exist on type 'HTMLElement'.
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
   Start at  18:21:03
   Duration  481ms (transform 86ms, setup 0ms, import 124ms, tests 19ms, environment 1.40s)

```

### npm run test:e2e

```text
$ npm run test:e2e

> clearblock@1.0.0 test:e2e
> playwright test


Running 5 tests using 1 worker

(node:3172655) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)


[1/5] tests/e2e/extension.spec.ts:49:1 › blocks a matching EasyList request and honors a site allowlist
[2/5] tests/e2e/extension.spec.ts:102:1 › publishes and applies synchronized user rules
[3/5] tests/e2e/extension.spec.ts:165:1 › loads the popup and options pages from the installed extension
[4/5] tests/e2e/extension.spec.ts:219:1 › YouTube automatically skips available ads without changing normal playback
[5/5] tests/e2e/extension.spec.ts:260:1 › YouTube automatic skip respects site and exact-page allowlists across navigation
  5 passed (16.2s)
```

### npm run package

```text
$ npm run package

> clearblock@1.0.0 package
> node scripts/package.mjs

Packaged /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/artifacts/clearblock-1.0.0.zip
```

### git diff --check

```text
$ git diff --check
```



## Defect fix, before and after

### npm run test:e2e -- --grep "YouTube automatically" (sandbox prevented fixture binding)

```text
$ npm run test:e2e -- --grep "YouTube automatically" (sandbox prevented fixture binding)

> clearblock@1.0.0 test:e2e
> playwright test --grep YouTube automatically


Running 1 test using 1 worker

[1/1] tests/e2e/extension.spec.ts:219:1 › YouTube automatically skips available ads without changing normal playback
  1) tests/e2e/extension.spec.ts:219:1 › YouTube automatically skips available ads without changing normal playback 

    Error: listen EPERM: operation not permitted 127.0.0.1

    Error: Server is not running.

    Error Context: test-results/extension-YouTube-automati-6e5b0-ut-changing-normal-playback/error-context.md

    Error Context: test-results/extension-YouTube-automati-6e5b0-ut-changing-normal-playback/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/extension-YouTube-automati-6e5b0-ut-changing-normal-playback/trace.zip
    Usage:

        npx playwright show-trace test-results/extension-YouTube-automati-6e5b0-ut-changing-normal-playback/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────


  1 failed
    tests/e2e/extension.spec.ts:219:1 › YouTube automatically skips available ads without changing normal playback 
```
### npm run test:e2e -- --grep "YouTube automatically" (outside sandbox, before implementation)

```text
$ npm run test:e2e -- --grep "YouTube automatically" (outside sandbox, before implementation)

> clearblock@1.0.0 test:e2e
> playwright test --grep YouTube automatically


Running 1 test using 1 worker

(node:3171181) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)


[1/1] tests/e2e/extension.spec.ts:219:1 › YouTube automatically skips available ads without changing normal playback
  1) tests/e2e/extension.spec.ts:219:1 › YouTube automatically skips available ads without changing normal playback 

    Error: expect(received).toBe(expected) // Object.is equality

    Expected: 1
    Received: 0

    Call Log:
    - Timeout 5000ms exceeded while waiting on the predicate

      221 |   const clicks = () => page.evaluate(() => (window as typeof window & {skipClicks: number}).skipClicks);
      222 |   await page.goto("https://www.youtube.com/watch?v=clearblock-skip");
    > 223 |   await expect.poll(clicks).toBe(1);
          |                             ^
      224 |   await page.waitForTimeout(1100);
      225 |   expect(await clicks()).toBe(1);
      226 |   expect(await page.locator("video").evaluate(video => ({
        at /home/debian/develop/sebastian/ai-tools/chrome_extensions/clearblock/tests/e2e/extension.spec.ts:223:29

    Error Context: test-results/extension-YouTube-automati-6e5b0-ut-changing-normal-playback/error-context.md

    Error Context: test-results/extension-YouTube-automati-6e5b0-ut-changing-normal-playback/error-context.md

    attachment #3: trace (application/zip) ─────────────────────────────────────────────────────────
    test-results/extension-YouTube-automati-6e5b0-ut-changing-normal-playback/trace.zip
    Usage:

        npx playwright show-trace test-results/extension-YouTube-automati-6e5b0-ut-changing-normal-playback/trace.zip

    ────────────────────────────────────────────────────────────────────────────────────────────────


  1 failed
    tests/e2e/extension.spec.ts:219:1 › YouTube automatically skips available ads without changing normal playback 
```
### npm run test:e2e -- --grep "YouTube" (after implementation)

```text
$ npm run test:e2e -- --grep "YouTube" (after implementation)

> clearblock@1.0.0 test:e2e
> playwright test --grep YouTube


Running 2 tests using 1 worker

(node:3172093) Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.
(Use `node --trace-warnings ...` to show where the warning was created)


[1/2] tests/e2e/extension.spec.ts:219:1 › YouTube automatically skips available ads without changing normal playback
[2/2] tests/e2e/extension.spec.ts:260:1 › YouTube automatic skip respects site and exact-page allowlists across navigation
  2 passed (15.7s)
```



## Departures from plan.md

Artifacts remain in the working tree on the existing main branch; no branch or commits requested for the shared parent repository.


## Known gaps

Connected Chrome had no YouTube tab. Live advertisement acceptance has not been performed. Browser fixtures verify behavior against modeled YouTube controls only.


Superseded: user clarified that advertisements must be filtered before playback, not automatically skipped. The automatic-click implementation and tests were removed. See ../YOUTUBE-PREROLL-BLOCK/.
