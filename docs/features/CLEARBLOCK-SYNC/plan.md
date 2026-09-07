---
feature: CLEARBLOCK-SYNC
stage: plan
status: accepted
branch: main
---

# Plan: ClearBlock user-rule synchronization

## Files that change

- `chrome_extensions/clearblock/src/shared/sync.ts` (new) — versioned payload validation, merge, and bounded encoding.
- `chrome_extensions/clearblock/src/shared/types.ts` (modified) — sync state and messages.
- `chrome_extensions/clearblock/src/background.ts` (modified) — sync lifecycle, storage listener, reconciliation, and publication.
- `chrome_extensions/clearblock/src/options/index.html`, `options.ts`, and `options.css` (modified) — opt-in setting and error display.
- `chrome_extensions/clearblock/_locales/*/messages.json` (modified) — localized sync labels and statuses.
- `chrome_extensions/clearblock/tests/unit/sync.test.ts` (new) — storage protocol tests.
- `chrome_extensions/clearblock/tests/e2e/extension.spec.ts` (modified) — installed-extension sync behavior.
- `chrome_extensions/clearblock/README.md` and `PRIVACY.md` (modified) — operation and privacy disclosure.
- `docs/features/CLEARBLOCK-SYNC/` (new) — traceable intent, design, plan, and evidence.

## Order of work

1. Add failing unit tests for snapshot encoding, validation, and merge behavior.
2. Implement the pure shared synchronization protocol until those tests pass.
3. Add typed background lifecycle and mutation hooks, then expose state and control messages.
4. Add the localized settings UI and privacy documentation.
5. Extend the real-extension test to enable sync, observe publication, inject a cloud snapshot, and observe local reconciliation.
6. Run all verification and package the updated extension.

## Risks

- Sync change events can echo a device's own publication; reconciliation must be idempotent.
- Manifest/chunk updates can be observed while stale chunks still exist; only manifest-referenced chunks may be decoded.
- Invalid or over-quota cloud state must not remove valid local rules.
- Initial enablement must merge, while later cloud deletions must remain authoritative rather than resurrecting local rules.

## Verification

- `cd chrome_extensions/clearblock && npm run lint`
- `cd chrome_extensions/clearblock && npm test`
- `cd chrome_extensions/clearblock && npm run build`
- `cd chrome_extensions/clearblock && npm run test:e2e`
- `cd chrome_extensions/clearblock && npm audit --omit=dev`
- `cd chrome_extensions/clearblock && npm run package`
- `cd chrome_extensions/clearblock && unzip -t artifacts/clearblock-1.0.0.zip`
