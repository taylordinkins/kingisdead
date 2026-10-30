"""Shared pytest configuration.

``@pytest.mark.pending("R-012")`` marks a test written from the spec before the rule is
implemented. It runs as a non-strict xfail so the suite (and the Stop hook) stays green
while work is in progress. The implementer removes the marker when the rule lands;
``/close-phase`` fails if any pending marker remains for a rule the phase claims to cover.

``@pytest.mark.regression("<report id>")`` marks a regression test for a playtest report. It must
fail until the bug is fixed, so it runs as ``xfail(strict=True)``: the suite stays green while the
bug exists, and an unexpected pass (XPASS) turns it red until the implementer removes the marker.
"""

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        pending = item.get_closest_marker("pending")
        if pending is not None:
            rule_id = pending.args[0] if pending.args else "unspecified rule"
            item.add_marker(
                pytest.mark.xfail(reason=f"pending implementation of {rule_id}", strict=False)
            )
        regression = item.get_closest_marker("regression")
        if regression is not None:
            report_id = regression.args[0] if regression.args else "unspecified report"
            item.add_marker(
                pytest.mark.xfail(reason=f"open playtest report {report_id}", strict=True)
            )
