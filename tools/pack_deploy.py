"""Package Stage 8 artifacts for deployment to demo.shvarev-demo.ru."""

import os
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_PATH = ROOT / "stage8_deploy.tar.gz"

ENTRIES = [
    ROOT / "apps" / "web" / "dist",
    ROOT / "apps" / "api" / "pulse",
    ROOT / "apps" / "api" / "pyproject.toml",
    ROOT / "hermes",
    ROOT / "infra",
]


def pack() -> None:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()

    print(f"Creating {ARCHIVE_PATH.name}...")
    with tarfile.open(ARCHIVE_PATH, "w:gz") as tar:
        for entry in ENTRIES:
            if not entry.exists():
                print(f"Warning: {entry} does not exist!")
                continue
            arcname = entry.relative_to(ROOT).as_posix()
            print(f"  Adding {arcname}")
            tar.add(entry, arcname=arcname)

    size_kb = ARCHIVE_PATH.stat().st_size / 1024
    print(f"Archive created successfully: {size_kb:.1f} KB")


if __name__ == "__main__":
    pack()
