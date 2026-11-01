"""The adapter's read-only swap_pairs lookahead (UI click-order independence for Manoeuvre)."""

import random

from kingisdead import constants as C
from kingisdead.game import KingIsDeadState
from server.adapters.kingisdead import KingIsDeadAdapter


def test_swap_pairs_match_canonical_sequences() -> None:
    adapter = KingIsDeadAdapter()
    game = adapter.load({"players": 2})
    rng = random.Random(3)
    seen = 0
    for _ in range(60):
        s = game.new_initial_state()
        while not s.is_terminal():
            assert isinstance(s, KingIsDeadState)
            if s.is_chance_node():
                s.apply_action(rng.choice(s.legal_actions()))
                continue
            pairs = adapter.view(s, 0)["swap_pairs"]
            first_pick = s.phase == C.PHASE_NEG_FIRST or (
                s.phase == C.PHASE_SWAP and not s.swap_picks
            )
            if first_pick and pairs:
                seen += 1
                for a, b in pairs:
                    assert a["region"] < b["region"]
                    c = s.clone()
                    c.apply_action(a["id"])
                    assert b["id"] in c.legal_actions()
            else:
                assert pairs == []
            s.apply_action(rng.choice(s.legal_actions()))
    assert seen > 0


# Report 20261101T181007-48abf3: history up to the Negotiate (PLAY 5) first pick.
_NEG_PREFIX = [
    3, 7, 6, 1, 0, 2, 4, 5, 0, 0, 1, 2, 2, 0, 2, 0, 1, 2, 1, 2, 0, 1, 1, 2, 1, 1, 2, 0, 2, 1,
    2, 1, 1, 2, 1, 0, 2, 2, 0, 0, 2, 13, 32, 3, 15, 30, 3, 15, 39, 1, 9, 29, 0, 4, 13, 8, 16,
    0, 0, 4, 8, 14, 13, 31, 4, 13, 8, 12, 32, 7, 29, 31, 32, 36, 5,
]  # fmt: skip


def test_negotiate_pairs_allow_any_two_eligible_cards() -> None:
    adapter = KingIsDeadAdapter()
    s = adapter.load({"players": 2}).new_initial_state()
    for a in _NEG_PREFIX:
        s.apply_action(a)
    assert isinstance(s, KingIsDeadState)
    assert s.phase == C.PHASE_NEG_FIRST
    pairs = adapter.view(s, 0)["swap_pairs"]
    regions = {(a["region"], b["region"]) for a, b in pairs}
    # Six eligible cards (regions 0, 1, 2, 4, 5, 6): every unordered pair appears once.
    assert {(0, 4), (2, 4), (4, 5)} <= regions
    assert len(regions) == 15 and len(pairs) == 15 and all(a < b for a, b in regions)
    for a, b in pairs:
        c = s.clone()
        c.apply_action(a["id"])
        assert b["id"] in c.legal_actions()
