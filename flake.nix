{
  description = "Home Manager configuration of irakli";

  inputs = {
    catppuccin = {
      url = "github:catppuccin/nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";

    home-manager.url = "github:nix-community/home-manager/master";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";

    nixvim.url = "github:nix-community/nixvim";
    nixvim.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      nixpkgs,
      home-manager,
      nixvim,
      catppuccin,
      ...
    }:
    let
      mkHome =
        system:
        let
          platformModule =
            {
              "aarch64-darwin" = ./modules/platform/darwin.nix;
              "x86_64-linux" = ./modules/platform/linux.nix;
            }
            .${system} or (throw "Unsupported platform: ${system}");
        in
        home-manager.lib.homeManagerConfiguration {
          pkgs = nixpkgs.legacyPackages.${system};

          modules = [
            catppuccin.homeModules.catppuccin
            nixvim.homeModules.nixvim
            ./home.nix
            platformModule
          ];
        };
    in
    {
      homeConfigurations."irakli@darwin" = mkHome "aarch64-darwin";
      homeConfigurations."irakli@linux" = mkHome "x86_64-linux";
    };
}
