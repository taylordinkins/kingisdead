"""Board and component constants. Implements R-001..R-006, R-008."""

# R-001: regions, fixed indices.
REGION_NAMES = (
    "Moray",
    "Strathclyde",
    "Lancaster",
    "Northumbria",
    "Gwynedd",
    "Warwick",
    "Essex",
    "Devon",
)
NUM_REGIONS = len(REGION_NAMES)

# R-002: adjacency, indexed by region.
ADJACENCY = (
    (1,),
    (0, 2, 3),
    (1, 3, 4, 5),
    (1, 2, 5, 6),
    (2, 5, 7),
    (2, 3, 4, 6, 7),
    (3, 5, 7),
    (4, 5, 6),
)

# R-003: factions and home regions.
FACTION_NAMES = ("Scottish", "Welsh", "English")
NUM_FACTIONS = len(FACTION_NAMES)
HOME_REGION = (0, 4, 6)

# R-004: region states.
REGION_OPEN = 0
REGION_CONTROLLED = 1
REGION_UNSTABLE = 2

# R-005: followers per faction by player count (R-007: 2 or 3 only).
FOLLOWERS_PER_FACTION = {2: 16, 3: 18}

# R-006: discs.
CONTROL_DISCS_PER_FACTION = 8
INSTABILITY_DISCS = 3

# R-008: card ids (docs/ACTIONS.md) and starting hand.
CARD_NAMES = {
    1: "Scottish Support",
    2: "Welsh Support",
    3: "English Support",
    4: "Assemble",
    5: "Negotiate",
    6: "Manoeuvre",
    7: "Outmanoeuvre",
}
STARTING_HAND = {1: 1, 2: 1, 3: 1, 4: 2, 5: 1, 6: 1, 7: 1}
