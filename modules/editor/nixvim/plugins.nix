{ ... }:

{
  programs.nixvim = {
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
