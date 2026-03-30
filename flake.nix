{
  description = "Home Manager configuration of irakli";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";

    home-manager.url = "github:nix-community/home-manager/master";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";

    nixvim.url = "github:nix-community/nixvim";
    nixvim.inputs.nixpkgs.follows = "nixpkgs";

    llm-agents.url = "github:numtide/llm-agents.nix";
    llm-agents.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      nixpkgs,
      home-manager,
      nixvim,
      llm-agents,
      ...
    }:
    let
      defaultProfile = "irakli";

      profileModules = {
        "${defaultProfile}" = ./profiles/irakli;
        claw = ./profiles/claw;
      };

      mkProfileModule = profile: profileModules.${profile} or (throw "Unsupported profile: ${profile}");

      platforms = {
        darwin = "aarch64-darwin";
        linux = "x86_64-linux";
      };

      platformNames = builtins.attrNames platforms;
      profileNames = builtins.attrNames profileModules;

      mkPlatformModule =
        system:
        {
          "aarch64-darwin" = ./modules/platform/darwin.nix;
          "x86_64-linux" = ./modules/platform/linux.nix;
        }
        .${system} or (throw "Unsupported platform: ${system}");

      mkHomeModule =
        {
          system,
          profile ? defaultProfile,
        }:
        {
          imports = [
            nixvim.homeModules.nixvim
            (mkProfileModule profile)
            (mkPlatformModule system)
          ];
        };

      mkHome =
        {
          system,
          profile ? defaultProfile,
        }:
        home-manager.lib.homeManagerConfiguration {
          pkgs = import nixpkgs {
            inherit system;
            overlays = [ llm-agents.overlays.default ];
          };

          modules = [
            (mkHomeModule {
              inherit system profile;
            })
          ];
        };
    in
    {
      homeModules = builtins.listToAttrs (
        builtins.map (platform: {
          name = platform;
          value =
            {
              profile ? defaultProfile,
            }:
            mkHomeModule {
              system = platforms.${platform};
              inherit profile;
            };
        }) platformNames
      );

      homeConfigurations =
        (builtins.listToAttrs (
          builtins.map (platform: {
            name = platform;
            value = mkHome {
              system = platforms.${platform};
            };
          }) platformNames
        ))
        // (builtins.listToAttrs (
          builtins.concatLists (
            builtins.map (
              profile:
              builtins.map (platform: {
                name = "${profile}@${platform}";
                value = mkHome {
                  system = platforms.${platform};
                  inherit profile;
                };
              }) platformNames
            ) profileNames
          )
        ));
    };
}
