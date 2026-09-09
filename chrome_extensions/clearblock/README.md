# ClearBlock

ClearBlock is a Manifest V3 Chrome extension that blocks ads and trackers,
hides cosmetic page elements, supports site and exact-page allowlisting, and
lets users select page elements to hide. Users can optionally synchronize
those allowlist and element rules through their signed-in Chrome profile.

## Requirements

- Node.js 24+
- npm 11+
- Chrome 127+

## Build and load

```bash
npm install
npx playwright install chromium
npm run build
```

Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**,
and select the generated `dist` directory.

Create the Chrome Web Store archive with:

```bash
npm run package
```

The ZIP is written to `artifacts/`.

## Filter list updates

The extension ships with EasyList, EasyPrivacy, EasyList China, and the official
ABP anti-circumvention filters (including YouTube player-data filters). The eyeo
engine applies upstream differential updates at runtime. To refresh the
packaged baseline rules before a release, run:

```bash
npm run rules:update
```

This command downloads filter data from the official EasyList distribution
endpoint, regenerates DNR rules, and records SHA-256 hashes in
`rules/metadata.json`.

## YouTube video ads

The ABP anti-circumvention subscription supplies player-data filters through
the bundled eyeo snippet engine. These suppress known advertisement fields
before the player uses them, rather than relying on ClearBlock clicking Skip.
The upstream list also includes fallback rules for some player variants.
Website and exact-page allowlisting use the same engine as other filtering.
The engine's early snippet cache is enabled. Initializing or updating that
cache can reload a page; before the first cache initialization completes,
very early player initialization can still race the filtering response.

After updating an unpacked installation, reload ClearBlock in
`chrome://extensions`, then reload the YouTube tab. YouTube changes may require
filter updates; fixture verification does not guarantee every live ad variant
is blocked.

## User-rule sync

Open ClearBlock settings and enable **Sync user rules** to synchronize website
allowlist entries, exact-page exceptions, and manually blocked elements through
Chrome Sync. Enabling it for the first time merges the rules already stored on
the device with the rules in the Chrome profile.

Filter lists, blocking counts, update state, and per-tab data remain local.
Turning sync off preserves both the current device's rules and the last cloud
copy.

## Privacy and licensing

ClearBlock does not include analytics, telemetry, accounts, remote
configuration, Acceptable Ads, or premium filter lists. See [PRIVACY.md](PRIVACY.md)
and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

ClearBlock is licensed under GPL-3.0-only because it includes eyeo's official
WebExtension Ad-Filtering Solution.
