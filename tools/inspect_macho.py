"""Inspect device ARM64 Mach-O images in the probe application on macOS."""

import argparse
from pathlib import Path
import re
import subprocess
import sys


def inspect(bundle):
    app = "PhoneOSProbe"
    frameworks = ("ProbeBase", "ProbePlugin")
    install_names = {name: f"@rpath/{name}.framework/{name}" for name in frameworks}
    dependencies = {
        app: {install_names["ProbePlugin"]},
        "ProbeBase": set(),
        "ProbePlugin": {install_names["ProbeBase"]},
    }
    for name, expected in dependencies.items():
        image = bundle / (app if name == app else f"Frameworks/{name}.framework/{name}")

        def image_tool(*arguments):
            result = subprocess.check_output(["xcrun", *arguments, str(image)], text=True)
            print(result.rstrip())
            return result

        if image_tool("lipo", "-archs").split() != ["arm64"]:
            raise ValueError(f"Expected a single arm64 slice: {name}")
        build = image_tool("vtool", "-show-build")
        if re.findall(r"^\s*platform\s+(\S+)", build, re.M) != ["IOS"]:
            raise ValueError(f"Expected iPhoneOS platform: {name}")
        if re.findall(r"^\s*minos\s+(\S+)", build, re.M) != ["16.3"]:
            raise ValueError(f"Expected minimum iOS 16.3: {name}")
        header = image_tool("otool", "-hv")
        kind = "EXECUTE" if name == app else "DYLIB"
        if not re.search(rf"\b{kind}\b", header):
            raise ValueError(f"Expected Mach-O type {kind}: {name}")

        commands = image_tool("otool", "-l")
        rpaths = re.findall(r"cmd\s+LC_RPATH\s+cmdsize\s+\d+\s+path\s+(\S+)", commands)
        if rpaths != (["@executable_path/Frameworks"] if name == app else []):
            raise ValueError(f"Unexpected RPATH entries for {name}: {rpaths}")
        if name != app:
            install_id = [line.strip() for line in image_tool("otool", "-D").splitlines()[1:] if line.strip()]
            if install_id != [install_names[name]]:
                raise ValueError(f"Unexpected install name for {name}: {install_id}")

        linked = {
            line.strip().split(" (", 1)[0]
            for line in image_tool("otool", "-L").splitlines()[1:]
            if line.strip()
        }
        if name != app:
            linked.discard(install_names[name])
        private = {path for path in linked if not path.startswith(("/System/Library/", "/usr/lib/"))}
        if private != expected:
            raise ValueError(f"Unexpected private dependencies for {name}: {sorted(private)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        inspect(args.bundle)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"Mach-O inspection failed: {error}")
