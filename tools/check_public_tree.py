"""Check the publication inventory, staged blobs and reachable Git history."""

from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
APPROVED = {
    ".github/workflows/iphoneos-probe.yml",
    ".gitignore", "CMakeLists.txt", "LICENSE", "README.md",
    "docs/PROVENANCE.md", "docs/INTEGRATION.md",
    "ios/Info.plist.in",
    "src/ProbeBase.c", "src/ProbePlugin.c", "src/main.m",
    "tests/test_infrastructure.py",
    "tools/build_iphoneos.sh", "tools/check_public_tree.py",
    "tools/inspect_ipa.py", "tools/inspect_macho.py",
}
SENSITIVE = {
    "credential or certificate": re.compile(
        r"-----BEGIN (?:[A-Z ]*PRIVATE KEY|CERTIFICATE)-----|"
        r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})|"
        r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|"
        r"https?://[^/\s:@]+:[^/\s@]+@",
    ),
    "personal filesystem path": re.compile(r"(?i)(?:[A-Z]:[\\/]Users[\\/]|/(?:Users|home)/)[\w.-]+"),
    "generated code or binary pointer": re.compile(
        r"(?i)\b(?:ds2_recomp\.\d+|PPC[_]FUNC_IMPL|rexglue\.recomp)\b|"
        r"^version https://git-lfs.github.com/spec/v1",
        re.M,
    ),
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def check_blob(path, mode, data):
    if path not in APPROVED:
        raise ValueError(f"Path outside the publication inventory: {path!r}")
    if mode not in {"100644", "100755"}:
        raise ValueError(f"Unsupported Git entry type: {path}")
    if len(data) > 100_000 or b"\0" in data:
        raise ValueError(f"Unexpected binary or oversized file: {path}")
    try:
        source = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"Non-UTF-8 file: {path}") from error
    for label, pattern in SENSITIVE.items():
        if pattern.search(source):
            raise ValueError(f"Possible {label} in {path}; review before publication")


def records(data):
    for entry in data.decode("utf-8").split("\0"):
        if entry:
            metadata, path = entry.split("\t", 1)
            yield metadata.split(), path


def check_repository():
    seen = set()

    def check_git_blob(path, mode, oid):
        if path not in APPROVED or mode not in {"100644", "100755"}:
            raise ValueError(f"Unexpected Git entry: {path!r} ({mode})")
        key = (path, mode, oid)
        if key not in seen:
            check_blob(path, mode, git("cat-file", "blob", oid))
            seen.add(key)

    staged = set()
    for (mode, oid, stage), path in records(git("ls-files", "--stage", "-z")):
        if stage != "0":
            raise ValueError(f"Unmerged Git entry: {path}")
        check_git_blob(path, mode, oid)
        staged.add(path)
    if staged != APPROVED:
        raise ValueError(f"Missing publication files: {sorted(APPROVED - staged)}")

    files = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode("utf-8")
    for path in filter(None, files.split("\0")):
        file = ROOT / path
        if path not in APPROVED or file.is_symlink() or not file.is_file():
            raise ValueError(f"Unexpected working-tree path: {path!r}")
        check_blob(path, "100644", file.read_bytes())

    head = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "HEAD"],
                          cwd=ROOT, capture_output=True)
    tips = ["--all", "HEAD"] if head.returncode == 0 else ["--all"]
    history = git("rev-list", *tips).decode().splitlines()
    for commit in history:
        for (mode, kind, oid), path in records(git("ls-tree", "-r", "-z", commit)):
            if kind != "blob":
                raise ValueError(f"Unexpected {kind} in history: {path}")
            check_git_blob(path, mode, oid)
    print(f"Publication inventory passed: {len(staged)} files, {len(history)} reachable commits")


if __name__ == "__main__":
    try:
        check_repository()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"Publication check failed: {error}")
