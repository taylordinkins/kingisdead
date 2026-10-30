"""Shared pytest configuration.

``@pytest.mark.pending("R-012")`` marks a test written from the spec before the rule is
implemented. It runs as a non-strict xfail so the suite (and the Stop hook) stays green
while work is in progress. The implementer removes the marker when the rule lands;
``/close-phase`` fails if any pending marker remains for a rule the phase claims to cover.
"""

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        marker = item.get_closest_marker("pending")
        if marker is None:
            continue
        rule_id = marker.args[0] if marker.args else "unspecified rule"
        item.add_marker(
            pytest.mark.xfail(reason=f"pending implementation of {rule_id}", strict=False)
        )
