"""Synthetic XCFramework and Mach-O tool-output tests for Windows."""

from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from inspect_moltenvk import check_archive_members, inspect_archive, select_moltenvk


class MoltenVKSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "MoltenVK.xcframework"
        self.root.mkdir()
        self.plist = self.root / "Info.plist"
        self.device = {
            "LibraryIdentifier": "device-from-metadata",
            "LibraryPath": "libMoltenVK.a",
            "SupportedPlatform": "ios",
            "SupportedArchitectures": ["arm64"],
        }
        self.simulator = {
            **self.device, "LibraryIdentifier": "simulator-from-metadata",
            "SupportedPlatformVariant": "simulator",
        }

    def write_entries(self, *entries):
        self.plist.write_bytes(plistlib.dumps({"AvailableLibraries": list(entries)}))

    def test_selects_device_when_simulator_is_first(self):
        self.write_entries(self.simulator, self.device)
        for entry in (self.simulator, self.device):
            directory = self.root / entry["LibraryIdentifier"]
            directory.mkdir()
            (directory / "libMoltenVK.a").write_bytes(b"synthetic")
        self.assertEqual(select_moltenvk(self.root),
                         (self.root / "device-from-metadata/libMoltenVK.a").resolve())

    def test_rejects_simulator_only_and_incompatible_architecture(self):
        for entry in (self.simulator, {**self.device, "SupportedArchitectures": ["x86_64"]}):
            with self.subTest(entry=entry):
                self.write_entries(entry)
                with self.assertRaisesRegex(ValueError, "found 0"):
                    select_moltenvk(self.root)

    def test_rejects_ambiguous_and_duplicate_entries(self):
        self.write_entries(self.device, {**self.device, "LibraryIdentifier": "second-device"})
        with self.assertRaisesRegex(ValueError, "found 2"):
            select_moltenvk(self.root)
        self.write_entries(self.device, self.device)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            select_moltenvk(self.root)

    def test_rejects_missing_or_invalid_metadata(self):
        with self.assertRaises(FileNotFoundError):
            select_moltenvk(self.root)
        self.plist.write_bytes(b"not a plist")
        with self.assertRaises(plistlib.InvalidFileException):
            select_moltenvk(self.root)
        self.plist.write_bytes(plistlib.dumps({}))
        with self.assertRaisesRegex(ValueError, "AvailableLibraries"):
            select_moltenvk(self.root)
        self.write_entries({**self.device, "LibraryPath": "../libMoltenVK.a"})
        with self.assertRaisesRegex(ValueError, "Invalid static"):
            select_moltenvk(self.root)

    def test_rejects_missing_archive(self):
        self.write_entries(self.device)
        with self.assertRaises(FileNotFoundError):
            select_moltenvk(self.root)


def build_command(platform="IOS", minimum="16.3"):
    return ("Load command 0\n      cmd LC_BUILD_VERSION\n  cmdsize 32\n"
            f" platform {platform}\n    minos {minimum}\n      sdk 18.5\n")


