{ lib, pkgs, ... }:

let
  ghosttyTerminfo = pkgs.runCommand "ghostty-terminfo" { } ''
    mkdir -p "$out/share/terminfo"
    ${pkgs.ncurses}/bin/tic -x -o "$out/share/terminfo" ${./ghostty.terminfo}
    test -f "$out/share/terminfo/78/xterm-ghostty"
  '';
in
{
  home.homeDirectory = "/Users/irakli";

  home.file.".terminfo/78/xterm-ghostty".source =
    "${ghosttyTerminfo}/share/terminfo/78/xterm-ghostty";

  nix.gc = {
    automatic = true;
    dates = "weekly";
  };

  launchd.agents.nix-gc.config.ProgramArguments = lib.mkForce [
    "${pkgs.nix}/bin/nix-collect-garbage"
    "--delete-older-than"
    "14d"
  ];

  programs.git.signing.signer = "/Applications/1Password.app/Contents/MacOS/op-ssh-sign";
}
