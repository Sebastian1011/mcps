---
feature: CLEARBLOCK
stage: intent
status: accepted
branch: main
---

# Intent: Add a standalone Chrome ad blocker extension

## Problem

The repository has no Chrome extension that blocks advertising and tracking requests. Users also lack a compact popup for per-site and per-page controls, a page element blocker, and a dedicated place to manage exceptions.

## Proposed outcome

Users can install ClearBlock from its own directory under `chrome_extensions`, block common ads and trackers, pause blocking for the current website or exact page, hide a selected page element, inspect local blocking counts, and manage allowlists from a standalone settings page.

## Affected users and systems

- Chrome users who load the extension unpacked or install its packaged ZIP.
- The repository's `chrome_extensions` collection, where ClearBlock must coexist with future extensions.

## Constraints

- The extension must use Chrome Manifest V3.
- The popup should follow the supplied visual reference without copying Adblock Plus branding.
- ClearBlock must not include paid features or a report-issue action.
- Website exceptions include the selected host and its subdomains; page exceptions match the exact URL including its query and excluding its fragment.
- Chinese and English interfaces are required.
- Blocking and settings data must remain local except for downloading filter-list updates.

## Out of scope

- Paid or premium features.
- Issue reporting, accounts, analytics, and telemetry.
- Guaranteed removal of every YouTube ad; filter-list-based blocking is best effort.
- Support for browsers other than Chrome.

## Open questions

None.
