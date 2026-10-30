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
never changes again (R-301). Followers can be on open regions only, except in the
moment of a power struggle (R-302).
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
as it closes the region, R-302), so followers are only ever on open regions. There is no per-region
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
defined in R-202 and per card). A player with no cards in hand has exactly one legal choice, pass
(⚑ C4: the rulebook does not address this case).
Example: A player holding only Negotiate when fewer than two cards are eligible may still play it
(no effect, summon still happens).

### R-102 — Playing a card
Source: rulebook "Taking actions" p6
Statement: Playing a card removes it from the player's hand for the rest of the game (a player
therefore plays at most 8 cards), resolves its effect (R-210..R-215), then the player summons a follower
(R-201). Then the turn passes to the next player (R-100). The card is recorded in the
player's play history in order. For the most recent card played the state also retains its type and,
for an effective Manoeuvre or Outmanoeuvre, the reference board B* (R-216).
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
resolved immediately and automatically (no player decision; resolution is R-300..R-304), the count is
reset to 0, and the player to act next is the player after the one who made the last pass. If
the game has not ended, play then continues as normal.
Example: 3 players: player 1 plays a card; 2, 0, 1 pass → struggle; player 2 acts next.

### R-106 — Empty hands still count
Source: PLAN.md C4
Statement: A player with no cards passes automatically (R-101) and that pass counts toward
R-105. A game in which all hands are empty therefore still terminates (every n passes resolves a
struggle, and at most 8 struggles occur).
Example: 2 players, both with empty hands: pass, pass → struggle.

### Actions and summon

### R-200 — Placement restriction
Source: rulebook "Taking actions" p6; PLAN.md C7
Statement: An action can place or move followers into open regions only, never into controlled or
unstable regions. Because followers are only on open regions (R-015), every follower move or swap
in this section is between open regions.
Example: A region with an English control disc can never receive a follower from Assemble.

### R-201 — Summon
Source: rulebook "Summoning followers to court" p6; PLAN.md C6
Statement: Immediately after resolving a card's effect, even a card with no effect, the acting
player chooses any one follower on any region and moves it to their own court. The choice is a
(region, faction) pair that is present on the board. A follower can never be taken from the supply
or from another court, and it need not be from a region the action touched. If no follower is on
any region, the summon is skipped. Summon never follows a pass.
Example: Regions hold Moray [2 Scots] and Essex [1 English]; summoning English leaves Essex empty.

