# The King is Dead — Rules Specification

**Status:** DRAFT

This is the contract between the rulebook and the code: every behaviour the engine implements has a
numbered rule here, and every rule has at least one test that cites its ID. It is written in Phase 1
(see PLAN.md §7) and reviewed by the user before any engine code is written.

Status values (only the user changes this line):
- **DRAFT** — being written; agents may edit freely.
- **APPROVED** — locked. A hook blocks edits; propose amendments to the user instead.
- **AMENDING** — temporarily unlocked by the user for an agreed change; set back to APPROVED after.

## Format

```
### R-012 — Support cards: eligible regions
Source: rulebook "The Action Cards"; PLAN.md §4 C7
Statement: <testable statement>
Example: <board fragment> → <result>
```

## Rules

Rule IDs are grouped by hundreds: R-0xx components and setup, R-1xx turn flow, R-2xx actions and
summon, R-3xx power struggle, R-4xx game end and scoring. Rulebook page numbers refer to the PDF
page (cover = p1). "C#" refers to PLAN.md §4. ⚑ marks a default the rulebook does not state.
The R-012 in the Format block above is illustrative only.

### Components and board

### R-001 — Regions and indices
Source: rulebook "Board" p3; PLAN.md C1
Statement: There are eight regions with fixed indices: 0 Moray, 1 Strathclyde, 2 Lancaster,
3 Northumbria, 4 Gwynedd, 5 Warwick, 6 Essex, 7 Devon. These indices are used in action IDs and
observations and never change. France is not a region: it is not indexed, cannot hold followers,
and only holds instability discs not yet on the board.
Example: Gwynedd is region 4; no action can target "France".

### R-002 — Adjacency
Source: PLAN.md C1 (D13, confirmed against the physical board)
Statement: Adjacency is symmetric and exactly:
Moray: Strathclyde · Strathclyde: Moray, Lancaster, Northumbria ·
Lancaster: Strathclyde, Northumbria, Gwynedd, Warwick ·
Northumbria: Strathclyde, Lancaster, Warwick, Essex · Gwynedd: Lancaster, Warwick, Devon ·
Warwick: Lancaster, Northumbria, Gwynedd, Essex, Devon · Essex: Northumbria, Warwick, Devon ·
Devon: Gwynedd, Warwick, Essex. No region is adjacent to itself. "Bordering" means adjacent.
Example: Moray borders only Strathclyde; Warwick borders five regions.

### R-003 — Factions and home regions
Source: rulebook "Contents" p2, "Setup" p4; PLAN.md C1
Statement: There are three factions with fixed indices: 0 Scottish, 1 Welsh, 2 English. Home
regions: Scottish → Moray (0), Welsh → Gwynedd (4), English → Essex (6).
Example: The English home region is Essex.

