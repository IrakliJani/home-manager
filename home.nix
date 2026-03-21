{ config, ... }:

{
  imports = [
    ./modules/packages.nix
    ./modules/git.nix
    ./modules/themes/catppuccin.nix
    ./modules/shell/oh-my-posh.nix
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

  xdg = {
    enable = true;
    configHome = "${config.home.homeDirectory}/.config";
    cacheHome = "${config.home.homeDirectory}/.cache";
    dataHome = "${config.home.homeDirectory}/.local/share";
    stateHome = "${config.home.homeDirectory}/.local/state";
  };

  themes.catppuccin = {
    enable = true;
    flavor = "mocha";
  };

  programs.home-manager.enable = true;
}
