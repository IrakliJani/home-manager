{ config, pkgs, ... }:

{
  home.packages = [ pkgs.zsh-completions ];

  programs.zsh = {
    enable = true;
    enableCompletion = true;

    dotDir = "${config.xdg.configHome}/zsh";

    shellAliases = {
      gs = "git status";
      gd = "git -c delta.side-by-side=false diff";
      gds = "git -c delta.side-by-side=true diff";
    };

    history = {
      append = true;
      path = "${config.xdg.dataHome}/zsh/zsh_history";
      expireDuplicatesFirst = true;
      extended = false;
      ignoreDups = true;
      ignoreSpace = true;
      share = true;
      save = 100000;
      size = 100000;
    };

    syntaxHighlighting.enable = true;
    autosuggestion.enable = true;
    historySubstringSearch.enable = true;
  };
}
