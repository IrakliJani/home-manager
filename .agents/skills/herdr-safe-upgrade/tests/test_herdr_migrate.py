from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/herdr_migrate.py"
LOADER = importlib.machinery.SourceFileLoader("herdr_migrate", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = MODULE
LOADER.exec_module(MODULE)


class HerdrMigrateTests(unittest.TestCase):
    def test_agent_can_replace_the_pane_shell_process(self) -> None:
        process = {"pid": 42, "argv": ["/nix/store/pi/bin/pi"]}
        process_info = {
            "shell_pid": 42,
            "foreground_processes": [process],
        }

        self.assertIsNone(MODULE.select_root_process(process_info))
        self.assertIs(MODULE.select_root_process(process_info, "pi"), process)

    def test_new_agent_session_supersedes_startup_session(self) -> None:
        startup = {
            "id": "startup",
            "path": "/sessions/startup.jsonl",
            "cwd": "/old",
            "created_at": "2026-09-04T09:44:13Z",
        }
        current = {
            "id": "current",
            "path": "/sessions/current.jsonl",
            "cwd": "/current",
            "created_at": "2026-09-04T10:13:25Z",
        }

        resolved, reason = MODULE.resolve_pi_session(
            ["pi", "--session", "startup"],
            "/current",
            datetime(2026, 9, 4, 9, 58, 16, tzinfo=timezone.utc),
            [startup, current],
            current["path"],
        )

        self.assertIs(resolved, current)
        self.assertEqual(reason, "agent-session-created-after-process-start")

    def test_old_conflicting_agent_session_is_rejected(self) -> None:
        startup = {
            "id": "startup",
            "path": "/sessions/startup.jsonl",
            "cwd": "/current",
            "created_at": "2026-09-04T09:44:13Z",
        }
        conflicting = {
            "id": "conflicting",
            "path": "/sessions/conflicting.jsonl",
            "cwd": "/current",
            "created_at": "2026-09-04T09:45:00Z",
        }

        with self.assertRaisesRegex(RuntimeError, "metadata disagree"):
            MODULE.resolve_pi_session(
                ["pi", "--session", "startup"],
                "/current",
                datetime(2026, 9, 4, 9, 58, 16, tzinfo=timezone.utc),
                [startup, conflicting],
                conflicting["path"],
            )


if __name__ == "__main__":
    unittest.main()
