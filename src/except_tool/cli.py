"""Command-line interface for the except analysis tool."""

from __future__ import annotations

import argparse
from pathlib import Path

from except_tool.analyzer import ModuleAnalyzer


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""

    parser = argparse.ArgumentParser(
        prog="except",
        description="Explore the potential exception surface of a Python statement.",
    )
    parser.add_argument("source_file", help="Path to the Python source file to inspect.")
    parser.add_argument("line", type=int, help="Line number containing the target statement.")
    return parser


def main() -> int:
    """Run the CLI and print the analysis report."""

    parser = build_parser()
    args = parser.parse_args()

    analyzer = ModuleAnalyzer(Path(args.source_file))
    report = analyzer.analyze_statement(args.line)

    print(f"Statement at line {report.statement_line}: {report.statement_source}")
    print()

    if report.findings:
        print("Potential exceptions:")
        for finding in report.findings:
            chain = " -> ".join(finding.path)
            details = f" (line {finding.line})"
            if finding.message:
                details += f": {finding.message}"
            print(f"- {finding.exception_name} via {chain}{details}")
    else:
        print("Potential exceptions:")
        print("- none found from explicit raise statements in resolved local functions")

    if report.unresolved_calls:
        print()
        print("Unresolved calls:")
        for unresolved in report.unresolved_calls:
            chain = " -> ".join(unresolved.path)
            print(f"- {unresolved.name} via {chain} (line {unresolved.line})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
