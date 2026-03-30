{ config, ... }:

{
  imports = [
    ../../modules/packages.nix
    ../../modules/git.nix
    ../../modules/shell/oh-my-posh.nix
    ../../modules/shell/zsh.nix
    ../../modules/shell/tmux.nix
    ../../modules/shell/direnv.nix
    ../../modules/shell/tools.nix
    ../../modules/editor/nixvim
  ];

  # home.username is set by profile modules (e.g. profiles/irakli, profiles/claw)
  # home.homeDirectory is set by modules/platform/{darwin,linux}.nix
  home.stateVersion = "25.05";

  home.sessionPath = [
    "$HOME/.local/bin"
  ];

  xdg = {
    enable = true;
    configHome = "${config.home.homeDirectory}/.config";
    cacheHome = "${config.home.homeDirectory}/.cache";
    dataHome = "${config.home.homeDirectory}/.local/share";
    stateHome = "${config.home.homeDirectory}/.local/state";
  };

  programs.home-manager.enable = true;

  home.file.".hushlogin".text = "";
}
