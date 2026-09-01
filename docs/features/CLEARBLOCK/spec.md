---
feature: CLEARBLOCK
stage: spec
status: accepted
branch: main
---

# Spec: ClearBlock Chrome extension

## Requirements

1. ClearBlock is an independent project at `chrome_extensions/clearblock` and produces a loadable Manifest V3 extension.
2. EasyList, EasyPrivacy, and EasyList China provide the initial blocking rules and can receive runtime differential updates.
3. The popup displays the current website and page, independent enable switches, local page and total blocked counts, a block-element action, and a settings action.
4. A website allowlist applies to the host and its subdomains. An exact-page allowlist preserves the query string and ignores the fragment.
5. The element picker previews and saves cosmetic hiding rules. Settings can list and remove those rules.
6. A standalone settings page can add, search, remove, and clear allowlist entries; manage element rules; display filter-list state; and request an update.
7. The extension automatically uses Chinese or English Chrome locale strings.
8. No paid feature, issue-report action, Acceptable Ads list, telemetry, account, or remote configuration is included.
9. A release command emits a Chrome Web Store ZIP.

## Design

- A classic Manifest V3 service worker starts eyeo's WebExtension Ad-Filtering Solution and owns subscription state, allowlist filters, messages, and local counters.
- The packaged baseline consists of generated declarative rules plus subscription data for the three selected lists. The engine handles compatible runtime updates.
- Popup and options pages are vanilla TypeScript, HTML, and CSS bundles. They communicate with the service worker through typed runtime messages.
- Allowlist entries are represented as user exception filters. Separate local metadata makes them manageable and preserves whether an entry is a site or exact page.
- The picker runs as an injected content script, creates an isolated overlay, derives a stable CSS selector, previews it, and stores the resulting cosmetic rule after confirmation.
- Counts are derived locally from extension blocking events and stored in local/session extension storage.

## Affected modules

- `chrome_extensions/clearblock/src/background.ts` — engine lifecycle, filtering state, allowlists, updates, messages, and counts.
- `chrome_extensions/clearblock/src/popup/` — toolbar popup.
- `chrome_extensions/clearblock/src/options/` — standalone settings page.
- `chrome_extensions/clearblock/src/picker.ts` — page element selection.
- `chrome_extensions/clearblock/src/shared/` — message and filter helpers.
- `chrome_extensions/clearblock/scripts/` and `rules/` — builds, packaging, and bundled rule data.
- `chrome_extensions/clearblock/tests/` — unit and browser-level verification.

No matching documents exist under `docs/architecture/`.

## Trade-offs and concerns

- Using the official eyeo engine gives mature ABP-compatible filtering and differential updates, at the cost of GPL-3.0-only distribution and a larger packaged extension.
- Filter-list blocking is simpler and more maintainable than custom per-site scripts, but fast-changing sites such as YouTube remain best effort.
- Exact-page exceptions are deliberately narrow; redirects or meaningful URL changes require another entry.
- Local counters avoid telemetry but are device/profile-specific and are not an authoritative global measure.

## Related ADRs

None. The design is contained within the new extension and does not change an existing repository-wide architecture.

## Acceptance criteria

- Type checking and unit tests pass.
- An isolated Chrome instance loads the built extension and exposes its service worker, popup, and options page.
- Browser tests prove an EasyList-matching request is blocked, a site exception permits it, and a page exception permits only the exact URL.
- The release ZIP passes an archive integrity check.
- Production dependency audit reports no known vulnerabilities.
