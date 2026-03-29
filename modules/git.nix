{ ... }:

{
  programs.git = {
    enable = true;

    lfs.enable = true;

    settings = {
      merge.conflictStyle = "zdiff3";
    };
  };
}
