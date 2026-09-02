{ ... }:

{
  home.file = {
    ".agents/skills/herdr-safe-upgrade".source = ../.agents/skills/herdr-safe-upgrade;
    ".agents/skills/nix-flake-fleet".source = ../.agents/skills/nix-flake-fleet;

    ".local/bin/nix-flake-fleet" = {
      source = ../.agents/skills/nix-flake-fleet/scripts/nix-flake-fleet;
      executable = true;
    };
  };
}
