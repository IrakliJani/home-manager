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

      pager = {
        branch = false;
        diff = "hunk pager";
        show = "hunk pager";
        stash = "hunk pager";
      };
    };
  };
}
