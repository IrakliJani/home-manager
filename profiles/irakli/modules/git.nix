{ config, ... }:

let
  userName = "Irakli Janiashvili";
  userEmail = "irakli.janiashvili@gmail.com";
  signingKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA/48Asjhf6j0n2pUZjb2NX9klFv/Z5VBpUq+lFUkSPX";
in
{
  xdg.configFile."git/allowed_signers".text = ''
    ${userEmail} ${signingKey}
  '';

  programs.git = {
    signing = {
      key = signingKey;
      signByDefault = true;
      format = "ssh";
      # Use ssh-keygen with the SSH agent selected by the session.
    };

    settings = {
      gpg.ssh.allowedSignersFile = "${config.xdg.configHome}/git/allowed_signers";

      user = {
        name = userName;
        email = userEmail;
      };
    };
  };
}
