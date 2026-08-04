{
  pkgs,
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

      # AI coding agent harnesses (from numtide/llm-agents.nix)
      llm-agents.pi
      llm-agents.opencode
      llm-agents.claude-code
      llm-agents.codex

      # Hugging Face CLI
      python3Packages.huggingface-hub

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
