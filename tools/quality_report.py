"""Measure the code before a release and save the numbers the «Код и качество» screen shows.

Runs the same checks as CI (pytest with coverage, ruff, mypy; eslint, tsc, vitest) and writes
`apps/api/pulse/quality.json`. Nothing on that screen is typed in by hand.

    python tools/quality_report.py
"""

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "apps" / "api"
WEB = ROOT / "apps" / "web"
OUT = API / "pulse" / "quality.json"
PY = API / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
NPX = "npx.cmd" if sys.platform == "win32" else "npx"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


def api() -> dict[str, object]:
    cov_file = API / ".coverage.json"
    tests = run([str(PY), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--cov=pulse", f"--cov-report=json:{cov_file}"], API)
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", tests.stdout)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", tests.stdout)) else 0
    coverage = 0.0
    if cov_file.exists():
        coverage = round(json.loads(cov_file.read_text(encoding="utf-8"))["totals"]["percent_covered"], 1)
        cov_file.unlink()
    files = list((API / "pulse").rglob("*.py"))
    return {
        "tests": passed + failed,
        "passed": passed,
        "coverage": coverage,
        "ruff": run([str(PY), "-m", "ruff", "check", "."], API).returncode == 0,
        "format": run([str(PY), "-m", "ruff", "format", "--check", "."], API).returncode == 0,
        "mypy": run([str(PY), "-m", "mypy"], API).returncode == 0,
        "files": len(files),
        "lines": sum(len(f.read_text(encoding="utf-8").splitlines()) for f in files),
    }


def web() -> dict[str, object]:
    report = WEB / ".vitest.json"
    run([NPX, "vitest", "run", "--reporter=json", f"--outputFile={report}"], WEB)
    tests = passed = 0
    if report.exists():
        data = json.loads(report.read_text(encoding="utf-8"))
        tests, passed = data.get("numTotalTests", 0), data.get("numPassedTests", 0)
        report.unlink()
    files = [f for f in (WEB / "src").rglob("*") if f.suffix in (".ts", ".tsx")]
    return {
        "tests": tests,
        "passed": passed,
        "lint": run([NPX, "eslint", "src"], WEB).returncode == 0,
        "typecheck": run([NPX, "tsc", "-b"], WEB).returncode == 0,
        "files": len(files),
        "lines": sum(len(f.read_text(encoding="utf-8").splitlines()) for f in files),
    }


def main() -> None:
    commit = run(["git", "rev-parse", "--short", "HEAD"], ROOT).stdout.strip()
    report = {"commit": commit, "measuredAt": datetime.now(UTC).isoformat(timespec="seconds"), "api": api(), "web": web()}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    ok = report["api"]["passed"] == report["api"]["tests"] and report["web"]["passed"] == report["web"]["tests"]  # type: ignore[index]
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
