{ pkgs, ... }:

{
  home.packages = with pkgs; [
    # networking
    curl
    wget

    # nix tooling
    nixd
    nixfmt

    # git stuff
    gitbutler

    # AI coding agent harnesses (from numtide/llm-agents.nix)
    llm-agents.pi
    llm-agents.opencode
    llm-agents.claude-code

    # fonts
    nerd-fonts.victor-mono
    nerd-fonts.jetbrains-mono

    # runtimes
    nodejs
    bun
    python3
  ];
}
