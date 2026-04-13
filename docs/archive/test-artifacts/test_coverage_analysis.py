#!/usr/bin/env python3
"""
Test coverage analysis script for mcp-common.
Generates a detailed report of uncovered code and prioritizes tests to write.
"""

import subprocess
import re
from pathlib import Path
from collections import defaultdict
import json

def get_coverage_data():
    """Get coverage data from pytest."""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--cov=mcp_common", "--cov-report=json", "-q"],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            cov_file = Path("coverage.json")
            if cov_file.exists():
                with open(cov_file) as f:
                    return json.load(f)

    except Exception as e:
        print(f"Error getting coverage data: {e}")

    return None

def analyze_missing_lines(file_data):
    """Analyze missing lines in coverage data."""
    missing_stats = defaultdict(list)

    if not file_data:
        return missing_stats

    for filename, file_coverage in file_data.get("files", {}).items():
        if "missing_lines" in file_coverage:
            missing_lines = file_coverage["missing_lines"]
            line_count = len(missing_lines)
            if line_count > 0:
                missing_stats[filename].extend(missing_lines)

    return missing_stats

def get_file_imports():
    """Get import statements for each file to understand dependencies."""
    imports = {}

    for py_file in Path("mcp_common").rglob("*.py"):
        if py_file.name == "__init__.py":
            continue

        try:
            with open(py_file, "r") as f:
                content = f.read()
                file_imports = []

                # Find import statements
                import_pattern = r"^(?:from\s+(\w+)\s+import|\s*import\s+(\w+))"
                for match in re.finditer(import_pattern, content, re.MULTILINE):
                    module = match.group(1) or match.group(2)
                    if module and not module.startswith("."):
                        file_imports.append(module)

                imports[str(py_file)] = file_imports
        except Exception:
            pass

    return imports

def generate_test_plan(missing_stats, imports):
    """Generate a plan for improving test coverage."""
    test_plan = []

    # Priority 1: Critical modules with low coverage
    critical_modules = [
        "mcp_common/websocket/server.py",
        "mcp_common/health.py",
        "mcp_common/parsing/tree_sitter/core.py",
        "mcp_common/parsing/tree_sitter/exceptions.py",
        "mcp_common/parsing/tree_sitter/grammars.py",
        "mcp_common/backends/pyobjc.py",
    ]

    for module in critical_modules:
        if module in missing_stats:
            missing_lines = len(missing_stats[module])
            test_plan.append({
                "module": module,
                "priority": "critical",
                "missing_lines": missing_lines,
                "suggested_tests": [
                    "Error handling tests",
                    "Edge case tests",
                    "Integration tests with dependencies",
                ]
            })

    # Priority 2: Other modules with missing coverage
    other_modules = [f for f in missing_stats.keys() if f not in critical_modules]
    for module in other_modules:
        missing_lines = len(missing_stats[module])
        if missing_lines > 5:  # Only include if more than 5 lines missing
            test_plan.append({
                "module": module,
                "priority": "medium",
                "missing_lines": missing_lines,
                "suggested_tests": [
                    "Unit tests for uncovered functions",
                    "Parameterized tests",
                ]
            })

    return test_plan

def main():
    print("🔍 Analyzing mcp-common test coverage...\n")

    # Get coverage data
    cov_data = get_coverage_data()

    if cov_data:
        # Get coverage summary
        summary = cov_data.get("summary", {})
        total_lines = summary.get("num_statements", 0)
        covered_lines = summary.get("covered_lines", 0)
        missing_lines = summary.get("missing_lines", 0)

        coverage_percent = (covered_lines / total_lines * 100) if total_lines > 0 else 0

        print(f"📊 Current Coverage Summary:")
        print(f"   Total lines: {total_lines}")
        print(f"   Covered: {covered_lines}")
        print(f"   Missing: {missing_lines}")
        print(f"   Coverage: {coverage_percent:.1f}%\n")

        # Analyze missing lines
        missing_stats = analyze_missing_lines(cov_data)

        print(f"🚫 Files with missing coverage:")
        for filename, lines in sorted(missing_stats.items()):
            line_count = len(lines)
            print(f"   {filename}: {line_count} lines missing")

        # Generate test plan
        imports = get_file_imports()
        test_plan = generate_test_plan(missing_stats, imports)

        print(f"\n📋 Test Improvement Plan:")
        print(f"{'Priority':<10} {'Module':<40} {'Lines':<6} {'Tests to Add'}")
        print("-" * 80)

        for item in test_plan:
            priority = item["priority"]
            module = Path(item["module"]).name
            lines = item["missing_lines"]
            tests = ", ".join(item["suggested_tests"][:2])

            priority_symbol = "🔴" if priority == "critical" else "🟡"
            print(f"{priority_symbol} {priority:<8} {module:<38} {lines:<6} {tests}")

        # Save detailed plan
        with open("test_coverage_plan.json", "w") as f:
            json.dump({
                "current_coverage": coverage_percent,
                "missing_stats": dict(missing_stats),
                "test_plan": test_plan
            }, f, indent=2)

        print(f"\n✅ Detailed plan saved to test_coverage_plan.json")
    else:
        print("❌ Could not get coverage data")

if __name__ == "__main__":
    main()