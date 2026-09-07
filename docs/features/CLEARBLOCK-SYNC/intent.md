---
feature: CLEARBLOCK-SYNC
stage: intent
status: accepted
branch: main
---

# Intent: Synchronize ClearBlock user configuration

## Problem

ClearBlock currently keeps its allowlists and manually blocked element rules only in one Chrome profile. A user who uses multiple Chrome installations must recreate those choices manually and cannot recover them through Chrome account synchronization.

## Proposed outcome

Users can opt in to synchronizing website exceptions, exact-page exceptions, and manually blocked element rules through their signed-in Chrome profile. Local-only operational data remains on each device.

## Affected users and systems

- ClearBlock users with one or more Chrome profiles.
- ClearBlock's background storage flow and standalone settings page.

## Constraints

- Synchronization is opt-in and can be disabled without deleting the current device's rules.
- Blocking counts, filter subscriptions, update state, and per-tab state must not synchronize.
- Existing local rules must not be discarded when synchronization is first enabled.
- Remote changes must be applied without requiring the settings page to remain open.
- The implementation must stay within Chrome Sync storage quotas and expose synchronization failures.

## Out of scope

- Direct Google Drive API or OAuth integration.
- Synchronizing browsing history or blocked-request logs.
- Cross-browser synchronization.

## Open questions

None. The preceding conversation selected Chrome account synchronization over direct Google Drive storage.
