{ ... }:

{
  programs.htop.enable = true;
  programs.btop.enable = true;
  programs.fzf.enable = true;
  programs.ripgrep.enable = true;
  programs.fd.enable = true;

  programs.eza = {
    enable = true;
    enableZshIntegration = true;
    git = true;
  };

  programs.delta = {
    enable = true;
    enableGitIntegration = true;
    options = {
      navigate = true;
      dark = true;
    };
  };
}
