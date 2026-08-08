{ pkgs, ... }:

let
  tomlFormat = pkgs.formats.toml { };
in
{
  xdg.configFile."herdr/config.toml" = {
    force = true;
    source = tomlFormat.generate "herdr-config.toml" {
      onboarding = false;

      ui = {
        agent_panel_sort = "priority";
        pane_borders = true;
        pane_gaps = false;
        pane_scrollbars = true;
        show_agent_labels_on_pane_borders = true;

        toast.delivery = "off";
      };

      experimental.pane_history = true;

      theme = {
        name = "terminal";
        auto_switch = false;
      };
    };
  };
}
