#!/usr/bin/python3
from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from pathlib import Path

import herdr_migrate as migration

BUNDLE = Path(__file__).resolve().parent
MANIFEST_PATH = BUNDLE / "manifest.json"
READY_PATH = BUNDLE / "reboot-ready.json"
SUCCESS_PATH = BUNDLE / "reboot-success.json"
FAILURE_PATH = BUNDLE / "reboot-failure.json"
LOCK_PATH = BUNDLE / "reboot-restore.lock"


def load_manifest() -> dict[str, object]:
    value = migration.read_json(MANIFEST_PATH)
    if not isinstance(value, dict):
        raise RuntimeError("manifest must be an object")
    migration.validate_manifest(value)
    return value


def validate_reboot_config(config: dict[str, object]) -> None:
    source = (
        config.get("old_binary"),
        config.get("old_version"),
        config.get("old_protocol"),
    )
    target = (
        config.get("new_binary"),
        config.get("new_version"),
        config.get("new_protocol"),
    )
    if source != target:
        raise RuntimeError(
            "reboot recovery requires identical source and target Herdr; "
            "use the protocol-upgrade cutover for version changes"
        )
    binary = Path(str(config["new_binary"]))
    if not binary.is_file():
        raise RuntimeError(f"Herdr binary is missing: {binary}")


def current_ping(socket_path: str) -> dict[str, object] | None:
    try:
        return migration.api_request(socket_path, "ping", {})
    except (OSError, RuntimeError, json.JSONDecodeError):
        return None


def prepare() -> None:
    if os.environ.get("HERDR_ENV") != "1":
        raise RuntimeError("prepare must run from a live Herdr-managed pane")
    if LOCK_PATH.exists() or SUCCESS_PATH.exists():
        raise RuntimeError("this reboot bundle has already been used")
    READY_PATH.unlink(missing_ok=True)

    config = migration.load_config()
    validate_reboot_config(config)
    manifest = migration.snapshot(MANIFEST_PATH, archive_scrollback=True)
    validation = migration.validate_manifest(manifest)
    self_test = migration.self_test(manifest)
    config_dir = Path(str(config["herdr_config_dir"]))
    migration.copy_runtime_files(config_dir, BUNDLE / "pre-reboot-config")
    result = {
        "prepared_at": migration.now_iso(),
        "bundle": str(BUNDLE),
        "source": manifest["source"],
        "counts": validation["counts"],
        "self_test": self_test["counts"],
    }
    migration.write_json(READY_PATH, result)
    print(json.dumps(result, indent=2, sort_keys=True))


