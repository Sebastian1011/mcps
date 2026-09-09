---
feature: YOUTUBE-PREROLL-BLOCK
stage: spec
status: accepted
branch: main
---


# Spec: YouTube preroll filtering

## Requirements

Load maintained player-data filtering rules by default, packaged for offline startup and updated through the existing subscription flow. Verify ad fields are unavailable when playback is selected, with zero ad request and zero Skip click.


## Design

Bundle the official ABP anti-circumvention subscription (D4028CDD-3D39-4624-ACC7-8140F4EC3238). Its circumvention type authorizes the existing eyeo snippet engine. Official rules override ytInitialPlayerResponse and ytplayer.config.args.raw_player_response adSlots/adPlacements/playerAds. Enable eyeo lightningSnippets so cached filters execute before initial page scripts. The first cache fill and later changes can reload the page. Existing content scripts and allowlist evaluation stay authoritative. ClearBlock must decline ewe:-prefixed runtime messages so the engine can deliver its filter configuration; returning {ok:true} for those messages breaks snippet initialization.


## Affected modules

Subscription generation and packaged data, manifest/subscription tests, README and third-party/privacy notices. Existing custom Skip changes are removed.


## Trade-offs and concerns

Use maintained upstream filtering rather than patching global JSON/fetch ourselves. The upstream list also contains fallback rules, including skip behavior, but acceptance must demonstrate player-data filtering without relying on them. Runtime injection timing and YouTube variants are material risks.


## Related ADRs

None; existing engine and subscription pipeline.


## Acceptance criteria

Installed-extension fixture consumes player data and requests content instead of advertising, with no click/seek. Allowlisting restores unfiltered data. Existing test suite passes. Record real-site verification separately.

