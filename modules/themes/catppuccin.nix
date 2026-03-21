{ lib, config, ... }:

let
  cfg = config.themes.catppuccin;
in
{
  options.themes.catppuccin = {
    enable = lib.mkEnableOption "shared Catppuccin settings";

    flavor = lib.mkOption {
      type = lib.types.enum [
        "latte"
        "frappe"
        "macchiato"
        "mocha"
      ];
      default = "mocha";
      description = "Catppuccin flavor used across themed applications.";
    };

    accent = lib.mkOption {
      type = lib.types.enum [
        "blue"
        "flamingo"
        "green"
        "lavender"
        "maroon"
        "mauve"
        "peach"
        "pink"
        "red"
        "rosewater"
        "sapphire"
        "sky"
        "teal"
        "yellow"
      ];
      default = "mauve";
      description = "Catppuccin accent used across themed applications.";
    };
  };

  config = lib.mkIf cfg.enable {
    catppuccin = {
      flavor = cfg.flavor;
      accent = cfg.accent;

      btop.enable = true;
      eza.enable = true;
      fzf.enable = true;
      tmux.enable = true;
      zsh-syntax-highlighting.enable = true;
    };
  };
}
