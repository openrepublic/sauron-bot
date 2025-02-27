with (import <nixpkgs> {});
stdenv.mkDerivation {
  name = "sauron-bot-uv";
  buildInputs = [
    libgcc.lib
    # Python requirements.
    python311Full
    python311Packages.uv
    python311Packages.zstandard
  ];
  src = null;
  shellHook = ''
    set -e

    LIB_GCC_PATH="${libgcc.lib}/lib"
    LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$LIB_GCC_PATH"
    export LD_LIBRARY_PATH

    # Install deps
    uv lock

  '';
}
