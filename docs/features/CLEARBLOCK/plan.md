---
feature: CLEARBLOCK
stage: plan
status: accepted
branch: main
---

# Plan: ClearBlock Chrome extension

## Files that change

- `chrome_extensions/clearblock/package.json` and lock/config files (new) — project tooling, pinned dependencies, and test configuration.
- `chrome_extensions/clearblock/scripts/` (new) — build, rule refresh, and release packaging.
- `chrome_extensions/clearblock/rules/` (new) — bundled EasyList, EasyPrivacy, and EasyList China data and generated rulesets.
- `chrome_extensions/clearblock/src/background.ts` and `src/shared/` (new) — filtering engine integration, state, filters, messages, updates, and counters.
- `chrome_extensions/clearblock/src/popup/` (new) — reference-inspired toolbar popup.
- `chrome_extensions/clearblock/src/options/` (new) — allowlist, cosmetic-rule, and subscription settings.
- `chrome_extensions/clearblock/src/picker.ts` (new) — injected element picker.
- `chrome_extensions/clearblock/_locales/` and `src/icons/` (new) — Chinese/English strings and original branding.
- `chrome_extensions/clearblock/tests/` (new) — unit and extension browser tests.
- `chrome_extensions/clearblock/README.md`, `PRIVACY.md`, `THIRD_PARTY_NOTICES.md`, and `COPYING` (new) — use, privacy, and licensing documentation.
- `docs/features/CLEARBLOCK/` (new) — intent, specification, plan, and raw verification evidence.

## Order of work

1. Scaffold the independent extension project and build pipeline; confirm a valid Manifest V3 build is emitted.
2. Generate the three baseline filter subscriptions and integrate the filtering engine; unit-test exception-filter construction and manifest constraints.
3. Implement popup state, local counters, website/page toggles, and settings navigation; confirm message contracts type-check.
4. Implement element picking and the standalone settings page; confirm allowlist and cosmetic-rule management through unit and browser tests.
5. Add localization, privacy/licensing documents, release packaging, and an original visual treatment.
6. Run type checking, unit tests, the isolated Chrome extension suite, dependency audit, package generation, and ZIP integrity checks.

## Risks

- Browser API behavior differs from DOM-only tests, so a real persistent Chrome context is required.
- Upstream filter format or engine updates can affect generated rules and runtime update behavior.
- Host-level exceptions must remove applicable parent-domain filters when re-enabling a subdomain.
- The generated rule data makes the package materially larger than a hand-written blocker.
- Dynamic video advertising can evade static filter lists.

## Verification

- `cd chrome_extensions/clearblock && npm run lint`
- `cd chrome_extensions/clearblock && npm test`
- `cd chrome_extensions/clearblock && npm run build`
- `cd chrome_extensions/clearblock && npm run test:e2e`
- `cd chrome_extensions/clearblock && npm audit --omit=dev`
- `cd chrome_extensions/clearblock && npm run package`
- `cd chrome_extensions/clearblock && unzip -t artifacts/clearblock-1.0.0.zip`