### R-202 — Partial actions
Source: rulebook "Partial actions" p6; PLAN.md C8
Statement: A card is resolved as fully as possible. If it cannot be fully resolved it is resolved
as far as possible, and if nothing can be done it has no effect. The card is still played (R-102)
and the summon (R-201) still happens. Where a card says "if there is at least one instance where
you can ..., you must", the engine offers only the choices that achieve the most complete form of
the effect that is available at that moment (the card's own rule gives the ordering of forms).
Example: Outmanoeuvre with a full 1-for-2 swap available may not be played as 1-for-1 (R-215).

### R-210 — Support cards: eligible regions
Source: rulebook "Scottish/Welsh/English Support" p9; PLAN.md C7
Statement: Let F be the card's faction and H its home region (R-003). A region r is eligible for
F's Support when r is open and either (a) r borders a region controlled by F, or (b) H is open
(no control or instability disc) and r borders H. H itself is eligible only through (a). Closed
regions are never eligible (R-200).
Example: Scottish Support, no discs on the board: eligible = {Strathclyde}. If Moray holds a Welsh
control disc and no region is Scottish-controlled, nothing is eligible.

### R-211 — Support cards: effect
Source: rulebook "Scottish/Welsh/English Support" p9; PLAN.md C7
Statement: The player chooses one eligible region and places min(2, supply of F) followers of F from
the supply into it; both go to the same region. If no region is eligible or the supply of F is 0,
the card has no effect and no region is chosen (⚑ the choice would not change the outcome).
Example: Supply holds 1 Welsh follower: Welsh Support places that one follower.

### R-212 — Assemble
Source: rulebook "Assemble" p9; PLAN.md C10
Statement: The player places one Scottish, then one Welsh, then one English follower from the
supply, each into any open region chosen separately (the regions may be equal). A faction with no
followers in the supply is skipped and the other factions are still placed. At least one open
region exists whenever a card can be played (the eighth struggle ends the game, R-304).
Example: Supply has no Welsh followers: Assemble places only a Scottish and an English follower.

### R-213 — Negotiate
Source: rulebook "Negotiate" p9; PLAN.md C9
Statement: A region card is eligible for Negotiate when it is face up and carries no negotiation
disc. If at least two are eligible, the player chooses two distinct eligible cards and swaps their
slots, then
places their own negotiation disc on one of the two cards of their choice (R-006: the disc is then
spent). If fewer than two are eligible there is no effect and the disc stays unused.
Example: Slots 1..8 face up, none with discs: Negotiate swapping slots 3 and 5, disc on the card
now in slot 3, leaves slots 3 and 5 exchanged and a disc on slot 3.

### R-214 — Manoeuvre
Source: rulebook "Manoeuvre" p9; PLAN.md C2, C8
Statement: The player chooses a follower (r1, f1) and a follower (r2, f2) with r1 ≠ r2, both on
regions, and swaps them: the faction-f1 follower moves to r2 and the faction-f2 follower moves to r1.
f1 may equal f2 (the board is unchanged but the card is played). If at least one swap is legal the
player must make one; a swap blocked by R-216 is not legal. If none is legal there is no effect.
Example: Moray [S S S S], Essex [E E E E]: swap (Moray, S) with (Essex, E) → Moray [S S S E],
Essex [E E E S].

### R-215 — Outmanoeuvre
Source: rulebook "Outmanoeuvre" p9; PLAN.md C2, C8
Statement: Two regions r1, r2 are a bordering pair (R-002). Form 1-for-2: the player chooses one
follower in r1 and two followers in r2 (a pair of factions present in r2; both of one faction
needs two of it) and swaps them: the single goes to r2, the two go to r1. Form 1-for-1: one
follower in r1 and one in r2, swapped. The player must use form 1-for-2 if any legal 1-for-2 swap
exists, else form 1-for-1 if any legal 1-for-1 swap exists, else the card has no effect. A swap
blocked by R-216 is not legal. Same-faction swaps are allowed.
Example: Moray [S S S S], Strathclyde [W W W W]: swap (Moray, S) with {W, W}: Moray [S S S W W],
Strathclyde [W W S]. 1-for-2 swaps exist anywhere, so a 1-for-1 swap is not allowed.

### R-216 — Undo block
Source: rulebook "Manoeuvre", "Outmanoeuvre" p9; PLAN.md C2, D20, D21
Statement: Let L be the most recent card played in the game. If L is a Manoeuvre or an
Outmanoeuvre that had an effect (each player holds one of each, so a play of the same type as L is
always by another player in the base game), the state retains a reference board B*: the position of
all regions (followers per faction in each region, and each region's state, R-004) immediately
before L's effect, with L's summoned follower removed (if L's player summoned one). A play of the same
card type as L is not legal if its resulting board (before its own summon) equals B*; this
applies to every form of the card (Manoeuvre; Outmanoeuvre 1-for-2 and 1-for-1) and whichever
region is picked first. Manoeuvre and Outmanoeuvre do not block each other. If L had no effect, or L
is any other card, nothing is blocked. A blocked play drops out of the mandatory-form choice
(R-214, R-215).
- A pure reverse swap always reproduces B*, so it is blocked. So is any other swap with the
  same result (e.g. the 1-for-2 case below). A same-faction no-op swap L leaves B* equal to the
  current board, so every no-op swap is blocked (⚑ PLAN.md D20).
Example 1: Moray [S S S S], Essex [E E E E], Devon [W W W W]. L = Manoeuvre swapping (Moray, S) with
(Essex, E), summoning a W from Devon. B* = Moray [S S S S], Essex [E E E E], Devon [W W W]. Now
Moray [S S S E], Essex [E E E S]. The next player may not pick (Moray, E) with (Essex, S), but may
pick (Moray, S) with (Essex, E).
Example 2: Moray [S], Strathclyde [W W], Devon [E], all other regions empty. Player 0 plays
Outmanoeuvre (the only 1-for-2 swap: (Moray, S) for {W, W}, giving Moray [W W], Strathclyde [S]) and
summons Devon's E, so B* = Moray [S], Strathclyde [W W], Devon []. Player 1 plays Outmanoeuvre: the
only 1-for-2 swap, (Strathclyde, S) for {W, W} from Moray, reproduces B* and is blocked, so player 1
must use 1-for-1, e.g. (Moray, W) with (Strathclyde, S) → Moray [W S], Strathclyde [W].
Example 3: Moray [S E], Strathclyde [S W E], Devon [W W W W]. L = Outmanoeuvre swapping (Moray, S)
for {S, W}, summoning a W from Devon: Moray [E S W], Strathclyde [E S]. B* = Moray [S E],
Strathclyde [S W E], Devon [W W W]. The next player's swap of (Strathclyde, E) for {E, W} from
Moray gives B* and is blocked, although it is not the same picks reversed.

### R-217 — Undo block lifetime
Source: rulebook "Manoeuvre" p9; PLAN.md C2, D21
Statement: The block applies only until another card is played: when any player plays any card, L
and B* are replaced (by the new card's data, or nothing, R-216). Passes do not clear it and a
summon is part of L, not a new card. A power struggle does not clear it (⚑ C2: the rulebook says
"at least one other action"; a struggle is not an action), but the struggle closes a region, so
no later play can reproduce B* where that region's state or followers differ.
Example: 3 players: player 0 Manoeuvres, 1 and 2 and 0 pass, a struggle resolves in a region that was
open in B* (now closed), player 1 acts: nothing can match B*, so no play is blocked. If instead
player 1 plays Assemble, player 2 is not blocked.

### Power struggle

### R-300 — Contested region
Source: rulebook "Power struggles" p6
Statement: The contested region is the region of the face-up region card in the lowest-numbered slot
(1–8). Negotiate (R-213) changes which region is in which slot, so it changes the order in which
regions are contested. At least one face-up card exists whenever a struggle is resolved, because the
game ends after the eighth struggle.
Example: Face-up cards in slots 3, 5, 8 → the region of slot 3 is contested.

### R-301 — Winner of a struggle
Source: rulebook "Power struggles" p6; PLAN.md C5
Statement: Count the followers of each faction in the contested region. If one faction has strictly
more than each other faction (and so at least 1), that faction controls the region: the region
becomes controlled by it (a control disc of that faction is placed). Otherwise (a tie for most
followers, including no followers at all) the region becomes unstable: an instability disc is
moved from France onto it.
Example: [S S W E] → Scottish control. [S S W W] → unstable. [] → unstable. [S W E] → unstable.

### R-302 — Followers leave
Source: rulebook "Power struggles" p6; PLAN.md C5
Statement: Once the region's state is set (R-301), all of its followers are returned to the supply.
Example: A region [S S W E] controlled by the Scots: supply gains 2 Scottish, 1 Welsh, 1 English.

### R-303 — Flip and record
Source: rulebook "Power struggles", "Coronation" p6–7; PLAN.md C3, C5
Statement: The contested region's card is turned face down (it stays in its slot and can no longer
be contested or negotiated, R-213). The number of struggles resolved increases by 1 (so the first
struggle is number 1). If a faction took control, the struggle's number is recorded as that
faction's most recent win; an unstable result records nothing. A faction that never won has
recent-win value −1.
Example: The third struggle gives the Welsh control: Welsh recent-win = 3.

### R-304 — After a struggle
Source: rulebook "Power struggles", "Game end" p6–7; PLAN.md C4
Statement: After R-300..R-303 the consecutive-pass count is reset (R-105). Then: if three
instability discs are on the board the game ends as an invasion (R-400); otherwise if the eighth
struggle has now been resolved the game ends as a coronation (R-400); otherwise play continues
(R-105). The invasion check comes first: if the eighth struggle makes the third instability disc, the
game is an invasion.
Example: Eight struggles with two unstable regions → coronation. The eighth struggle is the third
unstable → invasion.

### Game end and scoring

### R-400 — End triggers
Source: rulebook "Game end" p7; PLAN.md C4
Statement: The game ends immediately, with no further action, summon or struggle, when R-304
says so. Invasion ends it when the struggle that places the third instability disc has finished (R-304); coronation ends it after
the eighth struggle if no invasion occurred. A game that has ended has no legal actions and its
outcome is computed from the final state by R-402 (invasion) or R-403 and R-404 (coronation), with
returns by R-405.
Example: The third unstable region is placed → invasion, even though struggles remain.

### R-401 — Tie-break records
Source: rulebook "Game end" p7; PLAN.md C3
Statement: The state records, for tie-breaks: for each player the number of the most recent card they
played, counting card plays across the game in order from 1 (none if they never played); the number
of the card play at which each player's hand became empty (none if it never did); and each faction's
recent-win value (R-303).
Example: Player 1 played the 9th card overall, and it was their 8th card → their hand-empty time = 9.

### R-402 — Invasion winner
Source: rulebook "Invasion" p7; PLAN.md C3
Statement: Each player's number of complete sets is the minimum over the three factions of that
faction's follower count in the player's court. The player with the most sets wins. Among tied
players, the one with the highest last-play number (R-401, most recently played an action card)
wins; a player who never played has none and loses to any tied player who did. If none of the tied
players ever played a card the tied players share the win (R-405).
Example: Courts P0 [S S W E], P1 [S W E E]: both have 1 set. P1 played the later card → P1 wins.

### R-403 — Coronation ranking
Source: rulebook "Coronation" p7; PLAN.md C3
Statement: Factions are ranked by (number of regions they control, descending), then by recent-win
value (descending, R-303). Each struggle number is recorded for at most one faction, so two factions
that both control at least 1 region always differ on recent-win; a tie after both criteria needs
both to control 0 regions (both recent-win −1), and the rank of such tied factions is undefined.
At least 6 regions are controlled at coronation (at most two are unstable, since a third ends the
game, R-304), so at most two factions can tie this way and rank 1 is always defined.
Example: S controls 4, W 2, E 2: W and E tie on regions → the one whose recent-win is larger ranks 2nd.
Example: S controls 6, W 0, E 0 (two unstable): rank 1 = S; ranks 2 and 3 are undefined.

### R-404 — Coronation winner
Source: rulebook "Coronation" p7; PLAN.md C3
Statement: Step 1: the player with the most followers of the rank-1 faction in court wins; if unique,
done. Step 2: among the tied players, the one with the most followers of the rank-2 faction wins;
if the rank-2 faction is undefined this step is skipped. Step 3: among the players still tied, the
one whose hand became empty earliest (lowest hand-empty number, R-401) wins; a player whose hand
never became empty loses to any tied player whose hand did. If none of the still-tied players ever
emptied their hand, they share the win (R-405). Each step is applied only to players still tied.
Example: Rank 1 = S, rank 2 = W. Courts P0 [S S W], P1 [S S E], P2 [S]. P0 and P1 tie on S (2); W: P0 1,
P1 0 → P0 wins.

### R-405 — Returns
Source: PLAN.md D8, D9
Statement: Returns are computed only at the end of the game and are zero for every player at every
earlier state. If k of the n players win (k = 1 for a sole winner, k > 1 for a shared win), each winner
gets (n − k) / (k·(n − 1)) and each non-winner gets −1/(n − 1). Returns always sum to 0.
Example: n = 3, one winner: +1, −1/2, −1/2. n = 3, k = 2: +1/4, +1/4, −1/2. n = 2, k = 2: 0, 0.
