---
feature: YOUTUBE-AD-SKIP
stage: intent
status: superseded
branch: main
---


# Intent: YouTube automatic ad skipping

## Problem

YouTube preroll advertisements still require the user to click Skip manually.


## Proposed outcome

Automatically use the available Skip control on remaining YouTube player advertisements.


## Affected users and systems

ClearBlock users watching desktop YouTube.


## Constraints

Preserve normal playback and site/exact-page allowlisting. No additional permissions.


## Out of scope

Eliminating unskippable countdowns, removing sponsor segments, guaranteeing that advertisements never load.


## Open questions

None for automatic skipping. Live YouTube advertisement variants remain an acceptance limitation.


Superseded: user clarified that advertisements must be filtered before playback, not automatically skipped. The automatic-click implementation and tests were removed. See ../YOUTUBE-PREROLL-BLOCK/.
