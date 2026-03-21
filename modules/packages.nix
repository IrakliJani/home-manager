{ pkgs, ... }:

{
  home.packages = with pkgs; [
    # networking
    curl
    wget

    # nix tooling
    nixd
    nixfmt

    # system
    htop

    # git
    git-lfs

    # search
    ripgrep
    fd

    # fonts
    nerd-fonts.victor-mono
    nerd-fonts.jetbrains-mono

    # runtimes
    nodejs
    bun
    python
  ];
}
