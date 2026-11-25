"""Run actionlint on a local repository and verify the runner-context regression."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


INVALID_WORKFLOW = """name: Invalid runner context
on: workflow_dispatch
jobs:
  fixture:
    runs-on: ubuntu-latest
    env:
      REPORT: ${{ runner.temp }}/report.txt
    steps:
      - run: echo test
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path, nargs="?",
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--actionlint", default="actionlint")
    args = parser.parse_args()
    executable = shutil.which(args.actionlint)
    if executable is None:
        parser.error("actionlint was not found; install the official release or use --actionlint")
    repository = args.repository.resolve()
    directory = repository / ".github" / "workflows"
    workflows = sorted(path for path in directory.iterdir()
                       if path.is_file() and path.suffix in {".yaml", ".yml"}) if directory.is_dir() else []
    if not workflows:
        parser.error(f"No workflows found in {directory}")

    command = [str(Path(executable).resolve()), "-no-color"]
    status = subprocess.call(command + [str(path.relative_to(repository)) for path in workflows],
                             cwd=repository)
    if status:
        return status
    print(f"actionlint: {len(workflows)} workflows passed", flush=True)

    with tempfile.TemporaryDirectory(prefix="actionlint-context-") as temp:
        fixture = Path(temp) / "invalid-runner-context.yml"
        fixture.write_text(INVALID_WORKFLOW, encoding="utf-8")
        result = subprocess.run(command + [str(fixture)], cwd=temp, text=True, capture_output=True)
    diagnostics = result.stdout + result.stderr
    if result.returncode != 1 or 'context "runner" is not allowed here' not in diagnostics:
        print(f"Expected actionlint to reject the runner context fixture:\n{diagnostics}", file=sys.stderr)
        return 1
    print("Regression fixture rejected as expected:")
    print(diagnostics.rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
