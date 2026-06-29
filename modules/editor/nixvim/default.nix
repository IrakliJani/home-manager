{ pkgs, ... }:

{
  imports = [
    ./plugins.nix
    ./keymaps.nix
  ];

  programs.nixvim = {
    enable = true;
    defaultEditor = true;
    vimAlias = true;
    viAlias = true;

    nixpkgs.source = pkgs.path;

    globals.mapleader = ",";

    highlightOverride = {
      Normal.bg = "none";
      NormalNC.bg = "none";
      SignColumn.bg = "none";
      EndOfBuffer.bg = "none";
      LineNr.bg = "none";
      CursorLineNr.bg = "none";

      NormalFloat.bg = "none";
      FloatBorder.bg = "none";
      FloatTitle.bg = "none";

      Pmenu.bg = "none";
      PmenuSbar.bg = "none";
      PmenuThumb.bg = "none";

      StatusLine.bg = "none";
      StatusLineNC.bg = "none";
      TabLine.bg = "none";
      TabLineFill.bg = "none";
      WinBar.bg = "none";
      WinBarNC.bg = "none";

      BlinkCmpMenu.bg = "none";
      BlinkCmpDoc.bg = "none";
      BlinkCmpSignatureHelp.bg = "none";
      BlinkCmpMenuBorder.bg = "none";
      BlinkCmpDocBorder.bg = "none";
      BlinkCmpSignatureHelpBorder.bg = "none";
    };

    opts = {
      number = true;
      relativenumber = true;
      shiftwidth = 2;
      tabstop = 2;
      expandtab = true;
      mouse = "a";

      swapfile = false;
      backup = false;
      writebackup = false;
      undofile = true;
    };
  };
}
