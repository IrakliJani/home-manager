{
  config,
  lib,
  pkgs,
  ...
}:

let
  onePasswordAgentSocket = "${config.home.homeDirectory}/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock";
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

  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
    includes = [ "~/.orbstack/ssh/config" ];
    settings."*".IdentityAgent = "SSH_AUTH_SOCK";
  };

  home.sessionVariablesExtra = lib.mkAfter ''
    # Local shells use this Mac's 1Password agent; SSH sessions keep the forwarded agent.
    if [ -z "''${SSH_CONNECTION-}" ]; then
      export SSH_AUTH_SOCK=${lib.escapeShellArg onePasswordAgentSocket}
    fi
  '';
}
