"""Static analysis helpers for exploring possible exception paths."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path


@dataclass(slots=True)
class RaiseSite:
    """Represents an explicit raise statement discovered during analysis."""

    exception_name: str
    line: int
    message: str | None = None


@dataclass(slots=True)
class UnresolvedCall:
    """Represents a call edge that could not be resolved statically."""

    name: str
    line: int
    path: tuple[str, ...]


@dataclass(slots=True)
class ExceptionFinding:
    """Represents a reachable exception candidate and the call path to it."""

    exception_name: str
    line: int
    path: tuple[str, ...]
    message: str | None = None


@dataclass(slots=True)
class StatementReport:
    """Collects exception findings for a single target statement."""

    statement_source: str
    statement_line: int
    findings: list[ExceptionFinding] = field(default_factory=list)
    unresolved_calls: list[UnresolvedCall] = field(default_factory=list)
    call_tree: list["CallTreeNode"] = field(default_factory=list)


@dataclass(slots=True)
class CallTreeNode:
    """Represents one explored call in the statement's reachable call tree."""

    name: str
    line: int
    path: tuple[str, ...]
    resolved: bool
    definition_line: int | None = None
    recursive: bool = False
    findings: list[ExceptionFinding] = field(default_factory=list)
    children: list["CallTreeNode"] = field(default_factory=list)


class FunctionSummaryBuilder(ast.NodeVisitor):
    """Builds a summary of raises and direct calls for a function body."""

    def __init__(self) -> None:
        self.raises: list[RaiseSite] = []
        self.calls: list[tuple[str, int]] = []
        self._handled_stack: list[set[str | None]] = []

    def visit_Raise(self, node: ast.Raise) -> None:
        if node.exc is None:
            exc_name = "re-raise"
            message = None
        else:
            exc_name = _exception_name(node.exc)
            message = _raise_message(node.exc)

        if not self._is_handled(exc_name):
            self.raises.append(
                RaiseSite(exception_name=exc_name, line=node.lineno, message=message)
            )

    def visit_Call(self, node: ast.Call) -> None:
        call_name = _call_name(node)
        if call_name is not None:
            self.calls.append((call_name, node.lineno))
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        handled_here: set[str | None] = set()
        catches_all = False

        for handler in node.handlers:
            if handler.type is None:
                catches_all = True
                handled_here.add(None)
            else:
                for name in _handler_exception_names(handler.type):
                    handled_here.add(name)

        self._handled_stack.append(handled_here)
        for item in node.body:
            self.visit(item)
        self._handled_stack.pop()

        for handler in node.handlers:
            for item in handler.body:
                self.visit(item)
        for item in node.orelse:
            self.visit(item)
        for item in node.finalbody:
            self.visit(item)

        if catches_all:
            return

    def _is_handled(self, exc_name: str) -> bool:
        for handled in reversed(self._handled_stack):
            if None in handled or exc_name in handled:
                return True
        return False


@dataclass(slots=True)
class FunctionSummary:
    """Stores the extracted exception-relevant summary for a function."""

    name: str
    line: int
    raises: list[RaiseSite]
    calls: list[tuple[str, int]]


class ModuleAnalyzer:
    """Analyzes one Python module and reports possible exceptions for statements."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.source = path.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source, filename=str(path))
        self.lines = self.source.splitlines()
        self.function_summaries = self._build_function_summaries()

    def analyze_statement(self, line_number: int) -> StatementReport:
        """Analyze the statement covering the given line number."""

        statement = self._find_statement(line_number)
        statement_source = (
            ast.get_source_segment(self.source, statement) or statement.__class__.__name__
        )

        builder = FunctionSummaryBuilder()
        builder.visit(statement)

        report = StatementReport(
            statement_source=statement_source.strip(), statement_line=statement.lineno
        )

        visited: set[str] = set()
        for call_name, call_line in builder.calls:
            report.call_tree.append(
                self._explore_call(
                    call_name=call_name,
                    call_line=call_line,
                    path=(call_name,),
                    visited=visited,
                    report=report,
                )
            )

        self._dedupe_report(report)
        return report

    def _build_function_summaries(self) -> dict[str, FunctionSummary]:
        summaries: dict[str, FunctionSummary] = {}
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                builder = FunctionSummaryBuilder()
                for item in node.body:
                    builder.visit(item)
                summaries[node.name] = FunctionSummary(
                    name=node.name, line=node.lineno, raises=builder.raises, calls=builder.calls
                )
        return summaries

    def _find_statement(self, line_number: int) -> ast.stmt:
        best: ast.stmt | None = None
        best_span = None

        for node in ast.walk(self.tree):
            if not isinstance(node, ast.stmt):
                continue
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", start)
            if start is None or end is None:
                continue
            if start <= line_number <= end:
                span = end - start
                if best is None or span < best_span:
                    best = node
                    best_span = span

        if best is None:
            raise ValueError(f"No statement found at line {line_number}")
        return best

    def _explore_call(
        self,
        call_name: str,
        call_line: int,
        path: tuple[str, ...],
        visited: set[str],
        report: StatementReport,
    ) -> CallTreeNode:
        summary = self.function_summaries.get(call_name)
        if summary is None:
            report.unresolved_calls.append(
                UnresolvedCall(name=call_name, line=call_line, path=path)
            )
            return CallTreeNode(name=call_name, line=call_line, path=path, resolved=False)

        node = CallTreeNode(
            name=call_name, line=call_line, path=path, resolved=True, definition_line=summary.line
        )

        for raise_site in summary.raises:
            finding = ExceptionFinding(
                exception_name=raise_site.exception_name,
                line=raise_site.line,
                path=path,
                message=raise_site.message,
            )
            report.findings.append(finding)
            node.findings.append(finding)

        if call_name in visited:
            node.recursive = True
            return node

        visited.add(call_name)
        for nested_call_name, nested_call_line in summary.calls:
            node.children.append(
                self._explore_call(
                    call_name=nested_call_name,
                    call_line=nested_call_line,
                    path=path + (nested_call_name,),
                    visited=visited,
                    report=report,
                )
            )
        visited.remove(call_name)
        return node

    def _dedupe_report(self, report: StatementReport) -> None:
        unique_findings: dict[tuple[str, int, tuple[str, ...]], ExceptionFinding] = {}
        for finding in report.findings:
            key = (finding.exception_name, finding.line, finding.path)
            unique_findings[key] = finding
        report.findings = sorted(
            unique_findings.values(), key=lambda item: (item.line, item.exception_name, item.path)
        )

        unique_unresolved: dict[tuple[str, int, tuple[str, ...]], UnresolvedCall] = {}
        for unresolved in report.unresolved_calls:
            key = (unresolved.name, unresolved.line, unresolved.path)
            unique_unresolved[key] = unresolved
        report.unresolved_calls = sorted(
            unique_unresolved.values(), key=lambda item: (item.line, item.name, item.path)
        )


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    return None


def _exception_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _exception_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ast.dump(node, annotate_fields=False)


def _raise_message(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call) or not node.args:
        return None
    first_arg = node.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return first_arg.value
    return None


def _handler_exception_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Tuple):
        names: list[str] = []
        for elt in node.elts:
            names.extend(_handler_exception_names(elt))
        return names
    return [_exception_name(node)]
