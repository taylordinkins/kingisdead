"""Guards the ``pending`` marker convention the agent workflow relies on."""

import pytest


@pytest.mark.pending("R-000")
def test_pending_tests_do_not_fail_the_suite() -> None:
    raise AssertionError("pending tests run as non-strict xfail")
