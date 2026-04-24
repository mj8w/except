"""Static analysis helpers for exploring possible exception paths."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from except_tool.analyzer_data import BUILTIN_EXCEPTIONS
from except_tool.analyzer_data import NATIVE_EXCEPTION_NAMES
from except_tool.analyzer_data import STDLIB_METHOD_EXCEPTIONS
from except_tool.analyzer_data import SUMMARY_EXCEPTIONS
from except_tool.analyzer_data import module_source_path
from except_tool.analyzer_data import source_kind_for_path
from except_tool.analyzer_data import summary_source_for_name


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
class CallSite:
    """Represents a call made from a statement or function body."""

    name: str
    line: int
    handled_exceptions: frozenset[str | None] = frozenset()


@dataclass(slots=True)
class ResolvedCallTarget:
    """Describes a resolved function target and the analyzer that owns it."""

    analyzer: "ModuleAnalyzer"
    summary: "FunctionSummary"
    display_name: str
    summary_source: str | None = None


@dataclass(slots=True)
class ExceptionFinding:
    """Represents a reachable exception candidate and the call path to it."""

    exception_name: str
    line: int
    path: tuple[str, ...]
    message: str | None = None
    implicit: bool = False
    operation: str | None = None


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
    summary_source: str | None = None
    handled_exceptions: frozenset[str | None] = frozenset()
    findings: list[ExceptionFinding] = field(default_factory=list)
    children: list["CallTreeNode"] = field(default_factory=list)
    escaping_exceptions: list[str] = field(default_factory=list)
    swallowed_exceptions: list[str] = field(default_factory=list)


class NativeExceptionLineVisitor(ast.NodeVisitor):
    """Finds built-in exceptions that can be raised directly by one line."""

    def __init__(self) -> None:
        self.exception_names: set[str] = set()

    def visit_Raise(self, node: ast.Raise) -> None:
        if node.exc is not None:
            self._add_native_exception(_exception_name(node.exc))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = _call_name(node)
        if call_name in BUILTIN_EXCEPTIONS:
            self.exception_names.update(BUILTIN_EXCEPTIONS[call_name])
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        self.exception_names.add("TypeError")
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            self.exception_names.add("ZeroDivisionError")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.exception_names.update(("IndexError", "KeyError", "TypeError"))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.exception_names.add("AttributeError")
        self.generic_visit(node)

    def _add_native_exception(self, exception_name: str) -> None:
        if exception_name in NATIVE_EXCEPTION_NAMES:
            self.exception_names.add(exception_name)


def native_exceptions_for_line(line: str) -> list[str]:
    """Return built-in exception names that a single Python line could raise."""

    stripped = line.strip()
    if not stripped:
        return []

    tree = _parse_single_line(stripped)
    visitor = NativeExceptionLineVisitor()
    visitor.visit(tree)
    return sorted(visitor.exception_names)


class FunctionSummaryBuilder(ast.NodeVisitor):
    """Builds a summary of raises and direct calls for a function body."""

    def __init__(self, import_aliases: dict[str, str] | None = None) -> None:
        self.raises: list[RaiseSite] = []
        self.calls: list[CallSite] = []
        self.implicit_exceptions: list[tuple[str, int, str, str]] = []
        self.import_aliases = import_aliases or {}
        self.variable_types: dict[str, str] = {}
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
        call_name = _call_name(node, self.import_aliases, self.variable_types)
        if call_name is not None:
            self.calls.append(
                CallSite(
                    name=call_name,
                    line=node.lineno,
                    handled_exceptions=frozenset(self._active_handlers()),
                )
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._record_assignment_types(node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._record_assignment_types([node.target], node.value)
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            if not self._is_handled("ZeroDivisionError"):
                self.implicit_exceptions.append(
                    ("ZeroDivisionError", node.lineno, "arithmetic", "division")
                )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if not self._is_handled("IndexError"):
            self.implicit_exceptions.append(("IndexError", node.lineno, "subscript", "indexing"))
        if not self._is_handled("KeyError"):
            self.implicit_exceptions.append(("KeyError", node.lineno, "subscript", "indexing"))
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

    def _active_handlers(self) -> set[str | None]:
        active: set[str | None] = set()
        for handled in self._handled_stack:
            active.update(handled)
        return active

    def _record_assignment_types(self, targets: list[ast.expr], value: ast.AST | None) -> None:
        if value is None:
            return

        constructor_name = _call_name(value, self.import_aliases, self.variable_types)
        if constructor_name is None:
            return

        for target in targets:
            if isinstance(target, ast.Name):
                self.variable_types[target.id] = constructor_name


@dataclass(slots=True)
class FunctionSummary:
    """Stores the extracted exception-relevant summary for a function."""

    name: str
    line: int
    raises: list[RaiseSite]
    calls: list[CallSite]
    implicit_exceptions: list[tuple[str, int, str, str]] = field(default_factory=list)


class ModuleAnalyzer:
    """Analyzes one Python module and reports possible exceptions for statements."""

    def __init__(
        self,
        path: Path,
        module_name: str | None = None,
        analyzer_cache: dict[Path, "ModuleAnalyzer"] | None = None,
    ) -> None:
        self.path = path
        self.module_name = module_name or path.stem
        self._analyzer_cache = analyzer_cache if analyzer_cache is not None else {path: self}
        self.source = path.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source, filename=str(path))
        self.lines = self.source.splitlines()
        self.import_aliases = self._build_import_aliases()
        self.function_summaries = self._build_function_summaries()

    def analyze_statement(self, line_number: int) -> StatementReport:
        """Analyze the statement covering the given line number."""

        statement = self._find_statement(line_number)
        statement_source = (
            ast.get_source_segment(self.source, statement) or statement.__class__.__name__
        )

        builder = FunctionSummaryBuilder(self.import_aliases)
        builder.visit(statement)

        report = StatementReport(
            statement_source=statement_source.strip(), statement_line=statement.lineno
        )

        visited: set[tuple[Path, str]] = set()
        for call_site in builder.calls:
            report.call_tree.append(
                self._explore_call(
                    call_site=call_site, path=(call_site.name,), visited=visited, report=report
                )
            )

        self._dedupe_report(report)
        return report

    def _build_function_summaries(self) -> dict[str, FunctionSummary]:
        summaries: dict[str, FunctionSummary] = {}
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                builder = FunctionSummaryBuilder(self.import_aliases)
                for item in node.body:
                    builder.visit(item)
                summaries[node.name] = FunctionSummary(
                    name=node.name,
                    line=node.lineno,
                    raises=builder.raises,
                    calls=builder.calls,
                    implicit_exceptions=builder.implicit_exceptions,
                )
        return summaries

    def _build_import_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name.split(".", maxsplit=1)[0]
                    if alias.asname:
                        aliases[local_name] = alias.name
                    else:
                        aliases[local_name] = local_name
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    local_name = alias.asname or alias.name
                    aliases[local_name] = f"{node.module}.{alias.name}"
        return aliases

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
        call_site: CallSite,
        path: tuple[str, ...],
        visited: set[tuple[Path, str]],
        report: StatementReport,
    ) -> CallTreeNode:
        call_name = call_site.name
        call_line = call_site.line
        target = self._resolve_call_target(call_name)
        if target is None:
            node = CallTreeNode(
                name=call_name,
                line=call_line,
                path=path,
                resolved=False,
                handled_exceptions=call_site.handled_exceptions,
            )
            if call_name in BUILTIN_EXCEPTIONS:
                node.summary_source = "builtin summary"
                for exception_name in BUILTIN_EXCEPTIONS[call_name]:
                    finding = ExceptionFinding(
                        exception_name=exception_name,
                        line=call_line,
                        path=path,
                        implicit=True,
                        operation="builtin summary",
                    )
                    report.findings.append(finding)
                    node.findings.append(finding)
                node.escaping_exceptions = sorted(BUILTIN_EXCEPTIONS[call_name])
            elif call_name in STDLIB_METHOD_EXCEPTIONS:
                node.summary_source = "stdlib summary"
                for exception_name in STDLIB_METHOD_EXCEPTIONS[call_name]:
                    finding = ExceptionFinding(
                        exception_name=exception_name,
                        line=call_line,
                        path=path,
                        implicit=True,
                        operation="stdlib summary",
                    )
                    report.findings.append(finding)
                    node.findings.append(finding)
                node.escaping_exceptions = sorted(STDLIB_METHOD_EXCEPTIONS[call_name])
            elif call_name in SUMMARY_EXCEPTIONS:
                node.summary_source = summary_source_for_name(call_name)
                for exception_name in SUMMARY_EXCEPTIONS[call_name]:
                    finding = ExceptionFinding(
                        exception_name=exception_name,
                        line=call_line,
                        path=path,
                        implicit=True,
                        operation=node.summary_source,
                    )
                    report.findings.append(finding)
                    node.findings.append(finding)
                node.escaping_exceptions = sorted(SUMMARY_EXCEPTIONS[call_name])
            else:
                report.unresolved_calls.append(
                    UnresolvedCall(name=call_name, line=call_line, path=path)
                )
            return node

        summary = target.summary
        node = CallTreeNode(
            name=target.display_name,
            line=call_line,
            path=path,
            resolved=True,
            definition_line=summary.line,
            summary_source=target.summary_source,
            handled_exceptions=call_site.handled_exceptions,
        )

        for raise_site in summary.raises:
            finding = ExceptionFinding(
                exception_name=raise_site.exception_name,
                line=raise_site.line,
                path=path,
                message=raise_site.message,
                implicit=False,
            )
            report.findings.append(finding)
            node.findings.append(finding)

        for exc_name, exc_line, op_type, op_detail in summary.implicit_exceptions:
            finding = ExceptionFinding(
                exception_name=exc_name, line=exc_line, path=path, implicit=True, operation=op_type
            )
            report.findings.append(finding)
            node.findings.append(finding)

        visit_key = (target.analyzer.path, summary.name)
        if visit_key in visited:
            node.recursive = True
            self._refresh_escaping_exceptions(node)
            return node

        visited.add(visit_key)
        for nested_call_site in summary.calls:
            node.children.append(
                target.analyzer._explore_call(
                    call_site=nested_call_site,
                    path=path + (nested_call_site.name,),
                    visited=visited,
                    report=report,
                )
            )
        visited.remove(visit_key)
        self._refresh_escaping_exceptions(node)
        return node

    def _resolve_call_target(self, call_name: str) -> ResolvedCallTarget | None:
        summary = self.function_summaries.get(call_name)
        if summary is not None:
            return ResolvedCallTarget(analyzer=self, summary=summary, display_name=call_name)

        return self._resolve_imported_function(call_name)

    def _resolve_imported_function(self, call_name: str) -> ResolvedCallTarget | None:
        parts = call_name.split(".")
        for split_index in range(len(parts) - 1, 0, -1):
            module_name = ".".join(parts[:split_index])
            function_name = ".".join(parts[split_index:])
            if "." in function_name:
                continue

            analyzer = self._load_imported_analyzer(module_name)
            if analyzer is None:
                continue

            summary = analyzer.function_summaries.get(function_name)
            if summary is None:
                continue

            return ResolvedCallTarget(
                analyzer=analyzer,
                summary=summary,
                display_name=call_name,
                summary_source=source_kind_for_path(analyzer.path),
            )
        return None

    def _load_imported_analyzer(self, module_name: str) -> ModuleAnalyzer | None:
        source_path = module_source_path(module_name)
        if source_path is None:
            return None

        analyzer = self._analyzer_cache.get(source_path)
        if analyzer is not None:
            return analyzer

        analyzer = ModuleAnalyzer(
            source_path, module_name=module_name, analyzer_cache=self._analyzer_cache
        )
        self._analyzer_cache[source_path] = analyzer
        return analyzer

    def _refresh_escaping_exceptions(self, node: CallTreeNode) -> None:
        escaping: set[str] = set()
        escaping.update(finding.exception_name for finding in node.findings)
        for child in node.children:
            child_escaping = set(child.escaping_exceptions)
            swallowed = self._handled_exceptions(child_escaping, child.handled_exceptions)
            if swallowed:
                node.swallowed_exceptions = sorted(set(node.swallowed_exceptions).union(swallowed))
            escaping.update(child_escaping.difference(swallowed))
        node.escaping_exceptions = sorted(escaping)

    def _handled_exceptions(self, escaping: set[str], handled: frozenset[str | None]) -> set[str]:
        if not handled:
            return set()

        if None in handled:
            return set(escaping)
        return escaping.intersection(handled)

    def _dedupe_report(self, report: StatementReport) -> None:
        unique_findings: dict[tuple[str, int, tuple[str, ...]], ExceptionFinding] = {}
        escaping = set()
        for node in report.call_tree:
            escaping.update(node.escaping_exceptions)
        for finding in report.findings:
            if finding.exception_name not in escaping:
                continue
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


def _call_name(
    node: ast.AST,
    import_aliases: dict[str, str] | None = None,
    variable_types: dict[str, str] | None = None,
) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    raw_name = _dotted_name(node.func)
    if raw_name is None or import_aliases is None:
        return raw_name
    first_part = raw_name.split(".", maxsplit=1)[0]
    if variable_types is not None and first_part in variable_types:
        return _resolve_variable_type(raw_name, variable_types)
    if "." in raw_name and first_part not in import_aliases:
        return None
    return _resolve_import_alias(raw_name, import_aliases)


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base_name = _dotted_name(node.value)
        if base_name is None:
            return None
        return f"{base_name}.{node.attr}"
    return None


def _resolve_import_alias(name: str, import_aliases: dict[str, str]) -> str:
    first_part, separator, remaining = name.partition(".")
    resolved_first_part = import_aliases.get(first_part)
    if resolved_first_part is None:
        return name
    if not separator:
        return resolved_first_part
    return f"{resolved_first_part}.{remaining}"


def _resolve_variable_type(name: str, variable_types: dict[str, str]) -> str:
    first_part, separator, remaining = name.partition(".")
    resolved_first_part = variable_types.get(first_part)
    if resolved_first_part is None or not separator:
        return name
    return f"{resolved_first_part}.{remaining}"


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


def _parse_single_line(line: str) -> ast.Module:
    try:
        return ast.parse(line)
    except SyntaxError as first_error:
        try:
            return ast.parse(f"def _except_line_probe():\n    {line}")
        except SyntaxError:
            raise first_error
