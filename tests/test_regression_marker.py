"""Guards the ``regression`` marker convention: strict xfail, so a fix forces marker removal."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.regression("report-000")
def test_regression_tests_do_not_fail_the_suite() -> None:
    raise AssertionError("regression tests run as strict xfail while the bug is open")


def test_regression_marker_is_strict_xfail(tmp_path: Path) -> None:
    shutil.copy(Path(__file__).with_name("conftest.py"), tmp_path / "conftest.py")
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    pending(r): x\n    regression(r): x\n"
    )
    (tmp_path / "test_sample.py").write_text(
        "import pytest\n"
        "@pytest.mark.regression('r1')\n"
        "def test_still_failing():\n    assert False\n"
        "@pytest.mark.regression('r2')\n"
        "def test_fixed():\n    assert True\n"
    )
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert "1 failed, 1 xfailed" in proc.stdout, proc.stdout
    assert "XPASS(strict)" in proc.stdout, proc.stdout
