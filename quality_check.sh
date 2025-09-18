#!/bin/bash
# Script to run code quality checks

set -e

echo "🔍 Starting code quality checks..."

echo "📝 Running Black formatter..."
python -m black . --check || (echo "❌ Code formatting issues found. Run 'python -m black .' to fix." && exit 1)

echo "📦 Running isort import sorter..."
python -m isort . --check-only || (echo "❌ Import sorting issues found. Run 'python -m isort .' to fix." && exit 1)

echo "🔎 Running Flake8 linter..."
python -m flake8 . || (echo "❌ Linting issues found." && exit 1)

echo "🔍 Running MyPy type checker..."
python -m mypy backend/ || echo "⚠️  Type checking issues found (non-blocking)"

echo "✅ All code quality checks passed!"