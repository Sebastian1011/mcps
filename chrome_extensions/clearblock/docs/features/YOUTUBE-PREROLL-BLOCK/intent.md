---
feature: YOUTUBE-PREROLL-BLOCK
stage: intent
status: accepted
branch: main
---


# Intent: YouTube preroll filtering

## Problem

YouTube preroll ads still play. The user explicitly requires blocking them, not clicking Skip.


## Proposed outcome

Remove advertisement placements before the player chooses them, while retaining the requested content video.


## Affected users and systems

ClearBlock desktop YouTube users.


## Constraints

Use the existing MV3 filtering engine and respect site/page allowlists. Remove the mistaken custom automatic-click solution.


## Out of scope

Custom auto-clicking or seeking as a substitute for blocking; sponsor segments.


## Open questions

Live regional/account-specific YouTube behavior needs verification; source-backed filter behavior can be validated independently.

