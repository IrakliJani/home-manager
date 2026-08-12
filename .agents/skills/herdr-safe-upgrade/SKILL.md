---
name: herdr-safe-upgrade
description: Safely upgrades Herdr across incompatible socket protocols or preserves Herdr across a macOS reboot while rebuilding every live workspace, tab, split pane, agent session, foreground command, label, ratio, zoom, and focus state. Use for Home Manager or Nix Herdr upgrades where switching the client would strand an older running server, and for reboot-safe session recovery.
compatibility: macOS, launchctl, Python 3.9+, Herdr socket API, Nix/Home Manager
---

# Herdr Safe Upgrade and Reboot Recovery

Use a declarative manifest and a detached one-shot cutover for upgrades. Use the manual reboot helper for same-version macOS restarts. Never rely on a new Herdr client talking to an old-protocol server.

## Safety invariants

- Require explicit approval before stopping Herdr, activating the new Home Manager generation, or rebooting macOS.
- Prepare reboot recovery from a real Herdr pane with `HERDR_ENV=1`. Run post-reboot restoration from Terminal or Ghostty outside Herdr because it may stop a post-login Herdr server.
- Capture the absolute old Herdr binary before switching. Keep its Nix store path and the old Home Manager generation until verification succeeds.
- Build the target generation without activating it. Only run local commands such as `--version`, `status client`, and `api schema` with the target binary before cutover. Strip every inherited `HERDR_*` variable and never point it at the old socket.
- Build and activate the exact same Git-visible source. Git-backed flakes omit untracked files; do not let the repository or lock file drift after the verified build.
- Store runtime manifests and scrollback outside Git in a mode-`0700` migration bundle. They contain private paths, session IDs, commands, and terminal text.
- Do not persist process environments or secrets. The engine extracts only the Claude session ID from process environments.
- Do not garbage-collect Nix store paths during migration.
- The bundled engine intentionally refuses anything it cannot map exactly.

## Current engine scope

The engine supports:

- one running named Herdr session; stopped sessions are backed up but not replayed
- any number of workspaces, tabs, and panes in that session
- exact workspace identity CWD, per-pane CWD, nested split direction/ratio, labels, zoom, active tabs, and focus
- Pi sessions, Claude sessions, shell-only panes, and arbitrary foreground commands
- protocol-independent reconstruction through stable CLI/API operations

It refuses multiple running sessions or unsupported live agent kinds. Extend and re-test rather than weakening those guards.

The companion reboot helper supports only an identical source and target Herdr binary, version, and protocol. Use the upgrade cutover—not reboot recovery—when any of those change.

An arbitrary process is restarted from its resolved executable, root argv, and CWD; its RAM cannot be serialized. Agent conversations resume from durable session IDs. Scrollback is archived but not injected into recreated terminals.

## 1. Inspect before updating

Read the repository status and preserve unrelated changes.

```bash
OLD_HERDR=$(realpath "$(command -v herdr)")
OLD_HOME_MANAGER=$(realpath "$(command -v home-manager)")
herdr status
herdr session list --json
home-manager generations | head
```

Confirm `HERDR_ENV=1` when operating from a Herdr pane. Record the current socket and generation.

## 2. Update and build only

Update the flake as requested, then build without switching:

```bash
nix flake update
home-manager build --flake .#darwin
```

A `.#darwin` Git flake omits untracked files. Before building, ensure every intended new module is committed or at least tracked without staging unrelated changes. Avoid substituting `path:$PWD` when private untracked files could be copied to the Nix store. The eventual `switch_argv` must use the same flake reference and unchanged working tree.

Resolve and inspect the target without connecting it to the live socket. Remove the caller pane context as well as the socket override from these target-only commands:

```bash
NEW_HERDR=$(realpath result/home-path/bin/herdr)
TARGET_GENERATION=$(realpath result)
TARGET_ENV=(
  env
  -u HERDR_ENV
  -u HERDR_SOCKET_PATH
  -u HERDR_WORKSPACE_ID
  -u HERDR_TAB_ID
  -u HERDR_PANE_ID
)
"${TARGET_ENV[@]}" "$NEW_HERDR" --version
"${TARGET_ENV[@]}" "$NEW_HERDR" status client
"${TARGET_ENV[@]}" "$NEW_HERDR" api schema --json > /tmp/herdr-target-schema.json
```

Verify the build and accompanying package changes before migration. Record `TARGET_GENERATION`, and rebuild and recreate the bundle if the repository or lock file changes afterward.

## 3. Create the private bundle

The migration engine derives its bundle from its own parent directory, so copy all scripts into the bundle root. Do not run the engine in this skill directory.

