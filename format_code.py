#!/usr/bin/env python3
"""Script to format all Python code in the project."""

import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"Running {description}...")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        return False


def main():
    """Format all Python code in the project."""
    project_root = Path(__file__).parent

    print("Starting code formatting and quality checks...")

    # Commands to run
    commands = [
        (["python", "-m", "black", ".", "--check"], "Black format check"),
        (["python", "-m", "black", "."], "Black formatting"),
        (["python", "-m", "isort", ".", "--check-only"], "Import sorting check"),
        (["python", "-m", "isort", "."], "Import sorting"),
        (["python", "-m", "flake8", "."], "Flake8 linting"),
    ]

    success_count = 0
    for command, description in commands:
        if run_command(command, description):
            success_count += 1

    print(f"\nCompleted {success_count}/{len(commands)} tasks successfully")

    if success_count == len(commands):
        print("🎉 All code quality checks passed!")
        sys.exit(0)
    else:
        print("❌ Some checks failed. Please review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()