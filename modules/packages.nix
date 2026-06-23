{
  pkgs,
  pkgsUnstable,
  lib,
  ...
}:

{
  home.packages =
    with pkgs;
    [
      # networking
      curl
      wget

      # nix tooling
      nixd
      nixfmt

      # git workflows
      pkgsUnstable.graphite-cli

      # AI coding agent harnesses (from numtide/llm-agents.nix)
      llm-agents.pi
      llm-agents.opencode
      llm-agents.claude-code

      # terminal workspace manager
      llm-agents.herdr
    ]
    ++ lib.optionals pkgs.stdenv.hostPlatform.isDarwin [
      apfel-llm
    ]
    ++ [
      # fonts
      nerd-fonts.victor-mono
      nerd-fonts.jetbrains-mono

      # runtimes
      nodejs
      bun
      python3
    ];
}
