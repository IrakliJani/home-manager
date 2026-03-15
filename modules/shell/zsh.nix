{ ... }:

{
  programs.zsh = {
    enable = true;

    oh-my-zsh = {
      enable = true;
      plugins = [ "git" "sudo" ];
      theme = "simple";
    };

    shellAliases = {
      l = "eza -lbF --git";
      gs = "git status";
    };

    history = {
      append = true;
      size = 100000;
      save = 100000;
    };

    syntaxHighlighting.enable = true;
    autosuggestion.enable = true;
    historySubstringSearch.enable = true;
  };
}
