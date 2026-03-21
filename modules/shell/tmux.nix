{ ... }:

{
  programs.tmux = {
    enable = true;
    mouse = true;
    prefix = "C-b";
    baseIndex = 1;
    historyLimit = 50000;
    escapeTime = 0;

    extraConfig = ''
      # Split panes with sensible keys
      bind | split-window -h -c "#{pane_current_path}"
      bind - split-window -v -c "#{pane_current_path}"

      # New window keeps current path
      bind c new-window -c "#{pane_current_path}"
    '';
  };
}
