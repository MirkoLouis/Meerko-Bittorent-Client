# SPDX-License-Identifier: GPL-3.0-or-later
{
    description = "Meerko Bittorent: a privacy- and performance-focused BitTorrent client";

    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    };

    outputs = { self, nixpkgs }:
        let
            system = "x86_64-linux";
            pkgs = nixpkgs.legacyPackages.${system};
            lib = nixpkgs.lib;
            python = pkgs.python3;

            # Read the version from its single source, meerko_bittorent/__init__.py
            initLines = lib.splitString "\n" (builtins.readFile ./meerko_bittorent/__init__.py);
            versionMatches = builtins.filter (match: match != null)
                (map (line: builtins.match ''__version__ = "([^"]+)"'' line) initLines);
            version = builtins.head (builtins.head versionMatches);

            # Runtime Python dependencies, shared by the package and the dev shell
            runtimeDependencies = pythonPackages: [
                pythonPackages.libtorrent-rasterbar
                pythonPackages.tkinter
            ];

            # The application, built from pyproject.toml; the check phase runs the pytest suite
            package = python.pkgs.buildPythonApplication {
                pname = "meerko-bittorent";
                inherit version;
                src = ./.;
                pyproject = true;
                build-system = [ python.pkgs.setuptools ];
                dependencies = runtimeDependencies python.pkgs;
                nativeCheckInputs = [ python.pkgs.pytestCheckHook ];
                pythonImportsCheck = [ "meerko_bittorent" ];
                meta = {
                    description = "Privacy- and performance-focused BitTorrent client";
                    homepage = "https://github.com/MirkoLouis/Meerko-Bittorent-Client";
                    license = lib.licenses.gpl3Plus;
                    mainProgram = "meerko-bittorent";
                    platforms = [ system ];
                };
            };
        in
        {
            # nix build / nix run
            packages.${system}.default = package;
            apps.${system}.default = {
                type = "app";
                program = lib.getExe package;
            };

            # nix develop: Python with libtorrent, tkinter and pytest; no venv needed
            devShells.${system}.default = pkgs.mkShell {
                packages = [
                    (python.withPackages (pythonPackages:
                        runtimeDependencies pythonPackages ++ [ pythonPackages.pytest ]))
                ];
            };

            # nix flake check: builds the package, which runs the tests
            checks.${system}.default = package;
        };
}
