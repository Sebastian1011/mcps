---
feature: YOUTUBE-AD-SKIP
stage: plan
status: superseded
branch: main
---


# Plan: YouTube automatic ad skipping

## Files that change

- New: src/youtube.ts — automatic available Skip control.
- Modified: src/background.ts and src/shared/types.ts — page blocking query.
- Modified: scripts/build.mjs — bundle and register YouTube-only script.
- Modified: tests/e2e/extension.spec.ts — browser regression coverage.
- Modified: README.md — capability and limits.
- New: docs/features/YOUTUBE-AD-SKIP/*.md — artifacts.


## Order of work

1. Add an installed-extension YouTube DOM fixture and record the failing regression.
2. Implement the content script and allowlist query.
3. Run checks, build and package. Record raw output and live-verification limitations.


## Risks

YouTube may change player classes or reject synthetic clicks. Fixture tests cannot establish success for live account/region-specific ads. The feature deliberately leaves unskippable ads alone.


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


Superseded: user clarified that advertisements must be filtered before playback, not automatically skipped. The automatic-click implementation and tests were removed. See ../YOUTUBE-PREROLL-BLOCK/.