class ArchiveInspectionTests(unittest.TestCase):
    def test_excludes_only_a_verified_darwin_symbol_index(self):
        names = ("__.SYMDEF SORTED", "__.SYMDEF_64 SORTED")
        output = "libMoltenVK.a(real.o):\n" + build_command()

        def member(name, data):
            label = name.encode()
            extended = label + b"\0" * (-len(label) % 4)
            payload = extended + data
            header = (f"{'#1/' + str(len(extended)):<16}{0:<12}{0:<6}{0:<6}{0:<8}"
                      f"{len(payload):<10}").encode("ascii")
            return header + b"\x60\n" + payload + (b"\n" if len(payload) % 2 else b"")

        for width, name in zip((4, 8), names):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                archive = Path(folder) / "libMoltenVK.a"
                table = f"{name}\nreal.o\n"
                strings = b"_probe\0\0"
                index_size = 4 * width + len(strings)
                object_offset = 8 + len(member(name, bytes(index_size)))
                index = b"".join(value.to_bytes(width, "little")
                                 for value in (2 * width, 0, object_offset, len(strings))) + strings
                regular = member("real.o", b"fixture")
                with redirect_stderr(StringIO()) as report:
                    archive.write_bytes(b"!<arch>\n" + member(name, index) + regular)
                    self.assertEqual(check_archive_members(table, output, "16.3", archive), 1)
                    # LLVM ar already omits the index from its listing.
                    self.assertEqual(check_archive_members("real.o\n", output, "16.3", archive), 1)
                    with self.assertRaisesRegex(ValueError, "failed iPhoneOS"):
                        check_archive_members(table, output.replace("IOS", "IOSSIMULATOR"),
                                              "16.3", archive)
                    with self.assertRaisesRegex(ValueError, "every MoltenVK"):
                        check_archive_members(table + "unknown.o\n", output, "16.3", archive)
                    archive.write_bytes(b"!<arch>\n" + member(name, b"LLVM bitcode fixture") + regular)
                    with self.assertRaisesRegex(ValueError, "every MoltenVK"):
                        check_archive_members(table, output, "16.3", archive)
                self.assertIn("verified Darwin symbol index", report.getvalue())
                self.assertIn("could not classify", report.getvalue())

    def test_checks_every_archive_member_including_duplicate_names(self):
        output = (
            "/output/libMoltenVK.a(collision.o):\n" + build_command()
            + "/output/libMoltenVK.a(collision.o) (architecture arm64):\n" + build_command("2")
        )
        with redirect_stderr(StringIO()) as report:
            self.assertEqual(check_archive_members("collision.o\ncollision.o\n", output, "16.3"), 2)
        self.assertIn("Verified MoltenVK otool section #2 'collision.o'", report.getvalue())

    def test_incomplete_inventory_diagnostics_preserve_multiplicity(self):
        table = "collision.o\ncollision.o\n__.SYMDEF SORTED\n"
        output = "libMoltenVK.a(collision.o):\n" + build_command() + "libMoltenVK.a(other.o):\n"
        with redirect_stderr(StringIO()) as report:
            with self.assertRaisesRegex(ValueError, "every MoltenVK archive member"):
                check_archive_members(table, output, "16.3")
        for expected in ("only in ar -t: 'collision.o' (count 1)", "only in ar -t: '__.SYMDEF SORTED'",
                         "only in parsed otool output: 'other.o'", "otool header sample",
                         "Verified MoltenVK otool section #1", "Failed MoltenVK otool section #2"):
            self.assertIn(expected, report.getvalue())

    def test_simulator_and_unverified_platform_are_reported(self):
        output = ("libMoltenVK.a(sim.o):\n" + build_command("7")
                  + "libMoltenVK.a(no-platform.o):\n")
        with redirect_stderr(StringIO()) as report:
            with self.assertRaisesRegex(ValueError, "2 MoltenVK archive member"):
                check_archive_members("sim.o\nno-platform.o\n", output, "16.3")
        self.assertIn("'sim.o': expected one iPhoneOS LC_BUILD_VERSION; found ['7']", report.getvalue())
        self.assertIn("'no-platform.o': expected one iPhoneOS LC_BUILD_VERSION; found []",
                      report.getvalue())

    def test_keeps_unrecognized_non_object_header_for_diagnosis(self):
        with redirect_stderr(StringIO()) as report:
            with self.assertRaisesRegex(ValueError, "every MoltenVK archive member"):
                check_archive_members("unknown.o\n", "libMoltenVK.a(unknown.o): is not an object file\n",
                                      "16.3")
        self.assertIn("is not an object file", report.getvalue())
        self.assertIn("only in ar -t: 'unknown.o'", report.getvalue())

    def test_apple_archive_header_diagnostic_and_tool_failure(self):
        archive = Path("libMoltenVK.a")
        error = subprocess.CalledProcessError(1, ["xcrun", "otool"])
        for raw_headers in ("archive header line\n", error):
            with self.subTest(raw_headers=raw_headers):
                with patch("inspect_moltenvk.xcrun", side_effect=["arm64\n", "missing.o\n", "",
                                                                 raw_headers]) as tool:
                    with redirect_stderr(StringIO()) as report:
                        with self.assertRaisesRegex(ValueError, "every MoltenVK archive member"):
                            inspect_archive(archive, "16.3")
                tool.assert_called_with("otool", "-arch", "arm64", "-av", archive)
                expected = ("raw archive headers unavailable" if raw_headers is error
                            else "archive header line")
                self.assertIn(expected, report.getvalue())

    def test_primary_tool_failure_still_fails_inspection(self):
        error = subprocess.CalledProcessError(1, ["xcrun", "otool"])
        with patch("inspect_moltenvk.xcrun", side_effect=["arm64\n", "test.o\n", error]):
            with redirect_stderr(StringIO()):
                with self.assertRaises(subprocess.CalledProcessError):
                    inspect_archive(Path("libMoltenVK.a"), "16.3")


if __name__ == "__main__":
    unittest.main()
