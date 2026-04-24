"""Command-line interface for the except analysis tool."""

from __future__ import annotations

import argparse
from pathlib import Path

from except_tool.analyzer import ModuleAnalyzer

# TODO: If an installed library does not have Python source available, try
# other strategies for inspecting it.


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""

    parser = argparse.ArgumentParser(
        prog="except",
        description=(
            "Trace the exceptions that can be raised, swallowed, or left escaping "
            "from a Python line, including builtin, stdlib, and library call paths."
        ),
        epilog=(
            "Tree output tags: [raises] introduces exceptions at a row; [swallows] "
            "catches them there; [builtin summary], [stdlib summary], [stdlib source], "
            "[library summary], and [library source] describe where the row's "
            "exception knowledge came from."
        ),
    )
    parser.add_argument("source_file", help="Python source file to inspect.")
    parser.add_argument(
        "line", type=int, help="Line number containing the statement or function body to analyze."
    )
    parser.add_argument(
        "--format",
        choices=("summary", "tree"),
        default="summary",
        help=(
            "Output style: compact summary or two-column propagation tree with "
            "source and summary tags."
        ),
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

    explicit = [f for f in report.findings if not f.implicit]
    implicit = [f for f in report.findings if f.implicit]

    if explicit:
        print("Potential exceptions (explicit raise):")
        for finding in explicit:
            chain = " -> ".join(finding.path)
            details = f" (line {finding.line})"
            if finding.message:
                details += f": {finding.message}"
            print(f"- {finding.exception_name} via {chain}{details}")

    if implicit:
        print()
        print("Potential exceptions (implicit operations):")
        for finding in implicit:
            chain = " -> ".join(finding.path)
            op_label = f" [{finding.operation}]" if finding.operation else ""
            print(f"- {finding.exception_name} via {chain}" f" (line {finding.line}){op_label}")

    if not explicit and not implicit:
        print("Potential exceptions:")
        print("- none found from explicit raise statements in" " resolved local functions")

    if report.unresolved_calls:
        print()
        print("Unresolved calls:")
        for unresolved in report.unresolved_calls:
            chain = " -> ".join(unresolved.path)
            print(f"- {unresolved.name} via {chain} (line {unresolved.line})")

    return 0


def _print_tree_report(report) -> None:
    """Render a table view of explored calls and exception propagation."""

    print(f"{'Call tree':<36} Exceptions")
    if not report.call_tree:
        print("- no function calls found in the target statement")
        return

    for node in report.call_tree:
        _print_tree_node(node, indent="")


def _print_tree_node(node, indent: str) -> None:
    label = f"{indent}{node.name}"
    if node.recursive:
        label += " [recursive]"
    print(f"{label:<36} {_format_tree_exceptions(node)}")

    child_indent = f"{indent}  "
    for child in node.children:
        _print_tree_node(child, indent=child_indent)


def _format_tree_exceptions(node) -> str:
    parts = []
    if node.escaping_exceptions:
        parts.append(", ".join(node.escaping_exceptions))

    raised = sorted({finding.exception_name for finding in node.findings})
    if node.summary_source in {"builtin summary", "stdlib summary", "library summary"}:
        raised = []
    if raised:
        parts.append(f"[raises {', '.join(raised)}]")

    if node.swallowed_exceptions:
        parts.append(f"[swallows {', '.join(node.swallowed_exceptions)}]")

    if node.summary_source == "builtin summary":
        parts.append("[builtin summary]")
    elif node.summary_source == "stdlib summary":
        parts.append("[stdlib summary]")
    elif node.summary_source == "library summary":
        parts.append("[library summary]")
    elif node.summary_source == "stdlib source":
        parts.append("[stdlib source]")
    elif node.summary_source == "library source":
        parts.append("[library source]")

    if not parts:
        return "-"
    return "; ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
