{ ... }:

{
  programs.eza = {
    enable = true;
    enableZshIntegration = true;
    git = true;
  };

  programs.fzf = {
    enable = true;
  };
}
