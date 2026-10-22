from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

REQUIREMENTS = [
    ROOT / "student-3" / "requirements.txt",
    ROOT / "student-3" / "backend" / "requirements.txt",
    ROOT / "student-3" / "frontend" / "requirements.txt",
    ROOT / "student-3" / "database" / "requirements.txt",
]


def main():
    failed = False

    print("\n=== Dependency Vulnerability Audit ===")

    for requirement in REQUIREMENTS:
        relative_path = requirement.relative_to(ROOT)

        print(f"\nChecking: {relative_path}", flush=True)

        if not requirement.is_file():
            print(f"FAILED: Missing {relative_path}")
            failed = True
            continue

        command = [
            sys.executable,
            "-m",
            "pip_audit",
            "-r",
            str(requirement),
        ]

        # S603 reviewed: executable and arguments are fixed by this script.
        # No shell execution or user-controlled command strings are used.
        result = subprocess.run(  # noqa: S603
            command,
            cwd=ROOT,
            check=False,
        )

        if result.returncode != 0:
            print(f"FAILED: {relative_path}")
            failed = True
        else:
            print(f"PASSED: {relative_path}")

    if failed:
        print("\nDependency audit failed.")
        return 1

    print("\nAll dependency audits passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())