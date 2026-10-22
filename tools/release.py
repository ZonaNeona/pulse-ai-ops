"""Build a release archive for the server: measure quality, build the web app, pack.

    python tools/release.py            → pulse-release.tar.gz in the repository root

Then on the server: `infra/deploy.sh /tmp/pulse-release.tar.gz` (see the script header).
The release is refused if any check fails — the quality screen must never show a red build.
"""

import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "pulse-release.tar.gz"
NPM = "npm.cmd" if sys.platform == "win32" else "npm"
SKIP = {"__pycache__", ".venv", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
ENTRIES = [
    "apps/web/dist",
    "apps/api/pulse",
    "apps/api/pyproject.toml",
    "hermes",
    "infra",
    ".env.example",
    "README.md",
    "LICENSE",
]


def keep(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    return None if SKIP.intersection(Path(info.name).parts) else info


def main() -> None:
    if subprocess.run([sys.executable, str(ROOT / "tools" / "quality_report.py")], check=False).returncode:
        sys.exit("quality checks failed — no release")
    subprocess.run([NPM, "run", "build"], cwd=ROOT / "apps" / "web", check=True)
    with tarfile.open(ARCHIVE, "w:gz") as tar:
        for entry in ENTRIES:
            tar.add(ROOT / entry, arcname=entry, filter=keep)
    print(f"{ARCHIVE.name}: {ARCHIVE.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
