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

      gitbutler = {
        aiModelProvider = "openai";
        aiOpenAIKeyOption = "butlerAPI";
      };

      init.defaultBranch = "main";

      merge.conflictStyle = "zdiff3";

      pager.branch = false;
    };
  };
}
