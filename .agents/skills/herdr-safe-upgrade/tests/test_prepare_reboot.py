from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/prepare-reboot.py"
LOADER = importlib.machinery.SourceFileLoader("prepare_reboot", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = MODULE
LOADER.exec_module(MODULE)


class PrepareRebootTests(unittest.TestCase):
    def test_stable_path_drops_store_entries_and_duplicates(self) -> None:
        value = ":".join(
            (
                "/nix/store/old-fd/bin",
                "/Users/test/.nix-profile/bin",
                "/usr/bin",
                "/nix/store/old-ripgrep/bin",
                "/usr/bin",
                "/bin",
            )
        )
        self.assertEqual(
            MODULE.stable_recovery_path(value),
            "/Users/test/.nix-profile/bin:/usr/bin:/bin",
        )

    def test_empty_stable_path_has_system_fallback(self) -> None:
        self.assertEqual(
            MODULE.stable_recovery_path("/nix/store/only/bin"),
            "/usr/bin:/bin:/usr/sbin:/sbin",
        )

    def test_binary_version_is_derived_from_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "herdr"
            binary.write_text("#!/bin/sh\necho 'herdr 9.8.7'\n")
            binary.chmod(0o700)
            self.assertEqual(MODULE.binary_version(binary), "9.8.7")

    def test_shortcut_replacement_is_atomic_and_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            shortcut = root / "ready"
            MODULE.replace_shortcut(shortcut, first)
            self.assertEqual(shortcut.resolve(), first.resolve())
            MODULE.replace_shortcut(shortcut, second)
            self.assertEqual(shortcut.resolve(), second.resolve())
            shortcut.unlink()
            shortcut.write_text("not a symlink")
            with self.assertRaisesRegex(RuntimeError, "non-symlink"):
                MODULE.replace_shortcut(shortcut, first)

    def test_restore_instructions_derive_the_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            shortcut = bundle / "ready"
            MODULE.write_restore_instructions(bundle, shortcut)
            instructions = (bundle / "RESTORE-INSTRUCTIONS.txt").read_text()
            self.assertIn('migration-config.json', instructions)
            self.assertIn('["new_binary"]', instructions)
            self.assertNotRegex(instructions, r"herdr-\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
