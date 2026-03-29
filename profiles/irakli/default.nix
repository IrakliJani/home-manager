{ ... }:

{
  imports = [
    ../_shared
    ./modules/git.nix
  ];

  home.username = "irakli";
}
