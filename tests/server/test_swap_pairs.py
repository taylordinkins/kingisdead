"""The adapter's read-only swap_pairs lookahead (UI click-order independence for Manoeuvre)."""

import random

from kingisdead import constants as C
from kingisdead import rules
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
            first_pick = (
                s.phase == C.PHASE_NEG_FIRST
                or (s.phase == C.PHASE_SWAP and not s.swap_picks)
                or (
                    s.phase == C.PHASE_SWAP
                    and s.swap_mode == rules.MODE_ONE_FOR_TWO
                    and len(s.swap_picks) == 1
                )
            )
            if first_pick and pairs:
                seen += 1
                for a, b in pairs:
                    assert a["region"] <= b["region"]
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


def _outmanoeuvre_state() -> KingIsDeadState:
    from kingisdead.scenario import load_scenario

    s = load_scenario(
        {
            "format": 1,
            "kind": "state",
            "players": 2,
            "slots": [
                "Moray",
                "Strathclyde",
                "Lancaster",
                "Northumbria",
                "Gwynedd",
                "Warwick",
                "Essex",
                "Devon",
            ],  # fmt: skip
            "regions": {"Moray": {"W": 1}, "Strathclyde": {"S": 1, "E": 1}},
            "courts": [{}, {}],
            "to_play": 0,
            "hands": [
                [
                    "scottish_support",
                    "welsh_support",
                    "english_support",
                    "assemble",
                    "assemble",
                    "negotiate",
                    "manoeuvre",
                    "outmanoeuvre",
                ],
                [
                    "scottish_support",
                    "welsh_support",
                    "english_support",
                    "assemble",
                    "assemble",
                    "negotiate",
                    "manoeuvre",
                    "outmanoeuvre",
                ],
            ],  # fmt: skip
        }
    )
    assert isinstance(s, KingIsDeadState)
    return s


def test_outmanoeuvre_pair_followers_accept_either_click_order() -> None:
    """Pair in Strathclyde is {Scottish, English}; English clicked first must still be offered."""
    adapter = KingIsDeadAdapter()
    s = _outmanoeuvre_state()
    s.apply_action(7)  # PLAY Outmanoeuvre
    assert s.phase == C.PHASE_SWAP and s.swap_mode == rules.MODE_ONE_FOR_TWO
    assert adapter.view(s, 0)["swap_pairs"] == []  # single pick is not symmetric
    (single,) = s.legal_actions()
    s.apply_action(single)
    pairs = adapter.view(s, 0)["swap_pairs"]
    assert len(pairs) == 1
    first, second = pairs[0]
    assert (first["faction"], second["faction"]) == (0, 2)  # canonical: Scottish then English
    assert first["region"] == second["region"]
    # Offering English as a first click: it is the second element, so the UI can reverse.
    c = s.clone()
    c.apply_action(first["id"])
    assert second["id"] in c.legal_actions()


def test_outmanoeuvre_pair_invariant_random_play() -> None:
    adapter = KingIsDeadAdapter()
    game = adapter.load({"players": 2})
    rng = random.Random(11)
    seen = 0
    for _ in range(120):
        s = game.new_initial_state()
        while not s.is_terminal():
            assert isinstance(s, KingIsDeadState)
            if s.is_chance_node():
                s.apply_action(rng.choice(s.legal_actions()))
                continue
            if s.phase == C.PHASE_SWAP and s.swap_mode == rules.MODE_ONE_FOR_TWO:
                pairs = adapter.view(s, 0)["swap_pairs"]
                if len(s.swap_picks) == 1:
                    seen += 1
                    assert pairs
                    legal = set(s.legal_actions())
                    assert {a["id"] for a, _ in pairs} == legal
                    for a, b in pairs:
                        assert a["region"] == b["region"] and a["faction"] <= b["faction"]
                        c = s.clone()
                        c.apply_action(a["id"])
                        assert b["id"] in c.legal_actions()
                else:
                    assert pairs == []
            s.apply_action(rng.choice(s.legal_actions()))
    assert seen > 0
