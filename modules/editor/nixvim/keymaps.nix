{ ... }:

{
  programs.nixvim.keymaps = [
    { mode = "n"; key = "<leader>ff"; action = "<cmd>Telescope find_files<cr>"; options.desc = "Find files"; }
    { mode = "n"; key = "<leader>fg"; action = "<cmd>Telescope live_grep<cr>"; options.desc = "Live grep"; }
    { mode = "n"; key = "<leader>fb"; action = "<cmd>Telescope buffers<cr>"; options.desc = "Buffers"; }
    { mode = "n"; key = "<leader>gd"; action = "<cmd>CodeDiff<cr>"; options.desc = "CodeDiff"; }
    { mode = "n"; key = "<leader>gg"; action = "<cmd>Neogit<cr>"; options.desc = "Neogit"; }
    { mode = "n"; key = "<leader>gn"; action = "<cmd>Gitsigns next_hunk<cr>"; options.desc = "Next git hunk"; }
    { mode = "n"; key = "<leader>gp"; action = "<cmd>Gitsigns prev_hunk<cr>"; options.desc = "Previous git hunk"; }
    { mode = "n"; key = "<leader>gv"; action = "<cmd>Gitsigns preview_hunk<cr>"; options.desc = "Preview git hunk"; }
    { mode = "n"; key = "<leader>gs"; action = "<cmd>Gitsigns stage_hunk<cr>"; options.desc = "Stage git hunk"; }
    { mode = "n"; key = "<leader>gr"; action = "<cmd>Gitsigns reset_hunk<cr>"; options.desc = "Reset git hunk"; }

    { mode = "n"; key = "<leader>td"; action = "<cmd>lua vim.lsp.buf.definition()<cr>"; options.desc = "Go to definition"; }
    { mode = "n"; key = "<leader>tt"; action = "<cmd>lua vim.lsp.buf.hover()<cr>"; options.desc = "Hover"; }
  ];
}
