{ ... }:

{
  home.file = {
    ".agents/skills/nix-flake-fleet".source = ../.agents/skills/nix-flake-fleet;

    ".local/bin/nix-flake-fleet" = {
      source = ../.agents/skills/nix-flake-fleet/scripts/nix-flake-fleet;
      executable = true;
    };
  };
}