### R-004 — Region state
Source: rulebook "Taking actions" p6 ("regions with a control disc or an instability disc")
Statement: Each region is in exactly one state: open (no disc), controlled by a faction
(that faction's control disc), or unstable (an instability disc). Controlled and unstable regions
are together called closed. A region only ever moves open → controlled or open → unstable, and
never changes again (see Power struggle). Followers can be on open regions only, except in the
moment of a power struggle (R-3xx).
Example: A region with a Welsh control disc is closed and controlled by the Welsh.

### R-005 — Follower pool
Source: rulebook "Contents" p2, "Two-player" p4; PLAN.md D3
Statement: Each faction has 18 followers in a 3- (or 4-) player game and 16 in a 2-player game,
so 54 or 48 followers in total. Every follower is always in exactly one place: in a region, in a
player's court, or in the supply. A follower's identity is its faction only; followers of the same
faction are interchangeable. The total number of followers of each faction never changes.
Example: In a 2-player game there are 16 Scottish followers across regions, courts and supply.

### R-006 — Discs
Source: rulebook "Contents" p2, "Discs" p4
Statement: There are 8 control discs per faction (never exhausted: at most 8 regions can be
controlled), 3 instability discs, and one negotiation disc per player. Each negotiation disc is
either in its owner's hands (unused) or on a region card (spent); a spent disc never returns.
Example: A 2-player game has exactly 2 negotiation discs.

### R-007 — Player count
Source: rulebook "Setup" p4; PLAN.md D3
Statement: The base game supports 2 or 3 players. Any other count is rejected when the game is
created. (4 players is Phase 6.)
Example: Creating the game with `players=5` fails.

### R-008 — Starting hand
Source: rulebook "Cards" p4
Statement: Each player starts with exactly eight action cards: Scottish Support, Welsh Support,
English Support, Negotiate, Manoeuvre, Outmanoeuvre, and two copies of Assemble. Cunning action
cards are not used. The two Assemble copies are interchangeable. Hands are public in the base game
(perfect information).
Example: A fresh player's hand contains 2 Assemble and 1 of every other card.

### Setup

The rulebook sets up physically; the engine models the random parts as chance events. The sequence
of chance outcomes is defined in docs/ACTIONS.md; the distributions are defined here.

### R-010 — Region card order
Source: rulebook "Cards" p4; PLAN.md §5.4
Statement: There are 8 numbered slots (1–8) on the board edge. Each of the 8 region cards is
placed face up in a distinct slot, with the assignment a uniformly random permutation. No card has
a negotiation disc at setup.
Example: One possible result: slot 1 Devon, slot 2 Moray, … slot 8 Essex.

### R-011 — Home followers
Source: rulebook "Home regions" p4
Statement: Before any random draw, Moray holds 2 Scottish followers, Gwynedd 2 Welsh followers,
and Essex 2 English followers. These come out of the faction's pool of R-005.
Example: After home placement, Essex holds [0 Scottish, 0 Welsh, 2 English].

### R-012 — Court draws
Source: rulebook "Followers" p4
Statement: The bag contains every follower not placed by R-011 (2- or 3-player: each faction's
pool minus 2). Each player in seat order draws 2 followers from the bag into their court. Every
draw is uniform over the followers remaining in the bag (so a faction is drawn with probability
proportional to its remaining count).
Example: In a 2-player game the bag starts with 14 followers of each faction; seat 0 draws two.

### R-013 — Region fill
Source: rulebook "Followers" p4
Statement: After court draws, regions are filled in index order (0..7). Each region is topped up
from the bag, one uniform draw at a time, until it holds exactly 4 followers (so Moray, Gwynedd
and Essex receive 2 draws, and every other region 4). The bag is then empty of what was drawn;
all remaining followers form the supply.
Example: After the fill, every region holds exactly 4 followers.

### R-014 — Post-setup state
Source: rulebook "Followers", "Discs", "Cards" p4; PLAN.md C4
Statement: After setup: every region is open and holds 4 followers; each court holds 2 followers;
the supply holds the rest (2-player: 48 − 32 − 4 = 12; 3-player: 54 − 32 − 6 = 16); no instability
disc is on the board; every negotiation disc is unused; the consecutive-pass count is 0 and no
power struggle has been resolved; every hand is as in R-008; no card has been played. Player 0 is
the first to act (⚑ C4; the physical rule, "most recently visited a castle", is replaced by seat).
Example: A 3-player game starts with 16 followers in the supply and player 0 to act.

### R-015 — Follower conservation (invariant)
Source: derived from R-005, R-013
Statement: At every state, for each faction, followers in regions + courts + supply equal the
faction's pool (R-005). A closed region holds 0 followers (a struggle returns them all to the supply
as it closes the region, R-3xx), so followers are only ever on open regions. There is no per-region
follower limit after setup.
Example: After any action, Σ Scottish in regions, courts and supply = 16 (2-player).

### Turn flow

### R-100 — Turn order
Source: rulebook "Turns" p6; PLAN.md C4
Statement: Players act in increasing seat index, wrapping from the last seat to seat 0
(clockwise), starting with the first player of R-014. Exactly one player has the move at a time.
Example: 3 players: 0, 1, 2, 0, 1, 2, …, unless a power struggle intervenes (R-105).

### R-101 — Choices at the start of a turn
Source: rulebook "Turns", "Taking actions" p6; PLAN.md C4, C8
Statement: The player to act either passes or plays one card from their hand. Every card in hand
is always playable, even if its effect would be wholly or partly impossible (partial actions are
defined per card in R-2xx). A player with no cards in hand has exactly one legal choice, pass
(⚑ C4: the rulebook does not address this case).
Example: A player holding only Negotiate when fewer than two cards are eligible may still play it
(no effect, summon still happens).

### R-102 — Playing a card
Source: rulebook "Taking actions" p6
Statement: Playing a card removes it from the player's hand for the rest of the game (a player
therefore plays at most 8 cards), resolves its effect (R-2xx), then the player summons a follower
(Summon, R-2xx). Then the turn passes to the next player (R-100). The card is recorded in the
player's play history in order, and the identity of the most recent card played is retained.
Example: After playing Manoeuvre and summoning, the player's hand has 7 cards.

### R-103 — Pass
Source: rulebook "Turns" p6
Statement: Passing changes no board state, increments the consecutive-pass count by 1, and ends
the turn. A passing player may pass again or act on their next turn.
Example: Count 0, player 1 passes → count 1, player 2 to act.

### R-104 — Playing a card resets the pass count
Source: rulebook "Turns" p6 ("all the players pass in sequence"); PLAN.md C4
Statement: When a player plays a card, the consecutive-pass count is reset to 0 (before or after
the effect; the result is the same).
Example: Passes by players 0 and 1, then player 2 plays Assemble → count 0.

### R-105 — Power struggle trigger
Source: rulebook "Turns", "Power struggles" p6; PLAN.md C4
Statement: When the consecutive-pass count reaches the number of players, a power struggle is
resolved immediately and automatically (no player decision; resolution is R-3xx), the count is
reset to 0, and the player to act next is the player after the one who made the last pass. If
the game has not ended, play then continues as normal.
Example: 3 players: player 1 plays a card; 2, 0, 1 pass → struggle; player 2 acts next.

### R-106 — Empty hands still count
Source: PLAN.md C4
Statement: A player with no cards passes automatically (R-101) and that pass counts toward
R-105. A game in which all hands are empty therefore still terminates (every n passes resolves a
struggle, and at most 8 struggles occur).
Example: 2 players, both with empty hands: pass, pass → struggle.
