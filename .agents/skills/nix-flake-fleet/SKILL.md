---
name: nix-flake-fleet
description: Finds Nix flake projects under ~/code, reports their nixpkgs channel and lock/Git state, moves direct nixpkgs inputs to an unstable branch, and runs nix flake update across the fleet with backups and failure isolation. Use when listing, auditing, or mass-updating personal Nix flake projects.
compatibility: Python 3.10+, Nix with `nix flake update --flake` (tested on 2.34.6), macOS or Linux; Git is optional except for the GitHub rate-limit fallback
---

# Nix Flake Fleet

Use the bundled script to discover and update flakes under `~/code`. Discovery includes nested flakes and paths containing spaces. It skips generated trees such as `.git`, `.direnv`, `node_modules`, `target`, and `result`.

## Safety rules

- Start with `list` and `plan`. Report candidate, rewrite, missing-lock, and dirty-file counts before mutation.
- Treat `nixos-unstable` and `nixpkgs-unstable` as unstable. Do not normalize one to the other unless the user asks.
- The default `auto` target uses `nixos-unstable` for flakes that define NixOS systems and `nixpkgs-unstable` for package or development flakes.
- Rewrite only a direct `nixpkgs.url` or `inputs.nixpkgs.url` that points to `github:NixOS/nixpkgs`. Do not rewrite `follows`, similarly named inputs such as `nixpkgs-latest`, or unsupported URL forms automatically.
- By default, skip a candidate when its `flake.nix` or `flake.lock` was already modified. Use `--include-dirty` only after reviewing those paths or when the user explicitly requests all candidates.
- `sync` updates all lock inputs, not only `nixpkgs`. It does not build, deploy, activate, commit, push, delete Git changes, or garbage-collect.
- If the GitHub API quota is exhausted, the script resolves direct GitHub refs with `git ls-remote` and retries with pinned overrides. Nix preserves the original unpinned input declarations in the lock.
- A fleet update does not itself free Nix store space. Lock files are not GC roots. Handle generation deletion or garbage collection as a separate, explicitly approved task.
- Do not include the Home Manager repository unless the user changes `--root`; the default root is only `~/code`.

## Locate the script

Resolve relative paths from the directory that contains this `SKILL.md`. From that directory:

```bash
FLEET="$PWD/scripts/nix-flake-fleet"
```

After this Home Manager configuration installs it, `nix-flake-fleet` is also available on `PATH` and the skill is available globally at `~/.agents/skills/nix-flake-fleet`.

## 1. List candidates

```bash
"$FLEET" list
"$FLEET" list --json
```

The table reports whether `flake.lock` exists, the direct nixpkgs ref, and whether the candidate's `flake.nix` or `flake.lock` is dirty in Git.

For a different tree, place the global option before the command:

```bash
"$FLEET" --root /path/to/projects list
```

## 2. Preview the unstable migration

```bash
"$FLEET" plan
```

The default preserves an existing unstable ref. To force one branch across every supported direct input:

```bash
"$FLEET" plan --unstable-ref nixos-unstable --normalize
"$FLEET" plan --unstable-ref nixpkgs-unstable --normalize
```

Highlight any `REVIEW` entry. Its direct nixpkgs URL is unsupported and will not be rewritten automatically, although its lock can still be updated.

## 3. Apply and update all locks

For clean candidates only:

```bash
"$FLEET" sync --apply
```

When the user explicitly approves including pre-existing changes:

```bash
"$FLEET" sync --apply --include-dirty
```

Each candidate is a small transaction. Before editing, the script saves `flake.nix` and `flake.lock`. If `nix flake update` fails or times out, it restores both files for that candidate and continues. The final report, command logs, and backups are stored under:

```text
$XDG_STATE_HOME/nix-flake-fleet/runs/<timestamp>-<pid>/
```

If `XDG_STATE_HOME` is unset, the base is `~/.local/state`.

A nonzero exit means at least one candidate failed or was skipped. Read `report.json` and the referenced log. Fix authentication, an invalid input, a dirty-file decision, or a timeout, then rerun. Successful candidates can safely be processed again.

Use the global `--only` option before the command to retry selected root-relative paths without consuming requests for the whole fleet:

```bash
"$FLEET" \
  --only 'nixos-hetzner-metal-private' \
  --only 'nixos-hetzner-metal-public' \
  sync --apply --include-dirty
```

The unauthenticated GitHub API limit is 60 requests per hour. The default Git fallback handles direct `github:` input declarations without changing their lock-file origins. Disable it with `--no-github-git-fallback` only when requested. If a private repository or unsupported declaration still fails, do not repeatedly rerun the whole fleet: configure authentication or wait for the reset, then retry only failed paths.

## Lock-only update

To leave every `flake.nix` unchanged and update only locks:

```bash
"$FLEET" update --apply
"$FLEET" update --apply --include-dirty
```

## After the run

Report:

- discovered, updated, failed, and skipped counts
- every rewritten nixpkgs URL
- every failed or skipped path
- the `report.json` path

Do not run builds or garbage collection unless the user separately asks for them.