def check() -> None:
    config = migration.load_config()
    validate_reboot_config(config)
    manifest = load_manifest()
    report = migration.validate_manifest(manifest)
    result = {
        "bundle": str(BUNDLE),
        "binary": str(config["new_binary"]),
        "protocol": config["new_protocol"],
        "counts": report["counts"],
        "prepared": READY_PATH.exists(),
        "already_restored": SUCCESS_PATH.exists(),
        "restore_started": LOCK_PATH.exists(),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


def rollback(
    manifest: dict[str, object],
    *,
    binary: str,
    socket_path: str,
    protocol: int,
    env: dict[str, str],
    config_dir: Path,
    archived_state: Path,
    reason: str,
) -> dict[str, object]:
    migration.log(f"reboot rollback: {reason}")
    try:
        if current_ping(socket_path) is not None:
            migration.stop_server(binary, socket_path, env)
    except Exception as error:
        migration.log(f"rollback stop warning: {error}")

    failed_state = BUNDLE / f"failed-reboot-state-{int(time.time())}"
    migration.move_session_state(config_dir, failed_state)
    source_state = archived_state
    if not any(
        (source_state / name).exists()
        for name in ("session.json", "session-history.json")
    ):
        source_state = BUNDLE / "pre-reboot-config"
    migration.restore_legacy_state(config_dir, source_state)

    config = migration.load_config()
    process = migration.start_server(
        binary,
        env=env,
        cwd=str(config["repo"]),
        log_path=BUNDLE / "reboot-rollback-server.log",
    )
    migration.wait_for_server(socket_path, protocol, timeout=30)
    migration.run_restore_commands_on_existing(
        manifest,
        binary,
        socket_path,
        env,
    )
    result = {
        "rolled_back_at": migration.now_iso(),
        "reason": reason,
        "server_pid": process.pid,
        "restored_state_from": str(source_state),
    }
    migration.write_json(BUNDLE / "reboot-rollback.json", result)
    return result


def restore() -> None:
    if os.environ.get("HERDR_ENV") == "1":
        raise RuntimeError(
            "run restore from Terminal/Ghostty outside Herdr; it stops the Herdr server"
        )
    if not READY_PATH.exists():
        raise RuntimeError(f"reboot bundle was not prepared: {READY_PATH}")
    if SUCCESS_PATH.exists():
        raise RuntimeError(f"reboot restore already succeeded: {SUCCESS_PATH}")

    config = migration.load_config()
    validate_reboot_config(config)
    manifest = load_manifest()
    env = migration.configured_env(config)
    binary = str(config["new_binary"])
    version = str(config["new_version"])
    protocol = int(config["new_protocol"])
    socket_path = str(config["socket_path"])
    config_dir = Path(str(config["herdr_config_dir"]))
    archived_state = BUNDLE / "post-reboot-session-state"
    state_archived = False
    server_process = None

    try:
        descriptor = os.open(
            LOCK_PATH,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
    except FileExistsError as error:
        raise RuntimeError(f"reboot restore already started: {LOCK_PATH}") from error

    try:
        ping = current_ping(socket_path)
        if ping is not None:
            if ping.get("protocol") != protocol or ping.get("version") != version:
                raise RuntimeError(
                    "running Herdr does not match the prepared reboot bundle: "
                    f"version={ping.get('version')} protocol={ping.get('protocol')}"
                )
            migration.log(
                "stopping post-reboot Herdr server before deterministic restore"
            )
            migration.stop_server(binary, socket_path, env)

        migration.copy_runtime_files(config_dir, BUNDLE / "post-reboot-config")
        migration.move_session_state(config_dir, archived_state)
        state_archived = True
        socket_file = Path(socket_path)
        if socket_file.exists():
            socket_file.unlink()

        migration.log("starting an empty Herdr server")
        server_process = migration.start_server(
            binary,
            env=env,
            cwd=str(config["repo"]),
            log_path=BUNDLE / "reboot-server.log",
        )
        started = migration.wait_for_server(socket_path, protocol, timeout=30)
        if started.get("version") != version:
            raise RuntimeError(
                f"started Herdr {started.get('version')}, expected {version}"
            )

        migration.log(
            "restoring workspaces, tabs, panes, agents, focus, zoom, and ratios"
        )
        mapping = migration.restore_manifest(
            manifest,
            binary,
            socket_path,
            base_env=env,
            run_commands=True,
        )
        topology = migration.verify_topology(manifest, socket_path, mapping)
        if not topology["valid"]:
            raise RuntimeError(
                "restored topology verification failed: "
                + "; ".join(str(value) for value in topology["errors"])
            )
        pane_map = mapping.get("pane_map")
        if not isinstance(pane_map, dict):
            raise RuntimeError("restore returned no pane mapping")
        process_health = migration.wait_for_processes(
            manifest,
            socket_path,
            pane_map,
        )
        if not process_health["ready"]:
            raise RuntimeError(
                f"restored panes did not start: {process_health['missing']}"
            )
        topology = migration.verify_topology(manifest, socket_path, mapping)
        if not topology["valid"]:
            raise RuntimeError(
                "final topology verification failed: "
                + "; ".join(str(value) for value in topology["errors"])
            )

        result = {
            "completed_at": migration.now_iso(),
            "bundle": str(BUNDLE),
            "server_pid": server_process.pid if server_process else None,
            "topology": topology["counts"],
            "process_health": process_health,
            "mapping": mapping,
        }
        migration.write_json(SUCCESS_PATH, result)
        migration.log("reboot restore completed successfully")
        migration.run(
            [
                "osascript",
                "-e",
                'display notification "Herdr sessions restored successfully" with title "Herdr reboot recovery"',
            ],
            timeout=15,
            check=False,
        )
    except Exception as error:
        failure: dict[str, object] = {
            "failed_at": migration.now_iso(),
            "error": str(error),
            "traceback": traceback.format_exc(),
        }
        migration.write_json(FAILURE_PATH, failure)
        migration.log(str(failure["traceback"]))
        if state_archived:
            try:
                failure["rollback"] = rollback(
                    manifest,
                    binary=binary,
                    socket_path=socket_path,
                    protocol=protocol,
                    env=env,
                    config_dir=config_dir,
                    archived_state=archived_state,
                    reason=str(error),
                )
            except Exception:
                failure["rollback_error"] = traceback.format_exc()
            migration.write_json(FAILURE_PATH, failure)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "check", "restore"))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "check":
        check()
    elif args.command == "restore":
        restore()


if __name__ == "__main__":
    main()
