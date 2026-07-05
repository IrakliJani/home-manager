{
  description = "Home Manager configuration of irakli";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-26.05-darwin";
    nixpkgs-unstable.url = "github:nixos/nixpkgs/nixpkgs-unstable";

    home-manager.url = "github:nix-community/home-manager/release-26.05";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";

    nixvim.url = "github:nix-community/nixvim/nixos-26.05";
    nixvim.inputs.nixpkgs.follows = "nixpkgs";

    llm-agents.url = "github:numtide/llm-agents.nix";
    llm-agents.inputs.nixpkgs.follows = "nixpkgs";

    hunk.url = "github:modem-dev/hunk";
    hunk.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      nixpkgs,
      nixpkgs-unstable,
      home-manager,
      nixvim,
      llm-agents,
      hunk,
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
            hunk.homeManagerModules.default
            (mkProfileModule profile)
            (mkPlatformModule system)
          ];

          _module.args.pkgsUnstable = mkPkgsUnstable system;
        };

      overlays = [
        llm-agents.overlays.default
      ];

      unfreePackages = [
        "graphite-cli"
        "graphite-cli-unwrapped"
        "ungoogled-chromium"
      ];

      mkPkgs =
        system:
        import nixpkgs {
          inherit system overlays;
          config.allowUnfreePredicate = pkg: builtins.elem (nixpkgs.lib.getName pkg) unfreePackages;
        };

      mkPkgsUnstable =
        system:
        import nixpkgs-unstable {
          inherit system;
          config.allowUnfreePredicate = pkg: builtins.elem (nixpkgs-unstable.lib.getName pkg) unfreePackages;
        };

      mkHome =
        {
          system,
          profile ? defaultProfile,
        }:
        home-manager.lib.homeManagerConfiguration {
          pkgs = mkPkgs system;

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
