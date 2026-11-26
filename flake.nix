{
  description = "Home Manager configuration of irakli";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";

    home-manager.url = "github:nix-community/home-manager/master";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";

    nixvim.url = "github:nix-community/nixvim/main";
    nixvim.inputs.nixpkgs.follows = "nixpkgs";

    llm-agents.url = "github:numtide/llm-agents.nix";

    # Pinned: it runs at build time, so read the diff before moving it.
    agent-skills.url = "github:Kyure-A/agent-skills-nix/93a02cb60eda167de8c5baa085e4a2bcfc71b885";
    agent-skills.inputs.nixpkgs.follows = "nixpkgs";

    cursor-plugins.url = "github:cursor/plugins";
    cursor-plugins.flake = false;

    mattpocock-skills.url = "github:mattpocock/skills";
    mattpocock-skills.flake = false;

    # Private: Irakli's own skills and AGENTS.md. Fetching it needs his SSH key.
    irakli-skills.url = "git+ssh://git@github.com/IrakliJani/skills?ref=main";
    irakli-skills.flake = false;
  };

  outputs =
    {
      nixpkgs,
      home-manager,
      nixvim,
      llm-agents,
      agent-skills,
      cursor-plugins,
      mattpocock-skills,
      irakli-skills,
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
            agent-skills.homeManagerModules.default
            {
              programs.agent-skills.sources = {
                cursor.path = cursor-plugins;
                matt-engineering.path = mattpocock-skills;
                matt-productivity.path = mattpocock-skills;
              };
              # Lazy: only profiles that import irakli-skills.nix fetch it.
              _module.args.irakliSkills = irakli-skills;
            }
            (mkProfileModule profile)
            (mkPlatformModule system)
          ];
        };

      overlays = [
        (_final: prev: {
          llm-agents = llm-agents.packages.${prev.stdenv.hostPlatform.system};
        })
      ];

      mkPkgs = system: import nixpkgs { inherit system overlays; };

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
