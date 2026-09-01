# ClearBlock

ClearBlock is a Manifest V3 Chrome extension that blocks ads and trackers,
hides cosmetic page elements, supports site and exact-page allowlisting, and
lets users select page elements to hide.

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

The extension ships with EasyList, EasyPrivacy, and EasyList China. The eyeo
engine applies upstream differential updates at runtime. To refresh the
packaged baseline rules before a release, run:

```bash
npm run rules:update
```

This command downloads filter data from the official EasyList distribution
endpoint, regenerates DNR rules, and records SHA-256 hashes in
`rules/metadata.json`.

## Privacy and licensing

ClearBlock does not include analytics, telemetry, accounts, remote
configuration, Acceptable Ads, or premium filter lists. See [PRIVACY.md](PRIVACY.md)
and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

ClearBlock is licensed under GPL-3.0-only because it includes eyeo's official
WebExtension Ad-Filtering Solution.
