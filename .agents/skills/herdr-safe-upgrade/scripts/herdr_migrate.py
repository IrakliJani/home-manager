#!/usr/bin/python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

BUNDLE = Path(__file__).resolve().parent
CONFIG_PATH = BUNDLE / "migration-config.json"
MANIFEST_PATH = BUNDLE / "manifest.json"
FINAL_MANIFEST_PATH = BUNDLE / "manifest-final.json"
REPORT_PATH = BUNDLE / "validation-report.json"
SUCCESS_PATH = BUNDLE / "success.json"
FAILURE_PATH = BUNDLE / "failure.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    print(f"[{now_iso()}] {message}", flush=True)


def read_json(path: Path) -> object:
    with path.open() as file:
        return json.load(file)


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as file:
        json.dump(value, file, indent=2, sort_keys=True)
        file.write("\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def load_config() -> dict[str, object]:
    value = read_json(CONFIG_PATH)
    if not isinstance(value, dict):
        raise RuntimeError("migration config must be an object")
    return value


def clean_herdr_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base or os.environ)
    for key in list(env):
        if key.startswith("HERDR_"):
            env.pop(key, None)
    return env


def configured_env(config: dict[str, object]) -> dict[str, str]:
    env = clean_herdr_env()
    env["HOME"] = str(config["home"])
    env["PATH"] = str(config["path"])
    return env


def cli_env(socket_path: str, base: dict[str, str] | None = None) -> dict[str, str]:
    env = clean_herdr_env(base)
    env["HERDR_SOCKET_PATH"] = socket_path
    return env


