"""Check the synthetic IPA against its source bundle without extracting it."""

import argparse
import hashlib
import plistlib
import stat
import sys
from pathlib import Path, PurePosixPath
import zipfile


APP = "PhoneOSProbe"
PREFIX = f"Payload/{APP}.app/"
FRAMEWORKS = ("ProbeBase", "ProbePlugin")
EXECUTABLES = {APP} | {f"Frameworks/{name}.framework/{name}" for name in FRAMEWORKS}
PLISTS = {
    "Info.plist": {
        "CFBundleExecutable": APP,
        "CFBundleIdentifier": "org.iosprobe.app",
        "CFBundlePackageType": "APPL",
        "CFBundleSupportedPlatforms": ["iPhoneOS"],
        "MinimumOSVersion": "16.3",
    },
    **{
        f"Frameworks/{name}.framework/Info.plist": {
            "CFBundleExecutable": name,
            "CFBundleIdentifier": f"org.iosprobe.{name}",
            "CFBundlePackageType": "FMWK",
        }
        for name in FRAMEWORKS
    },
}
FILES = {PREFIX + name for name in EXECUTABLES | PLISTS.keys()}
DIRECTORIES = {
    f"{parent}/"
    for name in FILES
    for parent in PurePosixPath(name).parents
    if parent != PurePosixPath(".")
}


def inspect(ipa, bundle):
    with zipfile.ZipFile(ipa) as archive:
        entries = {}
        for entry in archive.infolist():
            name = entry.orig_filename
            if name in entries:
                raise ValueError(f"Duplicate entry: {name!r}")
            mode = entry.external_attr >> 16
            if name in DIRECTORIES:
                if entry.file_size or stat.S_IFMT(mode) not in (0, stat.S_IFDIR):
                    raise ValueError(f"Invalid directory: {name}")
            elif name in FILES:
                if entry.create_system != 3 or not stat.S_ISREG(mode):
                    raise ValueError(f"Expected a regular Unix file: {name}")
                if name.removeprefix(PREFIX) in EXECUTABLES and not mode & stat.S_IXUSR:
                    raise ValueError(f"Missing execute permission: {name}")
            else:
                raise ValueError(f"Entry outside bundle inventory: {name!r}")
            entries[name] = entry
        if FILES - entries.keys():
            raise ValueError(f"Missing bundle files: {sorted(FILES - entries.keys())}")

        for name, entry in sorted(entries.items()):
            content = archive.read(entry)  # Read every entry and verify its CRC.
            if name in DIRECTORIES:
                continue
            relative = name.removeprefix(PREFIX)
            sha = hashlib.sha256(content).hexdigest()
            if sha != hashlib.sha256((bundle / relative).read_bytes()).hexdigest():
                raise ValueError(f"Bundle hash mismatch: {name}")
            if relative in PLISTS:
                plist = plistlib.loads(content)
                if not isinstance(plist, dict) or any(
                    plist.get(key) != value for key, value in PLISTS[relative].items()
                ):
                    raise ValueError(f"Unexpected plist fields: {name}")
            print(f"{sha}  {name}")
    print(f"{hashlib.sha256(ipa.read_bytes()).hexdigest()}  {ipa.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        inspect(args.ipa, args.bundle)
    except (ValueError, OSError, zipfile.BadZipFile, plistlib.InvalidFileException) as error:
        sys.exit(f"IPA inspection failed: {error}")
