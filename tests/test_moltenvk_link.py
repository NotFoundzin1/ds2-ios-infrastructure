"""Test the link-probe Mach-O gate using synthetic Apple tool output."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from inspect_moltenvk_link import check_linked_image


class MoltenVKLinkTests(unittest.TestCase):
    header = "Mach header\nMH_MAGIC_64 ARM64 ALL 0x00 EXECUTE 15 650 NOUNDEFS\n"
    load = "Load command 0\n cmd LC_BUILD_VERSION\n platform IOS\n minos 16.3\n sdk 18.5\n"
    libraries = "probe:\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n"
    symbols = "0000000100001234 T _vkGetInstanceProcAddr\n"

    def inspect(self, arch="arm64", header=header, load=load, libraries=libraries, symbols=symbols):
        check_linked_image(arch, header, load, libraries, symbols, "16.3", "18.5")

    def test_accepts_static_symbol_and_device_image(self):
        self.inspect()

    def test_rejects_simulator_and_wrong_architecture(self):
        with self.assertRaisesRegex(ValueError, "iPhoneOS"):
            self.inspect(load=self.load.replace("IOS", "IOSSIMULATOR"))
        with self.assertRaisesRegex(ValueError, "arm64 only"):
            self.inspect(arch="x86_64")
        with self.assertRaisesRegex(ValueError, "MH_EXECUTE"):
            self.inspect(header=self.header.replace("EXECUTE", "DYLIB"))

    def test_rejects_wrong_minimum_and_sdk(self):
        for load in (self.load.replace("16.3", "16.2"), self.load.replace("18.5", "26.0")):
            with self.subTest(load=load), self.assertRaisesRegex(ValueError, "expected minos"):
                self.inspect(load=load)

    def test_rejects_dynamic_moltenvk_and_runner_dependencies(self):
        for dependency in ("@rpath/libMoltenVK.dylib", "/usr/lib/libMoltenVK.dylib", "/runner/lib/x.dylib"):
            with self.subTest(dependency=dependency), self.assertRaisesRegex(ValueError, "dynamic dependency"):
                self.inspect(libraries=self.libraries.replace("/usr/lib/libSystem.B.dylib", dependency))

    def test_rejects_incomplete_dependency_listing(self):
        with self.assertRaisesRegex(ValueError, "incomplete otool"):
            self.inspect(libraries="probe:\n")

    def test_rejects_unexpected_rpath_and_missing_definition(self):
        with self.assertRaisesRegex(ValueError, "LC_RPATH"):
            self.inspect(load=self.load + "Load command 1\n cmd LC_RPATH\n path /runner\n")
        for symbols in ("", "                 U _vkGetInstanceProcAddr\n",
                        self.symbols.replace("vkGet", "vkget")):
            with self.subTest(symbols=symbols), self.assertRaisesRegex(ValueError, "missing static definition"):
                self.inspect(symbols=symbols)


if __name__ == "__main__":
    unittest.main()
