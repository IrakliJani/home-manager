{ pkgs, ... }:

# Skills other people publish. Irakli's own live in the private ~/code/skills repo.
{
  programs.agent-skills = {
    enable = true;

    sources = {
      cursor = {
        subdir = "pstack/skills";
        # Its other skills share names with Matt Pocock's.
        filter.nameRegex = "unslop";
      };
      # One source per folder, because some agents miss nested skills.
      matt-engineering.subdir = "skills/engineering";
      matt-productivity.subdir = "skills/productivity";
    };

    skills.enable = [
      # cursor/plugins
      "unslop"

      # mattpocock/skills, engineering
      "code-review"
      "codebase-design"
      "diagnosing-bugs"
      "domain-modeling"
      "grill-with-docs"
      "implement"
      "implement-spec"
      "improve-codebase-architecture"
      "pr"
      "prototype"
      "research"
      "retro"
      "tdd"
      "to-spec"
      "to-tickets"
      "triage"
      "wayfinder"
      "wizard"

      # mattpocock/skills, productivity
      "grill-me"
      "grilling"
      "handoff"
      "teach"
      "to-questionnaire"
      "wait-what"
      "writing-for-agents"
    ];

    # Never use the default "symlink-tree": once it owns ~/.agents/skills, it
    # deletes every skill it does not manage. "link" leaves them alone.
    targets.agents = {
      enable = true;
      dest = ".agents/skills";
      structure = "link";
    };
  };

  # herdr ships its skill, so the skill always matches the installed version.
  home.file.".agents/skills/herdr".source = "${pkgs.llm-agents.herdr}/share/skills/herdr/herdr";
}
