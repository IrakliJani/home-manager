{ lib, pkgs, ... }:

let
  ghosttyTerminfoSource = ./ghostty.terminfo;
  ghosttyTerminfoSourceExists = builtins.pathExists ghosttyTerminfoSource;
  ghosttyTerminfo = pkgs.runCommand "ghostty-terminfo" { } ''
    mkdir -p "$out/share/terminfo"
    ${pkgs.ncurses}/bin/tic -x -o "$out/share/terminfo" ${ghosttyTerminfoSource}
    test -f "$out/share/terminfo/78/xterm-ghostty"
  '';
in
{
  home.homeDirectory = "/Users/irakli";

  warnings = lib.optional (!ghosttyTerminfoSourceExists) ''
    Ghostty terminfo source is missing at modules/platform/ghostty.terminfo;
    xterm-ghostty will not be installed.
  '';

  home.file = lib.optionalAttrs ghosttyTerminfoSourceExists {
    ".terminfo/78/xterm-ghostty".source = "${ghosttyTerminfo}/share/terminfo/78/xterm-ghostty";
  };

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
