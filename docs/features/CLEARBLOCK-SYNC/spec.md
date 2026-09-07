---
feature: CLEARBLOCK-SYNC
stage: spec
status: accepted
branch: main
---

# Spec: ClearBlock user-rule synchronization

## Requirements

1. The settings page provides an opt-in switch for Chrome account synchronization.
2. Only ClearBlock-managed website allowlist entries, exact-page allowlist entries, and element hiding rules synchronize.
3. Enabling synchronization merges existing local and cloud rules by filter text before publishing the result.
4. While enabled, local additions and removals publish a complete user-rule snapshot, and cloud snapshot changes replace the local managed-rule set.
5. Disabling synchronization stops cloud application and publication but preserves both local and previously uploaded cloud rules.
6. Synchronized data is versioned, validated before application, and split across bounded storage items so an individual item stays below Chrome's per-item quota.
7. Settings exposes the current enabled state and any most recent synchronization error.
8. Privacy documentation states what Chrome Sync receives and that Google processes it under the user's Chrome account settings.

## Design

- A new shared synchronization module serializes a versioned snapshot of ClearBlock metadata and filter text into UTF-8, then stores bounded base64 chunks plus a manifest in `chrome.storage.sync`.
- The opt-in flag stays in `chrome.storage.local`, allowing each Chrome installation to decide whether it participates.
- Background initialization reads the local flag. If enabled, an existing cloud snapshot is authoritative; if none exists, local managed rules seed it.
- The explicit disabled-to-enabled transition merges local and cloud snapshots to avoid first-use data loss.
- `chrome.storage.onChanged` debounces sync-area events, reads a complete manifest and chunk set, validates every rule, and reconciles only ClearBlock-managed filters in the eyeo engine.
- User-rule mutations trigger publication only when synchronization is enabled. Failures do not undo the local blocking choice and are surfaced through options state.

## Affected modules

- `chrome_extensions/clearblock/src/shared/sync.ts` — snapshot validation and chunk encoding/decoding.
- `chrome_extensions/clearblock/src/shared/types.ts` — synchronization state and runtime message types.
- `chrome_extensions/clearblock/src/background.ts` — opt-in lifecycle, reconciliation, publication, and change listener.
- `chrome_extensions/clearblock/src/options/` — synchronization control and status.
- `chrome_extensions/clearblock/_locales/` — English and Chinese synchronization strings.
- `chrome_extensions/clearblock/tests/` — serialization and browser behavior coverage.
- `chrome_extensions/clearblock/README.md` and `PRIVACY.md` — user-facing behavior and disclosure.

No matching documents exist under `docs/architecture/`.

## Trade-offs and concerns

- Chrome Sync is used instead of Google Drive `appDataFolder`; it avoids OAuth and Drive permissions but inherits Chrome Sync quotas and availability.
- Whole-snapshot last-writer behavior is simpler and gives deletions deterministic propagation. Simultaneous edits on disconnected devices can still resolve to the last cloud snapshot.
- Chunking adds a small storage protocol but avoids the much smaller per-item limit that a single JSON value would encounter.
- Disabling sync does not delete cloud data, preventing accidental loss but requiring Chrome profile data controls to remove the remote copy.

## Related ADRs

None. This storage protocol is private to ClearBlock and does not establish a repository-wide architecture.

## Acceptance criteria

- Unit tests prove Unicode-safe snapshot round trips, chunk size bounds, malformed-data rejection, and rule merging.
- Browser tests prove opt-in state, publication after a local rule change, and application of a simulated cloud snapshot.
- Existing blocking and allowlist browser tests remain green.
- Type checking, build, package generation, and ZIP integrity checks pass.
