{ config, pkgs, ... }:

{
  home.homeDirectory = "/home/${config.home.username}";

  home.packages = with pkgs; [
    ghostty.terminfo
  ];
}
