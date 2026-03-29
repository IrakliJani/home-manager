{ ... }:

{
  programs.git = {
    signing = {
      key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA/48Asjhf6j0n2pUZjb2NX9klFv/Z5VBpUq+lFUkSPX";
      signByDefault = true;
      format = "ssh";
      # signer set in modules/platform/darwin.nix
    };

    settings = {
      user = {
        name = "Irakli Janiashvili";
        email = "irakli.janiashvili@gmail.com";
      };
    };
  };
}
