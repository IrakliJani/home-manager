---
name: herdr-safe-upgrade
description: Safely upgrades Herdr across incompatible socket protocols while preserving and rebuilding every live workspace, tab, split pane, agent session, foreground command, label, ratio, zoom, and focus state. Use for Home Manager or Nix Herdr upgrades where switching the client would strand an older running server.
compatibility: macOS, launchctl, Python 3.9+, Herdr socket API, Nix/Home Manager
---

# Herdr Safe Upgrade

Use a declarative manifest and a detached one-shot cutover. Never rely on a new Herdr client talking to an old-protocol server.

## Safety invariants

- Require explicit approval before stopping Herdr or activating the new Home Manager generation.
- Capture the absolute old Herdr binary before switching. Keep its Nix store path and the old Home Manager generation until verification succeeds.
- Build the target generation without activating it. Only run local commands such as `--version`, `status client`, and `api schema` with the target binary before cutover. Never point it at the old socket.
- Store runtime manifests and scrollback outside Git in a mode-`0700` migration bundle. They contain private paths, session IDs, commands, and terminal text.
- Do not persist process environments or secrets. The engine extracts only the Claude session ID from process environments.
- Do not garbage-collect Nix store paths during migration.
- The bundled engine intentionally refuses anything it cannot map exactly.

## Current engine scope

The engine supports:

- one running named Herdr session; stopped sessions are backed up but not replayed
- any number of workspaces, tabs, and panes in that session
- exact nested split direction/ratio, CWD, labels, zoom, active tabs, and focus
- Pi sessions, Claude sessions, shell-only panes, and arbitrary foreground commands
- protocol-independent reconstruction through stable CLI/API operations

It refuses multiple running sessions or unsupported live agent kinds. Extend and re-test rather than weakening those guards.

An arbitrary process is restarted from its root argv and CWD; its RAM cannot be serialized. Agent conversations resume from durable session IDs. Scrollback is archived but not injected into recreated terminals.

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

Resolve and inspect the target without connecting it to the live socket:

```bash
NEW_HERDR=$(realpath result/home-path/bin/herdr)
"$NEW_HERDR" --version
"$NEW_HERDR" status client
"$NEW_HERDR" api schema --json > /tmp/herdr-target-schema.json
```

Verify the build and any accompanying package changes before migration.

## 3. Create the private bundle

The migration engine derives its bundle from its own parent directory, so copy both scripts into the bundle root. Do not run the engine in this skill directory.

```bash
SKILL_DIR=$(git rev-parse --show-toplevel)/.agents/skills/herdr-safe-upgrade
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BUNDLE="$HOME/.local/state/herdr/migrations/${STAMP}-SOURCE-to-TARGET"
mkdir -p -m 700 "$BUNDLE"
install -m 700 "$SKILL_DIR/scripts/herdr_migrate.py" "$BUNDLE/herdr_migrate.py"
install -m 700 "$SKILL_DIR/scripts/cutover-wrapper.sh" "$BUNDLE/cutover-wrapper.sh"
install -m 600 "$SKILL_DIR/assets/migration-config.example.json" "$BUNDLE/migration-config.json"
```

Fill every placeholder in `migration-config.json`. See [the example](assets/migration-config.example.json). Important fields:

- `old_binary`, `old_version`, `old_protocol`: live client/server
- `new_binary`, `new_version`, `new_protocol`: built target
- `old_generation`: rollback generation containing the old client
- `switch_argv`: exact activation command as an argv array, never a shell string
- `home`, `path`: environment inherited by the detached server and restored shells
- `profile_path`: active Home Manager profile symlink for reporting

Use absolute paths. The activation binary itself should be an absolute Nix store path.

## 4. Snapshot and prove restoration

```bash
"$BUNDLE/herdr_migrate.py" snapshot --archive-scrollback
"$BUNDLE/herdr_migrate.py" validate
"$BUNDLE/herdr_migrate.py" self-test
```

The snapshot combines:

- `session.snapshot` for global topology and focus
- raw `layout.export` for split trees and ratios
- `pane.process_info` plus process ancestry for root argv/CWD
- Pi session headers, names, process start times, and resume events
- `CLAUDE_CODE_SESSION_ID` plus the matching Claude JSONL
- Herdr config/session/history backups and per-pane scrollback

`self-test` starts the target server under a short isolated `/tmp` config, recreates the complete real topology with commands disabled, compares normalized layouts/focus/zoom, then stops and removes that server.

Do not continue unless both reports say `valid: true`, every pane is classified, all session files exist, and counts match the live snapshot. Present the report and get approval if cutover was not already approved.

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

1. takes and validates a fresh final source-protocol manifest
2. saves pre-stop state
3. stops the source server with the absolute old client
4. saves post-stop state and moves legacy session files aside
5. runs `switch_argv`
6. starts the target server and checks its protocol
7. recreates topology and maps all new IDs from API responses
8. resumes agents and restarts commands
9. verifies topology and waits for every expected agent/process
10. writes `success.json` or automatically attempts rollback

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
- no missing processes
- no lingering launchd job

Keep the bundle, old generation, and old binary until the user confirms the restored state. Never delete or garbage-collect them automatically.

## Failure handling

The engine records `failure.json`, stops whichever protocol is running, restores post-stop source state, activates `old_generation`, starts the old server, and restarts captured commands in the original pane IDs. Inspect `rollback.json` and `cutover.log`; never discard the bundle while diagnosing.
