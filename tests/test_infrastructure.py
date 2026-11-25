from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import plistlib
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_public_tree import check_blob
from inspect_ipa import APP, EXECUTABLES, PLISTS, PREFIX, inspect
from inspect_macho import inspect as inspect_macho


class PackageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.bundle = Path(temporary.name) / "Probe.app"
        self.ipa = Path(temporary.name) / "Probe.ipa"
        self.files = {name: f"synthetic {name}".encode() for name in EXECUTABLES}
        self.files.update({name: plistlib.dumps(fields) for name, fields in PLISTS.items()})

    def build(self, omit=None, extra=None, mode=stat.S_IFREG | 0o755):
        with zipfile.ZipFile(self.ipa, "w") as archive:
            for name, data in self.files.items():
                original = self.bundle / name
                original.parent.mkdir(parents=True, exist_ok=True)
                original.write_bytes(data)
                if name != omit:
                    entry = zipfile.ZipInfo(PREFIX + name)
                    entry.create_system = 3
                    entry.external_attr = (mode if name == APP else stat.S_IFREG | 0o755) << 16
                    archive.writestr(entry, data)
            if extra is not None:
                archive.writestr(extra, b"unexpected")

    def run_inspection(self):
        with redirect_stdout(StringIO()) as output:
            inspect(self.ipa, self.bundle)
        return output.getvalue()

    def test_valid(self):
        self.build()
        self.assertIn(self.ipa.name, self.run_inspection())

    def test_missing(self):
        self.build(omit="Frameworks/ProbeBase.framework/Info.plist")
        with self.assertRaisesRegex(ValueError, "Missing bundle files"):
            self.run_inspection()

    def test_unsafe_or_unexpected(self):
        for extra in ("Payload/../traverse", "/absolute", PREFIX + "unexpected.log"):
            with self.subTest(extra=extra):
                self.build(extra=extra)
                with self.assertRaisesRegex(ValueError, "outside bundle inventory"):
                    self.run_inspection()

    def test_duplicate(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.build(extra=PREFIX + APP)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.run_inspection()

    def test_mode_or_symlink(self):
        for mode in (stat.S_IFREG | 0o644, stat.S_IFLNK | 0o777):
            with self.subTest(mode=mode):
                self.build(mode=mode)
                with self.assertRaisesRegex(ValueError, "permission|regular"):
                    self.run_inspection()

    def test_digest(self):
        self.build()
        (self.bundle / APP).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_inspection()

    def test_crc(self):
        self.build()
        marker = self.files[APP]
        self.ipa.write_bytes(self.ipa.read_bytes().replace(marker, b"!" * len(marker)))
        with self.assertRaisesRegex(zipfile.BadZipFile, "CRC"):
            self.run_inspection()

    def test_plist(self):
        self.files["Info.plist"] = plistlib.dumps({"CFBundleExecutable": "other"})
        self.build()
        with self.assertRaisesRegex(ValueError, "Unexpected plist"):
            self.run_inspection()


class MachOTests(unittest.TestCase):
    @staticmethod
    def tool(command, **kwargs):
        _, tool, flag, path = command
        name = Path(path).name
        install = lambda n: f"@rpath/{n}.framework/{n}"
        links = {
            APP: [install("ProbePlugin")],
            "ProbePlugin": [install("ProbePlugin"), install("ProbeBase")],
            "ProbeBase": [install("ProbeBase")],
        }
        return {
            ("lipo", "-archs"): "arm64\n",
            ("vtool", "-show-build"): " platform IOS\n minos 16.3\n",
            ("otool", "-hv"): "filetype EXECUTE\n" if name == APP else "filetype DYLIB\n",
            ("otool", "-l"): (
                " cmd LC_RPATH\n cmdsize 48\n path @executable_path/Frameworks (offset 12)\n"
                if name == APP else ""
            ),
            ("otool", "-D"): f"{name}:\n{install(name)}\n",
            ("otool", "-L"): f"{name}:\n" + "".join(f"\t{link} (version)\n" for link in links[name]),
        }[(tool, flag)]

    def test_expected_images(self):
        with patch("inspect_macho.subprocess.check_output", side_effect=self.tool), redirect_stdout(StringIO()):
            inspect_macho(Path("Probe.app"))

    def test_simulator_or_bad_rpath(self):
        for flag, corrupt in (("-show-build", "platform IOSSIMULATOR\n minos 16.3\n"), ("-l", "")):
            with self.subTest(flag=flag):
                def emulate(command, **kwargs):
                    return corrupt if command[2] == flag else self.tool(command, **kwargs)

                with patch("inspect_macho.subprocess.check_output", side_effect=emulate):
                    with self.assertRaisesRegex(ValueError, "platform|RPATH"), redirect_stdout(StringIO()):
                        inspect_macho(Path("Probe.app"))


class PublicationTests(unittest.TestCase):
    def test_approved_text(self):
        check_blob("README.md", "100644", b"Example documentation")

    def test_reject_path_mode_binary_and_sensitive_content(self):
        for path, mode, data in (
            ("private/output.ipa", "100644", b"test"),
            ("README.md", "120000", b"target"),
            ("README.md", "100644", b"MZ\0"),
            ("README.md", "100644", b"-----BEGIN " + b"PRIVATE KEY-----"),
            ("README.md", "100644", b"C:" + b"/Users/" + b"someone"),
            ("README.md", "100644", b"PPC_" + b"FUNC_IMPL(example)"),
        ):
            with self.subTest(path=path, mode=mode):
                with self.assertRaises(ValueError):
                    check_blob(path, mode, data)