```bash
SKILL_DIR=$(git rev-parse --show-toplevel)/.agents/skills/herdr-safe-upgrade
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BUNDLE="$HOME/.local/state/herdr/migrations/${STAMP}-SOURCE-to-TARGET"
mkdir -p -m 700 "$BUNDLE"
install -m 700 "$SKILL_DIR/scripts/herdr_migrate.py" "$BUNDLE/herdr_migrate.py"
install -m 700 "$SKILL_DIR/scripts/cutover-wrapper.sh" "$BUNDLE/cutover-wrapper.sh"
install -m 700 "$SKILL_DIR/scripts/restore-after-reboot.py" "$BUNDLE/restore-after-reboot.py"
install -m 600 "$SKILL_DIR/assets/migration-config.example.json" "$BUNDLE/migration-config.json"
```

Fill every placeholder in `migration-config.json`. See [the example](assets/migration-config.example.json). Important fields:

- `old_binary`, `old_version`, `old_protocol`: live client/server
- `new_binary`, `new_version`, `new_protocol`: built target
- `new_generation`: exact `TARGET_GENERATION` store path proved by the build
- `old_generation`: rollback generation containing the old client
- `switch_argv`: exact activation command as an argv array, never a shell string
- `home`, `path`: environment inherited by the detached server and restored shells
- `profile_path`: active Home Manager profile symlink for reporting

Use absolute paths. The activation binary itself should be an absolute Nix store path.

## 4. Snapshot and prove restoration

```bash
"$BUNDLE/herdr_migrate.py" preflight
"$BUNDLE/herdr_migrate.py" snapshot --archive-scrollback
"$BUNDLE/herdr_migrate.py" validate
"$BUNDLE/herdr_migrate.py" self-test
```

`preflight` is non-mutating. It requires absolute executable paths, proves that `old_generation` is still active, and checks that `new_generation` and both Herdr binaries remain available.

The snapshot combines:

- `session.snapshot` for global topology and focus
- persisted workspace identity CWD, kept distinct from each pane's live CWD
- raw `layout.export` for split trees, ratios, and per-pane CWD
- `pane.process_info` plus process ancestry for root argv/CWD and the resolved executable path
- Pi session headers, names, process start times, and resume events
- `CLAUDE_CODE_SESSION_ID` plus the matching Claude JSONL
- Herdr config/session/history backups and per-pane scrollback

`self-test` starts the target server with its Herdr config and sockets isolated under `/tmp`, while retaining the configured real `HOME` so shell hooks, direnv, and desktop-authenticated tools behave like cutover. It recreates the complete topology with captured commands disabled, waits for every new shell and its direnv/Nix initialization to settle, compares normalized layouts/focus/zoom, then stops and removes that server. Complete any expected 1Password prompt; an unresolved prompt must remain a hard failure.

Workspace creation deserves special care: `workspace create --cwd` initializes both the workspace identity and its first tab's shell, but those CWDs can later diverge. The engine preserves the identity CWD, waits for shell startup hooks, sends a safely quoted `cd` to the new first-tab shell when needed, and waits until `session.snapshot` reports the expected pane CWD before creating splits or restarting anything. Every restored process is submitted only after its shell is the sole foreground process. A timeout is a hard failure.

The engine replaces stale diagnostics on every run, writes `self-test-report.json` on success or failure, and preserves the isolated server output as `self-test-server.log`. Layout mismatches include normalized expected and actual trees so CWD, direction, or ratio differences are directly diagnosable.

Do not continue unless both reports say `valid: true`, every pane is classified, all session files exist, and counts match the live snapshot. Present the report and get approval if cutover was not already approved.

### If self-test fails

The isolated server is removed and the live session is unchanged. Stop and inspect `self-test-report.json` and `self-test-server.log`. Fix reconstruction in the repository engine; never edit the captured manifest, weaken normalization, or skip verification to make the test pass. Preserve the failed bundled engine, install the corrected source into the bundle, run `python3 -m py_compile`, and rerun preflight, snapshot, validation, and self-test before asking for cutover approval.

## 5. Launch the detached cutover

Stopping Herdr kills the invoking pane, so use the bundled wrapper through `launchctl`. It waits long enough for the current assistant response to persist, then runs independently.

```bash
LABEL="local.$USER.herdr-migration-$(date -u +%Y%m%dT%H%M%SZ)"
launchctl submit -l "$LABEL" -- \
  /bin/zsh "$BUNDLE/cutover-wrapper.sh" "$LABEL" "$BUNDLE" 15
```

