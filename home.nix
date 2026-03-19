{ ... }:

{
  imports = [
    ./modules/packages.nix
    ./modules/git.nix
    ./modules/shell/zsh.nix
    ./modules/shell/tmux.nix
    ./modules/shell/direnv.nix
    ./modules/shell/tools.nix
    ./modules/editor/nixvim
  ];

  home.username = "irakli";
  # home.homeDirectory set in modules/platform/{darwin,linux}.nix
  home.stateVersion = "25.05";

  home.sessionPath = [
    "$HOME/.local/bin"
    "$HOME/.claude/local"
  ];

  programs.home-manager.enable = true;
}
