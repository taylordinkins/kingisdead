"""Tests for the Claude Code workflow hooks in `.claude/hooks/`.

Each hook runs as a subprocess against a temporary git repo holding a copy of the hooks, so the
`ROOT = Path(__file__).resolve().parents[2]` anchoring is exercised (the subprocess runs from an
unrelated cwd with a bogus CLAUDE_PROJECT_DIR). check.py's gate is tested through its decision
functions; the real lint/type/test commands are never run here.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

# Slow (~10s) and hooks rarely change: runs in CI and /close-phase, not in the stop gate.
pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_SRC = REPO_ROOT / ".claude" / "hooks"

SPEC_BODY = "# Spec\n\n**Status:** {status}\n\n## R-001\nFirst rule.\n"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(base: Path) -> Path:
    repo = (base / "repo").resolve()
    repo.mkdir()
    shutil.copytree(
        HOOKS_SRC, repo / ".claude" / "hooks", ignore=shutil.ignore_patterns("__pycache__")
    )
    write(repo, "docs/RULES_SPEC.md", SPEC_BODY.format(status="DRAFT"))
    write(repo, "kingisdead/game.py", "x = 1\n")
    write(repo, "tests/harness.py", "y = 1\n")
    write(repo, "PLAN.md", "plan\n")
    write(repo, "README.md", "readme\n")
    git(repo, "init", "-q", "-b", "master")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.fixture(scope="module")
def shared_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    repo = make_repo(tmp_path_factory.mktemp("shared"))
    (repo / "tests" / "link").symlink_to(repo / "kingisdead")
    return repo


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


def run_hook(
    repo: Path, hook: str, payload: dict[str, object], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": "/nonexistent/elsewhere"}
    return subprocess.run(
        [sys.executable, "-I", str(repo / ".claude" / "hooks" / hook)],
        input=json.dumps(payload),
        cwd=cwd or repo.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def tool(name: str, **tool_input: object) -> dict[str, object]:
    return {"tool_name": name, "tool_input": tool_input}


# --- settings and anchoring -------------------------------------------------------------------


def test_hooks_anchor_on_their_own_location() -> None:
    for script in HOOKS_SRC.glob("*.py"):
        source = script.read_text(encoding="utf-8")
        assert "CLAUDE_PROJECT_DIR" not in source, script.name
        assert "os.getcwd" not in source, script.name
        assert "ROOT = Path(__file__).resolve().parents[2]" in source, script.name


def test_push_deny_rules_and_no_push_allow() -> None:
    permissions = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())["permissions"]
    assert set(permissions["deny"]) >= {
        "Bash(git push *master*)",
        "Bash(git push *+*)",
        "Bash(git push *--force*)",
        "Bash(git push * -f*)",
    }
    assert not any(rule.startswith("Bash(git push") for rule in permissions["allow"])


# --- block_engine_reads.py --------------------------------------------------------------------


def engine_cases(root: str) -> list[tuple[str, dict[str, object], bool]]:
    """(id, payload, should_block)"""
    cases: list[tuple[str, dict[str, object], bool]] = [
        # Read
        ("read-engine", tool("Read", file_path="kingisdead/game.py"), True),
        ("read-engine-abs", tool("Read", file_path=f"{root}/kingisdead/game.py"), True),
        ("read-engine-dotdot", tool("Read", file_path="tests/../kingisdead/game.py"), True),
        ("read-engine-symlink", tool("Read", file_path="tests/link/game.py"), True),
        ("read-hooks", tool("Read", file_path=".claude/hooks/check.py"), True),
        ("read-harness", tool("Read", file_path="tests/harness.py"), False),
        ("read-spec", tool("Read", file_path="docs/RULES_SPEC.md"), False),
        ("read-spec-abs", tool("Read", file_path=f"{root}/docs/RULES_SPEC.md"), False),
        ("read-plan", tool("Read", file_path="PLAN.md"), False),
        ("read-pyproject", tool("Read", file_path="pyproject.toml"), False),
        ("read-readme", tool("Read", file_path="README.md"), False),
        # Grep
        ("grep-no-path", tool("Grep", pattern="def "), True),
        ("grep-root", tool("Grep", path=root), True),
        ("grep-dot", tool("Grep", pattern="x", path="."), True),
        ("grep-engine", tool("Grep", pattern="x", path="kingisdead"), True),
        (
            "grep-glob-dotdot",
            tool("Grep", pattern="x", path="tests", glob="../kingisdead/**"),
            True,
        ),
        (
            "grep-glob-names-pkg",
            tool("Grep", pattern="x", path="tests", glob="**/kingisdead/**"),
            True,
        ),
        ("grep-tests", tool("Grep", pattern="R012", path="tests"), False),
        ("grep-docs-glob", tool("Grep", pattern="R012", path="docs", glob="*.md"), False),
        ("grep-plan-file", tool("Grep", pattern="R012", path="PLAN.md"), False),
        # Glob
        ("glob-no-path", tool("Glob", pattern="**/*.py"), True),
        ("glob-root", tool("Glob", pattern="*.py", path=root), True),
        ("glob-dotdot", tool("Glob", pattern="../kingisdead/*.py", path="tests"), True),
        ("glob-names-pkg", tool("Glob", pattern="kingisdead/**", path="tests"), True),
        ("glob-tests", tool("Glob", pattern="**/*.py", path="tests"), False),
        # Bash blocked
        ("bash-cat-dot", tool("Bash", command="cat ./kingisdead/game.py"), True),
        ("bash-cat", tool("Bash", command="cat kingisdead/game.py"), True),
        ("bash-cat-abs", tool("Bash", command=f"cat {root}/kingisdead/game.py"), True),
        ("bash-cd", tool("Bash", command="cd kingisdead && cat game.py"), True),
        ("bash-cd-abs", tool("Bash", command=f"cd {root} && cat kingisdead/game.py"), True),
        ("bash-git-show", tool("Bash", command="git show HEAD:kingisdead/x.py"), True),
        ("bash-ls-pkg", tool("Bash", command="ls kingisdead"), True),
        (
            "bash-python-open",
            tool("Bash", command="python -c \"print(open('kingisdead/game.py').read())\""),
            True,
        ),
        ("bash-grep-dot", tool("Bash", command="grep -rn def ."), True),
        ("bash-grep-root", tool("Bash", command=f"grep -rn def {root}"), True),
        ("bash-grep-no-path", tool("Bash", command="grep -rn def"), True),
        ("bash-rg", tool("Bash", command="rg def"), True),
        ("bash-rg-dot", tool("Bash", command="rg def ."), True),
        ("bash-find-dot", tool("Bash", command="find . -name '*.py'"), True),
        ("bash-ls-R", tool("Bash", command="ls -R"), True),
        ("bash-ls-R-dot", tool("Bash", command="ls -R ."), True),
        ("bash-git-grep", tool("Bash", command="git grep def"), True),
        ("bash-chain", tool("Bash", command="uv run pytest -q && grep -rn def ."), True),
        # Bash allowed
        (
            "bash-pytest-root",
            tool("Bash", command=f"cd {root} && uv run pytest -q tests/rules"),
            False,
        ),
        ("bash-pytest", tool("Bash", command="uv run pytest -q -k R012"), False),
        ("bash-import", tool("Bash", command="uv run python -c 'import kingisdead'"), False),
        (
            "bash-from-import",
            tool("Bash", command="uv run python -c 'from kingisdead import game'"),
            False,
        ),
        ("bash-grep-tests", tool("Bash", command="grep -rn R012 tests/"), False),
        ("bash-grep-tests-abs", tool("Bash", command=f"grep -rn R012 {root}/tests/"), False),
        ("bash-rg-tests", tool("Bash", command="rg -g '*.py' R012 tests docs"), False),
        ("bash-find-tests", tool("Bash", command="find tests -name '*.py'"), False),
        ("bash-ls-tests", tool("Bash", command="ls -R tests"), False),
        ("bash-ls", tool("Bash", command="ls"), False),
        ("bash-cat-spec", tool("Bash", command="cat docs/RULES_SPEC.md"), False),
        ("bash-git-grep-tests", tool("Bash", command="git grep R012 -- tests"), False),
        ("bash-git-status", tool("Bash", command="git status"), False),
    ]
    return cases


ENGINE_CASES = engine_cases("{ROOT}")


@pytest.mark.parametrize(
    ("payload", "should_block"), [c[1:] for c in ENGINE_CASES], ids=[c[0] for c in ENGINE_CASES]
)
def test_block_engine_reads(
    shared_repo: Path, payload: dict[str, object], should_block: bool
) -> None:
    text = json.dumps(payload).replace("{ROOT}", str(shared_repo))
    result = run_hook(shared_repo, "block_engine_reads.py", json.loads(text))
    assert result.returncode == (2 if should_block else 0), result.stderr
    assert bool(result.stderr) == should_block


def test_block_engine_reads_tells_agent_to_pass_path(shared_repo: Path) -> None:
    result = run_hook(shared_repo, "block_engine_reads.py", tool("Grep", pattern="def "))
    assert "path" in result.stderr


def test_block_engine_reads_ignores_bad_json_and_other_tools(shared_repo: Path) -> None:
    script = shared_repo / ".claude" / "hooks" / "block_engine_reads.py"
    bad = subprocess.run(
        [sys.executable, str(script)], input="not json", capture_output=True, text=True
    )
    assert bad.returncode == 0
    assert (
        run_hook(
            shared_repo, "block_engine_reads.py", tool("Edit", file_path="kingisdead/x.py")
        ).returncode
        == 0
    )


# --- protect_spec.py --------------------------------------------------------------------------

BASH_BLOCKED_WHEN_LOCKED = [
    "echo x >> docs/RULES_SPEC.md",
    "echo x > docs/RULES_SPEC.md",
    "echo x >docs/RULES_SPEC.md",
    "cat foo | tee docs/RULES_SPEC.md",
    "sed -i s/a/b/ docs/RULES_SPEC.md",
    "sed -i 's/a/b/' docs/RULES_*.md",
    "sed -i s/a/b/ docs/*.md",
    "sed -i.bak s/a/b/ docs/RULES_S*",
    "perl -pi -e 's/a/b/' docs/RULES_SPEC.md",
    "mv docs/RULES_SPEC.md /tmp/x",
    "rm docs/RULES_SPEC.md",
    "git rm docs/RULES_SPEC.md",
    "git checkout .",
    "git checkout -- .",
    "git checkout docs",
    "git checkout docs/",
    "git checkout -- docs/RULES_SPEC.md",
    "git checkout -- 'docs/*'",
    "git checkout master -- docs/RULES_SPEC.md",
    "git checkout master -- tests/x.py",
    "git checkout other-branch docs/RULES_SPEC.md",
    "git checkout -f master",
    "git restore .",
    "git restore docs/",
    "git restore '*.md'",
    "git restore --source=HEAD~1 docs",
    "git restore --source=HEAD~1 tests/x.py",
    "git reset --hard",
    "git reset --hard HEAD~1",
    "git -C . reset --hard",
    "git stash",
    "git stash pop",
    "git stash push -u",
    "git clean -fd",
    "git clean -n",
]

BASH_ALLOWED_WHEN_LOCKED = [
    "grep -n R-012 docs/RULES_SPEC.md 2>&1",
    "uv run pytest > out; grep R-001 docs/RULES_SPEC.md",
    "uv run pytest 2>&1 | tail -5",
    "cat docs/RULES_SPEC.md",
    "git show HEAD:docs/RULES_SPEC.md > /tmp/spec.md",
    "git diff docs/RULES_SPEC.md",
    "git log -- docs/RULES_SPEC.md",
    "git stash list",
    "git stash show -p",
    "git checkout -b phase-1/x",
    "git checkout master",
    "git switch master",
    "git checkout -- tests/x.py",
    "git restore --staged tests/x.py",
    "git restore tests/x.py",
    "git reset HEAD~1",
    "git reset --soft HEAD~1",
    "git status",
    "sed -i s/a/b/ tests/x.py",
    "rm tests/x.py",
]


def set_status(repo: Path, status: str, extra: str = "") -> None:
    write(repo, "docs/RULES_SPEC.md", SPEC_BODY.format(status=status) + extra)


@pytest.mark.parametrize("command", BASH_BLOCKED_WHEN_LOCKED)
def test_spec_bash_blocked_when_approved(shared_repo: Path, command: str) -> None:
    set_status(shared_repo, "APPROVED")
    result = run_hook(shared_repo, "protect_spec.py", tool("Bash", command=command))
    assert result.returncode == 2, command
    assert "locked" in result.stderr


@pytest.mark.parametrize("command", BASH_ALLOWED_WHEN_LOCKED)
def test_spec_bash_allowed_when_approved(shared_repo: Path, command: str) -> None:
    set_status(shared_repo, "APPROVED")
    result = run_hook(shared_repo, "protect_spec.py", tool("Bash", command=command))
    assert result.returncode == 0, (command, result.stderr)


@pytest.mark.parametrize("status", ["DRAFT", "AMENDING"])
@pytest.mark.parametrize("command", BASH_BLOCKED_WHEN_LOCKED[::6])
def test_spec_bash_allowed_when_not_approved(shared_repo: Path, status: str, command: str) -> None:
    set_status(shared_repo, status)
    assert run_hook(shared_repo, "protect_spec.py", tool("Bash", command=command)).returncode == 0


@pytest.mark.parametrize(
    ("status", "blocked"), [("DRAFT", False), ("APPROVED", True), ("AMENDING", False)]
)
@pytest.mark.parametrize(
    "path", ["docs/RULES_SPEC.md", "{ROOT}/docs/RULES_SPEC.md", "tests/../docs/RULES_SPEC.md"]
)
@pytest.mark.parametrize("name", ["Edit", "Write"])
def test_spec_edit_write_lock(
    shared_repo: Path, name: str, path: str, status: str, blocked: bool
) -> None:
    set_status(shared_repo, status)
    payload = tool(name, file_path=path.replace("{ROOT}", str(shared_repo)))
    result = run_hook(shared_repo, "protect_spec.py", payload)
    assert result.returncode == (2 if blocked else 0)


def test_other_files_stay_editable_when_approved(shared_repo: Path) -> None:
    set_status(shared_repo, "APPROVED")
    for rel in ("docs/ACTIONS.md", "tests/x.py", "PLAN.md"):
        assert (
            run_hook(shared_repo, "protect_spec.py", tool("Write", file_path=rel)).returncode == 0
        )


# --- check.py ---------------------------------------------------------------------------------


def load_check(repo: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_under_test", repo / ".claude/hooks/check.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def check(repo: Path) -> Iterator[ModuleType]:
    module = load_check(repo)
    yield module
    sys.modules.pop("protect_spec", None)


@pytest.mark.parametrize(
    "path",
    [
        "kingisdead/game.py",
        "tests/rules/test_x.py",
        "tests/scenarios/a.json",
        "tests/playthroughs/golden.json",
        "tools/replay.py",
        "typings/pyspiel.pyi",
        "pyproject.toml",
        "uv.lock",
    ],
)
def test_check_watches(check: ModuleType, path: str) -> None:
    assert check.is_watched(path)


@pytest.mark.parametrize(
    "path",
    [
        "docs/RULES_SPEC.md",
        "README.md",
        "PLAN.md",
        "playtest/reports/a.json",
        ".claude/hooks/check.py",
    ],
)
def test_check_ignores(check: ModuleType, path: str) -> None:
    assert not check.is_watched(path)


@pytest.mark.parametrize(
    ("changed", "head", "stamp", "expected"),
    [
        ([], "abc", "abc", False),  # nothing changed, HEAD is the last green commit
        ([], None, None, False),  # empty repo, nothing changed
        ([], "abc", "old", True),  # HEAD moved since the last green run
        ([], "abc", None, True),  # never been green
        (["tests/x.py"], "abc", "abc", True),  # uncommitted watched changes
        (None, "abc", "abc", True),  # git status failed: run anyway
    ],
)
def test_check_needs_run(
    check: ModuleType,
    changed: list[str] | None,
    head: str | None,
    stamp: str | None,
    expected: bool,
) -> None:
    assert check.needs_run(changed, head, stamp) is expected


def test_check_uncommitted_watched(repo: Path, check: ModuleType) -> None:
    assert check.uncommitted_watched() == []
    write(repo, "docs/RULES_SPEC.md", "changed\n")
    write(repo, "notes.txt", "x\n")
    assert check.uncommitted_watched() == []
    write(repo, "tests/scenarios/new.json", "{}\n")
    write(repo, "tools/new.py", "\n")
    write(repo, "kingisdead/game.py", "x = 2\n")
    write(repo, "uv.lock", "\n")
    assert sorted(check.uncommitted_watched()) == [
        "kingisdead/game.py",
        "tests/scenarios/new.json",
        "tools/new.py",
        "uv.lock",
    ]
    git(repo, "mv", "tests/harness.py", "tests/renamed.py")
    assert {"tests/harness.py", "tests/renamed.py"} <= set(check.uncommitted_watched())


def test_check_status_failure_is_none(tmp_path: Path, check: ModuleType) -> None:
    check.ROOT = tmp_path  # not a git repo
    assert check.uncommitted_watched() is None
    assert check.head_sha() is None


def test_check_stamp_path_is_in_git_dir(repo: Path, check: ModuleType) -> None:
    assert check.stamp_path() == repo / ".git" / "kid-last-green"


def test_check_commands_match_ci_order(check: ModuleType) -> None:
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    names = [name for name, _ in check.CHECKS]
    assert names == ["ruff check", "ruff format", "pyright", "pytest"]
    commands = [" ".join(cmd[3:] if cmd[2] == "--quiet" else cmd[2:]) for _, cmd in check.CHECKS]
    assert commands[0] == "ruff check ."
    assert commands[1] == "ruff format --check ."
    assert commands[2] == "pyright"
    assert commands[3].startswith("pytest -q -x")
    assert all(
        cmd in ci
        for cmd in ("uv run ruff check .", "uv run ruff format --check .", "uv run pyright")
    )


def fake_check(code: int, marker: Path | None = None) -> list[str]:
    script = (
        f"import sys; open({str(marker)!r}, 'w').close(); sys.exit({code})"
        if marker
        else f"import sys; sys.exit({code})"
    )
    return [sys.executable, "-c", script]


def test_run_checks_stops_at_first_failure(tmp_path: Path, check: ModuleType) -> None:
    marker = tmp_path / "ran-third"
    check.CHECKS = [("a", fake_check(0)), ("b", fake_check(3)), ("c", fake_check(0, marker))]
    failure = check.run_checks()
    assert failure is not None and failure[0] == "b" and failure[2] == 3
    assert not marker.exists()


def test_run_checks_allows_no_tests_collected(check: ModuleType) -> None:
    check.CHECKS = [("pytest", fake_check(5)), ("after", fake_check(0))]
    assert check.run_checks() is None
    check.CHECKS = [("other", fake_check(5))]
    assert check.run_checks() is not None


class Gate:
    """Call check.main() in-process with run_checks stubbed; `calls` counts stub invocations."""

    def __init__(self, check: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        self.check = check
        self.monkeypatch = monkeypatch
        self.calls = 0

    def __call__(self, failure: tuple[str, list[str], int, str] | None = None) -> int:
        self.calls = 0

        def fake_run_checks() -> tuple[str, list[str], int, str] | None:
            self.calls += 1
            return failure

        self.check.run_checks = fake_run_checks
        self.monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
        return self.check.main()


@pytest.fixture
def gate(check: ModuleType, monkeypatch: pytest.MonkeyPatch) -> Gate:
    monkeypatch.setattr(check.shutil, "which", lambda _name: "/usr/bin/uv")  # pyright: ignore[reportUnknownLambdaType]
    return Gate(check, monkeypatch)


def test_check_main_skips_when_nothing_changed(repo: Path, gate: Gate) -> None:
    (repo / ".git" / "kid-last-green").write_text(git(repo, "rev-parse", "HEAD") + "\n")
    assert gate() == 0
    assert gate.calls == 0


def test_check_main_runs_and_stamps_when_head_moved(
    repo: Path, check: ModuleType, gate: Gate
) -> None:
    assert gate() == 0
    assert gate.calls == 1
    assert check.read_stamp() == git(repo, "rev-parse", "HEAD")
    assert gate() == 0
    assert gate.calls == 0
    write(repo, "tests/test_new.py", "\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "next")
    assert gate() == 0
    assert gate.calls == 1
    assert check.read_stamp() == git(repo, "rev-parse", "HEAD")


def test_check_main_runs_but_does_not_stamp_with_uncommitted_changes(
    repo: Path, check: ModuleType, gate: Gate
) -> None:
    write(repo, "kingisdead/game.py", "x = 2\n")
    assert gate() == 0
    assert gate.calls == 1
    assert check.read_stamp() is None


def test_check_main_failure_exits_2_without_stamp(
    check: ModuleType, gate: Gate, capsys: pytest.CaptureFixture[str]
) -> None:
    assert gate(("pyright", ["uv", "run", "pyright"], 1, "boom\n")) == 2
    err = capsys.readouterr().err
    assert "pyright failed" in err and "boom" in err
    assert check.read_stamp() is None


def test_check_main_warns_and_runs_when_git_status_fails(
    tmp_path: Path, check: ModuleType, gate: Gate, capsys: pytest.CaptureFixture[str]
) -> None:
    check.ROOT = tmp_path
    assert gate() == 0
    assert gate.calls == 1
    assert "git status" in capsys.readouterr().err
    assert not (tmp_path / ".git").exists()


def check_subprocess(repo: Path) -> subprocess.CompletedProcess[str]:
    return run_hook(repo, "check.py", {})


def test_spec_backstop_status_flip_only_is_fine(repo: Path) -> None:
    (repo / ".git" / "kid-last-green").write_text(git(repo, "rev-parse", "HEAD") + "\n")
    set_status(repo, "APPROVED")  # only the Status line differs from the committed DRAFT
    result = check_subprocess(repo)
    assert result.returncode == 0, result.stderr


def test_spec_backstop_trips_on_content_change_when_approved(repo: Path) -> None:
    (repo / ".git" / "kid-last-green").write_text(git(repo, "rev-parse", "HEAD") + "\n")
    set_status(repo, "APPROVED", extra="\n## R-002\nSneaky rule.\n")
    result = check_subprocess(repo)
    assert result.returncode == 2
    assert "locked" in result.stderr


def test_spec_backstop_trips_on_content_and_status_change(repo: Path) -> None:
    (repo / ".git" / "kid-last-green").write_text(git(repo, "rev-parse", "HEAD") + "\n")
    write(
        repo, "docs/RULES_SPEC.md", SPEC_BODY.format(status="APPROVED").replace("First", "Second")
    )
    assert check_subprocess(repo).returncode == 2


@pytest.mark.parametrize("status", ["DRAFT", "AMENDING"])
def test_spec_backstop_ignores_unlocked_spec(repo: Path, status: str) -> None:
    (repo / ".git" / "kid-last-green").write_text(git(repo, "rev-parse", "HEAD") + "\n")
    set_status(repo, status, extra="\n## R-002\nNew rule.\n")
    assert check_subprocess(repo).returncode == 0


def test_check_script_skips_instantly_when_unchanged(repo: Path) -> None:
    (repo / ".git" / "kid-last-green").write_text(git(repo, "rev-parse", "HEAD") + "\n")
    write(repo, "docs/ACTIONS.md", "unwatched change\n")
    result = check_subprocess(repo)
    assert result.returncode == 0
    assert result.stderr == ""