Immediately report the bundle and log path before the delay expires.

Always use `cutover-wrapper.sh`, not the Python engine directly through `launchctl submit`. Submitted jobs restart after normal exit; the wrapper removes its own label in an exit trap so a successful or failed migration remains one-shot. The engine also uses an exclusive `cutover.lock` as a second guard.

The detached cutover:

1. proves `old_generation` is still active and the built `new_generation` still exists
2. takes and validates a fresh final source-protocol manifest
3. saves pre-stop state
4. stops the source server with the absolute old client
5. saves post-stop state and moves legacy session files aside
6. runs `switch_argv` and proves the active profile equals `new_generation`
7. starts the target server and checks its protocol
8. recreates topology and maps all new IDs from API responses
9. waits for shell/direnv initialization, then resumes agents and restarts commands
10. verifies topology, exact agent session identities, and command executable/argv, rejecting stale agents and unrelated startup processes
11. writes `success.json` or automatically attempts rollback

## 6. Verify after reconnect

```bash
herdr status
cat "$BUNDLE/success.json"
herdr api snapshot > "$BUNDLE/post-migration-snapshot.json"
launchctl print "gui/$(id -u)/$LABEL"  # must report no such service
```

Require:

- target version and protocol on both client and server
- expected workspace/tab/pane/agent counts
- `process_health.ready: true`
- no missing or mismatched processes in `process-health-report.json`
- no lingering launchd job

Keep the bundle, old generation, and old binary until the user confirms the restored state. Never delete or garbage-collect them automatically.

## Same-version macOS reboot recovery

Use this flow when a reboot will kill every pane process but Herdr itself is not changing. Do not run the upgrade `cutover` command.

### Prepare inside Herdr

Confirm `HERDR_ENV=1`, inspect the live session as in step 1, then create a private bundle as in step 3. Name it for reboot recovery, for example:

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BUNDLE="$HOME/.local/state/herdr/migrations/${STAMP}-HERDR_VERSION-reboot"
```

In `migration-config.json`, set `old_binary` and `new_binary` to the same absolute Nix store binary. Set both versions and both protocols identically. Use `["/usr/bin/true"]` for `switch_argv`; reboot recovery never executes it. Keep the real generation, profile, `HOME`, and `PATH` values so the binary remains rooted and resumed shells have the original command environment.

Prepare and inspect the bundle:

```bash
"$BUNDLE/restore-after-reboot.py" prepare
"$BUNDLE/restore-after-reboot.py" check
cat "$BUNDLE/reboot-ready.json"
```

`prepare` takes and validates the manifest, archives scrollback, backs up runtime files, and runs the isolated topology self-test. Require `prepared: true`, exact live counts, and no validation errors. Do not create, close, move, split, or relabel panes after preparation; if topology changes, run `prepare` again before rebooting.

Get explicit approval before the user reboots. Do not install an automatic login job by default. Do not garbage-collect before recovery.

### Restore manually after reboot

Before opening Herdr, use Terminal or Ghostty outside Herdr:

```bash
BUNDLE="$HOME/.local/state/herdr/migrations/TIMESTAMP-HERDR_VERSION-reboot"
"$BUNDLE/restore-after-reboot.py" restore
```

The helper uses a one-shot lock, archives any post-login session state, starts an empty server with the captured absolute binary, reconstructs topology, resumes agents and commands, restores zoom/focus, and verifies every expected process. If Herdr started automatically at login, the helper safely stops that matching server first.

Verify before using the restored session:

```bash
cat "$BUNDLE/reboot-success.json"
herdr status
herdr session list --json
```

Require matching version/protocol, expected topology counts, and `process_health.ready: true`. Keep the private bundle until the user confirms every pane. Archived scrollback remains available in the bundle but is not injected into new terminals.

If restoration fails, do not delete `reboot-restore.lock` or rerun blindly. The helper writes `reboot-failure.json`, attempts to restore the archived post-reboot session state, restarts commands in original pane IDs, and records `reboot-rollback.json`. Inspect those files and `reboot-server.log` first.

## Failure handling

The engine records `failure.json`, stops whichever protocol is running, restores the source config and post-stop session state, activates `old_generation`, starts the old server, waits for the original pane IDs to stabilize, allows persisted agents to auto-resume, replaces stale or mismatched agent sessions, and restarts only missing processes after their shells are ready. Rollback also requires exact process health. Inspect `self-test-report.json`, `topology-verification-report.json`, `process-health-report.json`, `rollback-process-health-report.json`, `rollback.json`, and `cutover.log` as applicable; never discard the bundle while diagnosing.
