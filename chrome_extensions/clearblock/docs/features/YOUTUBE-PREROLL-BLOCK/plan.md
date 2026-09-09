---
feature: YOUTUBE-PREROLL-BLOCK
stage: plan
status: accepted
branch: main
---


# Plan: YouTube preroll filtering

## Files that change

src/background.ts (decline engine-owned runtime messages and enable early snippet caching); scripts/update-rules.mjs; rules/recommendations.json, rules/rulesets.json, rules/metadata.json and the new subscription/ruleset/map; tests/unit/manifest.test.ts; tests/e2e/extension.spec.ts; README.md; PRIVACY.md; THIRD_PARTY_NOTICES.md; feature artifacts.


## Order of work

1. Remove the previous custom Skip implementation and supersede its artifacts.
2. Add a failing player-data regression.
3. Fetch official anti-circumvention data, convert only the new list, retain the other three baselines, and add its ID to future updates.
4. Fix the engine-message response collision discovered by the failing regression.
5. Validate engine startup, filtering and allowlists; build and package; record evidence.


## Risks

Snippet injection timing, unsupported snippet variants and upstream changes. An isolated fixture cannot prove all live YouTube ads are blocked. Cold cache initialization remains asynchronous; cache fill/update can reload pages, and a player can race the first configuration response. Tests separately verify post-initialization early inline-script filtering and cached autoplay.


## Verification

```sh
npm run build
npm run test:e2e -- --grep "YouTube"
npm run lint
npm test
npm run test:e2e
npm run package
git diff --check
```

