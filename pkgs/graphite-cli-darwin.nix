{
  lib,
  stdenvNoCC,
  fetchurl,
}:

let
  version = "1.8.6";

  selectSystem =
    attrs:
    attrs.${stdenvNoCC.hostPlatform.system} or (
      throw "Unsupported system: ${stdenvNoCC.hostPlatform.system}"
    );

  suffix = selectSystem {
    x86_64-darwin = "darwin-x64";
    aarch64-darwin = "darwin-arm64";
  };
in
stdenvNoCC.mkDerivation {
  pname = "graphite-cli";
  inherit version;

  src = fetchurl {
    url = "https://registry.npmjs.org/@withgraphite/graphite-cli-${suffix}/-/graphite-cli-${suffix}-${version}.tgz";
    hash = selectSystem {
      x86_64-darwin = "sha256-oV0tanuk2dzB62uChni9CJtSw3eFECQi3aMBc+ZV7Do=";
      aarch64-darwin = "sha256-6eogi8fMOD5IgRyEdPRxdDa17WytB1JwTpKRzyyhQ2Q=";
    };
  };

  sourceRoot = "package";

  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    install -Dm755 bin/gt $out/bin/gt
    ln -s gt $out/bin/graphite
    runHook postInstall
  '';

  meta = {
    description = "CLI that makes creating stacked git changes fast & intuitive";
    homepage = "https://graphite.dev/docs/graphite-cli";
    downloadPage = "https://www.npmjs.com/package/@withgraphite/graphite-cli";
    license = lib.licenses.unfree; # no license specified
    mainProgram = "gt";
    platforms = [
      "x86_64-darwin"
      "aarch64-darwin"
    ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
}
