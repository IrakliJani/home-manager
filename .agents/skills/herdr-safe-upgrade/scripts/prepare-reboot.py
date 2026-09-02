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
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
COPY_MODES = {
    "herdr_migrate.py": 0o700,
    "cutover-wrapper.sh": 0o700,
    "restore-after-reboot.py": 0o700,
    "prepare-reboot.py": 0o700,
}


def run(
    argv: list[str],
    *,
    timeout: float | None = 60,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {shlex.join(argv)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def ping(socket_path: Path) -> dict[str, object]:
    request = json.dumps(
        {"id": "prepare-reboot:ping", "method": "ping", "params": {}},
        separators=(",", ":"),
    ).encode() + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(15)
        connection.connect(str(socket_path))
        connection.sendall(request)
        response = b""
        while b"\n" not in response:
            chunk = connection.recv(65536)
            if not chunk:
                break
            response += chunk
    if b"\n" not in response:
        raise RuntimeError("Herdr ping returned no complete response")
    value = json.loads(response.splitlines()[0])
    if not isinstance(value, dict):
        raise RuntimeError("Herdr ping returned an invalid response")
    if "error" in value:
        raise RuntimeError(f"Herdr ping failed: {value['error']}")
    result = value.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Herdr ping returned no result")
    return result


def server_binary(socket_path: Path) -> tuple[int, Path]:
    lsof = Path("/usr/sbin/lsof")
    ps = Path("/bin/ps")
    if not lsof.is_file() or not ps.is_file():
        raise RuntimeError("reboot preparation currently requires macOS lsof and ps")
    result = run([str(lsof), "-t", "--", str(socket_path)])
    pids = sorted({int(value) for value in result.stdout.split()})
    candidates: list[tuple[int, Path]] = []
    for pid in pids:
        executable_text = run(
            [str(ps), "-p", str(pid), "-o", "comm="],
            check=False,
        ).stdout.strip()
        command_text = run(
            [str(ps), "-p", str(pid), "-o", "command="],
            check=False,
        ).stdout.strip()
        if not executable_text or not command_text:
            continue
        executable = Path(executable_text).resolve()
        try:
            argv = shlex.split(command_text)
        except ValueError:
            continue
        if (
            executable.name == "herdr"
            and executable.is_file()
            and os.access(executable, os.X_OK)
            and len(argv) >= 2
            and Path(argv[0]).resolve() == executable
            and argv[1] == "server"
        ):
            candidates.append((pid, executable))
    if len(candidates) != 1:
        rendered = ", ".join(f"{pid}:{path}" for pid, path in candidates) or "none"
        raise RuntimeError(
            "expected exactly one Herdr server owning "
            f"{socket_path}, found {rendered}"
        )
    return candidates[0]


def binary_version(binary: Path) -> str:
    output = run([str(binary), "--version"], timeout=30).stdout.strip()
    match = re.fullmatch(r"herdr\s+(\S+)", output)
    if not match:
        raise RuntimeError(f"cannot parse Herdr version output: {output!r}")
    return match.group(1)


def stable_recovery_path(value: str) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for part in value.split(os.pathsep):
        if not part or part.startswith("/nix/store/") or part in seen:
            continue
        seen.add(part)
        parts.append(part)
    if not parts:
        return "/usr/bin:/bin:/usr/sbin:/sbin"
    return os.pathsep.join(parts)


def active_home_manager_profile(home: Path) -> tuple[Path, Path]:
    state_home = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
    candidates = [
        state_home / "nix/profiles/home-manager",
        home / ".local/state/nix/profiles/home-manager",
        Path(f"/nix/var/nix/profiles/per-user/{home.name}/home-manager"),
    ]
    seen: set[Path] = set()
    for profile in candidates:
        if profile in seen:
            continue
        seen.add(profile)
        if not (profile.exists() or profile.is_symlink()):
            continue
        generation = profile.resolve()
        if generation.is_dir() and (generation / "activate").is_file():
            return profile, generation
    raise RuntimeError("cannot find the active Home Manager generation")


def add_gc_root(store_path: Path, root: Path) -> None:
    nix_store = shutil.which("nix-store")
    if nix_store is None:
        raise RuntimeError("nix-store is unavailable; cannot pin recovery paths")
    run(
        [
            nix_store,
            "--realise",
            str(store_path),
            "--add-root",
            str(root),
        ],
        timeout=300,
    )


def write_restore_instructions(bundle: Path, shortcut: Path) -> None:
    content = f"""Herdr reboot recovery

After macOS starts, open Terminal or Ghostty outside Herdr and run:

  BUNDLE='{shortcut}'
  \"$BUNDLE/restore-after-reboot.py\" restore
  cat \"$BUNDLE/reboot-success.json\"

Derive the exact captured client and verify it:

  HERDR_BIN=$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[\"new_binary\"])' \"$BUNDLE/migration-config.json\")
  \"$HERDR_BIN\" status

Attach with:

  \"$HERDR_BIN\"

Do not run Herdr before restore. Keep this bundle until every pane is verified.
"""
    path = bundle / "RESTORE-INSTRUCTIONS.txt"
    path.write_text(content)
    path.chmod(0o600)


def replace_shortcut(shortcut: Path, bundle: Path) -> None:
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    if shortcut.exists() and not shortcut.is_symlink():
        raise RuntimeError(f"refusing to replace non-symlink shortcut: {shortcut}")
    temporary = shortcut.with_name(f".{shortcut.name}.{os.getpid()}.tmp")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(bundle)
    os.replace(temporary, shortcut)


def prepare(args: argparse.Namespace) -> dict[str, object]:
    if os.environ.get("HERDR_ENV") != "1":
        raise RuntimeError("run reboot preparation from a live Herdr pane")

    home = Path.home().resolve()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    socket_path = Path(
        args.socket
        or os.environ.get("HERDR_SOCKET_PATH", "")
        or config_home / "herdr/herdr.sock"
    ).expanduser().resolve()
    if not socket_path.exists():
        raise RuntimeError(f"Herdr socket is missing: {socket_path}")

    server_pid, binary = server_binary(socket_path)
    version = binary_version(binary)
    live = ping(socket_path)
    live_version = live.get("version")
    protocol = live.get("protocol")
    if live_version != version or not isinstance(protocol, int):
        raise RuntimeError(
            "live server does not match its executable: "
            f"binary={version}, server={live_version}, protocol={protocol}"
        )

    profile, generation = active_home_manager_profile(home)
    state_home = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
    migrations = Path(args.migrations_dir or state_home / "herdr/migrations").expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_version = re.sub(r"[^A-Za-z0-9._-]+", "-", version)
    bundle = migrations / f"{stamp}-{safe_version}-reboot"
    bundle.mkdir(parents=True, mode=0o700)
    bundle.chmod(0o700)

    for name, mode in COPY_MODES.items():
        source = SCRIPT_DIR / name
        if not source.is_file():
            raise RuntimeError(f"required recovery script is missing: {source}")
        destination = bundle / name
        shutil.copy2(source, destination)
        destination.chmod(mode)

    server_cwd = Path(args.server_cwd or home).expanduser().resolve()
    if not server_cwd.is_dir():
        raise RuntimeError(f"restored server working directory is missing: {server_cwd}")
    config = {
        "repo": str(server_cwd),
        "herdr_config_dir": str(socket_path.parent),
        "socket_path": str(socket_path),
        "old_binary": str(binary),
        "old_version": version,
        "old_protocol": protocol,
        "new_binary": str(binary),
        "new_version": version,
        "new_protocol": protocol,
        "new_generation": str(generation),
        "old_generation": str(generation),
        "profile_path": str(profile),
        "switch_argv": ["/usr/bin/true"],
        "home": str(home),
        "path": stable_recovery_path(
            os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
        ),
        "detected_server_pid": server_pid,
        "reboot_metadata_source": "live-server",
    }
    write_json(bundle / "migration-config.json", config)
    add_gc_root(binary.parents[1], bundle / "herdr-binary-root")
    add_gc_root(generation, bundle / "home-manager-generation-root")

    helper = bundle / "restore-after-reboot.py"
    prepared = run([str(helper), "prepare"], timeout=None)
    checked = run([str(helper), "check"], timeout=120)
    check_result = json.loads(checked.stdout)
    if not isinstance(check_result, dict) or check_result.get("prepared") is not True:
        raise RuntimeError(f"reboot helper did not report readiness:\n{checked.stdout}")

    shortcut = state_home / "herdr/reboot-ready"
    write_restore_instructions(bundle, shortcut)
    replace_shortcut(shortcut, bundle)

    ready = json.loads(prepared.stdout)
    return {
        "bundle": str(bundle),
        "shortcut": str(shortcut),
        "binary": str(binary),
        "version": version,
        "protocol": protocol,
        "server_pid": server_pid,
        "counts": ready.get("counts") if isinstance(ready, dict) else None,
        "prepared": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Derive the live Herdr binary, version, and protocol; create and "
            "validate a same-version macOS reboot-recovery bundle."
        )
    )
    parser.add_argument("--socket", type=Path, help="Herdr socket path")
    parser.add_argument("--migrations-dir", type=Path, help="bundle destination")
    parser.add_argument(
        "--server-cwd",
        type=Path,
        help="working directory for the restored Herdr server (default: HOME)",
    )
    args = parser.parse_args()
    try:
        result = prepare(args)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
