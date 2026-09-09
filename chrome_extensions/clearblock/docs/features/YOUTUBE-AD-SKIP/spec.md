---
feature: YOUTUBE-AD-SKIP
stage: spec
status: superseded
branch: main
---


# Spec: YouTube automatic ad skipping

## Requirements

Click only a visible, enabled YouTube Skip control while the player explicitly reports an advertisement. Do not seek, mute, change speed, or interact with normal video controls. Recheck allowlisting and URL before clicking.


## Design

A YouTube-only isolated content script checks for a skippable ad every 500 ms. Before clicking it asks the existing background runtime message handler whether the current URL is blocked. Revalidate the URL, ad state and button after the asynchronous reply. Failed requests do not click.


## Affected modules

src/youtube.ts, src/background.ts, src/shared/types.ts, scripts/build.mjs, tests/e2e/extension.spec.ts, README.md. No existing architecture documents in this extension.


## Trade-offs and concerns

A bounded automatic Skip fallback directly addresses manual interaction without patching player responses. It waits for YouTube to permit skipping; it does not block every preroll. Polling also handles SPA navigation and CSS visibility changes without observing the entire page.


## Related ADRs

None. Uses the existing content-script and runtime-message architecture.


## Acceptance criteria

Installed-extension fixture reproduces the missing skip before implementation and passes afterwards. Hidden/disabled controls and ordinary videos are untouched. Site and exact-page exceptions work, including SPA transitions. Typecheck, unit tests and existing extension tests pass.


Superseded: user clarified that advertisements must be filtered before playback, not automatically skipped. The automatic-click implementation and tests were removed. See ../YOUTUBE-PREROLL-BLOCK/.
