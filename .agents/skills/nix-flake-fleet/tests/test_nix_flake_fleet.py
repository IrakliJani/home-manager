from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/nix-flake-fleet"
LOADER = importlib.machinery.SourceFileLoader("nix_flake_fleet", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = MODULE
LOADER.exec_module(MODULE)


class NixSourceParsingTests(unittest.TestCase):
    def test_direct_inputs_ignore_comments_and_strings(self) -> None:
        source = '''
          # inputs.comment.url = "github:example/comment/main";
          /* inputs.block.url = "github:example/block/main"; */
          note = "inputs.double.url = \\"github:example/double/main\\";";
          text = ''inputs.indented.url = "github:example/indented/main";'';
          inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
          home-manager.url = "github:nix-community/home-manager/master";
        '''
        assignments = MODULE.find_direct_url_assignments(source)
        self.assertEqual(
            [(value.name, value.url) for value in assignments],
            [
                ("nixpkgs", "github:NixOS/nixpkgs/nixos-24.11"),
                ("home-manager", "github:nix-community/home-manager/master"),
            ],
        )

    def test_auto_target_ignores_documentation(self) -> None:
        sources = [
            "# nixosConfigurations is only documentation\npackages = {};",
            'description = "uses nixosSystem elsewhere"; packages = {};',
            "text = ''nixosConfigurations = {};''; packages = {};",
            "/* nixosSystem */ packages = {};",
            "my-nixosSystem-wrapper = true; packages = {};",
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(
                    MODULE.target_ref_for(source, "auto"),
                    "nixpkgs-unstable",
                )

    def test_auto_target_detects_nixos_code(self) -> None:
        sources = [
            "nixosConfigurations.host = {};",
            "host = nixpkgs.lib.nixosSystem {};",
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(
                    MODULE.target_ref_for(source, "auto"),
                    "nixos-unstable",
                )

    def test_only_supported_unstable_refs_are_preserved(self) -> None:
        self.assertTrue(MODULE.is_unstable("nixos-unstable"))
        self.assertTrue(MODULE.is_unstable("NIXPKGS-UNSTABLE"))
        self.assertFalse(MODULE.is_unstable("nixos-unstable-small"))
        self.assertFalse(MODULE.is_unstable("not-unstable"))
        self.assertFalse(MODULE.is_unstable(None))


if __name__ == "__main__":
    unittest.main()
