"""Inspect a public MoltenVK XCFramework without game or runtime inputs."""

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import plistlib
import re
import subprocess
import sys
from xml.parsers.expat import ExpatError


DARWIN_INDEX_WIDTH = {
    "__.SYMDEF": 4, "__.SYMDEF SORTED": 4,
    "__.SYMDEF_64": 8, "__.SYMDEF_64 SORTED": 8,
}


def select_moltenvk(xcframework):
    root = xcframework.resolve()
    with (root / "Info.plist").open("rb") as stream:
        metadata = plistlib.load(stream)
    entries = metadata.get("AvailableLibraries") if isinstance(metadata, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("XCFramework Info.plist has no valid AvailableLibraries")

    identifiers = set()
    candidates = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid AvailableLibraries entry")
        identifier = entry.get("LibraryIdentifier")
        library = entry.get("LibraryPath")
        platform = entry.get("SupportedPlatform")
        architectures = entry.get("SupportedArchitectures")
        if (not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", identifier)
                or identifier in {".", ".."} or library != "libMoltenVK.a"
                or not isinstance(platform, str) or not platform
                or not isinstance(architectures, list) or not architectures
                or not all(isinstance(arch, str) and arch for arch in architectures)
                or ("SupportedPlatformVariant" in entry
                    and not isinstance(entry["SupportedPlatformVariant"], str))):
            raise ValueError(f"Invalid static MoltenVK XCFramework metadata: {identifier!r}")
        if identifier in identifiers:
            raise ValueError(f"Duplicate XCFramework LibraryIdentifier: {identifier}")
        identifiers.add(identifier)
        if platform == "ios" and "arm64" in architectures and "SupportedPlatformVariant" not in entry:
            candidates.append((identifier, library))

    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one iOS device ARM64 MoltenVK library; found {len(candidates)}")
    identifier, library = candidates[0]
    archive = (root / identifier / library).resolve(strict=True)
    if not archive.is_relative_to(root) or not archive.is_file():
        raise ValueError(f"Invalid archive resolved from XCFramework metadata: {archive}")
    return archive


def xcrun(*args):
    return subprocess.check_output(["xcrun", *args], text=True)


def require_arm64(architectures, label):
    if architectures.split() != ["arm64"]:
        raise ValueError(f"{label}: expected arm64 only; found {architectures.strip()!r}")


def load_commands(output):
    return [
        (match.group(1), block)
        for block in re.split(r"^Load command \d+\s*$", output, flags=re.M)[1:]
        if (match := re.search(r"^[ \t]*cmd[ \t]+(\S+)", block, re.M))
    ]


def fields(commands, command, field):
    pattern = rf"^[ \t]*{field}[ \t]+(.+?)(?:[ \t]+\(offset \d+\))?[ \t]*$"
    values = []
    for kind, block in commands:
        if kind == command:
            matches = re.findall(pattern, block, re.M)
            if len(matches) != 1:
                raise ValueError(f"Missing or ambiguous {field} in {command}")
            values.append(matches[0])
    return values


def version(value):
    if not re.fullmatch(r"\d+(?:\.\d+){0,2}", value):
        raise ValueError(f"Invalid iOS version: {value!r}")
    parts = tuple(map(int, value.split(".")))
    return parts + (0,) * (3 - len(parts))


def check_device(commands, target, label):
    platform = fields(commands, "LC_BUILD_VERSION", "platform")
    minimum = fields(commands, "LC_BUILD_VERSION", "minos")
    if len(platform) != 1 or platform[0].upper() not in {"IOS", "2"}:
        raise ValueError(f"{label}: expected one iPhoneOS LC_BUILD_VERSION; found {platform}")
    if len(minimum) != 1 or version(minimum[0]) > version(target):
        raise ValueError(f"{label}: minimum iOS {minimum} is incompatible with iOS {target}")
    return minimum[0]


class ArchiveInventoryError(ValueError):
    """The tool output does not account for the full archive inventory."""


def verify_darwin_index(archive, name):
    """Identify the first member by its BSD header and little-endian ranlib layout."""
    width = DARWIN_INDEX_WIDTH[name]
    with archive.open("rb") as stream:
        if stream.read(8) != b"!<arch>\n":
            raise ValueError("Cannot verify a Darwin symbol index in a non-BSD archive")
        header = stream.read(60)
        size = header[48:58].strip()
        if len(header) != 60 or header[58:] != b"\x60\n" or not size.isdigit():
            raise ValueError("Malformed BSD archive header for the Darwin symbol index")
        size = int(size)
        end = 68 + size
        archive_size = stream.seek(0, 2)
        if end > archive_size:
            raise ValueError("Truncated Darwin symbol index")
        stream.seek(68)
        stored_name = header[:16].rstrip(b" ")
        if stored_name.startswith(b"#1/"):
            name_size = stored_name[3:]
            if not name_size.isdigit() or not 0 < int(name_size) <= min(size, 64):
                raise ValueError("Malformed BSD extended name for the Darwin symbol index")
            stored_name = stream.read(int(name_size)).rstrip(b"\0")
        if stored_name != name.encode("ascii"):
            raise ValueError(f"Darwin symbol index {name!r} is not the first archive member")

        def read_word():
            if stream.tell() + width > end:
                raise ValueError("Truncated Darwin ranlib table")
            return int.from_bytes(stream.read(width), "little")

        entries_size = read_word()
        entries_start = stream.tell()
        if entries_size % (2 * width) or entries_start + entries_size + width > end:
            raise ValueError("Invalid Darwin ranlib table size")
        stream.seek(entries_start + entries_size)
        strings_size = read_word()
        padding = end - stream.tell() - strings_size
        if not 0 <= padding <= 7:
            raise ValueError("Invalid Darwin ranlib string table size")
        stream.seek(end - padding)
        if any(stream.read(padding)):
            raise ValueError("Unexpected bytes after the Darwin ranlib string table")
        stream.seek(entries_start)
        for _ in range(entries_size // (2 * width)):
            string_offset, member_offset = read_word(), read_word()
            if string_offset >= strings_size or not end <= member_offset <= archive_size - 60:
                raise ValueError("Darwin ranlib entry points outside the archive or string table")


def check_archive_members(table, output, target, archive=None):
    # Match the filename before the member so an architecture suffix cannot become the member.
    sections = re.split(r"^[^\r\n]+?\(([^()\r\n]+)\)(?: \(architecture [^)\r\n]+\))?:[ \t]*$",
                        output, flags=re.M)
    names = sections[1::2]
    expected = Counter(table.splitlines())
    listed_count = expected.total()
    observed = Counter(names)
    missing = expected - observed
    if archive is not None and missing.total() == 1:
        name = next(iter(missing))
        if name in DARWIN_INDEX_WIDTH and expected[name] == 1:
            try:
                verify_darwin_index(archive, name)
            except ValueError as error:
                print(f"MoltenVK: could not classify {name!r} as a symbol index: {error}",
                      file=sys.stderr)
            else:
                del expected[name]
                print(f"MoltenVK: verified Darwin symbol index {name!r} (archive metadata)",
                      file=sys.stderr)
    inventory_matches = bool(names) and observed == expected
    print(f"MoltenVK inventory: ar listed {listed_count} members; "
          f"{expected.total()} require Mach-O inspection; "
          f"parsed {observed.total()} otool sections", file=sys.stderr)

    if not inventory_matches:
        for description, difference in (("only in ar -t", expected - observed),
                                        ("only in parsed otool output", observed - expected)):
            for name, count in sorted(difference.items()):
                print(f"  {description}: {name!r} (count {count})", file=sys.stderr)
        # The literal headers can expose a naming difference or a non-object diagnostic.
        header_lines = [line for line in output.splitlines()
                        if line and not line[0].isspace() and not line.startswith("Load command ")]
        sample = header_lines[:12] or output.splitlines()[:12]
        print(f"  otool header sample ({len(header_lines)} candidate lines):", file=sys.stderr)
        for line in sample:
            print(f"    {line!r}", file=sys.stderr)

    failures = 0
    for index, (name, body) in enumerate(zip(names, sections[2::2]), 1):
        label = f"MoltenVK otool section #{index} {name!r}"
        try:
            minimum = check_device(load_commands(body), target, label)
        except ValueError as error:
            failures += 1
            print(f"  Failed {label}: {error}", file=sys.stderr)
        else:
            print(f"  Verified {label}: iPhoneOS, minos {minimum}", file=sys.stderr)
    if not inventory_matches:
        raise ArchiveInventoryError("Could not inspect every MoltenVK archive member with otool; "
                                    "see the inventory differences and raw headers above")
    if failures:
        raise ValueError(f"{failures} MoltenVK archive member(s) failed iPhoneOS inspection")
    return len(names)


def inspect_archive(archive, target):
    print(f"MoltenVK: inspecting selected archive {archive}", file=sys.stderr)
    require_arm64(xcrun("lipo", "-archs", archive), archive)
    table = xcrun("ar", "-t", archive)
    output = xcrun("otool", "-arch", "arm64", "-l", archive)
    try:
        count = check_archive_members(table, output, target, archive)
    except ArchiveInventoryError:
        # Ask Apple otool for raw archive member headers, including archive bookkeeping.
        try:
            headers = xcrun("otool", "-arch", "arm64", "-av", archive).splitlines()
            print(f"MoltenVK raw archive header sample ({len(headers)} lines):", file=sys.stderr)
            for line in headers[:16]:
                print(f"  {line!r}", file=sys.stderr)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"MoltenVK raw archive headers unavailable: {error}", file=sys.stderr)
        raise
    print(f"MoltenVK: {count} ARM64 iPhoneOS members compatible with iOS {target}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xcframework", type=Path)
    parser.add_argument("--deployment-target", required=True)
    args = parser.parse_args()
    try:
        archive = select_moltenvk(args.xcframework)
        print(f"Selection: {archive.relative_to(args.xcframework.resolve())}")
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        print(f"Archive: {archive.stat().st_size} bytes; SHA-256 {digest}")
        inspect_archive(archive, args.deployment_target)
    except (OSError, ValueError, ExpatError, plistlib.InvalidFileException,
            subprocess.CalledProcessError) as error:
        parser.exit(1, f"MoltenVK inspection failed: {error}\n")


if __name__ == "__main__":
    main()
