{ pkgs, ... }:

{
  home.packages = with pkgs; [
    # networking
    curl
    wget

    # nix tooling
    nixd
    nixfmt

    # fonts
    nerd-fonts.victor-mono
    nerd-fonts.jetbrains-mono

    # runtimes
    nodejs
    bun
    deno
    python3
  ];
}
