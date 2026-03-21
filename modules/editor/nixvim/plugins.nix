{ config, ... }:

{
  programs.nixvim = {
    colorschemes.catppuccin = {
      enable = config.themes.catppuccin.enable;
      settings = {
        flavour = config.themes.catppuccin.flavor;
        term_colors = true;
        integrations = {
          diffview = true;
          gitsigns = true;
          telescope = true;
          treesitter_context = true;
        };
      };
    };

    plugins.lualine = {
      enable = true;
      settings.options = {
        section_separators = {
          left = "";
          right = "";
        };
        component_separators = {
          left = "";
          right = "";
        };
      };
    };
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
