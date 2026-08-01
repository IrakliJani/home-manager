{ pkgs, ... }:

{
  programs.helix = {
    enable = true;
    extraPackages = [ pkgs.typescript-language-server ];

    settings = {
      theme = "github_dark";

      editor = {
        line-number = "absolute";
        mouse = true;
        true-color = true;
        color-modes = false;
        bufferline = "multiple";
        cursorline = false;

        cursor-shape = {
          normal = "block";
          insert = "bar";
          select = "underline";
        };

        gutters = {
          layout = [
            "diff"
            "diagnostics"
            "line-numbers"
            "spacer"
          ];
        };

        statusline = {
          left = [
            "mode"
            "file-name"
            "read-only-indicator"
            "file-modification-indicator"
          ];
          center = [ ];
          right = [
            "diagnostics"
            "selections"
            "position"
          ];
          separator = "│";
        };
      };
    };
  };
}
