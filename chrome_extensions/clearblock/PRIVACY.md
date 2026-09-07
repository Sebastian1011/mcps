# ClearBlock Privacy Policy

ClearBlock processes website addresses and request metadata locally for the
single purpose of blocking ads and trackers, applying allowlist choices, and
showing local blocking statistics.

ClearBlock does not collect, sell, or transmit browsing history, blocking
statistics, personal information, or identifying information to ClearBlock's
developer. It contains no analytics, telemetry, advertising, ClearBlock
account, crash-report upload, or remote-configuration service.

The extension connects to `easylist-downloads.adblockplus.org` to download
updates for EasyList, EasyPrivacy, and EasyList China. Those downloads contain
filter-list data only; ClearBlock does not download or execute remote code. If
an update fails, the last valid packaged or downloaded rules remain active.

Allowlist entries and manually hidden element selectors are stored in Chrome
extension storage on the user's device. Chrome account synchronization is off
by default. If the user enables **Sync user rules** in ClearBlock settings,
those entries and selectors are also written to `chrome.storage.sync` and are
processed by Google according to the user's Chrome Sync settings and Google
privacy terms. Disabling the option stops further synchronization but does not
delete the last synchronized copy from the Chrome profile.

Filter data, blocking statistics, subscription update state, and per-tab state
remain on the device and are never placed in Chrome Sync. Local extension data
is removed when the extension is uninstalled; synchronized data is controlled
through the user's Chrome profile and Chrome Sync data controls.

The broad website access permission is necessary to block requests and hide
advertising elements on the pages the user visits. The `webRequest` permission
is used to observe request metadata for filtering reports and local counts; it
does not expose response bodies to ClearBlock.

Last updated: 2026-09-01.
