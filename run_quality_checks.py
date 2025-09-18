#!/usr/bin/env python3
"""
Comprehensive code quality check runner for the RAG system.
This script runs all quality checks and provides detailed feedback.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


class QualityChecker:
    """Handles running code quality checks."""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.failed_checks = []
        self.passed_checks = []

    def run_command(self, command: List[str], description: str, critical: bool = True) -> bool:
        """Run a command and track results."""
        print(f"🔍 {description}...")
        try:
            result = subprocess.run(
                command, check=True, capture_output=True, text=True, cwd=self.project_root
            )
            self.passed_checks.append(description)
            print(f"✅ {description} - PASSED")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            if critical:
                self.failed_checks.append(description)
                print(f"❌ {description} - FAILED")
            else:
                print(f"⚠️  {description} - WARNING")

            if e.stdout and e.stdout.strip():
                print(f"   stdout: {e.stdout.strip()}")
            if e.stderr and e.stderr.strip():
                print(f"   stderr: {e.stderr.strip()}")
            return False
        except FileNotFoundError:
            print(f"⚠️  {description} - TOOL NOT FOUND (skipping)")
            return False

    def check_formatting(self) -> None:
        """Check code formatting with Black."""
        self.run_command(
            ["python", "-m", "black", ".", "--check", "--diff"],
            "Black code formatting check"
        )

    def check_imports(self) -> None:
        """Check import sorting with isort."""
        self.run_command(
            ["python", "-m", "isort", ".", "--check-only", "--diff"],
            "Import sorting check"
        )

    def check_linting(self) -> None:
        """Check code style with flake8."""
        self.run_command(
            ["python", "-m", "flake8", "."],
            "Flake8 linting check"
        )

    def check_types(self) -> None:
        """Check types with mypy (non-critical)."""
        self.run_command(
            ["python", "-m", "mypy", "backend/"],
            "MyPy type checking",
            critical=False
        )

    def fix_formatting(self) -> None:
        """Auto-fix formatting issues."""
        print("\n🔧 Auto-fixing formatting issues...")
        self.run_command(
            ["python", "-m", "black", "."],
            "Black code formatting (fix)",
            critical=False
        )
        self.run_command(
            ["python", "-m", "isort", "."],
            "Import sorting (fix)",
            critical=False
        )

    def run_all_checks(self, auto_fix: bool = False) -> bool:
        """Run all quality checks."""
        print("🚀 Starting comprehensive code quality checks...\n")

        if auto_fix:
            self.fix_formatting()
            print()

        # Run all checks
        self.check_formatting()
        self.check_imports()
        self.check_linting()
        self.check_types()

        # Summary
        print(f"\n📊 Quality Check Summary:")
        print(f"✅ Passed: {len(self.passed_checks)}")
        print(f"❌ Failed: {len(self.failed_checks)}")

        if self.passed_checks:
            print("\n✅ Passed checks:")
            for check in self.passed_checks:
                print(f"   • {check}")

        if self.failed_checks:
            print("\n❌ Failed checks:")
            for check in self.failed_checks:
                print(f"   • {check}")
            print("\n💡 Run with --fix to auto-fix formatting issues")

        return len(self.failed_checks) == 0


def main():
    """Main entry point."""
    auto_fix = "--fix" in sys.argv or "-f" in sys.argv

    checker = QualityChecker()
    success = checker.run_all_checks(auto_fix=auto_fix)

    if success:
        print("\n🎉 All critical quality checks passed!")
        sys.exit(0)
    else:
        print("\n💥 Some quality checks failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()