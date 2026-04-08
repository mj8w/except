"""Command-line interface for the except analysis tool."""

from __future__ import annotations

import argparse
from pathlib import Path

from except_tool.analyzer import ModuleAnalyzer

# TODO: Create a text output mode that shows possible call trees and where
# exceptions are raised or handled.
# TODO: If an installed library does not have Python source available, try
# other strategies for inspecting it.


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""

    parser = argparse.ArgumentParser(
        prog="except", description="Explore the potential exception surface of a Python statement."
    )
    parser.add_argument("source_file", help="Path to the Python source file to inspect.")
    parser.add_argument("line", type=int, help="Line number containing the target statement.")
    parser.add_argument(
        "--format",
        choices=("summary", "tree"),
        default="summary",
        help="Choose between the compact exception summary and a tree debug view.",
    )
    return parser


def main() -> int:
    """Run the CLI and print the analysis report."""

    parser = build_parser()
    args = parser.parse_args()

    analyzer = ModuleAnalyzer(Path(args.source_file))
    report = analyzer.analyze_statement(args.line)

    print(f"Statement at line {report.statement_line}: {report.statement_source}")
    print()

    if args.format == "tree":
        _print_tree_report(report)
        return 0

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


def _print_tree_report(report) -> None:
    """Render a tree-shaped debug view of explored calls and exception sites."""

    print("Call tree:")
    if not report.call_tree:
        print("- no function calls found in the target statement")
        return

    for node in report.call_tree:
        _print_tree_node(node, indent="")


def _print_tree_node(node, indent: str) -> None:
    marker = "call" if node.resolved else "unresolved call"
    details = f"{indent}- {marker} {node.name} (line {node.line})"
    if node.definition_line is not None:
        details += f", def line {node.definition_line}"
    if node.recursive:
        details += " [recursive]"
    print(details)

    child_indent = f"{indent}  "
    for finding in node.findings:
        message = f": {finding.message}" if finding.message else ""
        print(
            f"{child_indent}- raises {finding.exception_name} " f"(line {finding.line}){message}"
        )
    for child in node.children:
        _print_tree_node(child, indent=child_indent)


if __name__ == "__main__":
    raise SystemExit(main())
