{ ... }:

{
  imports = [
    ../_shared
    ../../modules/agent-skills.nix
    ./modules/git.nix
  ];

  home.username = "irakli";
}
