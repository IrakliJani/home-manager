{ lib, pkgs, ... }:

{
  home.homeDirectory = "/Users/irakli";

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
