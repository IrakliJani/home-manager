{
  pkgs,
  lib,
  ...
}:

let
  withoutEnvApiKeys =
    {
      package,
      variables,
      preventDotenvFallback ? false,
    }:
    pkgs.symlinkJoin {
      name = package.name;
      paths = [ package ];
      nativeBuildInputs = [ pkgs.makeWrapper ];
      inherit (package) meta;
      postBuild = ''
        wrapProgram "$out/bin/${package.meta.mainProgram}" \
          ${lib.concatMapStringsSep " " (
            variable:
            if preventDotenvFallback then
              "--set ${lib.escapeShellArg variable} ''"
            else
              "--unset ${lib.escapeShellArg variable}"
          ) variables}
      '';
    };
in
{
  home.packages =
    with pkgs;
    [
      # networking
      curl
      wget

      # nix tooling
      nixd
      nixfmt

      # AI coding agent harnesses (from numtide/llm-agents.nix)
      # Keep the original executables, helpers, and completions; filter only their environment.
      (withoutEnvApiKeys {
        package = llm-agents.pi;
        # Bun respects existing empty values instead of refilling them from project dotenv files.
        preventDotenvFallback = true;
        variables = [
          "AI_GATEWAY_API_KEY"
          "ANTHROPIC_API_KEY"
          "ANTHROPIC_AUTH_TOKEN"
          "ANTHROPIC_OAUTH_TOKEN"
          "ANT_LING_API_KEY"
          "AWS_BEARER_TOKEN_BEDROCK"
          "AZURE_OPENAI_API_KEY"
          "BASETEN_API_KEY"
          "CEREBRAS_API_KEY"
          "CLOUDFLARE_API_KEY"
          "COPILOT_GITHUB_TOKEN"
          "DEEPSEEK_API_KEY"
          "FIREWORKS_API_KEY"
          "GEMINI_API_KEY"
          "GOOGLE_CLOUD_API_KEY"
          "GROQ_API_KEY"
          "HF_TOKEN"
          "KIMI_API_KEY"
          "META_API_KEY"
          "MINIMAX_API_KEY"
          "MINIMAX_CN_API_KEY"
          "MISTRAL_API_KEY"
          "MOONSHOT_API_KEY"
          "NVIDIA_API_KEY"
          "OPENCODE_API_KEY"
          "OPENAI_API_KEY"
          "OPENROUTER_API_KEY"
          "QWEN_TOKEN_PLAN_API_KEY"
          "QWEN_TOKEN_PLAN_CN_API_KEY"
          "RADIUS_API_KEY"
          "TOGETHER_API_KEY"
          "TYPESAFE_API_KEY"
          "XAI_API_KEY"
          "XIAOMI_API_KEY"
          "XIAOMI_TOKEN_PLAN_AMS_API_KEY"
          "XIAOMI_TOKEN_PLAN_CN_API_KEY"
          "XIAOMI_TOKEN_PLAN_SGP_API_KEY"
          "ZAI_API_KEY"
          "ZAI_CODING_CN_API_KEY"
        ];
      })
      llm-agents.opencode
      (withoutEnvApiKeys {
        package = llm-agents.claude-code;
        variables = [
          "ANTHROPIC_API_KEY"
          "ANTHROPIC_AUTH_TOKEN"
          "CLAUDE_CODE_API_KEY_FILE_DESCRIPTOR"
        ];
      })
      (withoutEnvApiKeys {
        package = llm-agents.codex;
        variables = [
          "OPENAI_API_KEY"
          "CODEX_API_KEY"
        ];
      })

      # Hugging Face CLI
      python3Packages.huggingface-hub

      # terminal workspace manager
      llm-agents.herdr
    ]
    ++ lib.optionals pkgs.stdenv.hostPlatform.isDarwin [
      apfel-llm
    ]
    ++ [
      # fonts
      nerd-fonts.victor-mono
      nerd-fonts.jetbrains-mono

      # runtimes
      nodejs
      bun
      python3
    ];
}
