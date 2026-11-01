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
            if s.phase == C.PHASE_SWAP and not s.swap_picks and pairs:
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
