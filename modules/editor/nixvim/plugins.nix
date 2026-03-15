{ ... }:

{
  programs.nixvim = {
    colorschemes.catppuccin.enable = true;

    plugins.lualine.enable = true;
    plugins.web-devicons.enable = true;
    plugins.telescope.enable = true;
    plugins.gitsigns.enable = true;
    plugins.diffview.enable = true;
    plugins.treesitter.enable = true;

    plugins.lsp = {
      enable = true;
      servers = {
        nixd.enable = true;
      };
    };
  };
}