def run(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    timeout: float = 60,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        env=env,
        cwd=cwd,
        timeout=timeout,
        check=False,
        capture_output=capture,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {shlex.join(argv)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def run_json(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    timeout: float = 60,
) -> dict[str, object]:
    result = run(argv, env=env, cwd=cwd, timeout=timeout)
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object from {shlex.join(argv)}")
    return value


def api_request(socket_path: str, method: str, params: dict[str, object]) -> dict[str, object]:
    request_id = f"migration:{method}:{time.time_ns()}"
    payload = json.dumps(
        {"id": request_id, "method": method, "params": params},
        separators=(",", ":"),
    ).encode() + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(15)
        connection.connect(socket_path)
        connection.sendall(payload)
        response = b""
        while b"\n" not in response:
            chunk = connection.recv(1024 * 1024)
            if not chunk:
                break
            response += chunk
    if not response:
        raise RuntimeError(f"empty response for {method}")
    value = json.loads(response.split(b"\n", 1)[0])
    if not isinstance(value, dict):
        raise RuntimeError(f"invalid response for {method}")
    error = value.get("error")
    if error is not None:
        raise RuntimeError(f"Herdr API {method} failed: {json.dumps(error)}")
    result = value.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"Herdr API {method} returned no result")
    return result


def wait_for_server(socket_path: str, protocol: int, timeout: float = 30) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            result = api_request(socket_path, "ping", {})
            if result.get("protocol") != protocol:
                raise RuntimeError(
                    f"expected protocol {protocol}, got {result.get('protocol')}"
                )
            return result
        except (OSError, RuntimeError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(0.1)
    raise RuntimeError(f"Herdr server did not become ready: {last_error}")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def process_start(pid: int) -> datetime:
    result = run(["ps", "-p", str(pid), "-o", "lstart="], timeout=10)
    value = result.stdout.strip()
    if not value:
        raise RuntimeError(f"cannot determine start time for pid {pid}")
    return datetime.strptime(value, "%a %b %d %H:%M:%S %Y").astimezone()


def process_parent(pid: int) -> int | None:
    result = run(["ps", "-p", str(pid), "-o", "ppid="], timeout=10, check=False)
    value = result.stdout.strip()
    return int(value) if value.isdigit() else None


def process_env_value(pid: int, key: str) -> str | None:
    result = run(
        ["ps", "eww", "-p", str(pid), "-o", "command="],
        timeout=10,
        check=False,
    )
    match = re.search(rf"(?:^|\s){re.escape(key)}=([^\s]+)", result.stdout)
    return match.group(1) if match else None


def select_root_process(process_info: dict[str, object]) -> dict[str, object] | None:
    processes_value = process_info.get("foreground_processes", [])
    if not isinstance(processes_value, list) or not processes_value:
        return None
    processes = [value for value in processes_value if isinstance(value, dict)]
    shell_pid = process_info.get("shell_pid")
    if isinstance(shell_pid, int):
        for process in processes:
            pid = process.get("pid")
            if isinstance(pid, int) and process_parent(pid) == shell_pid:
                return process
        for process in processes:
            if process.get("pid") == shell_pid:
                return None
    candidate_pids = {
        process["pid"] for process in processes if isinstance(process.get("pid"), int)
    }
    for process in processes:
        pid = process.get("pid")
        if isinstance(pid, int) and process_parent(pid) not in candidate_pids:
            return process
    return processes[-1]


def option_value(argv: list[str], option: str) -> str | None:
    try:
        index = argv.index(option)
    except ValueError:
        return None
    return argv[index + 1] if index + 1 < len(argv) else None


def index_pi_sessions() -> list[dict[str, object]]:
    root = Path.home() / ".pi" / "agent" / "sessions"
    sessions: list[dict[str, object]] = []
    for path in root.rglob("*.jsonl"):
        try:
            header: dict[str, object] | None = None
            name: str | None = None
            timestamps: list[str] = []
            with path.open(errors="replace") as file:
                for line in file:
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(value, dict):
                        continue
                    if header is None:
                        header = value
                    timestamp = value.get("timestamp")
                    if isinstance(timestamp, str):
                        timestamps.append(timestamp)
                    if value.get("type") == "session_info" and isinstance(
                        value.get("name"), str
                    ):
                        name = value["name"]
            if not header or header.get("type") != "session":
                continue
            session_id = header.get("id")
            cwd = header.get("cwd")
            timestamp = header.get("timestamp")
            if not all(isinstance(item, str) for item in (session_id, cwd, timestamp)):
                continue
            sessions.append(
                {
                    "id": session_id,
                    "path": str(path),
                    "cwd": cwd,
                    "created_at": timestamp,
                    "name": name,
                    "timestamps": timestamps,
                }
            )
        except OSError:
            continue
    return sessions


def resolve_pi_session(
    argv: list[str],
    cwd: str,
    started_at: datetime,
    sessions: list[dict[str, object]],
) -> tuple[dict[str, object] | None, str]:
    same_cwd = [session for session in sessions if session.get("cwd") == cwd]
    explicit = option_value(argv, "--session")
    if explicit:
        matches = [
            session
            for session in sessions
            if isinstance(session.get("id"), str)
            and (
                session["id"] == explicit
                or session["id"].startswith(explicit)
                or session.get("path") == explicit
            )
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Pi --session {explicit!r} resolved to {len(matches)} files")
        return matches[0], "explicit"

    requested_name = option_value(argv, "--name") or option_value(argv, "-n")
    if requested_name:
        matches = [session for session in same_cwd if session.get("name") == requested_name]
        close = [
            session
            for session in matches
            if abs((parse_iso(str(session["created_at"])) - started_at).total_seconds())
            <= 10
        ]
        if len(close) != 1:
            raise RuntimeError(
                f"Pi session name {requested_name!r} in {cwd} resolved to {len(close)} live files"
            )
        return close[0], "name-and-start"

    resume_requested = any(
        option in argv for option in ("--resume", "-r", "--continue", "-c")
    )
    if resume_requested:
        candidates: list[tuple[float, dict[str, object]]] = []
        for session in same_cwd:
            values = session.get("timestamps", [])
            if not isinstance(values, list):
                continue
            deltas = [
                abs((parse_iso(value) - started_at).total_seconds())
                for value in values
                if isinstance(value, str)
            ]
            if deltas:
                candidates.append((min(deltas), session))
        candidates.sort(key=lambda item: item[0])
        if not candidates or candidates[0][0] > 120:
            raise RuntimeError(f"cannot resolve resumed Pi session in {cwd}")
        if len(candidates) > 1 and candidates[1][0] - candidates[0][0] < 0.1:
            raise RuntimeError(f"ambiguous resumed Pi session in {cwd}")
        return candidates[0][1], "resume-event"

    close = [
        session
        for session in same_cwd
        if abs((parse_iso(str(session["created_at"])) - started_at).total_seconds())
        <= 10
    ]
    if len(close) == 1:
        return close[0], "created-at-process-start"
    if len(close) > 1:
        raise RuntimeError(f"ambiguous newly-created Pi session in {cwd}")
    if len(argv) == 1:
        return None, "blank-agent-without-session"
    raise RuntimeError(f"cannot resolve Pi session for command {shlex.join(argv)}")


def pi_resume_argv(original: list[str], session_id: str | None) -> list[str]:
    if not session_id:
        return ["pi"]
    options_with_value = {
        "--provider",
        "--model",
        "--api-key",
        "--system-prompt",
        "--append-system-prompt",
        "--mode",
        "--name",
        "-n",
        "--models",
        "--tools",
        "--exclude-tools",
        "--extension",
        "-e",
        "--skill",
        "--prompt-template",
        "--theme",
        "--thinking",
    }
    selectors_with_value = {"--session", "--session-id", "--fork"}
    selectors = {"--resume", "-r", "--continue", "-c"}
    preserved: list[str] = []
    index = 1
    while index < len(original):
        value = original[index]
        if value in selectors:
            index += 1
            continue
        if value in selectors_with_value:
            index += 2
            continue
        if value in options_with_value:
            if index + 1 >= len(original):
                raise RuntimeError(f"missing value after Pi option {value}")
            if value == "--api-key":
                raise RuntimeError("refusing to persist a Pi API key from argv")
            preserved.extend((value, original[index + 1]))
            index += 2
            continue
        if value.startswith("-"):
            preserved.append(value)
            index += 1
            continue
        # Positional prompts and @files must not be replayed when resuming.
        index += 1
    return ["pi", "--session", session_id, *preserved]


def claude_resume_argv(original: list[str], session_id: str) -> list[str]:
    args = list(original)
    if not args:
        args = ["claude"]
    args[0] = "claude"
    cleaned: list[str] = [args[0]]
    index = 1
    while index < len(args):
        value = args[index]
        if value in ("--resume", "-r", "--session-id"):
            index += 2 if index + 1 < len(args) else 1
            continue
        cleaned.append(value)
        index += 1
    return [cleaned[0], "--resume", session_id, *cleaned[1:]]


def layout_leaves(node: dict[str, object]) -> list[dict[str, object]]:
    node_type = node.get("type")
    if node_type == "pane":
        return [node]
    if node_type != "split":
        raise RuntimeError(f"unknown layout node: {node_type!r}")
    first = node.get("first")
    second = node.get("second")
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise RuntimeError("split node is missing children")
    return layout_leaves(first) + layout_leaves(second)


def copy_runtime_files(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in (
        "config.toml",
        "session.json",
        "session-history.json",
        "release-notes.json",
        ".plugins.lock",
        "herdr.log",
        "herdr-client.log",
        "herdr-server.log",
    ):
        path = source / name
        if path.exists() and path.is_file():
            shutil.copy2(path, destination / name)
            os.chmod(destination / name, 0o600)


def snapshot(output: Path, archive_scrollback: bool) -> dict[str, object]:
    config = load_config()
    old_binary = str(config["old_binary"])
    session_list = run_json([old_binary, "session", "list", "--json"], timeout=30)
    sessions_value = session_list.get("sessions")
    if not isinstance(sessions_value, list):
        raise RuntimeError("Herdr session list returned no sessions")
    pi_sessions = index_pi_sessions()
    captured_sessions: list[dict[str, object]] = []
    for listed in sessions_value:
        if not isinstance(listed, dict):
            continue
        if not listed.get("running"):
            captured_sessions.append({"registry": listed, "running": False})
            continue
        socket_path = listed.get("socket_path")
        session_dir = listed.get("session_dir")
        if not isinstance(socket_path, str) or not isinstance(session_dir, str):
            raise RuntimeError("running session lacks socket or directory")
        ping = api_request(socket_path, "ping", {})
        if ping.get("protocol") != config["old_protocol"]:
            raise RuntimeError(
                f"source server protocol changed: expected {config['old_protocol']}, got {ping.get('protocol')}"
            )
        snapshot_result = api_request(socket_path, "session.snapshot", {})
        live = snapshot_result.get("snapshot")
        if not isinstance(live, dict):
            raise RuntimeError("session.snapshot returned no snapshot")
        agents_result = api_request(socket_path, "agent.list", {})
        agents_value = agents_result.get("agents", [])
        agents = [value for value in agents_value if isinstance(value, dict)] if isinstance(agents_value, list) else []
        agent_by_pane = {
            value["pane_id"]: value
            for value in agents
            if isinstance(value.get("pane_id"), str)
        }
        tabs_value = live.get("tabs", [])
        panes_value = live.get("panes", [])
        workspaces_value = live.get("workspaces", [])
        tabs = [value for value in tabs_value if isinstance(value, dict)] if isinstance(tabs_value, list) else []
        panes = [value for value in panes_value if isinstance(value, dict)] if isinstance(panes_value, list) else []
        workspaces = [value for value in workspaces_value if isinstance(value, dict)] if isinstance(workspaces_value, list) else []

        session_file = Path(session_dir) / "session.json"
        persisted = read_json(session_file) if session_file.exists() else {}
        identity_cwds: list[str | None] = []
        if isinstance(persisted, dict) and isinstance(persisted.get("workspaces"), list):
            for workspace in persisted["workspaces"]:
                identity_cwds.append(
                    workspace.get("identity_cwd") if isinstance(workspace, dict) else None
                )

        layouts: dict[str, dict[str, object]] = {}
        for tab in tabs:
            tab_id = tab.get("tab_id")
            if not isinstance(tab_id, str):
                continue
            result = api_request(
                socket_path,
                "layout.export",
                {"tab_id": tab_id, "pane_id": None},
            )
            layout = result.get("layout")
            if not isinstance(layout, dict):
                raise RuntimeError(f"layout.export returned no layout for {tab_id}")
            layouts[tab_id] = layout

        process_by_pane: dict[str, dict[str, object]] = {}
        restore_by_pane: dict[str, dict[str, object]] = {}
        for pane in panes:
            pane_id = pane.get("pane_id")
            if not isinstance(pane_id, str):
                continue
            process_result = api_request(
                socket_path,
                "pane.process_info",
                {"pane_id": pane_id},
            )
            process_info = process_result.get("process_info")
            if not isinstance(process_info, dict):
                raise RuntimeError(f"pane.process_info returned no data for {pane_id}")
            process_by_pane[pane_id] = process_info
            root_process = select_root_process(process_info)
            agent = agent_by_pane.get(pane_id)
            agent_kind = agent.get("agent") if isinstance(agent, dict) else None
            pane_cwd = pane.get("foreground_cwd") or pane.get("cwd")
            if not isinstance(pane_cwd, str):
                raise RuntimeError(f"pane {pane_id} has no cwd")
            if root_process is None:
                restore_by_pane[pane_id] = {
                    "kind": "shell",
                    "argv": None,
                    "cwd": pane_cwd,
                    "reason": "no foreground process",
                }
                continue
            root_argv_value = root_process.get("argv")
            root_argv = [str(value) for value in root_argv_value] if isinstance(root_argv_value, list) else []
            root_pid = root_process.get("pid")
            root_cwd = root_process.get("cwd") if isinstance(root_process.get("cwd"), str) else pane_cwd
            if agent_kind == "pi":
                if not isinstance(root_pid, int) or not root_argv:
                    raise RuntimeError(f"Pi pane {pane_id} lacks process metadata")
                session, reason = resolve_pi_session(
                    root_argv,
                    root_cwd,
                    process_start(root_pid),
                    pi_sessions,
                )
                session_id = session.get("id") if session else None
                session_path = session.get("path") if session else None
                restore_by_pane[pane_id] = {
                    "kind": "agent",
                    "agent": "pi",
                    "argv": pi_resume_argv(root_argv, str(session_id) if session_id else None),
                    "cwd": root_cwd,
                    "session_id": session_id,
                    "session_path": session_path,
                    "resolution": reason,
                    "original_argv": root_argv,
                }
            elif agent_kind == "claude":
                if not isinstance(root_pid, int):
                    raise RuntimeError(f"Claude pane {pane_id} lacks a root pid")
                process_values = process_info.get("foreground_processes", [])
                process_pids = [
                    value.get("pid")
                    for value in process_values
                    if isinstance(value, dict) and isinstance(value.get("pid"), int)
                ] if isinstance(process_values, list) else []
                session_id = next(
                    (
                        value
                        for value in (
                            process_env_value(pid, "CLAUDE_CODE_SESSION_ID")
                            for pid in process_pids
                        )
                        if value
                    ),
                    None,
                )
                if not session_id:
                    raise RuntimeError(f"Claude pane {pane_id} lacks CLAUDE_CODE_SESSION_ID")
                session_matches = list((Path.home() / ".claude" / "projects").rglob(f"{session_id}.jsonl"))
                if len(session_matches) != 1:
                    raise RuntimeError(
                        f"Claude session {session_id} resolved to {len(session_matches)} files"
                    )
                restore_by_pane[pane_id] = {
                    "kind": "agent",
                    "agent": "claude",
                    "argv": claude_resume_argv(root_argv, session_id),
                    "cwd": root_cwd,
                    "session_id": session_id,
                    "session_path": str(session_matches[0]),
                    "resolution": "process-environment",
                    "original_argv": root_argv,
                }
            elif agent_kind:
                raise RuntimeError(f"unsupported live agent {agent_kind!r} in {pane_id}")
            else:
                if not root_argv:
                    raise RuntimeError(f"running pane {pane_id} has no argv")
                restore_by_pane[pane_id] = {
                    "kind": "command",
                    "argv": root_argv,
                    "cwd": root_cwd,
                    "original_argv": root_argv,
                }

        workspace_records: list[dict[str, object]] = []
        for workspace_index, workspace in enumerate(
            sorted(workspaces, key=lambda value: int(value.get("number", 0)))
        ):
            workspace_id = workspace.get("workspace_id")
            if not isinstance(workspace_id, str):
                continue
            workspace_tabs = sorted(
                [tab for tab in tabs if tab.get("workspace_id") == workspace_id],
                key=lambda value: int(value.get("number", 0)),
            )
            tab_records: list[dict[str, object]] = []
            for tab in workspace_tabs:
                tab_id = tab.get("tab_id")
                if not isinstance(tab_id, str):
                    continue
                layout = layouts[tab_id]
                leaves = layout_leaves(layout["root"])
                pane_records = []
                for leaf in leaves:
                    pane_id = leaf.get("pane_id")
                    if not isinstance(pane_id, str):
                        raise RuntimeError(f"layout leaf in {tab_id} has no pane id")
                    pane = next(
                        (value for value in panes if value.get("pane_id") == pane_id),
                        None,
                    )
                    if pane is None:
                        raise RuntimeError(f"layout references unknown pane {pane_id}")
                    pane_records.append(
                        {
                            "pane": pane,
                            "agent": agent_by_pane.get(pane_id),
                            "process_info": process_by_pane[pane_id],
                            "restore": restore_by_pane[pane_id],
                        }
                    )
                tab_records.append(
                    {
                        "tab": tab,
                        "layout": layout,
                        "panes": pane_records,
                    }
                )
            workspace_records.append(
                {
                    "workspace": workspace,
                    "identity_cwd": identity_cwds[workspace_index]
                    if workspace_index < len(identity_cwds)
                    else None,
                    "tabs": tab_records,
                }
            )

        if archive_scrollback:
            scrollback_dir = BUNDLE / "scrollback" / str(listed.get("name", "default"))
            scrollback_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            environment = cli_env(socket_path)
            for pane in panes:
                pane_id = pane.get("pane_id")
                if not isinstance(pane_id, str):
                    continue
                result = run(
                    [
                        old_binary,
                        "pane",
                        "read",
                        pane_id,
                        "--source",
                        "recent-unwrapped",
                        "--lines",
                        "100000",
                    ],
                    env=environment,
                    timeout=60,
                    check=False,
                )
                path = scrollback_dir / f"{pane_id.replace(':', '_')}.txt"
                path.write_text(result.stdout)
                os.chmod(path, 0o600)

        captured_sessions.append(
            {
                "registry": listed,
                "running": True,
                "ping": ping,
                "snapshot": live,
                "workspaces": workspace_records,
            }
        )

    manifest: dict[str, object] = {
        "manifest_version": 1,
        "captured_at": now_iso(),
        "source": {
            "binary": old_binary,
            "version": config["old_version"],
            "protocol": config["old_protocol"],
        },
        "target": {
            "binary": config["new_binary"],
            "version": config["new_version"],
            "protocol": config["new_protocol"],
        },
        "sessions": captured_sessions,
    }
    write_json(output, manifest)
    return manifest


def validate_manifest(manifest: dict[str, object]) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    counts = {
        "sessions": 0,
        "workspaces": 0,
        "tabs": 0,
        "panes": 0,
        "agents": 0,
        "commands": 0,
        "shells": 0,
    }
    session_ids: set[tuple[str, str]] = set()
    sessions = manifest.get("sessions")
    if not isinstance(sessions, list):
        errors.append("manifest has no sessions")
        sessions = []
    running_sessions = [value for value in sessions if isinstance(value, dict) and value.get("running")]
    counts["sessions"] = len(sessions)
    if len(running_sessions) != 1:
        errors.append(f"expected exactly one running session, found {len(running_sessions)}")
    for session in running_sessions:
        workspaces = session.get("workspaces")
        if not isinstance(workspaces, list):
            errors.append("running session has no workspaces")
            continue
        counts["workspaces"] += len(workspaces)
        for workspace in workspaces:
            if not isinstance(workspace, dict):
                errors.append("invalid workspace record")
                continue
            tabs = workspace.get("tabs")
            if not isinstance(tabs, list) or not tabs:
                errors.append("workspace has no tabs")
                continue
            counts["tabs"] += len(tabs)
            for tab in tabs:
                if not isinstance(tab, dict):
                    errors.append("invalid tab record")
                    continue
                layout = tab.get("layout")
                pane_records = tab.get("panes")
                if not isinstance(layout, dict) or not isinstance(layout.get("root"), dict):
                    errors.append("tab has no exported layout")
                    continue
                if not isinstance(pane_records, list):
                    errors.append("tab has no pane records")
                    continue
                leaf_ids = [leaf.get("pane_id") for leaf in layout_leaves(layout["root"])]
                record_ids = [
                    record.get("pane", {}).get("pane_id")
                    for record in pane_records
                    if isinstance(record, dict) and isinstance(record.get("pane"), dict)
                ]
                if leaf_ids != record_ids:
                    errors.append(f"layout/pane order mismatch in {layout.get('tab_id')}")
                counts["panes"] += len(pane_records)
                for record in pane_records:
                    if not isinstance(record, dict):
                        errors.append("invalid pane record")
                        continue
                    restore = record.get("restore")
                    if not isinstance(restore, dict):
                        errors.append("pane has no restore instruction")
                        continue
                    cwd = restore.get("cwd")
                    if not isinstance(cwd, str) or not Path(cwd).is_dir():
                        errors.append(f"missing pane cwd: {cwd!r}")
                    kind = restore.get("kind")
                    argv = restore.get("argv")
                    if kind == "agent":
                        counts["agents"] += 1
                        agent = restore.get("agent")
                        if agent not in ("pi", "claude"):
                            errors.append(f"unsupported agent kind: {agent!r}")
                        if not isinstance(argv, list) or not argv:
                            errors.append(f"agent {agent!r} has no resume argv")
                        session_id = restore.get("session_id")
                        session_path = restore.get("session_path")
                        if session_id:
                            key = (str(agent), str(session_id))
                            if key in session_ids:
                                errors.append(f"agent session is used twice: {key}")
                            session_ids.add(key)
                            if not isinstance(session_path, str) or not Path(session_path).is_file():
                                errors.append(f"missing agent session file: {session_path!r}")
                        elif restore.get("resolution") != "blank-agent-without-session":
                            errors.append(f"agent {agent!r} has no session identity")
                    elif kind == "command":
                        counts["commands"] += 1
                        if not isinstance(argv, list) or not argv:
                            errors.append("command pane has no argv")
                        elif str(argv[0]).startswith("/") and not Path(str(argv[0])).exists():
                            errors.append(f"command executable disappeared: {argv[0]}")
                    elif kind == "shell":
                        counts["shells"] += 1
                        if argv is not None:
                            errors.append("shell pane unexpectedly has argv")
                    else:
                        errors.append(f"unknown restore kind: {kind!r}")
    expected = {"workspaces": 0, "tabs": 0, "panes": 0, "agents": 0}
    for session in running_sessions:
        live = session.get("snapshot")
        if not isinstance(live, dict):
            errors.append("running session has no raw snapshot")
            continue
        for name in expected:
            values = live.get(name, [])
            if not isinstance(values, list):
                errors.append(f"raw snapshot has invalid {name}")
                continue
            expected[name] += len(values)
    for name, value in expected.items():
        if counts[name] != value:
            errors.append(f"expected {value} {name}, found {counts[name]}")
    classified_panes = counts["agents"] + counts["commands"] + counts["shells"]
    if classified_panes != counts["panes"]:
        errors.append(
            f"classified {classified_panes} panes, but captured {counts['panes']}"
        )
    report: dict[str, object] = {
        "validated_at": now_iso(),
        "valid": not errors,
        "counts": counts,
        "errors": errors,
        "warnings": warnings,
    }
    write_json(REPORT_PATH, report)
    if errors:
        raise RuntimeError("manifest validation failed:\n- " + "\n- ".join(errors))
    return report


def first_leaf(node: dict[str, object]) -> dict[str, object]:
    current = node
    while current.get("type") == "split":
        child = current.get("first")
        if not isinstance(child, dict):
            raise RuntimeError("split has no first child")
        current = child
    if current.get("type") != "pane":
        raise RuntimeError("layout has no first pane")
    return current


def cli_json(
    binary: str,
    socket_path: str,
    args: list[str],
    *,
    base_env: dict[str, str] | None = None,
    timeout: float = 60,
) -> dict[str, object]:
    return run_json(
        [binary, *args],
        env=cli_env(socket_path, base_env),
        timeout=timeout,
    )


def cli_ok(
    binary: str,
    socket_path: str,
    args: list[str],
    *,
    base_env: dict[str, str] | None = None,
    timeout: float = 60,
) -> None:
    run(
        [binary, *args],
        env=cli_env(socket_path, base_env),
        timeout=timeout,
    )


def set_shell_cwd(
    binary: str,
    socket_path: str,
    pane_id: str,
    cwd: str,
    *,
    base_env: dict[str, str] | None = None,
) -> None:
    cli_ok(
        binary,
        socket_path,
        ["pane", "run", pane_id, f"cd {shlex.quote(cwd)}"],
        base_env=base_env,
    )
    deadline = time.monotonic() + 10
    actual_cwd: object = None
    while time.monotonic() < deadline:
        snapshot = api_request(socket_path, "session.snapshot", {}).get("snapshot")
        panes = snapshot.get("panes", []) if isinstance(snapshot, dict) else []
        pane = next(
            (
                value
                for value in panes
                if isinstance(value, dict) and value.get("pane_id") == pane_id
            ),
            None,
        )
        if isinstance(pane, dict):
            actual_cwd = pane.get("foreground_cwd") or pane.get("cwd")
            if actual_cwd == cwd:
                return
        time.sleep(0.05)
    raise RuntimeError(
        f"pane {pane_id} did not change cwd to {cwd!r}; current cwd is {actual_cwd!r}"
    )


def instantiate_layout(
    binary: str,
    socket_path: str,
    node: dict[str, object],
    root_pane_id: str,
    pane_map: dict[str, str],
    *,
    base_env: dict[str, str] | None = None,
) -> None:
    node_type = node.get("type")
    if node_type == "pane":
        old_pane_id = node.get("pane_id")
        if not isinstance(old_pane_id, str):
            raise RuntimeError("source pane has no id")
        pane_map[old_pane_id] = root_pane_id
        return
    if node_type != "split":
        raise RuntimeError(f"unknown layout node {node_type!r}")
    first = node.get("first")
    second = node.get("second")
    direction = node.get("direction")
    ratio = node.get("ratio")
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise RuntimeError("split lacks child")
    if direction not in ("right", "down") or not isinstance(ratio, (int, float)):
        raise RuntimeError("split lacks direction or ratio")
    second_cwd = first_leaf(second).get("cwd")
    if not isinstance(second_cwd, str):
        raise RuntimeError("second split leaf has no cwd")
    response = cli_json(
        binary,
        socket_path,
        [
            "pane",
            "split",
            "--pane",
            root_pane_id,
            "--direction",
            str(direction),
            "--ratio",
            repr(float(ratio)),
            "--cwd",
            second_cwd,
            "--no-focus",
        ],
        base_env=base_env,
    )
    result = response.get("result")
    pane = result.get("pane") if isinstance(result, dict) else None
    new_pane_id = pane.get("pane_id") if isinstance(pane, dict) else None
    if not isinstance(new_pane_id, str):
        raise RuntimeError("pane.split returned no new pane")
    instantiate_layout(
        binary,
        socket_path,
        first,
        root_pane_id,
        pane_map,
        base_env=base_env,
    )
    instantiate_layout(
        binary,
        socket_path,
        second,
        new_pane_id,
        pane_map,
        base_env=base_env,
    )


def restore_manifest(
    manifest: dict[str, object],
    binary: str,
    socket_path: str,
    *,
    base_env: dict[str, str] | None = None,
    run_commands: bool,
) -> dict[str, object]:
    sessions = manifest.get("sessions")
    if not isinstance(sessions, list):
        raise RuntimeError("manifest has no sessions")
    running = [value for value in sessions if isinstance(value, dict) and value.get("running")]
    if len(running) != 1:
        raise RuntimeError("restore requires exactly one running session")
    source = running[0]
    workspaces = source.get("workspaces")
    if not isinstance(workspaces, list):
        raise RuntimeError("manifest has no workspaces")
    existing_result = api_request(socket_path, "workspace.list", {})
    existing_value = existing_result.get("workspaces", [])
    existing_ids = [
        value.get("workspace_id")
        for value in existing_value
        if isinstance(value, dict) and isinstance(value.get("workspace_id"), str)
    ] if isinstance(existing_value, list) else []

    workspace_map: dict[str, str] = {}
    tab_map: dict[str, str] = {}
    pane_map: dict[str, str] = {}
    restore_records: dict[str, dict[str, object]] = {}

    for workspace_record in workspaces:
        if not isinstance(workspace_record, dict):
            raise RuntimeError("invalid workspace")
        workspace = workspace_record.get("workspace")
        tabs = workspace_record.get("tabs")
        if not isinstance(workspace, dict) or not isinstance(tabs, list) or not tabs:
            raise RuntimeError("workspace lacks tabs")
        old_workspace_id = workspace.get("workspace_id")
        label = workspace.get("label")
        if not isinstance(old_workspace_id, str) or not isinstance(label, str):
            raise RuntimeError("workspace lacks id or label")
        first_tab_record = tabs[0]
        if not isinstance(first_tab_record, dict):
            raise RuntimeError("invalid first tab")
        first_layout = first_tab_record.get("layout")
        if not isinstance(first_layout, dict) or not isinstance(first_layout.get("root"), dict):
            raise RuntimeError("first tab has no layout")
        identity_cwd = workspace_record.get("identity_cwd")
        if not isinstance(identity_cwd, str):
            identity_cwd = first_leaf(first_layout["root"]).get("cwd")
        if not isinstance(identity_cwd, str):
            raise RuntimeError("workspace has no identity cwd")
        created = cli_json(
            binary,
            socket_path,
            [
                "workspace",
                "create",
                "--cwd",
                identity_cwd,
                "--label",
                label,
                "--no-focus",
            ],
            base_env=base_env,
        )
        result = created.get("result")
        new_workspace = result.get("workspace") if isinstance(result, dict) else None
        root_tab = result.get("tab") if isinstance(result, dict) else None
        root_pane = result.get("root_pane") if isinstance(result, dict) else None
        new_workspace_id = new_workspace.get("workspace_id") if isinstance(new_workspace, dict) else None
        new_root_tab_id = root_tab.get("tab_id") if isinstance(root_tab, dict) else None
        new_root_pane_id = root_pane.get("pane_id") if isinstance(root_pane, dict) else None
        if not all(isinstance(value, str) for value in (new_workspace_id, new_root_tab_id, new_root_pane_id)):
            raise RuntimeError("workspace.create returned incomplete identifiers")
        workspace_map[old_workspace_id] = new_workspace_id

        for tab_index, tab_record in enumerate(tabs):
            if not isinstance(tab_record, dict):
                raise RuntimeError("invalid tab")
            tab = tab_record.get("tab")
            layout = tab_record.get("layout")
            pane_records = tab_record.get("panes")
            if not isinstance(tab, dict) or not isinstance(layout, dict) or not isinstance(pane_records, list):
                raise RuntimeError("tab record is incomplete")
            old_tab_id = tab.get("tab_id")
            tab_label = tab.get("label")
            root = layout.get("root")
            if not isinstance(old_tab_id, str) or not isinstance(tab_label, str) or not isinstance(root, dict):
                raise RuntimeError("tab lacks id, label, or root")
            tab_cwd = first_leaf(root).get("cwd")
            if not isinstance(tab_cwd, str):
                raise RuntimeError("tab has no root cwd")
            if tab_index == 0:
                new_tab_id = new_root_tab_id
                new_tab_root_pane_id = new_root_pane_id
                cli_ok(
                    binary,
                    socket_path,
                    ["tab", "rename", new_tab_id, tab_label],
                    base_env=base_env,
                )
                if tab_cwd != identity_cwd:
                    set_shell_cwd(
                        binary,
                        socket_path,
                        new_tab_root_pane_id,
                        tab_cwd,
                        base_env=base_env,
                    )
            else:
                created_tab = cli_json(
                    binary,
                    socket_path,
                    [
                        "tab",
                        "create",
                        "--workspace",
                        new_workspace_id,
                        "--cwd",
                        tab_cwd,
                        "--label",
                        tab_label,
                        "--no-focus",
                    ],
                    base_env=base_env,
                )
                tab_result = created_tab.get("result")
                new_tab = tab_result.get("tab") if isinstance(tab_result, dict) else None
                new_root_pane = tab_result.get("root_pane") if isinstance(tab_result, dict) else None
                new_tab_id = new_tab.get("tab_id") if isinstance(new_tab, dict) else None
                new_tab_root_pane_id = new_root_pane.get("pane_id") if isinstance(new_root_pane, dict) else None
                if not isinstance(new_tab_id, str) or not isinstance(new_tab_root_pane_id, str):
                    raise RuntimeError("tab.create returned incomplete identifiers")
            tab_map[old_tab_id] = new_tab_id
            instantiate_layout(
                binary,
                socket_path,
                root,
                new_tab_root_pane_id,
                pane_map,
                base_env=base_env,
            )
            for pane_record in pane_records:
                if not isinstance(pane_record, dict):
                    continue
                pane = pane_record.get("pane")
                restore = pane_record.get("restore")
                if isinstance(pane, dict) and isinstance(pane.get("pane_id"), str) and isinstance(restore, dict):
                    restore_records[pane["pane_id"]] = restore
            if layout.get("zoomed"):
                focused_old = layout.get("focused_pane_id")
                focused_new = pane_map.get(str(focused_old))
                if focused_new:
                    cli_ok(
                        binary,
                        socket_path,
                        ["pane", "zoom", "--pane", focused_new, "--on"],
                        base_env=base_env,
                    )

    for old_workspace_id in existing_ids:
        cli_ok(
            binary,
            socket_path,
            ["workspace", "close", str(old_workspace_id)],
            base_env=base_env,
        )

    if run_commands:
        for old_pane_id, restore in restore_records.items():
            argv = restore.get("argv")
            if not isinstance(argv, list) or not argv:
                continue
            new_pane_id = pane_map.get(old_pane_id)
            if not new_pane_id:
                raise RuntimeError(f"no new pane mapping for {old_pane_id}")
            command = shlex.join([str(value) for value in argv])
            cli_ok(
                binary,
                socket_path,
                ["pane", "run", new_pane_id, command],
                base_env=base_env,
                timeout=30,
            )

    # Restore each workspace's active tab and each tab's focused pane, ending on
    # the globally focused workspace/tab/pane from the source snapshot.
    for workspace_record in workspaces:
        if not isinstance(workspace_record, dict):
            continue
        workspace = workspace_record.get("workspace")
        tabs = workspace_record.get("tabs")
        if not isinstance(workspace, dict) or not isinstance(tabs, list):
            continue
        active_old = workspace.get("active_tab_id")
        active_new = tab_map.get(str(active_old))
        for tab_record in tabs:
            if not isinstance(tab_record, dict):
                continue
            layout = tab_record.get("layout")
            if not isinstance(layout, dict):
                continue
            focused_old = layout.get("focused_pane_id")
            focused_new = pane_map.get(str(focused_old))
            if focused_new:
                api_request(socket_path, "pane.focus", {"pane_id": focused_new})
        if active_new:
            api_request(socket_path, "tab.focus", {"tab_id": active_new})

    source_snapshot = source.get("snapshot")
    if isinstance(source_snapshot, dict):
        focused_workspace = workspace_map.get(str(source_snapshot.get("focused_workspace_id")))
        focused_tab = tab_map.get(str(source_snapshot.get("focused_tab_id")))
        focused_pane = pane_map.get(str(source_snapshot.get("focused_pane_id")))
        if focused_workspace:
            api_request(socket_path, "workspace.focus", {"workspace_id": focused_workspace})
        if focused_tab:
            api_request(socket_path, "tab.focus", {"tab_id": focused_tab})
        if focused_pane:
            api_request(socket_path, "pane.focus", {"pane_id": focused_pane})

    return {
        "workspace_map": workspace_map,
        "tab_map": tab_map,
        "pane_map": pane_map,
    }


def normalized_layout(node: dict[str, object]) -> object:
    if node.get("type") == "pane":
        return {"type": "pane", "cwd": node.get("cwd")}
    first = node.get("first")
    second = node.get("second")
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise RuntimeError("invalid split in normalized layout")
    return {
        "type": "split",
        "direction": node.get("direction"),
        "ratio": round(float(node.get("ratio", 0)), 5),
        "first": normalized_layout(first),
        "second": normalized_layout(second),
    }


def verify_topology(
    manifest: dict[str, object],
    socket_path: str,
    mapping: dict[str, object],
) -> dict[str, object]:
    sessions = manifest["sessions"]
    source = next(value for value in sessions if isinstance(value, dict) and value.get("running"))
    expected_workspaces = source["workspaces"]
    current = api_request(socket_path, "session.snapshot", {})["snapshot"]
    actual_workspaces = current["workspaces"]
    actual_tabs = current["tabs"]
    actual_panes = current["panes"]
    errors: list[str] = []
    layout_mismatches: list[dict[str, object]] = []
    expected_tab_count = sum(len(value["tabs"]) for value in expected_workspaces)
    expected_pane_count = sum(
        len(tab["panes"])
        for workspace in expected_workspaces
        for tab in workspace["tabs"]
    )
    if len(actual_workspaces) != len(expected_workspaces):
        errors.append(f"workspace count {len(actual_workspaces)} != {len(expected_workspaces)}")
    if len(actual_tabs) != expected_tab_count:
        errors.append(f"tab count {len(actual_tabs)} != {expected_tab_count}")
    if len(actual_panes) != expected_pane_count:
        errors.append(f"pane count {len(actual_panes)} != {expected_pane_count}")
    workspace_map = mapping["workspace_map"]
    tab_map = mapping["tab_map"]
    pane_map = mapping["pane_map"]
    for workspace_record in expected_workspaces:
        old_workspace = workspace_record["workspace"]
        new_workspace_id = workspace_map[old_workspace["workspace_id"]]
        actual_workspace = next(
            (value for value in actual_workspaces if value["workspace_id"] == new_workspace_id),
            None,
        )
        if not actual_workspace or actual_workspace.get("label") != old_workspace.get("label"):
            errors.append(f"workspace label mismatch for {old_workspace['workspace_id']}")
        elif actual_workspace.get("active_tab_id") != tab_map.get(str(old_workspace.get("active_tab_id"))):
            errors.append(f"active tab mismatch for {old_workspace['workspace_id']}")
        for tab_record in workspace_record["tabs"]:
            old_tab = tab_record["tab"]
            new_tab_id = tab_map[old_tab["tab_id"]]
            actual_tab = next((value for value in actual_tabs if value["tab_id"] == new_tab_id), None)
            if not actual_tab or actual_tab.get("label") != old_tab.get("label"):
                errors.append(f"tab label mismatch for {old_tab['tab_id']}")
            exported = api_request(
                socket_path,
                "layout.export",
                {"tab_id": new_tab_id, "pane_id": None},
            )["layout"]
            expected_layout = normalized_layout(tab_record["layout"]["root"])
            actual_layout = normalized_layout(exported["root"])
            if actual_layout != expected_layout:
                errors.append(f"layout mismatch for {old_tab['tab_id']}")
                layout_mismatches.append(
                    {
                        "source_tab_id": old_tab["tab_id"],
                        "target_tab_id": new_tab_id,
                        "expected": expected_layout,
                        "actual": actual_layout,
                    }
                )
            if bool(exported.get("zoomed")) != bool(tab_record["layout"].get("zoomed")):
                errors.append(f"zoom mismatch for {old_tab['tab_id']}")
            expected_focused_pane = pane_map.get(str(tab_record["layout"].get("focused_pane_id")))
            if exported.get("focused_pane_id") != expected_focused_pane:
                errors.append(f"focused pane mismatch for {old_tab['tab_id']}")
    source_snapshot = source.get("snapshot")
    if isinstance(source_snapshot, dict):
        if current.get("focused_workspace_id") != workspace_map.get(str(source_snapshot.get("focused_workspace_id"))):
            errors.append("global focused workspace mismatch")
        if current.get("focused_tab_id") != tab_map.get(str(source_snapshot.get("focused_tab_id"))):
            errors.append("global focused tab mismatch")
        if current.get("focused_pane_id") != pane_map.get(str(source_snapshot.get("focused_pane_id"))):
            errors.append("global focused pane mismatch")
    return {
        "verified_at": now_iso(),
        "valid": not errors,
        "errors": errors,
        "layout_mismatches": layout_mismatches,
        "counts": {
            "workspaces": len(actual_workspaces),
            "tabs": len(actual_tabs),
            "panes": len(actual_panes),
            "agents": len(current.get("agents", [])),
        },
        "snapshot": current,
    }


def start_server(
    binary: str,
    *,
    env: dict[str, str],
    cwd: str,
    log_path: Path,
) -> subprocess.Popen[bytes]:
    output = log_path.open("ab", buffering=0)
    process = subprocess.Popen(
        [binary, "server"],
        env=clean_herdr_env(env),
        cwd=cwd,
        stdout=output,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return process


def stop_server(binary: str, socket_path: str, env: dict[str, str]) -> None:
    run(
        [binary, "server", "stop"],
        env=cli_env(socket_path, env),
        timeout=30,
        check=False,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            api_request(socket_path, "ping", {})
        except (OSError, RuntimeError):
            return
        time.sleep(0.1)
    raise RuntimeError("Herdr server did not stop")


def self_test(manifest: dict[str, object]) -> dict[str, object]:
    config = load_config()
    new_binary = str(config["new_binary"])
    report_path = BUNDLE / "self-test-report.json"
    saved_log_path = BUNDLE / "self-test-server.log"
    for stale_path in (report_path, saved_log_path):
        stale_path.unlink(missing_ok=True)
    root = Path("/tmp") / f"herdr-migration-test-{os.getpid()}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(mode=0o700)
    env = clean_herdr_env()
    env["HOME"] = str(root)
    env["XDG_CONFIG_HOME"] = str(root / ".c")
    socket_path = str(root / ".c" / "herdr" / "herdr.sock")
    server_log_path = root / "server.log"
    process: subprocess.Popen[bytes] | None = None
    try:
        process = start_server(
            new_binary,
            env=env,
            cwd=str(root),
            log_path=server_log_path,
        )
        wait_for_server(socket_path, int(config["new_protocol"]), timeout=30)
        mapping = restore_manifest(
            manifest,
            new_binary,
            socket_path,
            base_env=env,
            run_commands=False,
        )
        verification = verify_topology(manifest, socket_path, mapping)
        write_json(report_path, verification)
        if not verification["valid"]:
            raise RuntimeError(
                "isolated topology restore failed; inspect self-test-report.json:\n- "
                + "\n- ".join(str(value) for value in verification["errors"])
            )
        return verification
    except Exception as error:
        if not report_path.exists():
            write_json(
                report_path,
                {
                    "verified_at": now_iso(),
                    "valid": False,
                    "errors": [str(error)],
                    "layout_mismatches": [],
                    "counts": {},
                },
            )
        raise
    finally:
        if process is not None:
            try:
                stop_server(new_binary, socket_path, env)
            except Exception:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        if server_log_path.exists():
            shutil.copy2(server_log_path, saved_log_path)
            os.chmod(saved_log_path, 0o600)
        shutil.rmtree(root, ignore_errors=True)


def move_session_state(config_dir: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("session.json", "session-history.json"):
        source = config_dir / name
        if source.exists():
            target = destination / name
            if target.exists():
                target.unlink()
            shutil.move(str(source), str(target))
            os.chmod(target, 0o600)


def restore_legacy_state(config_dir: Path, source: Path) -> None:
    for name in ("session.json", "session-history.json"):
        current = config_dir / name
        if current.exists():
            current.unlink()
        archived = source / name
        if archived.exists():
            shutil.copy2(archived, current)


def run_restore_commands_on_existing(
    manifest: dict[str, object],
    binary: str,
    socket_path: str,
    env: dict[str, str],
) -> None:
    sessions = manifest["sessions"]
    source = next(value for value in sessions if isinstance(value, dict) and value.get("running"))
    panes = api_request(socket_path, "pane.list", {}).get("panes", [])
    current_ids = {
        value.get("pane_id") for value in panes if isinstance(value, dict)
    } if isinstance(panes, list) else set()
    for workspace in source["workspaces"]:
        for tab in workspace["tabs"]:
            for pane_record in tab["panes"]:
                pane_id = pane_record["pane"]["pane_id"]
                restore = pane_record["restore"]
                argv = restore.get("argv")
                if pane_id not in current_ids or not isinstance(argv, list) or not argv:
                    continue
                cli_ok(
                    binary,
                    socket_path,
                    ["pane", "run", pane_id, shlex.join([str(value) for value in argv])],
                    base_env=env,
                )


def rollback(manifest: dict[str, object], reason: str) -> dict[str, object]:
    config = load_config()
    old_binary = str(config["old_binary"])
    new_binary = str(config["new_binary"])
    socket_path = str(config["socket_path"])
    config_dir = Path(str(config["herdr_config_dir"]))
    env = configured_env(config)
    log(f"rollback: {reason}")
    try:
        ping = api_request(socket_path, "ping", {})
        protocol = ping.get("protocol")
        stop_server(new_binary if protocol == config["new_protocol"] else old_binary, socket_path, env)
    except Exception as error:
        log(f"rollback stop warning: {error}")
    failed_state = BUNDLE / f"failed-state-{int(time.time())}"
    move_session_state(config_dir, failed_state)
    legacy_state = BUNDLE / "post-stop-config"
    restore_legacy_state(config_dir, legacy_state)
    old_activate = str(config["old_generation"]) + "/activate"
    activation = run([old_activate], env=env, timeout=600, check=False)
    log(f"rollback activation exit={activation.returncode}")
    process = start_server(
        old_binary,
        env=env,
        cwd=str(config["repo"]),
        log_path=BUNDLE / "rollback-server.log",
    )
    wait_for_server(socket_path, int(config["old_protocol"]), timeout=30)
    run_restore_commands_on_existing(manifest, old_binary, socket_path, env)
    result = {
        "rolled_back_at": now_iso(),
        "reason": reason,
        "old_server_pid": process.pid,
        "protocol": config["old_protocol"],
    }
    write_json(BUNDLE / "rollback.json", result)
    return result


def wait_for_processes(
    manifest: dict[str, object],
    socket_path: str,
    pane_map: dict[str, str],
    timeout: float = 180,
) -> dict[str, object]:
    sessions = manifest["sessions"]
    source = next(value for value in sessions if isinstance(value, dict) and value.get("running"))
    expected: dict[str, dict[str, object]] = {}
    for workspace in source["workspaces"]:
        for tab in workspace["tabs"]:
            for pane_record in tab["panes"]:
                restore = pane_record["restore"]
                if restore.get("argv"):
                    expected[pane_map[pane_record["pane"]["pane_id"]]] = restore
    deadline = time.monotonic() + timeout
    last_missing: list[str] = []
    while time.monotonic() < deadline:
        snapshot_value = api_request(socket_path, "session.snapshot", {})["snapshot"]
        agents_value = snapshot_value.get("agents", [])
        agent_by_pane = {
            value.get("pane_id"): value.get("agent")
            for value in agents_value
            if isinstance(value, dict)
        } if isinstance(agents_value, list) else {}
        missing: list[str] = []
        for pane_id, restore in expected.items():
            if restore.get("kind") == "agent":
                if agent_by_pane.get(pane_id) != restore.get("agent"):
                    missing.append(pane_id)
                continue
            result = api_request(socket_path, "pane.process_info", {"pane_id": pane_id})
            info = result.get("process_info")
            processes = info.get("foreground_processes") if isinstance(info, dict) else None
            shell_pid = info.get("shell_pid") if isinstance(info, dict) else None
            has_foreground_command = isinstance(processes, list) and any(
                isinstance(process, dict) and process.get("pid") != shell_pid
                for process in processes
            )
            if not has_foreground_command:
                missing.append(pane_id)
        if not missing:
            return {
                "ready": True,
                "checked_at": now_iso(),
                "expected_processes": len(expected),
                "running_processes": len(expected),
                "detected_agents": len(agent_by_pane),
                "missing": [],
            }
        last_missing = missing
        time.sleep(1)
    snapshot_value = api_request(socket_path, "session.snapshot", {})["snapshot"]
    agents_value = snapshot_value.get("agents", [])
    detected_agents = len(agents_value) if isinstance(agents_value, list) else 0
    return {
        "ready": False,
        "checked_at": now_iso(),
        "expected_processes": len(expected),
        "running_processes": len(expected) - len(last_missing),
        "detected_agents": detected_agents,
        "missing": last_missing,
    }


def cutover_preflight(config: dict[str, object]) -> tuple[list[str], str, str, str]:
    switch_argv = config.get("switch_argv")
    if not isinstance(switch_argv, list) or not switch_argv or not all(
        isinstance(value, str) for value in switch_argv
    ):
        raise RuntimeError("migration config requires switch_argv as a string array")
    if not os.path.isabs(switch_argv[0]) or not os.access(switch_argv[0], os.X_OK):
        raise RuntimeError("switch_argv must start with an absolute executable")
    profile_path_value = config.get("profile_path")
    old_generation_value = config.get("old_generation")
    new_generation_value = config.get("new_generation")
    if not isinstance(profile_path_value, str):
        raise RuntimeError("migration config requires profile_path")
    if not isinstance(old_generation_value, str):
        raise RuntimeError("migration config requires old_generation")
    if not isinstance(new_generation_value, str):
        raise RuntimeError("migration config requires new_generation")
    profile_path = os.path.expanduser(profile_path_value)
    old_generation = os.path.realpath(old_generation_value)
    new_generation = os.path.realpath(new_generation_value)
    active_generation = os.path.realpath(profile_path)
    if active_generation != old_generation:
        raise RuntimeError(
            "active Home Manager generation changed since snapshot preparation: "
            f"expected {old_generation}, found {active_generation}"
        )
    if not Path(new_generation).is_dir() or not (Path(new_generation) / "activate").is_file():
        raise RuntimeError(f"built target generation is unavailable: {new_generation}")
    for role, binary in (
        ("old", config.get("old_binary")),
        ("new", config.get("new_binary")),
    ):
        if (
            not isinstance(binary, str)
            or not os.path.isabs(binary)
            or not os.access(binary, os.X_OK)
        ):
            raise RuntimeError(f"{role} Herdr binary is unavailable: {binary}")
    return [str(value) for value in switch_argv], profile_path, old_generation, new_generation


def cutover() -> None:
    config = load_config()
    switch_argv, profile_path, old_generation, new_generation = cutover_preflight(config)
    lock_path = BUNDLE / "cutover.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
    except FileExistsError:
        raise RuntimeError("cutover already started")
    env = configured_env(config)
    old_binary = str(config["old_binary"])
    new_binary = str(config["new_binary"])
    socket_path = str(config["socket_path"])
    config_dir = Path(str(config["herdr_config_dir"]))
    manifest: dict[str, object] | None = None
    server_process: subprocess.Popen[bytes] | None = None
    try:
        log(
            "generation preflight passed: "
            f"source={old_generation} target={new_generation}"
        )
        log(f"capturing final protocol-{config['old_protocol']} manifest")
        manifest = snapshot(FINAL_MANIFEST_PATH, archive_scrollback=False)
        report = validate_manifest(manifest)
        log(f"final manifest valid: {json.dumps(report['counts'], sort_keys=True)}")
        copy_runtime_files(config_dir, BUNDLE / "pre-stop-config")
        log(f"stopping Herdr {config['old_version']} with the absolute old client")
        stop_server(old_binary, socket_path, env)
        copy_runtime_files(config_dir, BUNDLE / "post-stop-config")
        move_session_state(config_dir, BUNDLE / "legacy-session-state")
        log(f"running activation command: {shlex.join(switch_argv)}")
        switch = run(
            switch_argv,
            env=env,
            cwd=str(config["repo"]),
            timeout=1800,
            check=False,
        )
        (BUNDLE / "home-manager-switch.stdout.log").write_text(switch.stdout)
        (BUNDLE / "home-manager-switch.stderr.log").write_text(switch.stderr)
        if switch.returncode != 0:
            raise RuntimeError(f"Home Manager switch failed with exit {switch.returncode}")
        active_generation = os.path.realpath(profile_path)
        if active_generation != new_generation:
            raise RuntimeError(
                "Home Manager activated an unverified generation: "
                f"expected {new_generation}, found {active_generation}"
            )
        version = run([new_binary, "--version"], env=env, timeout=30).stdout.strip()
        log(f"activated {version}")
        server_process = start_server(
            new_binary,
            env=env,
            cwd=str(config["repo"]),
            log_path=BUNDLE / "new-server.log",
        )
        ping = wait_for_server(socket_path, int(config["new_protocol"]), timeout=30)
        log(f"new server ready: version={ping.get('version')} protocol={ping.get('protocol')}")
        mapping = restore_manifest(
            manifest,
            new_binary,
            socket_path,
            base_env=env,
            run_commands=True,
        )
        topology = verify_topology(manifest, socket_path, mapping)
        write_json(BUNDLE / "topology-verification-report.json", topology)
        if not topology["valid"]:
            raise RuntimeError(
                "restored topology verification failed: "
                + "; ".join(str(value) for value in topology["errors"])
            )
        process_health = wait_for_processes(
            manifest,
            socket_path,
            mapping["pane_map"],
        )
        if not process_health["ready"]:
            raise RuntimeError(
                f"restored panes did not start: {process_health['missing']}"
            )
        result = {
            "completed_at": now_iso(),
            "source": manifest["source"],
            "target": manifest["target"],
            "topology": topology["counts"],
            "process_health": process_health,
            "active_generation": active_generation,
            "server_pid": server_process.pid if server_process else None,
            "bundle": str(BUNDLE),
        }
        write_json(SUCCESS_PATH, result)
        log("migration completed successfully")
        run(
            [
                "osascript",
                "-e",
                f'display notification "Herdr {config["new_version"]} restored successfully" with title "Herdr migration"',
            ],
            timeout=15,
            check=False,
        )
    except Exception as error:
        trace = traceback.format_exc()
        failure = {
            "failed_at": now_iso(),
            "error": str(error),
            "traceback": trace,
        }
        write_json(FAILURE_PATH, failure)
        log(trace)
        if manifest is not None:
            try:
                failure["rollback"] = rollback(manifest, str(error))
                write_json(FAILURE_PATH, failure)
            except Exception:
                failure["rollback_error"] = traceback.format_exc()
                write_json(FAILURE_PATH, failure)
                log(failure["rollback_error"])
        run(
            [
                "osascript",
                "-e",
                'display notification "Migration failed; inspect cutover.log" with title "Herdr migration"',
            ],
            timeout=15,
            check=False,
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight")
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--archive-scrollback", action="store_true")
    subparsers.add_parser("validate")
    subparsers.add_parser("self-test")
    subparsers.add_parser("cutover")
    args = parser.parse_args()
    if args.command == "preflight":
        _, _, old_generation, new_generation = cutover_preflight(load_config())
        log(
            "cutover preflight passed: "
            f"source={old_generation} target={new_generation}"
        )
    elif args.command == "snapshot":
        value = snapshot(MANIFEST_PATH, args.archive_scrollback)
        report = validate_manifest(value)
        log(f"snapshot complete: {json.dumps(report['counts'], sort_keys=True)}")
    elif args.command == "validate":
        value = read_json(MANIFEST_PATH)
        if not isinstance(value, dict):
            raise RuntimeError("manifest must be an object")
        report = validate_manifest(value)
        log(f"manifest valid: {json.dumps(report['counts'], sort_keys=True)}")
    elif args.command == "self-test":
        value = read_json(MANIFEST_PATH)
        if not isinstance(value, dict):
            raise RuntimeError("manifest must be an object")
        report = self_test(value)
        log(f"self-test passed: {json.dumps(report['counts'], sort_keys=True)}")
    elif args.command == "cutover":
        cutover()


if __name__ == "__main__":
    main()
