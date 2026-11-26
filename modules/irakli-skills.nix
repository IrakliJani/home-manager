{ irakliSkills, ... }:

# Irakli's own skills and AGENTS.md, from the private IrakliJani/skills repo.
{
  programs.agent-skills = {
    sources.irakli.path = irakliSkills;
    skills.enableAll = [ "irakli" ];
  };

  home.file.".agents/AGENTS.md".source = "${irakliSkills}/AGENTS.md";

  home.file.".local/bin/nix-flake-fleet" = {
    source = "${irakliSkills}/nix-flake-fleet/scripts/nix-flake-fleet";
    executable = true;
  };
}
