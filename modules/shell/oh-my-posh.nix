{ ... }:

{
  programs.oh-my-posh = {
    enable = true;
    enableZshIntegration = true;

    settings = {
      "$schema" = "https://raw.githubusercontent.com/JanDeDobbeleer/oh-my-posh/main/themes/schema.json";
      version = 4;
      final_space = true;

      palette = {
        os = "#ACB0BE";
        closer = "p:os";
        pink = "#F5C2E7";
        lavender = "#B4BEFE";
        blue = "#89B4FA";
      };

      blocks = [
        {
          type = "prompt";
          alignment = "left";
          segments = [
            {
              type = "os";
              style = "plain";
              foreground = "p:os";
              template = "{{.Icon}} ";
            }
            {
              type = "session";
              style = "plain";
              foreground = "p:blue";
              template = "{{ .UserName }}@{{ .HostName }} ";
            }
            {
              type = "path";
              style = "plain";
              foreground = "p:pink";
              template = "{{ .Path }} ";
              options = {
                folder_icon = "....";
                home_icon = "~";
                style = "agnoster_short";
                max_depth = 2;
              };
            }
            {
              type = "git";
              style = "plain";
              foreground = "p:lavender";
              template = "{{ .HEAD }} ";
              options = {
                branch_icon = " ";
                cherry_pick_icon = "cherry-pick ";
                commit_icon = "@ ";
                fetch_status = false;
                fetch_upstream_icon = false;
                merge_icon = "merge ";
                no_commits_icon = "empty ";
                rebase_icon = "rebase ";
                revert_icon = "revert ";
                tag_icon = "tag ";
              };
            }
          ];
        }
        {
          type = "prompt";
          alignment = "right";
          segments = [
            {
              type = "executiontime";
              style = "plain";
              foreground = "p:pink";
              template = "{{ .FormattedMs }} ";
              options = {
                always_enabled = true;
                threshold = 0;
                style = "roundrock";
              };
            }
            {
              type = "text";
              style = "plain";
              foreground = "p:closer";
              template = "󰇘 ";
            }
            {
              type = "status";
              style = "plain";
              foreground = "#A6E3A1";
              foreground_templates = [
                "{{ if gt .Code 0 }}#F38BA8{{ end }}"
              ];
              template = "{{ .Code }} ";
              options = {
                always_enabled = true;
              };
            }
          ];
        }
        {
          type = "prompt";
          alignment = "left";
          newline = true;
          segments = [
            {
              type = "status";
              style = "plain";
              foreground = "p:closer";
              foreground_templates = [
                "{{ if gt .Code 0 }}#F38BA8{{ end }}"
              ];
              template = "";
              options = {
                always_enabled = true;
              };
            }
          ];
        }
      ];
    };
  };
}
