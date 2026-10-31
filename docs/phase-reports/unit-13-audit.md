# Unit 13 audit (rules-auditor)

Verdict: the engine conforms to the spec. No blockers. No rule ambiguities.

## Method

- 66 mutation probes against the engine: 63 killed, 2 equivalent mutants (`no_void`,
  `persist_noswap`), 1 test gap (`use_rank3`). `out_no_capture` was killed only by the goldens.
- Independent flow / struggle / scoring oracle over the 3 goldens plus 1,500 random games, and an
  independent card oracle over 5,880 + 700 card plays: all matching.
- R-216 examples 2 and 3 and the R-217 example were played end to end.
- Legality probe: clean.
- Goldens: 2p seed 1 invasion, P0 wins [1, -1]; 3p seed 2 coronation, P1 wins; 2p seed 3
  coronation, P1 wins.
- `tools/sim_stats.py` end-type logic matches R-304 / R-400.
- Unit 8 item on R-304 ordering is resolved by the R-402 tests in `tests/rules/test_game_end.py`.

## Findings and resolution

| Id | Finding | Status |
|----|---------|--------|
| M1 | R-404: rank-3 followers not shown to be excluded from tie-breaks (`use_rank3` survived) | Fixed: `test_R404_rank3_followers_are_not_a_tiebreak`; mutant `ranking[:3]` fails it |
| M2 | R-216/R-217 examples 2 and 3 only tested via injected B* scenario | Fixed: real-play tests from the pre-L board added (injected tests kept); disabling the block fails both. Example 3 uses pick `F(1,E)` (21) for seat 1, then mask `[F(0,S)]` |
| S1 | R-405 formula test only checked helper `_exp` | Fixed: literal `returns()` asserts for n=2 shared win `[0, 0]` and n=3 sole winner `[1, -0.5, -0.5]` |
| S2 | vacuous `or True` assertion in the R-216 3-player test | Fixed: removed |
| S3 | R-217 no-swap test docstring misleading | Fixed: docstring notes `persist_noswap` is an equivalent mutant; no assertion change |
| S4 | `_rec` mapped 0/negative to None, hiding wrong "never" values | Fixed: `_rec` is strict (`None` stays `None`, otherwise `int`) |
| S5 | unused `pend` helper and unused `pending` marker | Fixed: removed |
| S6 | `sim_stats` reported 0 violations if invariants import failed | Fixed: exits non-zero with a clear error |
| - | equivalent mutants `no_void`, `persist_noswap` | Accepted, not killable by any test |
