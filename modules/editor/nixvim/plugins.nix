{ ... }:

{
  programs.nixvim = {
    colorscheme = "github_dark_default";

    colorschemes.github-theme = {
      enable = true;
      settings.options = {
        transparent = true;
        terminal_colors = true;
        styles.comments = "italic";
      };
    };

    plugins.lualine = {
      enable = true;
      settings.options = {
        theme = "auto";
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
    plugins.treesitter = {
      enable = true;
      highlight.enable = true;
      indent.enable = true;
    };
    plugins.codediff = {
      enable = true;
      settings = {
        view.layout = "side-by-side";
      };
    };

    plugins.neogit = {
      enable = true;
      settings = {
        kind = "tab";
        diff_viewer = "codediff";
        integrations = {
          codediff = true;
          diffview = false;
        };
        disable_commit_confirmation = true;
      };
    };

    plugins.blink-cmp = {
      enable = true;
      setupLspCapabilities = true;
      settings = {
        keymap.preset = "default";
        sources.default = [
          "lsp"
          "path"
        ];
        completion = {
          documentation.auto_show = true;
          accept.auto_brackets.enabled = false;
        };
        appearance = {
          use_nvim_cmp_as_default = true;
          nerd_font_variant = "normal";
        };
      };
    };

    plugins.noice = {
      enable = true;
      settings = {
        cmdline.enabled = false;
        messages.enabled = false;
        popupmenu.enabled = false;
        notify.enabled = false;

        lsp = {
          progress.enabled = false;
          hover.enabled = true;
          signature.enabled = false;
          override = {
            "vim.lsp.util.convert_input_to_markdown_lines" = true;
            "vim.lsp.util.stylize_markdown" = true;
          };
          documentation.opts = {
            max_width = 100;
            max_height = 30;
            win_options = {
              wrap = true;
              linebreak = true;
              conceallevel = 2;
            };
          };
        };

        presets.lsp_doc_border = true;
      };
    };

    plugins.lsp = {
      enable = true;
      servers = {
        nixd.enable = true;
        ts_ls.enable = true;
      };
    };
  };
}
