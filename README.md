# home-manager

Personal Home Manager flake with profile support.

## Profiles and targets

This flake exposes:

- Profile aliases:
  - `darwin` (defaults to `irakli` profile)
  - `linux` (defaults to `irakli` profile)
- Explicit profile targets:
  - `irakli@darwin`
  - `irakli@linux`
  - `claw@darwin`
  - `claw@linux`

## Activate from your shell

From this repo directory (`~/.config/home-manager`):

```bash
# If home-manager is already installed
home-manager switch --flake .#darwin
home-manager switch --flake .#linux
home-manager switch --flake .#claw@linux
```

If you do **not** have home-manager installed globally:

```bash
# One-shot run via nix
nix run github:nix-community/home-manager -- switch --flake .#darwin

# Or temporary shell
nix shell github:nix-community/home-manager -c home-manager switch --flake .#darwin
```

## Build only (no activation)

```bash
# quick eval/build test
home-manager build --flake .#darwin
home-manager build --flake .#claw@linux
```

## Use this flake from NixOS

You can consume this Home Manager flake from a NixOS configuration via `home-manager.nixosModules.home-manager`.

```nix
# in your flake inputs
home-manager.url = "github:nix-community/home-manager/release-25.11";
irakli-home.url = "github:IrakliJani/home-manager";

# in your nixosSystem modules
home-manager.nixosModules.home-manager

# in your host module
home-manager.users.<user> = irakli-home.homeModules.linux {
  profile = "irakli"; # or "claw"
};
```

## Notes

- Shared config lives in `profiles/_shared`.
- Profile-specific overrides live under `profiles/<name>/`.
