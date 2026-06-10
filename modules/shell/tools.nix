{ ... }:

{
  programs.htop.enable = true;
  programs.btop.enable = true;
  programs.fzf.enable = true;
  programs.ripgrep.enable = true;
  programs.fd.enable = true;

  programs.nix-index = {
    enable = true;
    enableZshIntegration = true;
  };

  programs.eza = {
    enable = true;
    enableZshIntegration = true;
    git = true;
  };

  programs.hunk = {
    enable = true;
    # Avoid setting core.pager: Hunk is great for diffs, but breaks/non-terminates
    # plain paged commands like `git log`.
    enableGitIntegration = false;
    settings = {
      theme = "graphite";
      mode = "split";
      line_numbers = true;
    };
  };
}
