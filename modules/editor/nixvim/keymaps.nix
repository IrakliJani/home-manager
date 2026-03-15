{ ... }:

{
  programs.nixvim.keymaps = [
    { mode = "n"; key = "<leader>ff"; action = "<cmd>Telescope find_files<cr>"; options.desc = "Find files"; }
    { mode = "n"; key = "<leader>fg"; action = "<cmd>Telescope live_grep<cr>"; options.desc = "Live grep"; }
    { mode = "n"; key = "<leader>fb"; action = "<cmd>Telescope buffers<cr>"; options.desc = "Buffers"; }
    { mode = "n"; key = "<leader>gd"; action = "<cmd>DiffviewOpen<cr>"; options.desc = "Diffview open"; }
    { mode = "n"; key = "<leader>gh"; action = "<cmd>DiffviewFileHistory %<cr>"; options.desc = "File history"; }
    { mode = "n"; key = "<leader>gc"; action = "<cmd>DiffviewClose<cr>"; options.desc = "Diffview close"; }
  ];
}
