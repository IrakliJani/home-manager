{ ... }:

{
  programs.git = {
    enable = true;

    lfs.enable = true;

    settings = {
      branch.sort = "committerdate";

      diff = {
        colorMoved = "default";
        ignoreWhitespace = "all";
      };

      init.defaultBranch = "main";

      merge.conflictStyle = "zdiff3";

      pager.branch = false;
    };
  };

  programs.delta = {
    enable = true;
    enableGitIntegration = true;
    options = {
      dark = true;
      navigate = true;
      side-by-side = false;
      line-numbers = true;
      hyperlinks = true;
    };
  };
}
