"""Check the linked synthetic iPhoneOS executable and print its imports."""

import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess

from inspect_moltenvk import check_device, fields, load_commands, require_arm64, version, xcrun


def check_linked_image(archs, header, output, libraries, symbols, target, sdk):
    require_arm64(archs, "Link probe")
    if not re.search(r"^\s*MH_MAGIC_64\s+ARM64\s+\S+\s+\S+\s+EXECUTE\s", header, re.M):
        raise ValueError("Link probe: expected ARM64 MH_EXECUTE")

    commands = load_commands(output)
    minimum = check_device(commands, target, "Link probe")
    sdk_versions = fields(commands, "LC_BUILD_VERSION", "sdk")
    if version(minimum) != version(target) or [version(item) for item in sdk_versions] != [version(sdk)]:
        raise ValueError(f"Link probe: expected minos {target} and SDK {sdk}; found {minimum}, {sdk_versions}")
    if any(command in {"LC_RPATH", "LC_ID_DYLIB"} for command, _ in commands):
        raise ValueError("Link probe: unexpected LC_RPATH or LC_ID_DYLIB")

    lines = libraries.splitlines()
    if len(lines) < 2 or not lines[0].endswith(":"):
        raise ValueError("Link probe: incomplete otool dynamic dependency listing")
    for line in lines[1:]:
        dependency, separator, _ = line.strip().partition(" (")
        path = PurePosixPath(dependency)
        if (not separator or not dependency.startswith(("/System/Library/", "/usr/lib/"))
                or ".." in path.parts or "moltenvk" in dependency.lower()):
            raise ValueError(f"Link probe: unexpected dynamic dependency {dependency!r}")
    if not re.search(r"^[0-9A-Fa-f]+[ \t]+[Tt][ \t]+_vkGetInstanceProcAddr[ \t]*$", symbols, re.M):
        raise ValueError("Link probe: missing static definition of vkGetInstanceProcAddr")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--deployment-target", required=True)
    parser.add_argument("--sdk-version", required=True)
    args = parser.parse_args()
    try:
        archs = xcrun("lipo", "-archs", args.binary)
        header = xcrun("otool", "-hv", args.binary)
        output = xcrun("otool", "-l", args.binary)
        libraries = xcrun("otool", "-L", args.binary)
        symbols = xcrun("nm", "-U", args.binary)
        undefined = xcrun("nm", "-u", "-m", args.binary)
        print(f"Architecture: {archs.strip()}\n{header.rstrip()}")
        print(f"Build metadata:\n{fields(load_commands(output), 'LC_BUILD_VERSION', 'platform')}")
        print(f"Dynamic dependencies:\n{libraries.rstrip()}")
        print(f"Undefined symbols and providers:\n{undefined.rstrip()}")
        check_linked_image(archs, header, output, libraries, symbols,
                           args.deployment_target, args.sdk_version)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"MoltenVK link inspection failed: {error}\n")
    print(f"Static vkGetInstanceProcAddr verified: iPhoneOS ARM64, minos {args.deployment_target}, "
          f"SDK {args.sdk_version}")


if __name__ == "__main__":
    main()
