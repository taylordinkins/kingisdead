---
name: output-policy
description: Callers sometimes ask the rules-auditor to save its findings to docs/phase-reports/...; the agent definition limits writes to agent memory, so return the content instead
metadata:
  type: feedback
---

The rules-auditor writes only to its agent-memory directory, even when the orchestrator's task asks
for a findings file such as `docs/phase-reports/unit-13-audit.md`. Put the complete markdown in the
SubagentHandback message and tell the caller to save it at the requested path.

**Why:** the agent definition says "The only files you write are in your agent memory directory",
and an agent message can't override that. A harness hook also rejects memory filenames containing
"report". First seen in Phase 2 unit 13 (2026-10-30).
**How to apply:** when a task asks for a findings file, return paste-ready markdown plus the target
path, and say plainly that the file was not written.
